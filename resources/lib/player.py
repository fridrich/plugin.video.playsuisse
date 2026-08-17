# Copyright (C) 2026 Fridrich Strba
#
# This file is part of plugin.video.playsuisse.
#
# plugin.video.playsuisse is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import xbmc
import xbmcgui
import xbmcplugin
import inputstreamhelper

from resources.lib.auth import PlaySuisseAuth
from resources.lib.api import PlaySuisseAPI


class PlaySuissePlaybackMonitor(xbmc.Player):
    """Monitors playback to dynamically configure preferred audio and subtitle languages."""

    def __init__(self, addon, primary_lang):
        super().__init__()
        self.addon = addon
        self.primary_lang = primary_lang
        self.configured = False

    def onAVStarted(self):
        """Called when audio and video streams start playing."""
        xbmc.log("PlaySuissePlaybackMonitor: Playback started, configuring languages.", xbmc.LOGDEBUG)

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
            "fr": ("fra", "fre"),
            "de": ("deu", "ger"),
            "it": ("ita",),
            "rm": ("roh",)
        }
        if target_lang in mapping:
            return stream_lang in mapping[target_lang]
        return False

    def _configure_audio(self):
        pref_audio = self.addon.getSetting("audio_language") or "auto"
        xbmc.log(f"PlaySuissePlaybackMonitor: Preferred audio setting is '{pref_audio}'", xbmc.LOGDEBUG)

        try:
            audio_streams = self.getAvailableAudioStreams()
            if not audio_streams:
                return

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
                if isinstance(stream, dict):
                    lang_code = stream.get("language")
                elif isinstance(stream, str):
                    lang_code = stream

                if lang_code:
                    if self._match_lang(lang_code, target_lang):
                        selected_idx = idx
                        break
                    if self._match_lang(lang_code, self.primary_lang):
                        fallback_idx = idx

            # Apply selection: target_lang first, fallback to original language if target not found
            if selected_idx != -1:
                xbmc.log(f"PlaySuissePlaybackMonitor: Selecting audio track {selected_idx} ({target_lang})", xbmc.LOGDEBUG)
                self.setAudioStream(selected_idx)
            elif fallback_idx != -1:
                xbmc.log(f"PlaySuissePlaybackMonitor: Target audio {target_lang} not found. Falling back to original language {self.primary_lang} (track {fallback_idx})", xbmc.LOGDEBUG)
                self.setAudioStream(fallback_idx)
        except Exception as e:
            xbmc.log(f"PlaySuissePlaybackMonitor: Error configuring audio stream: {e}", xbmc.LOGERROR)

    def _configure_subtitles(self):
        pref_subs = self.addon.getSetting("subtitle_language") or "off"
        xbmc.log(f"PlaySuissePlaybackMonitor: Preferred subtitle setting is '{pref_subs}'", xbmc.LOGDEBUG)

        try:
            if pref_subs == "off":
                self.showSubtitles(False)
                return

            subtitle_streams = self.getAvailableSubtitleStreams()
            if not subtitle_streams:
                self.showSubtitles(False)
                return

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
                xbmc.log(f"PlaySuissePlaybackMonitor: Selecting subtitle track {selected_idx} ({pref_subs})", xbmc.LOGDEBUG)
                self.setSubtitleStream(selected_idx)
                self.showSubtitles(True)
            else:
                xbmc.log(f"PlaySuissePlaybackMonitor: Preferred subtitle {pref_subs} not found. Turning subtitles off.", xbmc.LOGDEBUG)
                self.showSubtitles(False)
        except Exception as e:
            xbmc.log(f"PlaySuissePlaybackMonitor: Error configuring subtitle stream: {e}", xbmc.LOGERROR)


class PlaySuissePlayer:
    """Natively resolves and plays Play Suisse streams without relying on external binaries."""

    def __init__(self, addon):
        self.addon = addon
        self.auth = PlaySuisseAuth(addon)
        self.api = PlaySuisseAPI()

    def resolve_and_play(self, handle, asset_id, title):
        """Authenticates natively in Python and resolves the authorized HLS (.m3u8) stream."""
        # 1. Fetch user credentials and id_token (with busy dialog)
        xbmc.executebuiltin("ActivateWindow(busydialognocancel)")
        try:
            id_token = self.auth.get_token()
            # 2. Fetch asset details containing medias with authorization token
            asset_data = self.api.get_asset(asset_id, token=id_token)
        except Exception as e:
            xbmc.executebuiltin("Dialog.Close(busydialognocancel)")
            err_str = str(e)
            xbmc.log(f"PlaySuissePlayer: Playback resolution failed: {err_str}", xbmc.LOGERROR)

            # Select notification depending on error type
            if "CREDENTIALS_MISSING" in err_str:
                msg_id = 30101
            else:
                msg_id = 30100

            xbmcgui.Dialog().notification(
                self.addon.getAddonInfo('name'),
                self.addon.getLocalizedString(msg_id),
                xbmcgui.NOTIFICATION_ERROR,
                5000
            )
            return
        finally:
            xbmc.executebuiltin("Dialog.Close(busydialognocancel)")

        # 3. Locate the HLS stream
        medias = asset_data.get("medias") or []
        hls_url = None
        for m in medias:
            if m.get("type") == "HLS" and m.get("url"):
                hls_url = m.get("url")
                break

        if not hls_url:
            xbmc.log(f"PlaySuissePlayer: No HLS stream found for asset {asset_id}", xbmc.LOGERROR)
            xbmcgui.Dialog().notification(
                self.addon.getAddonInfo('name'),
                self.addon.getLocalizedString(30100),
                xbmcgui.NOTIFICATION_ERROR,
                5000
            )
            return

        # 4. Sign/Authorize the HLS URL with our token
        # Append id_token query parameter to authorize playback
        authorized_url = hls_url + ("&" if "?" in hls_url else "?") + f"id_token={id_token}"

        # 5. Configure inputstream.adaptive and setResolvedUrl
        helper = inputstreamhelper.Helper("hls")
        if not helper.check_inputstream():
            xbmc.log("PlaySuissePlayer: Unable to setup inputstream.adaptive", xbmc.LOGERROR)
            return

        play_item = xbmcgui.ListItem(title, path=authorized_url)
        ia = "inputstream.adaptive"
        play_item.setProperty("inputstream", ia)
        play_item.setProperty(f"{ia}.manifest_type", "hls")

        # Flag original audio language for inputstream.adaptive
        # to append "(original)"
        original_lang = asset_data.get("primaryLanguage")
        if original_lang:
            prop = f"{ia}.original_audio_language"
            play_item.setProperty(prop, original_lang)

        # Start playback
        xbmcplugin.setResolvedUrl(handle, True, play_item)

        # Keep the script alive temporarily until playback starts and we configure languages
        monitor = PlaySuissePlaybackMonitor(self.addon, original_lang)
        timeout = 20  # Max 10 seconds (wait 0.5s per loop)
        while not monitor.configured and timeout > 0:
            xbmc.sleep(500)
            timeout -= 1
