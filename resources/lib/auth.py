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

class PlaySuisseAuth:
    """Manages the PKCE OAuth2 session login flow and token caching."""

    CLIENT_ID = "1e33f1bf-8bf3-45e4-bbd9-c9ad934b5fca"
    LOGIN_BASE = "https://account.srgssr.ch"

    def __init__(self, addon):
        self.addon = addon
        self.session_file = xbmcvfs.translatePath("special://profile/addon_data/plugin.video.playsuisse/session.json")

    def get_token(self):
        """Returns a cached valid token, or performs a login if missing/expired."""
        if os.path.exists(self.session_file):
            try:
                with open(self.session_file, "r") as f:
                    session_data = json.load(f)
                token = session_data.get("id_token")
                # Check if cached token is less than 50 minutes old (tokens last 1hr)
                if time.time() - session_data.get("timestamp", 0) < 3000:
                    return token
            except Exception as e:
                xbmc.log(f"PlaySuisseAuth: Error reading session cache: {e}", xbmc.LOGDEBUG)

        return self._login()

    def _login(self):
        """Executes the full multi-step OAuth2 PKCE login handshake in pure Python."""
        email = self.addon.getSetting("email")
        password = self.addon.getSetting("password")
        if not email or not password:
            raise Exception("CREDENTIALS_MISSING")

        # 1. Generate PKCE Verifier and Challenge
        code_verifier = uuid.uuid4().hex + uuid.uuid4().hex + uuid.uuid4().hex
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()).decode().rstrip('=')

        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:136.0) Gecko/20100101 Firefox/136.0"
        })

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
        res = session.get(authz_url, params=params, timeout=15)
        parsed_query = parse_qs(urlparse(res.url).query)
        request_id = parsed_query.get('requestId', [None])[0]
        if not request_id:
            raise Exception("AUTHZ_FAILED")

        # Step 2: Submit username (initiate)
        init_url = f"{self.LOGIN_BASE}/verification-srv/v2/authenticate/initiate/password"
        payload = {
            'usage_type': 'INITIAL_AUTHENTICATION',
            'request_id': request_id,
            'medium_id': 'PASSWORD',
            'type': 'password',
            'identifier': email,
        }
        res = session.post(init_url, json=payload, timeout=15)
        res_json = res.json()
        exchange_id = res_json.get('data', {}).get('exchange_id', {}).get('exchange_id')
        if not exchange_id:
            raise Exception("USERNAME_INVALID")

        # Step 3: Submit password (authenticate)
        auth_url = f"{self.LOGIN_BASE}/verification-srv/v2/authenticate/authenticate/password"
        payload = {
            'requestId': request_id,
            'exchange_id': exchange_id,
            'type': 'password',
            'password': password,
        }
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
        res = session.post(token_url, params=params, timeout=15)
        res_json = res.json()
        id_token = res_json.get('id_token')
        if not id_token:
            raise Exception("TOKEN_TRADE_FAILED")

        # Cache the session to disk
        profile_dir = os.path.dirname(self.session_file)
        if not os.path.exists(profile_dir):
            os.makedirs(profile_dir)
        try:
            with open(self.session_file, "w") as f:
                json.dump({
                    "id_token": id_token,
                    "timestamp": time.time()
                }, f)
        except Exception as e:
            xbmc.log(f"PlaySuisseAuth: Failed to write session cache: {e}", xbmc.LOGERROR)

        return id_token
