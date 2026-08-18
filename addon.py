# Copyright (C) 2026 Fridrich Strba
#
# This file is part of plugin.video.playsuisse.
#
# plugin.video.playsuisse is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import os
import sys
from urllib.parse import parse_qsl, urlencode

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

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

        # 3. Continue Watching (Page ID: continue_watching)
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

    # 4. Categories Folder (String ID 30010: Categories)
    cat_item = xbmcgui.ListItem(label=ADDON.getLocalizedString(30010))
    cat_url = build_url({"mode": "categories"})
    xbmcplugin.addDirectoryItem(ADDON_HANDLE, cat_url, cat_item, isFolder=True)

    # 5. Search Folder (String ID 30085: Search)
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
        # If this is the 'my_list' page, we can pass is_resume_list=False
        list_assets(modules[0]["assets"])
    else:
        # List each module as a subfolder
        for i, mod in enumerate(modules):
            title = mod.get("title") or ""
            # The web's main carousel is internally named "Smart Hero V3" etc.
            if "smart hero" in title.lower():
                title = ADDON.getLocalizedString(30086)

            item = xbmcgui.ListItem(label=title)
            url = build_url({
                "mode": "module",
                "page_id": page_id,
                "module_idx": i,
                "title": title
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


def get_resume_position(asset):
    """Safely parses the resume position in seconds from the GraphQL 'watch' structure."""
    watch = asset.get("watch")
    if not watch:
        return 0

    # 1. Direct watch.progress (e.g. Movies)
    progress = watch.get("progress")
    if progress:
        position = progress.get("position")
        completed = progress.get("completed")
        if position and not completed:
            return int(position)

    # 2. Nested watch.watch.progress (e.g. Episodes inside Series)
    nested_watch = watch.get("watch")
    if isinstance(nested_watch, dict):
        nested_progress = nested_watch.get("progress")
        if nested_progress:
            position = nested_progress.get("position")
            completed = nested_progress.get("completed")
            if position and not completed:
                return int(position)

    return 0


def get_my_list_ids():
    """Fetches the user's My List page and returns a set of asset IDs."""
    id_token = None
    try:
        from resources.lib.auth import PlaySuisseAuth
        auth_mgr = PlaySuisseAuth(ADDON)
        if os.path.exists(auth_mgr.session_file):
            id_token = auth_mgr.get_token()
    except Exception:
        pass

    if not id_token:
        return set()

    try:
        page_data = api.get_page("my_list", token=id_token)
        modules = page_data.get("modules") or []
        for mod in modules:
            title_lower = (mod.get("title") or "").lower()
            if any(term in title_lower for term in ("ma liste", "meine liste", "la mia lista", "my list", "glista", "watchlist")):
                assets = mod.get("assets") or []
                return {str(a.get("id")) for a in assets if a.get("id")}
    except Exception as e:
        xbmc.log(f"PlaySuisse: Failed to fetch My List IDs: {e}", xbmc.LOGERROR)
    return set()


def get_asset_context_menu(asset_id, name, is_in_mylist=False, is_resume_list=False, resume_seconds=0):
    """Builds custom context menu actions dynamically based on state."""
    id_token = None
    try:
        from resources.lib.auth import PlaySuisseAuth
        auth_mgr = PlaySuisseAuth(ADDON)
        if os.path.exists(auth_mgr.session_file):
            id_token = auth_mgr.get_token()
    except Exception:
        pass

    if not id_token:
        return []

    menu_items = []

    # 1. My List context action (Add vs Remove)
    if is_in_mylist:
        menu_items.append((ADDON.getLocalizedString(30111), f"RunPlugin({build_url({'mode': 'remove_mylist', 'id': asset_id, 'title': name})})"))
    else:
        menu_items.append((ADDON.getLocalizedString(30110), f"RunPlugin({build_url({'mode': 'add_mylist', 'id': asset_id, 'title': name})})"))

    # 2. Continue Watching context action (only if it has progress or we are in the resume list)
    if is_resume_list or resume_seconds > 0:
        menu_items.append((ADDON.getLocalizedString(30112), f"RunPlugin({build_url({'mode': 'hide_resume', 'id': asset_id, 'title': name})})"))

    return menu_items


def get_episode_context_menu(ep_id, name, resume_seconds=0):
    """Builds custom context menu actions for episodes."""
    id_token = None
    try:
        from resources.lib.auth import PlaySuisseAuth
        auth_mgr = PlaySuisseAuth(ADDON)
        if os.path.exists(auth_mgr.session_file):
            id_token = auth_mgr.get_token()
    except Exception:
        pass

    if not id_token:
        return []

    menu_items = []
    # Episodes cannot be added to My List individually (only Series can), but can be hidden from Continue Watching
    if resume_seconds > 0:
        menu_items.append((ADDON.getLocalizedString(30112), f"RunPlugin({build_url({'mode': 'hide_resume', 'id': ep_id, 'title': name})})"))
    return menu_items


def list_assets(assets, is_resume_list=False):
    """Helper to convert GraphQL asset structures to Kodi ListItems."""
    my_list_ids = get_my_list_ids()

    for asset in assets:
        asset_id = asset.get("id")
        name = asset.get("name") or "Video"
        desc = asset.get("description") or ""
        year = asset.get("year")
        duration = asset.get("duration")

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

        resume_seconds = get_resume_position(asset)

        # Context menu actions (My List & Continue Watching)
        is_in_mylist = str(asset_id) in my_list_ids
        item.addContextMenuItems(get_asset_context_menu(asset_id, name, is_in_mylist, is_resume_list, resume_seconds))

        # Thumbnail
        thumb = asset.get("thumbnail16x9") or {}
        thumb_url = thumb.get("url")
        if thumb_url:
            item.setArt({"thumb": thumb_url, "poster": thumb_url, "fanart": thumb_url})

        # Set play progress / resume position for Kodi to display progress and prompt for resume
        if resume_seconds > 0:
            item.setProperty("ResumeTime", str(resume_seconds))
            if duration:
                item.setProperty("TotalTime", str(duration))

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
    # Check if we have an authenticated session silently
    id_token = None
    try:
        from resources.lib.auth import PlaySuisseAuth
        auth_mgr = PlaySuisseAuth(ADDON)
        if os.path.exists(auth_mgr.session_file):
            id_token = auth_mgr.get_token()
    except Exception:
        pass

    asset_data = api.get_asset(series_id, token=id_token)
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

        resume_seconds = get_resume_position(ep)

        # Context menu actions for episodes
        item.addContextMenuItems(get_episode_context_menu(ep_id, name, resume_seconds))

        # Thumbnail
        thumb = ep.get("thumbnail16x9") or {}
        thumb_url = thumb.get("url")
        if thumb_url:
            item.setArt({"thumb": thumb_url, "poster": thumb_url, "fanart": thumb_url})

        # Set play progress / resume position for Kodi to display progress and prompt for resume
        if resume_seconds > 0:
            item.setProperty("ResumeTime", str(resume_seconds))
            if duration:
                item.setProperty("TotalTime", str(duration))

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
        # If this is the 'Continue Watching' watchlist, tell list_assets to enable hide context action on all items
        list_assets(target_module["assets"], is_resume_list=(list_type == "resume"))
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


def handle_keymap_sync():
    """Manages creation or removal of the custom Home-to-Fullscreen keymap."""
    keymaps_dir = xbmcvfs.translatePath("special://profile/keymaps/")
    keymap_file = os.path.join(keymaps_dir, "playsuisse_keymap.xml")

    enable_keymap = ADDON.getSetting("enable_keymap") == "true"

    if enable_keymap:
        if not os.path.exists(keymaps_dir):
            try:
                os.makedirs(keymaps_dir)
            except Exception:
                pass

        if not os.path.exists(keymap_file):
            keymap_content = """<?xml version="1.0" encoding="UTF-8"?>
<keymap>
  <Home>
    <keyboard>
      <back>Fullscreen</back>
      <backspace>Fullscreen</backspace>
    </keyboard>
    <remote>
      <back>Fullscreen</back>
    </remote>
  </Home>
</keymap>
"""
            try:
                with open(keymap_file, "w") as f:
                    f.write(keymap_content)
                xbmc.log("PlaySuisse: Successfully wrote custom Home-to-Fullscreen keymap.", xbmc.LOGINFO)
            except Exception as e:
                xbmc.log(f"PlaySuisse: Failed to write custom keymap: {e}", xbmc.LOGERROR)
    else:
        if os.path.exists(keymap_file):
            try:
                os.remove(keymap_file)
                xbmc.log("PlaySuisse: Successfully removed custom Home-to-Fullscreen keymap.", xbmc.LOGINFO)
            except Exception as e:
                xbmc.log(f"PlaySuisse: Failed to remove custom keymap: {e}", xbmc.LOGERROR)


def run():
    """Main routing and execution logic."""
    # Synchronize keymap with settings
    handle_keymap_sync()

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
    elif mode == "add_mylist":
        try:
            from resources.lib.auth import PlaySuisseAuth
            auth_mgr = PlaySuisseAuth(ADDON)
            id_token = auth_mgr.get_token()
            if id_token:
                api.add_to_my_list(item_id, token=id_token)
                xbmcgui.Dialog().notification("Play Suisse", ADDON.getLocalizedString(30113).format(title=title))
                xbmc.executebuiltin("Container.Refresh")
        except Exception as e:
            xbmc.log(f"PlaySuisse: Add to My List failed: {e}", xbmc.LOGERROR)
            xbmcgui.Dialog().notification("Play Suisse", ADDON.getLocalizedString(30114))
    elif mode == "remove_mylist":
        try:
            from resources.lib.auth import PlaySuisseAuth
            auth_mgr = PlaySuisseAuth(ADDON)
            id_token = auth_mgr.get_token()
            if id_token:
                api.remove_from_my_list(item_id, token=id_token)
                xbmcgui.Dialog().notification("Play Suisse", ADDON.getLocalizedString(30115).format(title=title))
                xbmc.executebuiltin("Container.Refresh")
        except Exception as e:
            xbmc.log(f"PlaySuisse: Remove from My List failed: {e}", xbmc.LOGERROR)
            xbmcgui.Dialog().notification("Play Suisse", ADDON.getLocalizedString(30116))
    elif mode == "hide_resume":
        try:
            from resources.lib.auth import PlaySuisseAuth
            auth_mgr = PlaySuisseAuth(ADDON)
            id_token = auth_mgr.get_token()
            if id_token:
                api.hide_from_continue_watching(item_id, token=id_token)
                xbmcgui.Dialog().notification("Play Suisse", ADDON.getLocalizedString(30117).format(title=title))
                xbmc.executebuiltin("Container.Refresh")
        except Exception as e:
            xbmc.log(f"PlaySuisse: Hide from Continue Watching failed: {e}", xbmc.LOGERROR)
            xbmcgui.Dialog().notification("Play Suisse", ADDON.getLocalizedString(30118))


if __name__ == "__main__":
    run()
