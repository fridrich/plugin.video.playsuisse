# Copyright (C) 2026 Fridrich Strba
#
# This file is part of plugin.video.playsuisse.
#
# plugin.video.playsuisse is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import sys
from urllib.parse import parse_qsl, urlencode

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

from resources.lib.api import PlaySuisseAPI
from resources.lib.player import PlaySuissePlayer

ADDON = xbmcaddon.Addon()
ADDON_HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]

api = PlaySuisseAPI()
player = PlaySuissePlayer(ADDON)

def build_url(query):
    """Utility to build callback URLs for Kodi plugin routing."""
    return f"{BASE_URL}?{urlencode(query)}"

def main_menu():
    """Renders the main menu of the addon mimicking the official web portal."""
    # Check if we have an authenticated session silently
    id_token = None
    try:
        from resources.lib.auth import PlaySuisseAuth
        auth_mgr = PlaySuisseAuth(ADDON)
        import os
        if os.path.exists(auth_mgr.session_file):
            id_token = auth_mgr.get_token()
    except Exception as e:
        xbmc.log(f"PlaySuisse: Main menu session check failed: {e}", xbmc.LOGDEBUG)

    # 1. Home / Highlights (Page ID: homepage)
    home_item = xbmcgui.ListItem(label=ADDON.getLocalizedString(30050))
    home_url = build_url({"mode": "page", "id": "homepage", "title": ADDON.getLocalizedString(30050)})
    xbmcplugin.addDirectoryItem(ADDON_HANDLE, home_url, home_item, isFolder=True)

    # If authenticated, show personalized My List and Continue Watching
    if id_token:
        # 2. My List (Page ID: my_list)
        mylist_item = xbmcgui.ListItem(label=ADDON.getLocalizedString(30035))
        mylist_url = build_url({"mode": "page", "id": "my_list", "title": ADDON.getLocalizedString(30035)})
        xbmcplugin.addDirectoryItem(ADDON_HANDLE, mylist_url, mylist_item, isFolder=True)

        # 3. Continue Watching (String ID 30036: Continue Watching)
        resume_item = xbmcgui.ListItem(label=ADDON.getLocalizedString(30036))
        resume_url = build_url({"mode": "watchlist", "id": "resume", "title": ADDON.getLocalizedString(30036)})
        xbmcplugin.addDirectoryItem(ADDON_HANDLE, resume_url, resume_item, isFolder=True)

    # 4. Fiction (Page ID: fiction)
    fiction_item = xbmcgui.ListItem(label=ADDON.getLocalizedString(30037))
    fiction_url = build_url({"mode": "page", "id": "fiction", "title": ADDON.getLocalizedString(30037)})
    xbmcplugin.addDirectoryItem(ADDON_HANDLE, fiction_url, fiction_item, isFolder=True)

    # 5. Documentaries (Page ID: documentary)
    doc_item = xbmcgui.ListItem(label=ADDON.getLocalizedString(30038))
    doc_url = build_url({"mode": "page", "id": "documentary", "title": ADDON.getLocalizedString(30038)})
    xbmcplugin.addDirectoryItem(ADDON_HANDLE, doc_url, doc_item, isFolder=True)

    # 6. Categories Folder (String ID 30010: Categories)
    cat_item = xbmcgui.ListItem(label=ADDON.getLocalizedString(30010))
    cat_url = build_url({"mode": "categories"})
    xbmcplugin.addDirectoryItem(ADDON_HANDLE, cat_url, cat_item, isFolder=True)

    # 7. Search Folder (String ID 30085: Search)
    search_item = xbmcgui.ListItem(label=ADDON.getLocalizedString(30085))
    search_url = build_url({"mode": "search_input"})
    xbmcplugin.addDirectoryItem(ADDON_HANDLE, search_url, search_item, isFolder=True)

    xbmcplugin.endOfDirectory(ADDON_HANDLE)


def list_categories():
    """Lists all available categories."""
    categories = api.get_categories()
    for cat in categories:
        item = xbmcgui.ListItem(label=cat["title"])
        url = build_url({"mode": "page", "id": cat["page_id"], "title": cat["title"]})
        xbmcplugin.addDirectoryItem(ADDON_HANDLE, url, item, isFolder=True)
    xbmcplugin.endOfDirectory(ADDON_HANDLE)


def list_page(page_id, page_title):
    """Renders modules or assets on a specific page."""
    # Check if we have an authenticated session silently
    id_token = None
    try:
        from resources.lib.auth import PlaySuisseAuth
        auth_mgr = PlaySuisseAuth(ADDON)
        import os
        if os.path.exists(auth_mgr.session_file):
            id_token = auth_mgr.get_token()
    except Exception:
        pass

    page_data = api.get_page(page_id, token=id_token)
    modules = page_data.get("modules") or []

    if not modules:
        xbmcplugin.endOfDirectory(ADDON_HANDLE, False)
        return

    # If there is only one module, flatten it and list its assets directly
    if len(modules) == 1:
        list_assets(modules[0]["assets"])
    else:
        # List each module as a subfolder
        for i, mod in enumerate(modules):
            item = xbmcgui.ListItem(label=mod["title"])
            url = build_url({
                "mode": "module",
                "page_id": page_id,
                "module_idx": i,
                "title": mod["title"]
            })
            xbmcplugin.addDirectoryItem(ADDON_HANDLE, url, item, isFolder=True)
        xbmcplugin.endOfDirectory(ADDON_HANDLE)

def list_module(page_id, module_idx):
    """Lists assets inside a specific module of a page."""
    # Check if we have an authenticated session silently
    id_token = None
    try:
        from resources.lib.auth import PlaySuisseAuth
        auth_mgr = PlaySuisseAuth(ADDON)
        import os
        if os.path.exists(auth_mgr.session_file):
            id_token = auth_mgr.get_token()
    except Exception:
        pass

    page_data = api.get_page(page_id, token=id_token)
    modules = page_data.get("modules") or []
    try:
        module = modules[int(module_idx)]
        list_assets(module["assets"])
    except (IndexError, ValueError):
        xbmcplugin.endOfDirectory(ADDON_HANDLE, False)

def list_assets(assets):
    """Helper to convert GraphQL asset structures to Kodi ListItems."""
    for asset in assets:
        asset_id = asset.get("id")
        name = asset.get("name") or "Video"
        desc = asset.get("description") or ""
        year = asset.get("year")
        duration = asset.get("duration")

        # Determine if it's a series (series are folders, movies are playable files)
        # Note: if it has duration/year but we are unsure, we can check via asset details.
        # But normally Series have years represented as ranges (e.g. '2017-2022') or duration is null.
        is_series = duration is None or duration == 0

        item = xbmcgui.ListItem(label=name)
        info = {
            "title": name,
            "plot": desc,
        }
        if year:
            try:
                info["year"] = int(str(year)[:4])
            except ValueError:
                pass
        if duration:
            info["duration"] = int(duration)

        item.setInfo("video", info)

        # Thumbnail
        thumb = asset.get("thumbnail16x9") or {}
        thumb_url = thumb.get("url")
        if thumb_url:
            item.setArt({"thumb": thumb_url, "poster": thumb_url, "fanart": thumb_url})

        if is_series:
            url = build_url({"mode": "series_details", "id": asset_id, "title": name})
            xbmcplugin.addDirectoryItem(ADDON_HANDLE, url, item, isFolder=True)
        else:
            # Playable Movie
            url = build_url({"mode": "play", "id": asset_id, "title": name})
            item.setProperty("IsPlayable", "true")
            xbmcplugin.addDirectoryItem(ADDON_HANDLE, url, item, isFolder=False)

    xbmcplugin.setContent(ADDON_HANDLE, "videos")
    xbmcplugin.endOfDirectory(ADDON_HANDLE)

def list_series_episodes(series_id, series_title):
    """Lists all episodes belonging to a series."""
    asset_data = api.get_asset(series_id)
    episodes = asset_data.get("episodes") or []

    for ep in episodes:
        ep_id = ep.get("id")
        name = ep.get("name") or "Episode"
        desc = ep.get("description") or ""
        year = ep.get("year")
        duration = ep.get("duration")
        ep_num = ep.get("episodeNumber")
        season_num = ep.get("seasonNumber")

        display_name = name
        if ep_num is not None:
            display_name = f"E{ep_num} - {name}"
            if season_num is not None:
                display_name = f"S{season_num} {display_name}"

        item = xbmcgui.ListItem(label=display_name)
        info = {
            "title": name,
            "plot": desc,
            "tvshowtitle": series_title,
        }
        if ep_num is not None:
            info["episode"] = ep_num
        if season_num is not None:
            info["season"] = season_num
        if year:
            try:
                info["year"] = int(str(year)[:4])
            except ValueError:
                pass
        if duration:
            info["duration"] = int(duration)

        item.setInfo("video", info)

        # Thumbnail
        thumb = ep.get("thumbnail16x9") or {}
        thumb_url = thumb.get("url")
        if thumb_url:
            item.setArt({"thumb": thumb_url, "poster": thumb_url, "fanart": thumb_url})

        url = build_url({"mode": "play", "id": ep_id, "title": name})
        item.setProperty("IsPlayable", "true")
        xbmcplugin.addDirectoryItem(ADDON_HANDLE, url, item, isFolder=False)

    xbmcplugin.setContent(ADDON_HANDLE, "episodes")
    xbmcplugin.endOfDirectory(ADDON_HANDLE)


def handle_watchlist(list_type):
    """Fetches the homepage and filters out the 'My List' or 'Continue Watching' module."""
    id_token = None
    try:
        from resources.lib.auth import PlaySuisseAuth
        auth_mgr = PlaySuisseAuth(ADDON)
        id_token = auth_mgr.get_token()
    except Exception as e:
        xbmc.log(f"PlaySuisse: Watchlist authentication failed: {e}", xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(ADDON_HANDLE, False)
        return

    if not id_token:
        xbmcplugin.endOfDirectory(ADDON_HANDLE, False)
        return

    page_data = api.get_page("homepage", token=id_token)
    modules = page_data.get("modules") or []

    target_module = None
    for mod in modules:
        title_lower = (mod.get("title") or "").lower()
        if list_type == "watchlist":
            if any(term in title_lower for term in ("ma liste", "meine liste", "la mia lista", "my list", "glista", "watchlist")):
                target_module = mod
                break
        elif list_type == "resume":
            if any(term in title_lower for term in ("reprendre", "weiterschauen", "continua", "continue", "cuntinuar")):
                target_module = mod
                break

    if target_module and target_module.get("assets"):
        list_assets(target_module["assets"])
    else:
        xbmcplugin.endOfDirectory(ADDON_HANDLE, True)


def handle_search_input():
    """Prompts the user for a search term and lists matching assets."""
    keyboard = xbmc.Keyboard("", ADDON.getLocalizedString(30085))
    keyboard.doModal()
    if keyboard.isConfirmed():
        query = keyboard.getText()
        if query:
            results = api.search(query)
            list_assets(results)
        else:
            xbmcplugin.endOfDirectory(ADDON_HANDLE, False)
    else:
        xbmcplugin.endOfDirectory(ADDON_HANDLE, False)


def handle_login():
    """Triggers authentication with email and password prompting."""
    from resources.lib.auth import PlaySuisseAuth
    auth = PlaySuisseAuth(ADDON)

    # Clear existing session cache to force fresh handshake
    import os
    if os.path.exists(auth.session_file):
        try:
            os.remove(auth.session_file)
        except Exception:
            pass

    # Prompt and perform login handshake
    try:
        if not auth.prompt_credentials_and_login():
            return

        xbmcgui.Dialog().ok(
            ADDON.getAddonInfo('name'),
            ADDON.getLocalizedString(30102)
        )
    except Exception as e:
        err_str = str(e)
        xbmc.log(f"PlaySuisse login action failed: {err_str}", xbmc.LOGERROR)

        if "CREDENTIALS_MISSING" in err_str:
            msg_id = 30101
        elif "USERNAME_INVALID" in err_str:
            msg_id = 30103
        elif "PASSWORD_INVALID" in err_str:
            msg_id = 30104
        else:
            msg_id = 30100

        xbmcgui.Dialog().ok(
            ADDON.getAddonInfo('name'),
            ADDON.getLocalizedString(msg_id)
        )


def run():
    """Main routing and execution logic."""
    params = dict(parse_qsl(sys.argv[2][1:]))
    mode = params.get("mode")
    item_id = params.get("id")
    title = params.get("title") or "Video"

    if mode is None:
        main_menu()
    elif mode == "categories":
        list_categories()
    elif mode == "watchlist":
        handle_watchlist(item_id)
    elif mode == "page":
        list_page(item_id, title)
    elif mode == "module":
        list_module(params.get("page_id"), params.get("module_idx"))
    elif mode == "series_details":
        list_series_episodes(item_id, title)
    elif mode == "search_input":
        handle_search_input()
    elif mode == "login":
        handle_login()
    elif mode == "play":
        player.resolve_and_play(ADDON_HANDLE, item_id, title)


if __name__ == "__main__":
    run()
