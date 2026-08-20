# Copyright (C) 2026 Fridrich Strba
#
# This file is part of plugin.video.playsuisse.
#
# plugin.video.playsuisse is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import os
import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs
import inputstreamhelper

from resources.lib.auth import PlaySuisseAuth
from resources.lib.api import PlaySuisseAPI


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

            # 2. Try to fetch playback session containing signed HLS URL and register play on server
            hls_url = None
            is_signed_url = False
            playback_error = None
            try:
                session_data, playback_error = self.api.get_playback_session(asset_id, token=id_token)
                playback_url = session_data.get("playbackUrl")
                if playback_url:
                    hls_url = playback_url
                    is_signed_url = True
            except Exception as e:
                xbmc.log(f"PlaySuissePlayer: Playback session creation failed, falling back: {e}", xbmc.LOGWARNING)

            # 3. Fetch asset details containing metadata (and media streams as fallback)
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

        # 4. Locate the HLS stream if not already obtained from playback session
        if not hls_url:
            medias = asset_data.get("medias") or []
            for m in medias:
                if m.get("type") == "HLS" and m.get("url"):
                    hls_url = m.get("url")
                    break

        if not hls_url:
            xbmc.log(f"PlaySuissePlayer: No HLS stream found for asset {asset_id}", xbmc.LOGERROR)
            # Show the server's own reason (e.g. a device/session limit) when we have one,
            # instead of always falling back to the generic "failed to play" message.
            message = playback_error or self.addon.getLocalizedString(30100)
            xbmcgui.Dialog().notification(
                self.addon.getAddonInfo('name'),
                message,
                xbmcgui.NOTIFICATION_ERROR,
                5000
            )
            return

        # 5. Authorize/Sign the HLS URL
        if is_signed_url:
            authorized_url = hls_url
        else:
            # Append id_token query parameter to authorize playback
            authorized_url = hls_url + ("&" if "?" in hls_url else "?") + f"id_token={id_token}"

        # 6. Configure inputstream.adaptive and setResolvedUrl
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

        # Run the playback monitor script in a separate background process
        # to select languages without delaying the video startup
        addon_path = xbmcvfs.translatePath(self.addon.getAddonInfo('path'))
        monitor_script = os.path.join(addon_path, "resources", "lib", "monitor.py")
        xbmc.executebuiltin(f'RunScript("{monitor_script}", "{original_lang}", "{asset_id}", "{title}")')
