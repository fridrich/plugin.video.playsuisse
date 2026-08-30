# Copyright (C) 2026 Fridrich Strba
#
# This file is part of plugin.video.playsuisse.
#
# plugin.video.playsuisse is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import json
import os
import sys
import time
from urllib.parse import parse_qsl, urlencode

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

from resources.lib.auth import PlaySuisseAuth
from resources.lib.api import PlaySuisseAPI
from resources.lib.player import PlaySuissePlayer

ADDON = xbmcaddon.Addon()
ADDON_HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]

api = PlaySuisseAPI()
player = PlaySuissePlayer(ADDON)
auth_mgr = PlaySuisseAuth(ADDON)


def build_url(query):
    """Utility to build callback URLs for Kodi plugin routing."""
    return f"{BASE_URL}?{urlencode(query)}"


def get_cached_token():
    """Returns the cached auth token without ever prompting for login.

    Used by read-only menu/listing code that should silently render as
    "logged out" when there is no session yet, rather than forcing an
    interactive login prompt just from browsing.
    """
    try:
        if os.path.exists(auth_mgr.session_file):
            return auth_mgr.get_token()
    except Exception as e:
        xbmc.log(f"PlaySuisse: Session check failed: {e}", xbmc.LOGDEBUG)
    return None


def notify_session_expired():
    """Tells the user their session died server-side (e.g. a revoked or
    rejected token) instead of just silently showing an empty listing.
    """
    xbmcgui.Dialog().notification(
        ADDON.getAddonInfo('name'),
        ADDON.getLocalizedString(30119),
        xbmcgui.NOTIFICATION_ERROR,
        5000,
    )


MAIN_MENU_LANGUAGES = {
    "de": {
        "home": "Startseite",
        "fiction": "Fiktion",
        "documentary": "Docu",
        "family": "Familie",
        "music": "Musik",
        "categories": "Themen",
        "mylist": "Meine Liste",
        "continue_watching": "Weiterschauen",
        "search": "Suche",
        "highlights": "Highlights",
    },
    "fr": {
        "home": "Accueil",
        "fiction": "Fiction",
        "documentary": "Documentaire",
        "family": "Famille",
        "music": "Musique",
        "categories": "Catégories",
        "mylist": "Ma liste",
        "continue_watching": "Reprendre la lecture",
        "search": "Recherche",
        "highlights": "À la une",
    },
    "it": {
        "home": "Home",
        "fiction": "Fiction",
        "documentary": "Documentari",
        "family": "Famiglia",
        "music": "Musica",
        "categories": "Categorie",
        "mylist": "La mia lista",
        "continue_watching": "Continua a guardare",
        "search": "Cerca",
        "highlights": "In primo piano",
    },
    "rm": {
        "home": "Home",
        "fiction": "Ficziun",
        "documentary": "Documentaziuns",
        "family": "Famiglia",
        "music": "Musica",
        "categories": "Temas",
        "mylist": "Mia glista",
        "continue_watching": "Continuar la lectura",
        "search": "Tschertgar",
        "highlights": "En evidenza",
    },
    "en": {
        "home": "Home",
        "fiction": "Fiction",
        "documentary": "Documentary",
        "family": "Family",
        "music": "Music",
        "categories": "Categories",
        "mylist": "My List",
        "continue_watching": "Continue Watching",
        "search": "Search",
        "highlights": "Highlights",
    },
}


def get_main_menu_language():
    """Determines the active language for the main menu labels."""
    lang_setting = ADDON.getSetting("language")
    if lang_setting and lang_setting != "auto":
        return lang_setting

    # Fallback to Kodi's language
    kodi_lang = xbmc.getLanguage(xbmc.ISO_639_1, True)
    if kodi_lang in ("de", "fr", "it", "rm"):
        return kodi_lang

    # Check for long/variant codes
    kodi_lang_lower = kodi_lang.lower()
    if "de" in kodi_lang_lower:
        return "de"
    if "fr" in kodi_lang_lower:
        return "fr"
    if "it" in kodi_lang_lower:
        return "it"
    if "rm" in kodi_lang_lower:
        return "rm"

    # Default/fallback to English
    return "en"


def main_menu():
    """Renders the main menu of the addon mimicking the official web portal."""
    # Check if we have an authenticated session silently
    token = get_cached_token()

    lang = get_main_menu_language()
    labels = MAIN_MENU_LANGUAGES.get(lang, MAIN_MENU_LANGUAGES["en"])

    # 1. Startseite (Page ID: homepage)
    home_item = xbmcgui.ListItem(label=labels["home"])
    home_url = build_url(
        {"mode": "page", "id": "homepage", "title": labels["home"]}
    )
    xbmcplugin.addDirectoryItem(
        ADDON_HANDLE, home_url, home_item, isFolder=True
    )

    # 2. Fiktion (Page ID: fiction)
    fiction_item = xbmcgui.ListItem(label=labels["fiction"])
    fiction_url = build_url(
        {"mode": "page", "id": "fiction", "title": labels["fiction"]}
    )
    xbmcplugin.addDirectoryItem(
        ADDON_HANDLE, fiction_url, fiction_item, isFolder=True
    )

    # 3. Docu (Page ID: documentary)
    doc_item = xbmcgui.ListItem(label=labels["documentary"])
    doc_url = build_url(
        {"mode": "page", "id": "documentary", "title": labels["documentary"]}
    )
    xbmcplugin.addDirectoryItem(ADDON_HANDLE, doc_url, doc_item, isFolder=True)

    # 4. Familie (Page ID: family)
    family_item = xbmcgui.ListItem(label=labels["family"])
    family_url = build_url(
        {"mode": "page", "id": "entertainment", "title": labels["family"]}
    )
    xbmcplugin.addDirectoryItem(
        ADDON_HANDLE, family_url, family_item, isFolder=True
    )

    # 5. Musik (Page ID: music)
    music_item = xbmcgui.ListItem(label=labels["music"])
    music_url = build_url(
        {"mode": "page", "id": "music", "title": labels["music"]}
    )
    xbmcplugin.addDirectoryItem(
        ADDON_HANDLE, music_url, music_item, isFolder=True
    )

    # 6. Themen (Categories Folder)
    cat_item = xbmcgui.ListItem(label=labels["categories"])
    cat_url = build_url({"mode": "categories"})
    xbmcplugin.addDirectoryItem(ADDON_HANDLE, cat_url, cat_item, isFolder=True)

    # If authenticated, show personalized My List and Continue Watching
    if token:
        # 7. Meine Liste (Page ID: my_list)
        mylist_item = xbmcgui.ListItem(label=labels["mylist"])
        mylist_url = build_url(
            {"mode": "page", "id": "my_list", "title": labels["mylist"]}
        )
        xbmcplugin.addDirectoryItem(
            ADDON_HANDLE, mylist_url, mylist_item, isFolder=True
        )

        # 8. Weiterschauen (Page ID: continue_watching)
        resume_item = xbmcgui.ListItem(label=labels["continue_watching"])
        resume_url = build_url(
            {
                "mode": "watchlist",
                "id": "resume",
                "title": labels["continue_watching"],
            }
        )
        xbmcplugin.addDirectoryItem(
            ADDON_HANDLE, resume_url, resume_item, isFolder=True
        )

    # 9. Suche (Search Folder)
    search_item = xbmcgui.ListItem(label=labels["search"])
    search_url = build_url({"mode": "search_input"})
    xbmcplugin.addDirectoryItem(
        ADDON_HANDLE, search_url, search_item, isFolder=True
    )

    xbmcplugin.endOfDirectory(ADDON_HANDLE)


def list_categories():
    """Lists all available categories."""
    categories = api.get_categories()
    for cat in categories:
        item = xbmcgui.ListItem(label=cat["title"])
        url = build_url(
            {"mode": "page", "id": cat["page_id"], "title": cat["title"]}
        )
        xbmcplugin.addDirectoryItem(ADDON_HANDLE, url, item, isFolder=True)
    xbmcplugin.endOfDirectory(ADDON_HANDLE)


def list_page(page_id, page_title):
    """Renders modules or assets on a specific page."""
    # Check if we have an authenticated session silently
    token = get_cached_token()

    page_data, page_error = api.get_page(page_id, token=token)
    modules = page_data.get("modules") or []

    if not modules:
        if page_error == "AUTH_EXPIRED":
            notify_session_expired()
        xbmcplugin.endOfDirectory(ADDON_HANDLE, False)
        return

    # If there is only one module, flatten it and list its assets directly
    if len(modules) == 1:
        assets = modules[0]["assets"]
        if page_id == "my_list":
            # Every asset here is by definition in My List - no need to look
            # it up.
            list_assets(
                assets,
                known_mylist_ids={
                    str(a.get("id")) for a in assets if a.get("id")
                },
            )
        else:
            list_assets(assets)
    else:
        # List each module as a subfolder
        for i, mod in enumerate(modules):
            title = mod.get("title") or ""
            title_lower = title.lower()

            # Skip 'Continue Watching' and 'My List' modules on the homepage
            # to avoid duplication with root menu shortcuts
            if page_id == "homepage":
                if any(
                    term in title_lower
                    for term in (
                        "reprendre",
                        "weiterschauen",
                        "continua",
                        "continue",
                        "cuntinuar",
                    )
                ):
                    continue
                if any(
                    term in title_lower
                    for term in (
                        "ma liste",
                        "meine liste",
                        "la mia lista",
                        "my list",
                        "glista",
                        "watchlist",
                    )
                ):
                    continue

            # The web's main carousel is internally named "Smart Hero V3" etc.
            if "smart hero" in title_lower:
                lang = get_main_menu_language()
                labels = MAIN_MENU_LANGUAGES.get(
                    lang, MAIN_MENU_LANGUAGES["en"]
                )
                title = labels["highlights"]

            item = xbmcgui.ListItem(label=title)
            url = build_url(
                {
                    "mode": "module",
                    "page_id": page_id,
                    "module_idx": i,
                    "title": title,
                }
            )
            xbmcplugin.addDirectoryItem(ADDON_HANDLE, url, item, isFolder=True)
        xbmcplugin.endOfDirectory(ADDON_HANDLE)


def list_module(page_id, module_idx):
    """Lists assets inside a specific module of a page."""
    # Check if we have an authenticated session silently
    token = get_cached_token()

    page_data, page_error = api.get_page(page_id, token=token)
    modules = page_data.get("modules") or []
    try:
        module = modules[int(module_idx)]
        list_assets(module["assets"])
    except (IndexError, ValueError):
        if page_error == "AUTH_EXPIRED":
            notify_session_expired()
        xbmcplugin.endOfDirectory(ADDON_HANDLE, False)


def get_resume_position(asset):
    """Safely parses the resume position in seconds from the GraphQL
    'watch' structure.
    """
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


MYLIST_CACHE_TTL = 60  # seconds


def _mylist_cache_path():
    """Resolves the path to the local My List id cache file, creating the
    profile dir if needed.
    """
    profile_dir = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
    if not os.path.exists(profile_dir):
        try:
            os.makedirs(profile_dir)
        except Exception:
            pass
    return os.path.join(profile_dir, "mylist_cache.json")


def _invalidate_my_list_cache():
    """Drops the cached My List ids so the next listing re-fetches the
    authoritative set.
    """
    try:
        os.remove(_mylist_cache_path())
    except Exception:
        pass


def get_my_list_ids():
    """Returns the set of My List asset IDs, backed by a short-lived
    local cache so ordinary browsing doesn't pay for an extra GraphQL
    round-trip on every listing.
    """
    cache_path = _mylist_cache_path()
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r") as f:
                cache = json.load(f)
            if time.time() - cache.get("timestamp", 0) < MYLIST_CACHE_TTL:
                return set(cache.get("ids") or [])
        except Exception:
            pass

    token = get_cached_token()

    if not token:
        return set()

    ids = set()
    try:
        page_data, _ = api.get_page("my_list", token=token)
        modules = page_data.get("modules") or []
        for mod in modules:
            title_lower = (mod.get("title") or "").lower()
            if any(
                term in title_lower
                for term in (
                    "ma liste",
                    "meine liste",
                    "la mia lista",
                    "my list",
                    "glista",
                    "watchlist",
                )
            ):
                assets = mod.get("assets") or []
                ids = {str(a.get("id")) for a in assets if a.get("id")}
                break
    except Exception as e:
        xbmc.log(
            f"PlaySuisse: Failed to fetch My List IDs: {e}", xbmc.LOGERROR
        )
        return set()

    try:
        tmp_path = f"{cache_path}.tmp"
        with open(tmp_path, "w") as f:
            json.dump({"ids": sorted(ids), "timestamp": time.time()}, f)
        os.replace(tmp_path, cache_path)
    except Exception:
        pass

    return ids


def get_asset_context_menu(
    asset_id, name, is_in_mylist=False, is_resume_list=False, resume_seconds=0
):
    """Builds custom context menu actions dynamically based on state."""
    token = get_cached_token()

    if not token:
        return []

    menu_items = []

    # 1. My List context action (Add vs Remove)
    if is_in_mylist:
        menu_items.append(
            (
                ADDON.getLocalizedString(30111),
                "RunPlugin({})".format(
                    build_url(
                        {
                            "mode": "remove_mylist",
                            "id": asset_id,
                            "title": name,
                        }
                    )
                ),
            )
        )
    else:
        menu_items.append(
            (
                ADDON.getLocalizedString(30110),
                "RunPlugin({})".format(
                    build_url(
                        {"mode": "add_mylist", "id": asset_id, "title": name}
                    )
                ),
            )
        )

    # 2. Continue Watching context action (only if it has progress or we are
    # in the resume list)
    if is_resume_list or resume_seconds > 0:
        menu_items.append(
            (
                ADDON.getLocalizedString(30112),
                "RunPlugin({})".format(
                    build_url(
                        {"mode": "hide_resume", "id": asset_id, "title": name}
                    )
                ),
            )
        )

    return menu_items


def get_episode_context_menu(ep_id, name, resume_seconds=0):
    """Builds custom context menu actions for episodes."""
    token = get_cached_token()

    if not token:
        return []

    menu_items = []
    # Episodes cannot be added to My List individually (only Series can),
    # but can be hidden from Continue Watching
    if resume_seconds > 0:
        url = build_url({"mode": "hide_resume", "id": ep_id, "title": name})
        menu_items.append(
            (ADDON.getLocalizedString(30112), f"RunPlugin({url})")
        )
    return menu_items


def list_assets(assets, is_resume_list=False, known_mylist_ids=None):
    """Helper to convert GraphQL asset structures to Kodi ListItems."""
    # If the caller knows these assets are exactly the My List contents
    # (e.g. rendering the My List page), skip the extra lookup entirely.
    my_list_ids = (
        known_mylist_ids if known_mylist_ids is not None else get_my_list_ids()
    )

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
        item.addContextMenuItems(
            get_asset_context_menu(
                asset_id, name, is_in_mylist, is_resume_list, resume_seconds
            )
        )

        # Thumbnail
        thumb = asset.get("thumbnail16x9") or {}
        thumb_url = thumb.get("url")
        if thumb_url:
            item.setArt(
                {"thumb": thumb_url, "poster": thumb_url, "fanart": thumb_url}
            )

        # Set play progress / resume position for Kodi to display progress and
        # prompt for resume
        if resume_seconds > 0:
            item.setProperty("ResumeTime", str(resume_seconds))
            if duration:
                item.setProperty("TotalTime", str(duration))

        if is_series:
            url = build_url(
                {"mode": "series_details", "id": asset_id, "title": name}
            )
            xbmcplugin.addDirectoryItem(ADDON_HANDLE, url, item, isFolder=True)
        else:
            # Playable Movie
            url = build_url({"mode": "play", "id": asset_id, "title": name})
            item.setProperty("IsPlayable", "true")
            xbmcplugin.addDirectoryItem(
                ADDON_HANDLE, url, item, isFolder=False
            )

    xbmcplugin.setContent(ADDON_HANDLE, "videos")
    xbmcplugin.endOfDirectory(ADDON_HANDLE)


def list_series_episodes(series_id, series_title):
    """Lists all episodes belonging to a series."""
    # Check if we have an authenticated session silently
    token = get_cached_token()

    asset_data, asset_error = api.get_asset(series_id, token=token)
    episodes = asset_data.get("episodes") or []

    if not episodes and asset_error == "AUTH_EXPIRED":
        notify_session_expired()

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
        item.addContextMenuItems(
            get_episode_context_menu(ep_id, name, resume_seconds)
        )

        # Thumbnail
        thumb = ep.get("thumbnail16x9") or {}
        thumb_url = thumb.get("url")
        if thumb_url:
            item.setArt(
                {"thumb": thumb_url, "poster": thumb_url, "fanart": thumb_url}
            )

        # Set play progress / resume position for Kodi to display progress and
        # prompt for resume
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
    """Fetches the homepage and filters out the 'My List' or
    'Continue Watching' module.
    """
    try:
        token = auth_mgr.get_token()
    except Exception as e:
        xbmc.log(
            f"PlaySuisse: Watchlist authentication failed: {e}", xbmc.LOGERROR
        )
        xbmcplugin.endOfDirectory(ADDON_HANDLE, False)
        return

    if not token:
        xbmcplugin.endOfDirectory(ADDON_HANDLE, False)
        return

    page_data, _ = api.get_page("homepage", token=token)
    modules = page_data.get("modules") or []

    target_module = None
    for mod in modules:
        title_lower = (mod.get("title") or "").lower()
        if list_type == "watchlist":
            if any(
                term in title_lower
                for term in (
                    "ma liste",
                    "meine liste",
                    "la mia lista",
                    "my list",
                    "glista",
                    "watchlist",
                )
            ):
                target_module = mod
                break
        elif list_type == "resume":
            if any(
                term in title_lower
                for term in (
                    "reprendre",
                    "weiterschauen",
                    "continua",
                    "continue",
                    "cuntinuar",
                )
            ):
                target_module = mod
                break

    if target_module and target_module.get("assets"):
        assets = target_module["assets"]
        if list_type == "watchlist":
            # Every asset here is by definition in My List - no need to look
            # it up.
            list_assets(
                assets,
                known_mylist_ids={
                    str(a.get("id")) for a in assets if a.get("id")
                },
            )
        else:
            # If this is the 'Continue Watching' watchlist, tell list_assets to
            # enable hide context action on all items
            list_assets(assets, is_resume_list=(list_type == "resume"))
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
    # Clear existing session cache to force fresh handshake
    if os.path.exists(auth_mgr.session_file):
        try:
            os.remove(auth_mgr.session_file)
        except Exception:
            pass

    # Prompt and perform login handshake
    try:
        if not auth_mgr.prompt_credentials_and_login():
            return

        xbmcgui.Dialog().ok(
            ADDON.getAddonInfo('name'), ADDON.getLocalizedString(30102)
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
            ADDON.getAddonInfo('name'), ADDON.getLocalizedString(msg_id)
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
                xbmc.log(
                    "PlaySuisse: Successfully wrote custom "
                    "Home-to-Fullscreen keymap.",
                    xbmc.LOGINFO,
                )
            except Exception as e:
                xbmc.log(
                    f"PlaySuisse: Failed to write custom keymap: {e}",
                    xbmc.LOGERROR,
                )
    else:
        if os.path.exists(keymap_file):
            try:
                os.remove(keymap_file)
                xbmc.log(
                    "PlaySuisse: Successfully removed custom "
                    "Home-to-Fullscreen keymap.",
                    xbmc.LOGINFO,
                )
            except Exception as e:
                xbmc.log(
                    f"PlaySuisse: Failed to remove custom keymap: {e}",
                    xbmc.LOGERROR,
                )


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
            token = auth_mgr.get_token()
            if token:
                api.add_to_my_list(item_id, token=token)
                _invalidate_my_list_cache()
                xbmcgui.Dialog().notification(
                    "Play Suisse",
                    ADDON.getLocalizedString(30113).format(title=title),
                )
                xbmc.executebuiltin("Container.Refresh")
        except Exception as e:
            xbmc.log(f"PlaySuisse: Add to My List failed: {e}", xbmc.LOGERROR)
            xbmcgui.Dialog().notification(
                "Play Suisse", ADDON.getLocalizedString(30114)
            )
    elif mode == "remove_mylist":
        try:
            token = auth_mgr.get_token()
            if token:
                api.remove_from_my_list(item_id, token=token)
                _invalidate_my_list_cache()
                xbmcgui.Dialog().notification(
                    "Play Suisse",
                    ADDON.getLocalizedString(30115).format(title=title),
                )
                xbmc.executebuiltin("Container.Refresh")
        except Exception as e:
            xbmc.log(
                f"PlaySuisse: Remove from My List failed: {e}", xbmc.LOGERROR
            )
            xbmcgui.Dialog().notification(
                "Play Suisse", ADDON.getLocalizedString(30116)
            )
    elif mode == "hide_resume":
        try:
            token = auth_mgr.get_token()
            if token:
                api.hide_from_continue_watching(item_id, token=token)
                xbmcgui.Dialog().notification(
                    "Play Suisse",
                    ADDON.getLocalizedString(30117).format(title=title),
                )
                xbmc.executebuiltin("Container.Refresh")
        except Exception as e:
            xbmc.log(
                f"PlaySuisse: Hide from Continue Watching failed: {e}",
                xbmc.LOGERROR,
            )
            xbmcgui.Dialog().notification(
                "Play Suisse", ADDON.getLocalizedString(30118)
            )


if __name__ == "__main__":
    run()
