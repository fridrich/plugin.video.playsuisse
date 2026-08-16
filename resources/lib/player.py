# Copyright (C) 2026 Fridrich Strba
#
# This file is part of plugin.video.playsuisse.
#
# plugin.video.playsuisse is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import subprocess
import json
import xbmc
import xbmcgui
import xbmcplugin
import inputstreamhelper

class PlaySuissePlayer:
    """Invokes system yt-dlp binary with user credentials to resolve HLS streams."""

    def __init__(self, addon):
        self.addon = addon

    def resolve_and_play(self, handle, asset_id, title):
        """Resolves the watch URL using yt-dlp and hands the stream to Kodi's player."""
        email = self.addon.getSetting("email")
        password = self.addon.getSetting("password")

        if not email or not password:
            xbmcgui.Dialog().notification(
                self.addon.getAddonInfo('name'),
                self.addon.getLocalizedString(30101),
                xbmcgui.NOTIFICATION_ERROR,
                5000
            )
            return

        url = f"https://www.playsuisse.ch/watch/{asset_id}"
        cmd = [
            "/usr/bin/yt-dlp",
            "--username", email,
            "--password", password,
            "--dump-json",
            url
        ]

        xbmc.executebuiltin("ActivateWindow(busydialognocancel)")
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
        finally:
            xbmc.executebuiltin("Dialog.Close(busydialognocancel)")

        if process.returncode != 0:
            err_msg = stderr.decode('utf-8', errors='ignore')
            xbmc.log(f"PlaySuissePlayer: yt-dlp failed: {err_msg}", xbmc.LOGERROR)
            xbmcgui.Dialog().notification(
                self.addon.getAddonInfo('name'),
                self.addon.getLocalizedString(30100),
                xbmcgui.NOTIFICATION_ERROR,
                5000
            )
            return

        try:
            data = json.loads(stdout.decode('utf-8'))
        except Exception as e:
            xbmc.log(f"PlaySuissePlayer: Failed to parse JSON: {e}", xbmc.LOGERROR)
            return

        # Extract manifest URL (can be top-level 'url', 'manifest_url', or inside 'formats')
        m3u8_url = data.get('url') or data.get('manifest_url')
        if not m3u8_url:
            formats = data.get('formats', [])
            for f in formats:
                if f.get('protocol') == 'm3u8_native' or 'm3u8' in f.get('url', ''):
                    m3u8_url = f.get('url')
                    break

        if not m3u8_url:
            xbmc.log("PlaySuissePlayer: No playable HLS url found in yt-dlp output", xbmc.LOGERROR)
            return

        helper = inputstreamhelper.Helper("hls")
        if not helper.check_inputstream():
            xbmc.log("PlaySuissePlayer: Unable to setup inputstream.adaptive", xbmc.LOGERROR)
            return

        play_item = xbmcgui.ListItem(title, path=m3u8_url)
        ia = "inputstream.adaptive"
        play_item.setProperty("inputstream", ia)
        play_item.setProperty(f"{ia}.manifest_type", "hls")

        # Set subtitle tracks if returned by yt-dlp
        subtitles = []
        for lang, tracks in data.get('subtitles', {}).items():
            for track in tracks:
                if track.get('ext') == 'vtt' or 'vtt' in track.get('url', ''):
                    subtitles.append(track.get('url'))
        if subtitles:
            play_item.setSubtitles(subtitles)

        xbmcplugin.setResolvedUrl(handle, True, play_item)
