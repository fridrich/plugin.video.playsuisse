# Copyright (C) 2026 Fridrich Strba
#
# This file is part of plugin.video.playsuisse.
#
# plugin.video.playsuisse is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import sys
import xbmc
import xbmcaddon

ADDON = xbmcaddon.Addon("plugin.video.playsuisse")


class PlaySuissePlaybackMonitor(xbmc.Player):
    """Monitors playback to dynamically configure preferred audio and subtitle languages."""

    def __init__(self, primary_lang):
        xbmc.Player.__init__(self)
        self.primary_lang = primary_lang
        self.configured = False

    def onAVStarted(self):
        """Called when audio and video streams start playing."""
        xbmc.sleep(1000)  # Give Kodi's audio engine time to stabilize

        # Ignore short intro/logo clips preceding the main video
        total_time = self.getTotalTime()
        if total_time > 0 and total_time < 25:
            xbmc.log(f"PlaySuissePlaybackMonitor: Short intro/logo detected ({total_time} s), skipping track configuration.", xbmc.LOGDEBUG)
            return

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
            "fr": ("fra", "fre", "french", "français", "francais"),
            "de": ("deu", "ger", "german", "deutsch"),
            "it": ("ita", "italian", "italiano"),
            "rm": ("roh", "romansh", "rumantsch", "rumantch")
        }
        if target_lang in mapping:
            for term in mapping[target_lang]:
                if term in stream_lang:
                    return True
        return False

    def _configure_audio(self):
        pref_audio = ADDON.getSetting("audio_language") or "auto"
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
        pref_subs = ADDON.getSetting("subtitle_language") or "off"
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


def main():
    primary_lang = sys.argv[1] if len(sys.argv) > 1 else ""
    monitor = PlaySuissePlaybackMonitor(primary_lang)

    # Keep background script alive until playback starts and we configure languages, or 25s timeout
    timeout = 50  # 25 seconds
    while not monitor.configured and timeout > 0:
        xbmc.sleep(500)
        timeout -= 1


if __name__ == "__main__":
    main()
