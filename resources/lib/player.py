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

        # Run the playback monitor script in a separate background process
        # to select languages without delaying the video startup
        monitor_script = xbmcvfs.translatePath("special://addon/plugin.video.playsuisse/resources/lib/monitor.py")
        xbmc.executebuiltin(f"RunScript({monitor_script}, {original_lang})")
