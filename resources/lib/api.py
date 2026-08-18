# Copyright (C) 2026 Fridrich Strba
#
# This file is part of plugin.video.playsuisse.
#
# plugin.video.playsuisse is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import requests
import xbmc

class PlaySuisseAPI:
    """GraphQL client for unauthenticated Play Suisse catalog browsing."""

    GRAPHQL_URL = "https://www.playsuisse.ch/api/graphql"

    def __init__(self):
        pass

    def _get_active_locale(self):
        """Gets the locale based on the addon setting, falling back to Kodi's language."""
        import xbmcaddon
        try:
            addon = xbmcaddon.Addon("plugin.video.playsuisse")
            lang_setting = addon.getSetting("language")
            if lang_setting and lang_setting != "auto":
                return lang_setting
        except Exception:
            pass
        return self._get_kodi_locale()

    def _get_kodi_locale(self):
        """Maps Kodi's current language to Play Suisse's supported locales."""
        lang = xbmc.getLanguage(xbmc.ISO_639_1, True)
        if lang in ("de", "fr", "it", "rm"):
            return lang
        # Fallback mappings for some long codes or common variations
        lang_lower = lang.lower()
        if "de" in lang_lower:
            return "de"
        if "it" in lang_lower:
            return "it"
        if "rm" in lang_lower:
            return "rm"
        # Default to French
        return "fr"

    def _query(self, query, variables=None, token=None):
        """Executes a POST request to the Play Suisse GraphQL endpoint."""
        locale = self._get_active_locale()
        headers = {
            "Content-Type": "application/json",
            "locale": locale,
            "x-playsuisse-locale": locale,
            "x-playsuisse-app": "id=web&version=1.1.27",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
            headers["x-playsuisse-access-token"] = token
        payload = {
            "query": query,
            "variables": variables or {}
        }
        try:
            res = requests.post(self.GRAPHQL_URL, json=payload, headers=headers, timeout=15)
            if res.ok:
                return res.json().get("data", {})
            xbmc.log(f"PlaySuisseAPI: GraphQL request failed with code {res.status_code}", xbmc.LOGERROR)
        except Exception as e:
            xbmc.log(f"PlaySuisseAPI: Connection error: {e}", xbmc.LOGERROR)
        return {}

    def get_categories(self):
        """Returns a list of all categories with their associated pages."""
        q = """
        query GetCategories {
            categoriesV2 {
                id
                page {
                    id
                    title
                }
            }
        }
        """
        data = self._query(q)
        results = []
        for cat in data.get("categoriesV2", []):
            cat_id = cat.get("id")
            page = cat.get("page") or {}
            title = page.get("title") or cat_id.capitalize()
            page_id = page.get("id") or cat_id
            results.append({
                "id": cat_id,
                "page_id": page_id,
                "title": title
            })
        return sorted(results, key=lambda x: x["title"])

    def get_page(self, page_id, token=None):
        """Retrieves a specific page's modules and their asset items."""
        q = """
        query GetPage($pageId: ID!) {
            pageV2(id: $pageId) {
                id
                title
                description
                modules {
                    __typename
                    ... on ModuleCollection {
                        title
                        assets {
                            id
                            name
                            description
                            year
                            duration
                            thumbnail16x9 {
                                url
                            }
                            watch {
                                ... on AssetMediaV2 {
                                    progress {
                                        position
                                        completed
                                    }
                                }
                                ... on AssetV2 {
                                    id
                                    watch {
                                        ... on AssetMediaV2 {
                                            progress {
                                                position
                                                completed
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                    ... on ModuleDynamicCollection {
                        title
                        assets {
                            id
                            name
                            description
                            year
                            duration
                            thumbnail16x9 {
                                url
                            }
                            watch {
                                ... on AssetMediaV2 {
                                    progress {
                                        position
                                        completed
                                    }
                                }
                                ... on AssetV2 {
                                    id
                                    watch {
                                        ... on AssetMediaV2 {
                                            progress {
                                                position
                                                completed
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        data = self._query(q, {"pageId": page_id}, token=token)
        page = data.get("pageV2") or {}
        modules_list = []
        for mod in page.get("modules", []):
            assets = mod.get("assets") or []
            if not assets:
                continue
            modules_list.append({
                "typename": mod.get("__typename"),
                "title": mod.get("title") or page.get("title") or "Videos",
                "assets": assets
            })
        return {
            "id": page.get("id"),
            "title": page.get("title"),
            "description": page.get("description"),
            "modules": modules_list
        }

    def search(self, search_query):
        """Searches the Play Suisse catalog for the given term."""
        q = """
        query Search($query: String!) {
            searchPageV2(query: $query) {
                id
                modules {
                    __typename
                    ... on ModuleCollection {
                        title
                        assets {
                            id
                            name
                            description
                            year
                            duration
                            thumbnail16x9 {
                                url
                            }
                            watch {
                                ... on AssetMediaV2 {
                                    progress {
                                        position
                                        completed
                                    }
                                }
                                ... on AssetV2 {
                                    id
                                    watch {
                                        ... on AssetMediaV2 {
                                            progress {
                                                position
                                                completed
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                    ... on ModuleDynamicCollection {
                        title
                        assets {
                            id
                            name
                            description
                            year
                            duration
                            thumbnail16x9 {
                                url
                            }
                            watch {
                                ... on AssetMediaV2 {
                                    progress {
                                        position
                                        completed
                                    }
                                }
                                ... on AssetV2 {
                                    id
                                    watch {
                                        ... on AssetMediaV2 {
                                            progress {
                                                position
                                                completed
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        data = self._query(q, {"query": search_query})
        page = data.get("searchPageV2") or {}
        assets_list = []
        # Pull all found assets from search modules
        for mod in page.get("modules", []):
            # Focus on search results ModuleCollection primarily
            if mod.get("__typename") == "ModuleCollection":
                assets_list.extend(mod.get("assets") or [])
        # Fallback: pull other modules if search result collection was empty
        if not assets_list:
            for mod in page.get("modules", []):
                assets_list.extend(mod.get("assets") or [])

        # Filter duplicates by ID
        seen = set()
        unique_assets = []
        for a in assets_list:
            aid = a.get("id")
            if aid and aid not in seen:
                seen.add(aid)
                unique_assets.append(a)
        return unique_assets

    def get_asset(self, asset_id, token=None):
        """Retrieves detailed asset metadata and its episodes if it's a series."""
        q = """
        query GetAsset($assetId: ID!) {
            assetV2(id: $assetId) {
                id
                name
                primaryLanguage
                description
                descriptionLong
                year
                contentTypes
                directors
                mainCast
                productionCountries
                duration
                episodeNumber
                seasonNumber
                seriesName
                medias {
                    type
                    url
                }
                watch {
                    ... on AssetMediaV2 {
                        progress {
                            position
                            completed
                        }
                    }
                    ... on AssetV2 {
                        id
                        watch {
                            ... on AssetMediaV2 {
                                progress {
                                    position
                                    completed
                                }
                            }
                        }
                    }
                }
                episodes {
                    id
                    name
                    description
                    year
                    duration
                    episodeNumber
                    seasonNumber
                    thumbnail16x9 {
                        url
                    }
                    watch {
                        ... on AssetMediaV2 {
                            progress {
                                position
                                    completed
                            }
                        }
                        ... on AssetV2 {
                            id
                            watch {
                                ... on AssetMediaV2 {
                                    progress {
                                        position
                                        completed
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        data = self._query(q, {"assetId": asset_id}, token=token)
        return data.get("assetV2") or {}

    def get_playback_session(self, asset_id, token=None):
        """Creates a playback session on the server and retrieves the signed stream URL."""
        q = """
        mutation PlaybackSession($assetId: String!) {
            playbackSession(assetId: $assetId) {
                playbackUrl
                thumbnailUrl(templated: true)
            }
        }
        """
        data = self._query(q, {"assetId": asset_id}, token=token)
        return data.get("playbackSession") or {}

    def add_to_my_list(self, asset_id, token=None):
        """Adds an asset to the user's My List."""
        q = """
        mutation addToMyList($assetId: String!) {
            addToMyList(assetId: $assetId) {
                assetId
            }
        }
        """
        data = self._query(q, {"assetId": asset_id}, token=token)
        return data.get("addToMyList") or {}

    def remove_from_my_list(self, asset_id, token=None):
        """Removes an asset from the user's My List."""
        q = """
        mutation removeFromMyList($assetId: String!) {
            removeFromMyList(assetId: $assetId) {
                assetId
            }
        }
        """
        data = self._query(q, {"assetId": asset_id}, token=token)
        return data.get("removeFromMyList") or {}

    def hide_from_continue_watching(self, asset_id, token=None):
        """Hides an asset from the user's Continue Watching list."""
        q = """
        mutation hideFromContinueWatching($id: String!) {
            hideAssetFromContinueWatching(id: $id)
        }
        """
        data = self._query(q, {"id": asset_id}, token=token)
        return data.get("hideAssetFromContinueWatching") or False
