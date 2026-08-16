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

    def _query(self, query, variables=None):
        """Executes a POST request to the Play Suisse GraphQL endpoint."""
        locale = self._get_active_locale()
        headers = {
            "Content-Type": "application/json",
            "locale": locale,
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:136.0) Gecko/20100101 Firefox/136.0"
        }
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

    def get_page(self, page_id):
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
                        }
                    }
                }
            }
        }
        """
        data = self._query(q, {"pageId": page_id})
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

    def get_asset(self, asset_id):
        """Retrieves detailed asset metadata and its episodes if it's a series."""
        q = """
        query GetAsset($assetId: ID!) {
            assetV2(id: $assetId) {
                id
                name
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
                }
            }
        }
        """
        data = self._query(q, {"assetId": asset_id})
        return data.get("assetV2") or {}
