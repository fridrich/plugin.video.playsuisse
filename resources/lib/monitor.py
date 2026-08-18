# Copyright (C) 2026 Fridrich Strba
#
# This file is part of plugin.video.playsuisse.
#
# plugin.video.playsuisse is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import base64
import json
import os
import ssl
import sys
import time
import traceback
import urllib.error
import urllib.request
import uuid
import xbmc
import xbmcaddon
import xbmcvfs

ADDON = xbmcaddon.Addon("plugin.video.playsuisse")


def clean_str(val):
    """Strips null bytes and whitespaces from strings returned by Kodi's C++ bindings."""
    if isinstance(val, str):
        return val.replace("\x00", "").replace("\0", "").strip()
    return val


class PlaySuissePlaybackMonitor(xbmc.Player):
    """Monitors playback to dynamically configure languages and track server-side progress."""

    def __init__(self, primary_lang, asset_id="", title=""):
        xbmc.Player.__init__(self)
        self.primary_lang = clean_str(primary_lang)
        self.asset_id = clean_str(asset_id)
        self.title = clean_str(title)
        self.configured = False
        self.playback_active = False
        self.is_eof = False
        self.last_position = 0
        self.session_id = str(uuid.uuid4())[:16].replace("-", "")

    def onPlayBackStarted(self):
        xbmc.log("PlaySuissePlaybackMonitor: onPlayBackStarted callback", xbmc.LOGINFO)
        self.playback_active = True
        self.is_eof = False

    def onPlayBackStopped(self):
        xbmc.log("PlaySuissePlaybackMonitor: onPlayBackStopped callback", xbmc.LOGINFO)
        self.playback_active = False

    def onPlayBackEnded(self):
        xbmc.log("PlaySuissePlaybackMonitor: onPlayBackEnded callback", xbmc.LOGINFO)
        self.playback_active = False
        self.is_eof = True

    def onPlayBackPaused(self):
        xbmc.log("PlaySuissePlaybackMonitor: onPlayBackPaused callback", xbmc.LOGINFO)
        self.send_event("pause")

    def onPlayBackResumed(self):
        xbmc.log("PlaySuissePlaybackMonitor: onPlayBackResumed callback", xbmc.LOGINFO)
        self.send_event("play")

    def onAVStarted(self):
        """Called when audio and video streams start playing."""
        xbmc.log("PlaySuissePlaybackMonitor: onAVStarted callback", xbmc.LOGINFO)

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

        xbmc.log(f"PlaySuissePlaybackMonitor: Detected duration: {duration} s", xbmc.LOGINFO)

        # Ignore short intro/logo clips preceding the main video
        if duration > 0 and duration < 25:
            xbmc.log(f"PlaySuissePlaybackMonitor: Short intro/logo detected ({duration} s), skipping track configuration.", xbmc.LOGINFO)
            # DO NOT set self.configured = True here.
            # We want to wait for the actual main video to trigger a second onAVStarted!
            return

        xbmc.log("PlaySuissePlaybackMonitor: Playback started, configuring languages.", xbmc.LOGINFO)

        # Configure Audio Track
        self._configure_audio()

        # Configure Subtitle Track
        self._configure_subtitles()

        self.configured = True

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
            "en": ("eng", "english")
        }
        if target_lang in mapping:
            for term in mapping[target_lang]:
                if term in stream_lang:
                    return True
        return False

    def _configure_audio(self):
        pref_audio = ADDON.getSetting("audio_language") or "auto"
        xbmc.log(f"PlaySuissePlaybackMonitor: Preferred audio setting is '{pref_audio}'", xbmc.LOGINFO)

        try:
            audio_streams = self.getAvailableAudioStreams()
            if not audio_streams:
                xbmc.log("PlaySuissePlaybackMonitor: No audio streams available", xbmc.LOGINFO)
                return

            # Log raw audio streams metadata for diagnostics
            xbmc.log(f"PlaySuissePlaybackMonitor: Available audio streams: {json.dumps(audio_streams)}", xbmc.LOGINFO)

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
                    # Avoid selecting descriptive audio or commentary if possible
                    is_descriptive = any(term in stream_name.lower() for term in ("ad", "description", "commentary"))
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
                if current_lang and self._match_lang(current_lang, target_lang):
                    xbmc.log(f"PlaySuissePlaybackMonitor: Audio track for '{target_lang}' is already active ('{current_lang}'). Skipping selection to prevent silence.", xbmc.LOGINFO)
                else:
                    xbmc.log(f"PlaySuissePlaybackMonitor: Selecting audio track {target_idx} ({target_lang})", xbmc.LOGINFO)
                    self.setAudioStream(target_idx)
            else:
                xbmc.log(f"PlaySuissePlaybackMonitor: Target audio {target_lang} (fallback {self.primary_lang}) not found", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"PlaySuissePlaybackMonitor: Error configuring audio stream: {e}\n{traceback.format_exc()}", xbmc.LOGERROR)

    def _configure_subtitles(self):
        pref_subs = ADDON.getSetting("subtitle_language") or "off"
        xbmc.log(f"PlaySuissePlaybackMonitor: Preferred subtitle setting is '{pref_subs}'", xbmc.LOGINFO)

        try:
            if pref_subs == "off":
                self.showSubtitles(False)
                return

            subtitle_streams = self.getAvailableSubtitleStreams()
            if not subtitle_streams:
                self.showSubtitles(False)
                return

            # Log raw subtitle streams metadata for diagnostics
            xbmc.log(f"PlaySuissePlaybackMonitor: Available subtitle streams: {json.dumps(subtitle_streams)}", xbmc.LOGINFO)

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
                current_lang = xbmc.getInfoLabel('VideoPlayer.SubtitlesLanguage')
                subtitles_on = xbmc.getCondVisibility('VideoPlayer.SubtitlesEnabled')
                if subtitles_on and current_lang and self._match_lang(current_lang, pref_subs):
                    xbmc.log(f"PlaySuissePlaybackMonitor: Subtitle track for '{pref_subs}' is already active ('{current_lang}'). Skipping selection.", xbmc.LOGINFO)
                else:
                    xbmc.log(f"PlaySuissePlaybackMonitor: Selecting subtitle track {selected_idx} ({pref_subs})", xbmc.LOGINFO)
                    self.setSubtitleStream(selected_idx)
                self.showSubtitles(True)
            else:
                xbmc.log(f"PlaySuissePlaybackMonitor: Preferred subtitle {pref_subs} not found. Turning subtitles off.", xbmc.LOGINFO)
                self.showSubtitles(False)
        except Exception as e:
            xbmc.log(f"PlaySuissePlaybackMonitor: Error configuring subtitle stream: {e}\n{traceback.format_exc()}", xbmc.LOGERROR)

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
            subtitles_on = xbmc.getCondVisibility('VideoPlayer.SubtitlesEnabled')
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

    def _get_ui_locale(self):
        """Gets the locale based on the addon setting, falling back to Kodi's language."""
        try:
            lang_setting = ADDON.getSetting("language")
            if lang_setting and lang_setting != "auto":
                return lang_setting

            kodi_lang = xbmc.getLanguage(xbmc.ISO_639_1, True)
            if kodi_lang:
                kodi_lang = kodi_lang.lower()
                if "de" in kodi_lang:
                    return "de"
                if "it" in kodi_lang:
                    return "it"
                if "rm" in kodi_lang:
                    return "rm"
        except Exception:
            pass
        return "fr"

    def _get_user_info(self):
        """Loads session.json and extracts sub (account_id) and caches the real profile_id from the GraphQL API."""
        user_id = None
        try:
            profile_dir = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
            session_file = os.path.join(profile_dir, "session.json")
            if os.path.exists(session_file):
                with open(session_file, "r") as f:
                    session_data = json.load(f)
                id_token = session_data.get("id_token")
                if id_token:
                    clean_token = clean_str(id_token)
                    parts = clean_token.split(".")
                    if len(parts) >= 2:
                        payload = parts[1]
                        payload += "=" * ((4 - len(payload) % 4) % 4)
                        decoded = base64.b64decode(payload).decode('utf-8', errors='ignore')
                        token_payload = json.loads(decoded)
                        user_id = clean_str(token_payload.get("sub"))

                        cached_profile_id = session_data.get("profile_id")
                        if cached_profile_id:
                            return {
                                "account_id": user_id,
                                "profile_id": clean_str(cached_profile_id)
                            }

                        url = "https://www.playsuisse.ch/api/graphql?complex_subs=true&stipo_env=production2&discontinuity=true"
                        query_payload = [
                            {
                                "operationName": "AppConfig",
                                "variables": {},
                                "extensions": {
                                    "persistedQuery": {
                                        "version": 1,
                                        "sha256Hash": "3cdb8a136dccdaee568e872c55c2d30578a919a3f02656b335bec80a88129d89"
                                    }
                                }
                            },
                            {
                                "operationName": "UserProfileWithPreferencesAndUserInfo",
                                "variables": {},
                                "extensions": {
                                    "persistedQuery": {
                                        "version": 1,
                                        "sha256Hash": "93b24b6d887b532304d2fbc6a422b52092d853edf17cf33488ccf0218f8c6e3c"
                                    }
                                }
                            }
                        ]
                        headers = {
                            "Authorization": "Bearer " + clean_token,
                            "Content-Type": "application/json",
                            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                            "x-playsuisse-app": "id=web&version=1.1.27",
                            "x-playsuisse-locale": self._get_ui_locale()
                        }

                        req = urllib.request.Request(url, data=json.dumps(query_payload).encode("utf-8"), headers=headers, method="POST")
                        ctx = ssl.create_default_context()
                        ctx.check_hostname = False
                        ctx.verify_mode = ssl.CERT_NONE

                        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
                            res_data = json.loads(response.read().decode("utf-8"))
                            if res_data and isinstance(res_data, list) and len(res_data) > 1:
                                profile_data = res_data[1].get("data", {}).get("userProfile", {})
                                profile_id = clean_str(profile_data.get("profileId"))

                                if profile_id:
                                    session_data["profile_id"] = profile_id
                                    try:
                                        with open(session_file, "w") as f_out:
                                            json.dump(session_data, f_out)
                                    except Exception as write_err:
                                        xbmc.log(f"PlaySuissePlaybackMonitor: Failed to cache profile_id: {write_err}", xbmc.LOGWARNING)

                                return {
                                    "account_id": user_id,
                                    "profile_id": profile_id
                                }
        except Exception as e:
            xbmc.log(f"PlaySuissePlaybackMonitor: Failed to fetch active profile ID: {e}", xbmc.LOGERROR)

        return {"account_id": user_id, "profile_id": user_id}

    def send_event(self, event_name):
        """Sends progress telemetry directly to the Play Suisse DataLab Event Gateway."""
        if not self.asset_id:
            xbmc.log("PlaySuissePlaybackMonitor: Skip sending event, no asset_id provided", xbmc.LOGWARNING)
            return

        try:
            # Determine position: use self.last_position for stop/eof events since player is destroyed
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
                xbmc.log("PlaySuissePlaybackMonitor: Skip sending event, no user profile_id found", xbmc.LOGWARNING)
                return

            # Derive a stable 10-digit guest_id by hashing the profile ID
            guest_id = str(abs(hash(profile_id)))[:10]
            user_lang = self.primary_lang if self.primary_lang else "fr"

            date_time_iso = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())

            url = "https://data.playsuisse-datalab.com/gateway/events"
            headers = {
                "Content-Type": "application/json",
                "Ocp-Apim-Subscription-Key": "c2db00036f3e4e02a161cd269b39a332;product=rio-all-clients",
                "Ocp-Apim-Trace": "1",
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://www.playsuisse.ch/"
            }

            audio_lang = self._get_active_audio_lang()
            sub_lang = self._get_active_subtitle_lang()

            def to_2_letter(lang):
                if not lang:
                    return None
                lang = lang.lower()
                mapping = {
                    "fre": "fr", "fra": "fr", "fr": "fr", "français": "fr", "francais": "fr",
                    "ger": "de", "deu": "de", "de": "de", "deutsch": "de",
                    "ita": "it", "it": "it", "italiano": "it",
                    "rom": "rm", "roh": "rm", "rm": "rm", "rumantsch": "rm",
                    "eng": "en", "en": "en", "english": "en"
                }
                return mapping.get(lang, "fr")

            payload = {
                "data_schema_version": "1.0.0",
                "context": {
                    "app": {
                        "name": "Play Suisse",
                        "version": "1.1.27",
                        "build": "0",
                        "platform": "web"
                    },
                    "user": {
                        "user_id": user_id,
                        "profile_id": profile_id,
                        "guest_id": guest_id,
                        "language": user_lang
                    },
                    "player": {
                        "name": "RIOLetterbox",
                        "version": "3.37.0"
                    },
                    "session": {
                        "id": self.session_id,
                        "start_time": date_time_iso
                    },
                    "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                },
                "events": [
                    {
                        "type": "media_progressed",
                        "date_time": date_time_iso,
                        "asset": {
                            "id": self.asset_id
                        },
                        "media": {
                            "position_in_secs": position,
                            "audio_lang": to_2_letter(audio_lang),
                            "txt_lang": to_2_letter(sub_lang) if self._is_subtitles_on() else None
                        },
                        "collection": {
                            "id": "358305",
                            "position_in_page": 0,
                            "version": "hero_bandit:2.0.0"
                        }
                    }
                ]
            }

            xbmc.log(f"PlaySuissePlaybackMonitor: Sending media_progressed event to Datalab for asset {self.asset_id} at position {position}s...", xbmc.LOGINFO)

            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")

            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
                status_code = response.getcode()
                response_text = response.read().decode("utf-8", errors="ignore")
                clean_res = clean_str(response_text[:200])
                xbmc.log(f"PlaySuissePlaybackMonitor: Sent media_progressed event to Datalab. Status: {status_code}, Response: {clean_res}", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"PlaySuissePlaybackMonitor: Failed to send Datalab event: {e}\n{traceback.format_exc()}", xbmc.LOGERROR)


def main():
    xbmc.log("PlaySuissePlaybackMonitor: Background script starting...", xbmc.LOGINFO)
    primary_lang = clean_str(sys.argv[1]) if len(sys.argv) > 1 else ""
    asset_id = clean_str(sys.argv[2]) if len(sys.argv) > 2 else ""
    title = clean_str(sys.argv[3]) if len(sys.argv) > 3 else ""
    xbmc.log(f"PlaySuissePlaybackMonitor: Arguments parsed: lang={primary_lang}, asset_id={asset_id}, title={title}", xbmc.LOGINFO)

    monitor = PlaySuissePlaybackMonitor(primary_lang, asset_id, title)

    # Keep background script alive until playback starts and we configure languages, or 60s timeout (allows for pre-rolls)
    timeout = 120  # 60 seconds (120 * 500ms)
    while not monitor.configured and timeout > 0:
        if not monitor.playback_active and timeout < 110: # If playback stopped and we're not just starting
             break
        xbmc.sleep(500)
        timeout -= 1

    xbmc.log(f"PlaySuissePlaybackMonitor: Script configured status: {monitor.configured}", xbmc.LOGINFO)

    if monitor.configured and asset_id:
        xbmc.log(f"PlaySuissePlaybackMonitor: Starting progress tracking loop for asset {asset_id}", xbmc.LOGINFO)

        monitor.send_event("play")
        last_heartbeat = time.time()

        while monitor.playback_active or monitor.isPlayingVideo():
            if xbmc.Monitor().abortRequested():
                xbmc.log("PlaySuissePlaybackMonitor: Abort requested by Kodi", xbmc.LOGINFO)
                break

            # Continuously monitor and record the last known valid position
            if monitor.isPlayingVideo():
                try:
                    pos = int(monitor.getTime())
                    if pos > 0:
                        monitor.last_position = pos
                except Exception:
                    pass

            now = time.time()
            if now - last_heartbeat >= 30.0:
                if monitor.isPlayingVideo():
                    monitor.send_event("pos")
                last_heartbeat = now

            xbmc.sleep(1000)

        if monitor.is_eof:
            monitor.send_event("eof")
        else:
            monitor.send_event("stop")

        xbmc.log("PlaySuissePlaybackMonitor: Playback finished, stopping progress tracking loop", xbmc.LOGINFO)


if __name__ == "__main__":
    main()
