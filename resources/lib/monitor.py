# Copyright (C) 2026 Fridrich Strba
#
# This file is part of plugin.video.playsuisse.
#
# plugin.video.playsuisse is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import base64
import hashlib
import json
import os
import sys
import time
import traceback
import urllib.error
import urllib.request
import uuid
import xbmc
import xbmcaddon
import xbmcvfs

# monitor.py and auth.py are colocated in resources/lib -- this just makes
# that explicit rather than relying on Kodi's script-invocation sys.path.
sys.path.insert(0, os.path.dirname(__file__))
from auth import PlaySuisseAuth  # noqa: E402

ADDON = xbmcaddon.Addon("plugin.video.playsuisse")


def clean_str(val):
    """Strips null bytes and whitespaces from strings returned by Kodi's
    C++ bindings.
    """
    if isinstance(val, str):
        return val.replace("\x00", "").replace("\0", "").strip()
    return val


class PlaySuissePlaybackMonitor(xbmc.Player):
    """Monitors playback to dynamically configure languages and track
    server-side progress.
    """

    def __init__(self, primary_lang, asset_id="", title="", series_id=""):
        xbmc.Player.__init__(self)
        self.primary_lang = clean_str(primary_lang)
        self.asset_id = clean_str(asset_id)
        self.title = clean_str(title)
        self.series_id = clean_str(series_id)
        self.configured = False
        self.playback_active = False
        self.is_eof = False
        self.last_position = 0
        self.session_id = str(uuid.uuid4())[:16].replace("-", "")
        # File path of this asset's own playback, set once confirmed in
        # onAVStarted -- isPlayingVideo() alone can't tell "my" video apart
        # from Up Next's next episode.
        self._playing_file = None
        self._stop_signal = False

    def _matches_own_file(self):
        """True unless a different file is now playing (Up Next moved on
        and this stale object is still receiving global player callbacks).
        """
        if not self._playing_file:
            return True
        try:
            return self.getPlayingFile() == self._playing_file
        except Exception:
            return True

    def onPlayBackStarted(self):
        if not self._matches_own_file():
            return
        xbmc.log(
            "PlaySuissePlaybackMonitor: onPlayBackStarted callback",
            xbmc.LOGINFO,
        )
        self.playback_active = True
        self.is_eof = False

    def onPlayBackStopped(self):
        xbmc.log(
            "PlaySuissePlaybackMonitor: onPlayBackStopped callback",
            xbmc.LOGINFO,
        )
        self.playback_active = False
        self._stop_signal = True

    def onPlayBackEnded(self):
        xbmc.log(
            "PlaySuissePlaybackMonitor: onPlayBackEnded callback", xbmc.LOGINFO
        )
        self.playback_active = False
        self.is_eof = True
        self._stop_signal = True

    def onPlayBackPaused(self):
        if not self._matches_own_file():
            return
        xbmc.log(
            "PlaySuissePlaybackMonitor: onPlayBackPaused callback",
            xbmc.LOGINFO,
        )
        self.send_event("pause")

    def onPlayBackResumed(self):
        if not self._matches_own_file():
            return
        xbmc.log(
            "PlaySuissePlaybackMonitor: onPlayBackResumed callback",
            xbmc.LOGINFO,
        )
        self.send_event("play")

    def onAVStarted(self):
        """Called when audio and video streams start playing."""
        self._try_configure()

    def _try_configure(self):
        """Configure audio/subtitles and register Up Next once. Called from
        onAVStarted, and also polled from main()'s wait loop as a fallback --
        onAVStarted/onPlayBackStarted never fire for inputstream.adaptive
        content on some platforms (confirmed on OSMC/ARM), even though the
        video plays back fine.
        """
        # Player callbacks are global -- this object can still get called
        # after it's done its job and Up Next has moved on to another video.
        if self.configured:
            return
        if not self.isPlayingVideo():
            return

        xbmc.log(
            "PlaySuissePlaybackMonitor: onAVStarted callback", xbmc.LOGINFO
        )

        # Wait up to 3 seconds for the duration to become valid
        duration = 0
        for _ in range(6):
            try:
                duration = self.getTotalTime()
            except Exception:
                duration = 0
            if duration > 0:
                break
            xbmc.sleep(500)

        xbmc.log(
            f"PlaySuissePlaybackMonitor: Detected duration: {duration} s",
            xbmc.LOGINFO,
        )

        # Ignore short intro/logo clips preceding the main video
        if duration > 0 and duration < 25:
            xbmc.log(
                "PlaySuissePlaybackMonitor: Short intro/logo detected "
                f"({duration} s), skipping track configuration.",
                xbmc.LOGINFO,
            )
            # DO NOT set self.configured = True here.
            # We want to wait for the actual main video to trigger a second
            # onAVStarted!
            return

        xbmc.log(
            "PlaySuissePlaybackMonitor: Playback started, "
            "configuring languages.",
            xbmc.LOGINFO,
        )

        # Configure Audio Track
        self._configure_audio()

        # Configure Subtitle Track
        self._configure_subtitles()

        try:
            self._playing_file = self.getPlayingFile()
        except Exception:
            pass

        self.configured = True
        self._setup_upnext()

    def _setup_upnext(self):
        """Discovers the next episode and registers with service.upnext if installed."""
        try:
            # 0. Check settings if Up Next integration is enabled
            try:
                if ADDON.getSetting("enable_upnext") == "false":
                    xbmc.log(
                        "PlaySuissePlaybackMonitor: Up Next integration is disabled in settings.",
                        xbmc.LOGINFO,
                    )
                    return
            except Exception as se:
                xbmc.log(
                    f"PlaySuissePlaybackMonitor: Failed to read enable_upnext setting: {se}",
                    xbmc.LOGWARNING,
                )

            # 1. Verify service.upnext is active/installed
            if not xbmc.getCondVisibility("System.HasAddon(service.upnext)"):
                xbmc.log(
                    "PlaySuissePlaybackMonitor: service.upnext is not active/installed. Skipping.",
                    xbmc.LOGINFO,
                )
                return

            # 2. Get authentication token
            auth = PlaySuisseAuth(ADDON)
            token = auth.get_token()

            from api import PlaySuisseAPI
            api = PlaySuisseAPI()

            # 3. Retrieve metadata of current episode
            asset_data, _ = api.get_asset(self.asset_id, token=token)
            if not asset_data:
                xbmc.log(
                    "PlaySuissePlaybackMonitor: Could not retrieve current asset metadata for Up Next",
                    xbmc.LOGWARNING,
                )
                return

            # 4. Check if it's an episode of a series
            episode_num = asset_data.get("episodeNumber")
            season_num = asset_data.get("seasonNumber")
            series_name = asset_data.get("seriesName")

            if episode_num is None or not series_name:
                xbmc.log(
                    f"PlaySuissePlaybackMonitor: Asset {self.asset_id} is not an episode. Skipping Up Next.",
                    xbmc.LOGINFO,
                )
                return

            # 5. Resolve parent series ID
            series_id = self.series_id if hasattr(self, "series_id") and self.series_id else None
            if not series_id:
                # Fallback: search for series by name
                search_results = api.search(series_name)
                for asset in search_results:
                    if (
                        asset.get("name") == series_name
                        and (asset.get("duration") is None or asset.get("duration") == 0)
                    ):
                        series_id = asset.get("id")
                        break

            if not series_id:
                xbmc.log(
                    f"PlaySuissePlaybackMonitor: Could not resolve parent series ID for '{series_name}'",
                    xbmc.LOGWARNING,
                )
                return

            # 6. Retrieve series metadata to find the next episode
            series_data, _ = api.get_asset(series_id, token=token)
            if not series_data:
                xbmc.log(
                    f"PlaySuissePlaybackMonitor: Could not retrieve series metadata for {series_id}",
                    xbmc.LOGWARNING,
                )
                return

            episodes = series_data.get("episodes") or []
            current_idx = -1
            for i, ep in enumerate(episodes):
                if ep.get("id") == self.asset_id:
                    current_idx = i
                    break

            if current_idx == -1 or current_idx + 1 >= len(episodes):
                xbmc.log(
                    "PlaySuissePlaybackMonitor: No next episode found in series",
                    xbmc.LOGINFO,
                )
                return

            next_ep = episodes[current_idx + 1]
            next_id = next_ep.get("id")
            next_title = next_ep.get("name")

            # 7. Build current episode and next episode payload
            current_episode_payload = {
                "episodeid": self.asset_id,
                "tvshowid": series_id,
                "title": self.title,
                "season": season_num or 1,
                "episode": episode_num or 1,
            }

            next_thumb = (next_ep.get("thumbnail16x9") or {}).get("url") or ""
            art = {
                "thumb": next_thumb,
                "tvshow.poster": (series_data.get("image2x3WithTitle") or {}).get("url") or "",
                "tvshow.fanart": (series_data.get("image16x9WithTitle") or {}).get("url") or "",
            }

            next_episode_payload = {
                "episodeid": next_id,
                "tvshowid": series_id,
                "title": next_title,
                "showtitle": series_name,
                "season": next_ep.get("seasonNumber") or 1,
                "episode": next_ep.get("episodeNumber") or 1,
                "plot": next_ep.get("description") or "",
                "art": art,
            }

            from urllib.parse import urlencode
            next_play_url = (
                "plugin://plugin.video.playsuisse/?"
                + urlencode({
                    "mode": "play",
                    "id": next_id,
                    "title": next_title,
                    "series_id": series_id,
                })
            )

            payload = {
                "current_episode": current_episode_payload,
                "next_episode": next_episode_payload,
                "play_url": next_play_url,
                "notification_time": 30,
            }

            # 8. Encode and send JSON-RPC notification
            json_bytes = json.dumps(payload).encode("utf-8")
            encoded_payload = base64.b64encode(json_bytes).decode("ascii")

            rpc_call = {
                "jsonrpc": "2.0",
                "method": "JSONRPC.NotifyAll",
                "params": {
                    "sender": "plugin.video.playsuisse.SIGNAL",
                    "message": "upnext_data",
                    "data": [encoded_payload],
                },
                "id": 1,
            }

            xbmc.executeJSONRPC(json.dumps(rpc_call))
            xbmc.log(
                "PlaySuissePlaybackMonitor: Successfully registered next "
                f"episode S{next_episode_payload['season']}E{next_episode_payload['episode']} "
                "with service.upnext",
                xbmc.LOGINFO,
            )

        except Exception as e:
            xbmc.log(
                f"PlaySuissePlaybackMonitor: Failed to setup Up Next: {e}\n{traceback.format_exc()}",
                xbmc.LOGERROR,
            )

    def _match_lang(self, stream_lang, target_lang):
        if not stream_lang or not target_lang:
            return False
        stream_lang = stream_lang.lower()
        target_lang = target_lang.lower()
        if stream_lang == target_lang:
            return True
        mapping = {
            "fr": ("fra", "fre", "french", "français", "francais"),
            "de": ("deu", "ger", "german", "deutsch"),
            "it": ("ita", "italian", "italiano"),
            "rm": ("roh", "romansh", "rumantsch", "rumantch"),
            "en": ("eng", "english"),
        }
        if target_lang in mapping:
            for term in mapping[target_lang]:
                if term in stream_lang:
                    return True
        return False

    def _configure_audio(self):
        pref_audio = ADDON.getSetting("audio_language") or "auto"
        xbmc.log(
            "PlaySuissePlaybackMonitor: Preferred audio setting is "
            f"'{pref_audio}'",
            xbmc.LOGINFO,
        )

        try:
            audio_streams = self.getAvailableAudioStreams()
            if not audio_streams:
                xbmc.log(
                    "PlaySuissePlaybackMonitor: No audio streams available",
                    xbmc.LOGINFO,
                )
                return

            # Log raw audio streams metadata for diagnostics
            xbmc.log(
                "PlaySuissePlaybackMonitor: Available audio streams: "
                f"{json.dumps(audio_streams)}",
                xbmc.LOGINFO,
            )

            # Determine target audio language code
            if pref_audio == "auto":
                target_lang = self.primary_lang
            else:
                target_lang = pref_audio

            # Find matching stream
            selected_idx = -1
            fallback_idx = -1

            for idx, stream in enumerate(audio_streams):
                lang_code = None
                stream_name = ""
                if isinstance(stream, dict):
                    lang_code = stream.get("language")
                    stream_name = stream.get("name", "")
                elif isinstance(stream, str):
                    lang_code = stream
                    stream_name = stream

                if lang_code:
                    # Avoid selecting descriptive audio or commentary
                    # if possible
                    is_descriptive = any(
                        term in stream_name.lower()
                        for term in ("ad", "description", "commentary")
                    )
                    if self._match_lang(lang_code, target_lang):
                        if is_descriptive:
                            if selected_idx == -1:
                                selected_idx = idx
                        else:
                            selected_idx = idx
                            break
                    if self._match_lang(lang_code, self.primary_lang):
                        if is_descriptive:
                            if fallback_idx == -1:
                                fallback_idx = idx
                        else:
                            fallback_idx = idx

            target_idx = selected_idx if selected_idx != -1 else fallback_idx

            if target_idx != -1:
                # Check if the target audio language is already active
                current_lang = xbmc.getInfoLabel('VideoPlayer.AudioLanguage')
                if current_lang and self._match_lang(
                    current_lang, target_lang
                ):
                    xbmc.log(
                        "PlaySuissePlaybackMonitor: Audio track for "
                        f"'{target_lang}' is already active "
                        f"('{current_lang}'). "
                        "Skipping selection to prevent silence.",
                        xbmc.LOGINFO,
                    )
                else:
                    xbmc.log(
                        "PlaySuissePlaybackMonitor: Selecting audio track "
                        f"{target_idx} ({target_lang})",
                        xbmc.LOGINFO,
                    )
                    self.setAudioStream(target_idx)
            else:
                xbmc.log(
                    "PlaySuissePlaybackMonitor: Target audio "
                    f"{target_lang} (fallback {self.primary_lang}) not found",
                    xbmc.LOGINFO,
                )
        except Exception as e:
            xbmc.log(
                "PlaySuissePlaybackMonitor: Error configuring audio stream: "
                f"{e}\n{traceback.format_exc()}",
                xbmc.LOGERROR,
            )

    def _configure_subtitles(self):
        pref_subs = ADDON.getSetting("subtitle_language") or "off"
        xbmc.log(
            "PlaySuissePlaybackMonitor: Preferred subtitle setting is "
            f"'{pref_subs}'",
            xbmc.LOGINFO,
        )

        try:
            if pref_subs == "off":
                self.showSubtitles(False)
                return

            subtitle_streams = self.getAvailableSubtitleStreams()
            if not subtitle_streams:
                self.showSubtitles(False)
                return

            # Log raw subtitle streams metadata for diagnostics
            xbmc.log(
                "PlaySuissePlaybackMonitor: Available subtitle streams: "
                f"{json.dumps(subtitle_streams)}",
                xbmc.LOGINFO,
            )

            selected_idx = -1
            for idx, stream in enumerate(subtitle_streams):
                lang_code = None
                if isinstance(stream, dict):
                    lang_code = stream.get("language")
                elif isinstance(stream, str):
                    lang_code = stream

                if lang_code and self._match_lang(lang_code, pref_subs):
                    selected_idx = idx
                    break

            if selected_idx != -1:
                # Check if the target subtitle language is already active
                current_lang = xbmc.getInfoLabel(
                    'VideoPlayer.SubtitlesLanguage'
                )
                subtitles_on = xbmc.getCondVisibility(
                    'VideoPlayer.SubtitlesEnabled'
                )
                if (
                    subtitles_on
                    and current_lang
                    and self._match_lang(current_lang, pref_subs)
                ):
                    xbmc.log(
                        "PlaySuissePlaybackMonitor: Subtitle track for "
                        f"'{pref_subs}' is already active ('{current_lang}'). "
                        "Skipping selection.",
                        xbmc.LOGINFO,
                    )
                else:
                    xbmc.log(
                        "PlaySuissePlaybackMonitor: Selecting subtitle track "
                        f"{selected_idx} ({pref_subs})",
                        xbmc.LOGINFO,
                    )
                    self.setSubtitleStream(selected_idx)
                self.showSubtitles(True)
            else:
                xbmc.log(
                    "PlaySuissePlaybackMonitor: Preferred subtitle "
                    f"{pref_subs} not found. Turning subtitles off.",
                    xbmc.LOGINFO,
                )
                self.showSubtitles(False)
        except Exception as e:
            xbmc.log(
                "PlaySuissePlaybackMonitor: Error configuring subtitle "
                "stream: "
                f"{e}\n{traceback.format_exc()}",
                xbmc.LOGERROR,
            )

    def _get_active_audio_lang(self):
        try:
            lang = xbmc.getInfoLabel('VideoPlayer.AudioLanguage')
            if lang:
                return clean_str(lang).upper()
        except Exception:
            pass
        return "UND"

    def _get_active_subtitle_lang(self):
        try:
            subtitles_on = xbmc.getCondVisibility(
                'VideoPlayer.SubtitlesEnabled'
            )
            if not subtitles_on:
                return "UND"

            lang = xbmc.getInfoLabel('VideoPlayer.SubtitlesLanguage')
            if lang:
                return clean_str(lang).upper()
        except Exception:
            pass
        return "UND"

    def _is_subtitles_on(self):
        try:
            return xbmc.getCondVisibility('VideoPlayer.SubtitlesEnabled')
        except Exception:
            return False

    def _is_own_video_playing(self):
        if not self._playing_file:
            return False
        try:
            return self.isPlayingVideo() and self.getPlayingFile() == self._playing_file
        except Exception:
            return False

    def _get_user_info(self):
        """Loads session.json, extracts sub (account_id), and caches
        the real profile_id from the GraphQL API.
        """
        user_id = None
        try:
            profile_dir = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
            session_file = os.path.join(profile_dir, "session.json")
            if os.path.exists(session_file):
                with open(session_file, "r") as f:
                    session_data = json.load(f)
                id_token = session_data.get("id_token")
                # Authorization header uses access_token, the correct OAuth2
                # bearer credential for resource APIs; id_token is only
                # decoded locally here for its "sub" (account id) claim.
                bearer_token = session_data.get("access_token") or id_token
                if id_token:
                    clean_token = clean_str(id_token)
                    parts = clean_token.split(".")
                    if len(parts) >= 2:
                        payload = parts[1]
                        payload += "=" * ((4 - len(payload) % 4) % 4)
                        decoded = base64.b64decode(payload).decode(
                            'utf-8', errors='ignore'
                        )
                        token_payload = json.loads(decoded)
                        user_id = clean_str(token_payload.get("sub"))

                        cached_profile_id = session_data.get("profile_id")
                        if cached_profile_id:
                            return {
                                "account_id": user_id,
                                "profile_id": clean_str(cached_profile_id),
                            }

                        # Not cached yet (e.g. a session.json predating
                        # profile_id caching) -- fetch it live via the same
                        # call auth.py makes right after login, and cache
                        # it back so this only happens once per session.
                        if bearer_token:
                            profile_id = PlaySuisseAuth.fetch_profile_id(
                                bearer_token
                            )
                            if profile_id:
                                session_data["profile_id"] = profile_id
                                try:
                                    tmp_path = f"{session_file}.tmp"
                                    with open(tmp_path, "w") as f_out:
                                        json.dump(session_data, f_out)
                                    os.replace(tmp_path, session_file)
                                except Exception as write_err:
                                    xbmc.log(
                                        "PlaySuissePlaybackMonitor: Failed "
                                        f"to cache profile_id: {write_err}",
                                        xbmc.LOGWARNING,
                                    )
                                return {
                                    "account_id": user_id,
                                    "profile_id": clean_str(profile_id),
                                }

                        return {
                            "account_id": user_id,
                            "profile_id": user_id,
                        }
        except Exception as e:
            xbmc.log(
                "PlaySuissePlaybackMonitor: Failed to extract active "
                f"profile ID: {e}",
                xbmc.LOGERROR,
            )

        return {"account_id": user_id, "profile_id": user_id}

    def send_event(self, event_name):
        """Sends progress telemetry directly to the Play Suisse DataLab
        Event Gateway.
        """
        if not self.asset_id:
            xbmc.log(
                "PlaySuissePlaybackMonitor: Skip sending event, "
                "no asset_id provided",
                xbmc.LOGWARNING,
            )
            return

        try:
            # Determine position: use self.last_position for stop/eof
            # events since player is destroyed
            if event_name in ("stop", "eof"):
                position = self.last_position
            else:
                try:
                    position = int(self.getTime())
                    if position > 0:
                        self.last_position = position
                except Exception:
                    position = self.last_position

            if position < 0:
                position = 0

            user_info = self._get_user_info()
            user_id = user_info.get("account_id")
            profile_id = user_info.get("profile_id")

            if not profile_id:
                xbmc.log(
                    "PlaySuissePlaybackMonitor: Skip sending event, "
                    "no user profile_id found",
                    xbmc.LOGWARNING,
                )
                return

            # Stable 10-digit guest_id (sha256, not hash() - the latter
            # is randomized per-process)
            guest_id = str(
                int(hashlib.sha256(profile_id.encode("utf-8")).hexdigest(), 16)
                % 10**10
            ).zfill(10)
            user_lang = self.primary_lang if self.primary_lang else "fr"

            date_time_iso = time.strftime(
                "%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()
            )

            url = "https://data.playsuisse-datalab.com/gateway/events"
            headers = {
                "Content-Type": "application/json",
                "Ocp-Apim-Subscription-Key": (
                    "c2db00036f3e4e02a161cd269b39a332;"
                    "product=rio-all-clients"
                ),
                "Ocp-Apim-Trace": "1",
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://www.playsuisse.ch/",
            }

            audio_lang = self._get_active_audio_lang()
            sub_lang = self._get_active_subtitle_lang()

            def to_2_letter(lang):
                if not lang:
                    return None
                lang = lang.lower()
                mapping = {
                    "fre": "fr",
                    "fra": "fr",
                    "fr": "fr",
                    "français": "fr",
                    "francais": "fr",
                    "ger": "de",
                    "deu": "de",
                    "de": "de",
                    "deutsch": "de",
                    "ita": "it",
                    "it": "it",
                    "italiano": "it",
                    "rom": "rm",
                    "roh": "rm",
                    "rm": "rm",
                    "rumantsch": "rm",
                    "eng": "en",
                    "en": "en",
                    "english": "en",
                }
                return mapping.get(lang, "fr")

            payload = {
                "data_schema_version": "1.0.0",
                "context": {
                    "app": {
                        "name": "Play Suisse",
                        "version": "1.1.27",
                        "build": "0",
                        "platform": "web",
                    },
                    "user": {
                        "user_id": user_id,
                        "profile_id": profile_id,
                        "guest_id": guest_id,
                        "language": user_lang,
                    },
                    "player": {"name": "RIOLetterbox", "version": "3.37.0"},
                    "session": {
                        "id": self.session_id,
                        "start_time": date_time_iso,
                    },
                    "user_agent": (
                        "Mozilla/5.0 (X11; Linux x86_64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                },
                "events": [
                    {
                        "type": "media_progressed",
                        "date_time": date_time_iso,
                        "asset": {"id": self.asset_id},
                        "media": {
                            "position_in_secs": position,
                            "audio_lang": to_2_letter(audio_lang),
                            "txt_lang": (
                                to_2_letter(sub_lang)
                                if self._is_subtitles_on()
                                else None
                            ),
                        },
                        "collection": {
                            "id": "358305",
                            "position_in_page": 0,
                            "version": "hero_bandit:2.0.0",
                        },
                    }
                ],
            }

            xbmc.log(
                "PlaySuissePlaybackMonitor: Sending media_progressed event to "
                f"Datalab for asset {self.asset_id} "
                f"at position {position}s...",
                xbmc.LOGINFO,
            )

            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                status_code = response.getcode()
                response_text = response.read().decode(
                    "utf-8", errors="ignore"
                )
                clean_res = clean_str(response_text[:200])
                xbmc.log(
                    "PlaySuissePlaybackMonitor: Sent media_progressed "
                    "event to "
                    f"Datalab. Status: {status_code}, "
                    f"Response: {clean_res}",
                    xbmc.LOGINFO,
                )
        except Exception as e:
            xbmc.log(
                "PlaySuissePlaybackMonitor: Failed to send Datalab event: "
                f"{e}\n{traceback.format_exc()}",
                xbmc.LOGERROR,
            )


def main():
    xbmc.log(
        "PlaySuissePlaybackMonitor: Background script starting...",
        xbmc.LOGINFO,
    )
    primary_lang = clean_str(sys.argv[1]) if len(sys.argv) > 1 else ""
    asset_id = clean_str(sys.argv[2]) if len(sys.argv) > 2 else ""
    title = clean_str(sys.argv[3]) if len(sys.argv) > 3 else ""
    series_id = clean_str(sys.argv[4]) if len(sys.argv) > 4 else ""
    xbmc.log(
        "PlaySuissePlaybackMonitor: Arguments parsed: "
        f"lang={primary_lang}, asset_id={asset_id}, title={title}, series_id={series_id}",
        xbmc.LOGINFO,
    )

    monitor = PlaySuissePlaybackMonitor(primary_lang, asset_id, title, series_id)
    kodi_monitor = xbmc.Monitor()

    # Keep background script alive until playback starts and we configure
    # languages, or 60s timeout (allows for pre-rolls)
    timeout = 120  # 60 seconds (120 * 500ms)
    while not monitor.configured and timeout > 0:
        if monitor._stop_signal:
            break
        monitor._try_configure()
        if kodi_monitor.waitForAbort(0.5):
            break
        timeout -= 1

    xbmc.log(
        "PlaySuissePlaybackMonitor: Script configured status: "
        f"{monitor.configured}",
        xbmc.LOGINFO,
    )

    if monitor.configured and asset_id:
        xbmc.log(
            "PlaySuissePlaybackMonitor: Starting progress tracking "
            f"loop for asset {asset_id}",
            xbmc.LOGINFO,
        )

        monitor.send_event("play")
        last_heartbeat = time.time()

        while monitor.playback_active or monitor._is_own_video_playing():
            if kodi_monitor.abortRequested():
                xbmc.log(
                    "PlaySuissePlaybackMonitor: Abort requested by Kodi",
                    xbmc.LOGINFO,
                )
                break

            # Continuously monitor and record the last known valid position
            # Use isPlayingVideo to ensure we don't accidentally read the position
            # of a newly started video (like when Up Next automatically skips)
            if monitor.isPlayingVideo():
                try:
                    pos = int(monitor.getTime())
                    # Only update if the position moved forward (prevents capturing
                    # the 0-10s range of a newly launched video overriding our
                    # 50-minute mark before the loop exits)
                    if pos > monitor.last_position:
                        monitor.last_position = pos
                except Exception:
                    pass

            now = time.time()
            if now - last_heartbeat >= 30.0:
                monitor.send_event("pos")
                last_heartbeat = now

            if kodi_monitor.waitForAbort(1.0):
                break

        if monitor.is_eof:
            monitor.send_event("eof")
        else:
            monitor.send_event("stop")

        xbmc.log(
            "PlaySuissePlaybackMonitor: Playback finished, "
            "stopping progress tracking loop",
            xbmc.LOGINFO,
        )


if __name__ == "__main__":
    main()
