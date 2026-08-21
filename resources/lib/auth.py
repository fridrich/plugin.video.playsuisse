# Copyright (C) 2026 Fridrich Strba
#
# This file is part of plugin.video.playsuisse.
#
# plugin.video.playsuisse is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import base64
import hashlib
import json
import os
import time
import uuid
from urllib.parse import parse_qs, urlparse

import requests
import xbmc
import xbmcvfs

try:
    from curl_cffi import requests as curl_requests
except ImportError:
    curl_requests = None


class PlaySuisseAuth:
    """Manages the PKCE OAuth2 session login, token caching, and token
    refresh flows.
    """

    CLIENT_ID = "1e33f1bf-8bf3-45e4-bbd9-c9ad934b5fca"
    LOGIN_BASE = "https://account.srgssr.ch"

    USER_AGENT = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    SEC_CH_UA = (
        '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"'
    )

    @classmethod
    def _browser_headers(
        cls,
        accept,
        referer,
        dest,
        mode,
        site,
        origin=None,
        content_type=None,
        navigation=False,
    ):
        """Builds a Chrome 120-like header set for one PKCE flow step (to
        match the TLS impersonation).
        """
        headers = {
            "User-Agent": cls.USER_AGENT,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        }
        if content_type:
            headers["Content-Type"] = content_type
        if origin:
            headers["Origin"] = origin
        headers["Referer"] = referer
        headers.update(
            {
                "Sec-Ch-Ua": cls.SEC_CH_UA,
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Linux"',
                "Sec-Fetch-Dest": dest,
                "Sec-Fetch-Mode": mode,
                "Sec-Fetch-Site": site,
            }
        )
        if navigation:
            headers["Sec-Fetch-User"] = "?1"
            headers["Upgrade-Insecure-Requests"] = "1"
        return headers

    def __init__(self, addon):
        self.addon = addon

        # Resolve the official profile directory for cross-device compatibility
        profile_dir = xbmcvfs.translatePath(self.addon.getAddonInfo("profile"))
        if not os.path.exists(profile_dir):
            try:
                os.makedirs(profile_dir)
            except Exception:
                pass

        self.session_file = os.path.join(profile_dir, "session.json")

        # Log the expected path for easy debugging on any new device
        xbmc.log(f"PlaySuisseAuth: Profile dir: {profile_dir}", xbmc.LOGINFO)

    def prompt_credentials_and_login(self):
        """Prompts the user interactively and authenticates, caching only
        tokens.
        """
        # Safety: Close any busy dialog so that the keyboards are fully
        # interactive
        xbmc.executebuiltin("Dialog.Close(busydialognocancel)")

        # Pre-fill keyboard inputs with any legacy values from settings
        email = self.addon.getSetting("email")
        password = self.addon.getSetting("password")

        # Prompt for Email
        keyboard = xbmc.Keyboard(email, self.addon.getLocalizedString(30000))
        keyboard.doModal()
        if not keyboard.isConfirmed():
            return False
        email = keyboard.getText().strip()
        if not email:
            return False

        # Prompt for Password
        keyboard = xbmc.Keyboard(
            password, self.addon.getLocalizedString(30001), True
        )
        keyboard.doModal()
        if not keyboard.isConfirmed():
            return False
        password = keyboard.getText()
        if not password:
            return False

        # Re-activate busy dialog during network login handshake
        xbmc.executebuiltin("ActivateWindow(busydialognocancel)")
        try:
            self._login_with_credentials(email, password)
            return True
        finally:
            # Always clear the plaintext password, whether login succeeded or
            # failed, so a failed attempt never leaves it sitting in settings.
            self.addon.setSetting("password", "")
            xbmc.executebuiltin("Dialog.Close(busydialognocancel)")

    def _cached_bearer_token(self, session_data):
        """Returns the token that should be used as an Authorization: Bearer
        credential for the resource APIs. access_token is the correct OAuth2
        credential for this (typ "at+jwt"); id_token is only a fallback for
        session.json files predating access_token being persisted.
        """
        return session_data.get("access_token") or session_data.get(
            "id_token"
        )

    def get_token(self):
        """Returns a cached valid token, refreshes if expired, or performs
        login.
        """
        # 1. Try to read cached session
        if os.path.exists(self.session_file):
            try:
                with open(self.session_file, "r") as f:
                    session_data = json.load(f)
                token = self._cached_bearer_token(session_data)
                refresh_token = session_data.get("refresh_token")
                expires_at = session_data.get("expires_at")

                if expires_at is not None:
                    is_fresh = time.time() < expires_at - 60
                else:
                    # Legacy session file predating expires_at: fall back to
                    # the original heuristic (tokens last ~1hr).
                    is_fresh = (
                        time.time() - session_data.get("timestamp", 0) < 3000
                    )

                if is_fresh:
                    return token

                # Token is expired, try to use refresh token
                if refresh_token:
                    try:
                        return self._refresh_token(session_data)
                    except Exception as e:
                        xbmc.log(
                            f"PlaySuisseAuth: Token refresh failed: {e}",
                            xbmc.LOGDEBUG,
                        )
            except Exception as e:
                xbmc.log(
                    f"PlaySuisseAuth: Error reading session cache: {e}",
                    xbmc.LOGDEBUG,
                )

        # 2. No session, or refresh token failed. Prompt the user interactively
        if not self.prompt_credentials_and_login():
            raise Exception("CREDENTIALS_MISSING")

        # Read and return the freshly acquired token from session.json
        if os.path.exists(self.session_file):
            try:
                with open(self.session_file, "r") as f:
                    session_data = json.load(f)
                return self._cached_bearer_token(session_data)
            except Exception:
                pass

        raise Exception("LOGIN_FAILED")

    def _write_session_cache(self, data):
        """Atomically writes the session cache to avoid a truncated file on
        a crash or power loss.
        """
        profile_dir = os.path.dirname(self.session_file)
        if not os.path.exists(profile_dir):
            os.makedirs(profile_dir)
        tmp_path = f"{self.session_file}.tmp"
        try:
            with open(tmp_path, "w") as f:
                json.dump(data, f)
            os.replace(tmp_path, self.session_file)
        except Exception as e:
            xbmc.log(
                f"PlaySuisseAuth: Failed to write session cache: {e}",
                xbmc.LOGERROR,
            )

    def _refresh_token(self, session_data):
        """Trades a cached refresh token for a fresh token set.

        cidaas rotates the refresh_token on every use, invalidating the
        previous one, so the result must always be persisted -- reusing an
        old refresh_token after a successful refresh will fail.
        """
        refresh_token = session_data.get("refresh_token")
        client_id = session_data.get("client_id") or self.CLIENT_ID

        if curl_requests:
            session = curl_requests.Session(impersonate="chrome120")
        else:
            session = requests.Session()

        session.headers.clear()
        session.headers.update(
            self._browser_headers(
                accept="application/json, text/plain, */*",
                referer="https://www.playsuisse.ch/",
                origin="https://www.playsuisse.ch",
                dest="empty",
                mode="cors",
                site="cross-site",
            )
        )

        # Hit the real token endpoint directly rather than the /proxy/token
        # alias, which 301-redirects here (and a redirected POST would lose
        # its body).
        token_url = f"{self.LOGIN_BASE}/token-srv/token"
        data = {
            'client_id': client_id,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token',
        }

        res = session.post(token_url, data=data, timeout=15)
        if not res.ok:
            raise Exception("REFRESH_FAILED")

        res_json = res.json()
        id_token = res_json.get("id_token")
        access_token = res_json.get("access_token")
        new_refresh_token = res_json.get("refresh_token")
        expires_in = res_json.get("expires_in")

        if not id_token or not access_token:
            raise Exception("REFRESH_FAILED")

        if not new_refresh_token:
            xbmc.log(
                "PlaySuisseAuth: Refresh response did not include a new "
                "refresh_token; reusing the previous one, which cidaas may "
                "already have invalidated -- the next refresh could fail.",
                xbmc.LOGWARNING,
            )
            new_refresh_token = refresh_token

        # Cache the new session tokens
        new_session_data = dict(session_data)
        new_session_data.update(
            {
                "id_token": id_token,
                "access_token": access_token,
                "refresh_token": new_refresh_token,
                "client_id": client_id,
                "expires_at": (
                    time.time() + expires_in if expires_in else None
                ),
                "timestamp": time.time(),
            }
        )
        self._write_session_cache(new_session_data)

        return access_token

    def _login_with_credentials(self, email, password):
        """Executes the full multi-step OAuth2 PKCE login handshake in pure
        Python.
        """
        # 1. Generate PKCE Verifier and Challenge
        code_verifier = uuid.uuid4().hex + uuid.uuid4().hex + uuid.uuid4().hex
        code_challenge = (
            base64.urlsafe_b64encode(
                hashlib.sha256(code_verifier.encode()).digest()
            )
            .decode()
            .rstrip('=')
        )

        if curl_requests:
            session = curl_requests.Session(impersonate="chrome120")
        else:
            session = requests.Session()

        # Step 1: Initial authz request to register login session
        authz_url = f"{self.LOGIN_BASE}/authz-srv/authz"
        params = {
            'client_id': self.CLIENT_ID,
            'redirect_uri': 'https://www.playsuisse.ch/auth',
            'scope': 'email profile openid offline_access',
            'response_type': 'code',
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256',
            'view_type': 'login',
        }
        session.headers.clear()
        session.headers.update(
            self._browser_headers(
                accept=(
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,image/apng,*/*;q=0.8,"
                    "application/signed-exchange;v=b3;q=0.7"
                ),
                referer="https://www.playsuisse.ch/",
                dest="document",
                mode="navigate",
                site="cross-site",
                navigation=True,
            )
        )
        res = session.get(authz_url, params=params, timeout=15)
        parsed_query = parse_qs(urlparse(res.url).query)
        request_id = parsed_query.get('requestId', [None])[0]
        if not request_id:
            msg = (
                f"PlaySuisseAuth: Step 1 authz failed. "
                f"Status: {res.status_code}, URL: {res.url}, "
                f"Body: {res.text[:500]}"
            )
            xbmc.log(msg, xbmc.LOGERROR)
            raise Exception("AUTHZ_FAILED")

        # Step 2: Submit username (initiate)
        init_url = (
            f"{self.LOGIN_BASE}/verification-srv/v2"
            "/authenticate/initiate/password"
        )
        payload = {
            'usage_type': 'INITIAL_AUTHENTICATION',
            'request_id': request_id,
            'medium_id': 'PASSWORD',
            'type': 'password',
            'identifier': email,
        }
        session.headers.clear()
        session.headers.update(
            self._browser_headers(
                accept="application/json, text/plain, */*",
                referer=res.url,
                origin="https://account.srgssr.ch",
                content_type="application/json",
                dest="empty",
                mode="cors",
                site="same-origin",
            )
        )
        res = session.post(init_url, json=payload, timeout=15)
        res_json = res.json()
        exchange_id = (
            res_json.get('data', {}).get('exchange_id', {}).get('exchange_id')
        )
        if not exchange_id:
            raise Exception("USERNAME_INVALID")

        # Step 3: Submit password (authenticate)
        auth_url = (
            f"{self.LOGIN_BASE}/verification-srv/v2"
            "/authenticate/authenticate/password"
        )
        payload = {
            'requestId': request_id,
            'exchange_id': exchange_id,
            'type': 'password',
            'password': password,
        }
        session.headers.clear()
        session.headers.update(
            self._browser_headers(
                accept="application/json, text/plain, */*",
                referer=res.url,
                origin="https://account.srgssr.ch",
                content_type="application/json",
                dest="empty",
                mode="cors",
                site="same-origin",
            )
        )
        res = session.post(auth_url, json=payload, timeout=15)
        res_json = res.json()
        login_data = res_json.get('data')
        if not login_data:
            raise Exception("PASSWORD_INVALID")

        # Step 4: Finalize verification and get auth code redirect
        verify_url = f"{self.LOGIN_BASE}/login-srv/verification/login"
        payload = {
            'requestId': request_id,
            'exchange_id': login_data['exchange_id']['exchange_id'],
            'verificationType': 'password',
            'sub': login_data['sub'],
            'status_id': login_data['status_id'],
            'rememberMe': True,
            'lat': '',
            'lon': '',
        }
        session.headers.clear()
        session.headers.update(
            self._browser_headers(
                accept=(
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,image/apng,*/*;q=0.8,"
                    "application/signed-exchange;v=b3;q=0.7"
                ),
                referer=res.url,
                origin="https://account.srgssr.ch",
                content_type="application/x-www-form-urlencoded",
                dest="document",
                mode="navigate",
                site="same-origin",
                navigation=True,
            )
        )
        res = session.post(verify_url, data=payload, timeout=15)
        parsed_query = parse_qs(urlparse(res.url).query)
        authorization_code = parsed_query.get('code', [None])[0]
        if not authorization_code:
            raise Exception("VERIFICATION_FAILED")

        # Step 5: Trade authorization code for id_token
        token_url = f"{self.LOGIN_BASE}/proxy/token"
        params = {
            'client_id': self.CLIENT_ID,
            'redirect_uri': 'https://www.playsuisse.ch/auth',
            'code': authorization_code,
            'code_verifier': code_verifier,
            'grant_type': 'authorization_code',
        }
        session.headers.clear()
        session.headers.update(
            self._browser_headers(
                accept="application/json, text/plain, */*",
                referer="https://www.playsuisse.ch/",
                origin="https://www.playsuisse.ch",
                dest="empty",
                mode="cors",
                site="cross-site",
            )
        )
        res = session.post(token_url, params=params, timeout=15)
        res_json = res.json()
        id_token = res_json.get('id_token')
        access_token = res_json.get('access_token')
        refresh_token = res_json.get('refresh_token')
        expires_in = res_json.get('expires_in')
        if not id_token or not access_token:
            raise Exception("TOKEN_TRADE_FAILED")

        # Cache the session to disk
        self._write_session_cache(
            {
                "id_token": id_token,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "client_id": self.CLIENT_ID,
                "expires_at": (
                    time.time() + expires_in if expires_in else None
                ),
                "timestamp": time.time(),
            }
        )

        return access_token, refresh_token
