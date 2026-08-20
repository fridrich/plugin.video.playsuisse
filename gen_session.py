#!/usr/bin/env python3
# Copyright (C) 2026 Fridrich Strba
#
# Standalone CLI to generate Play Suisse session tokens on a PC.
# Usage:
#   1. Secure Prompt (No Escaping Needed):
#      ./gen_session.py --username="your_email@example.com" > session.json
#
#   2. Password File (No Escaping Needed):
#      ./gen_session.py --username="your_email@example.com" --password-file="pass.txt" > session.json
#
#   3. Command Line (Requires Single Quotes):
#      ./gen_session.py --username="your_email@example.com" --password='your_password_here' > session.json

import sys
import os
import argparse
import base64
import hashlib
import json
import time
import uuid
from urllib.parse import parse_qs, urlparse
import requests

try:
    from curl_cffi import requests as curl_requests
except ImportError:
    curl_requests = None

CLIENT_ID = "1e33f1bf-8bf3-45e4-bbd9-c9ad934b5fca"
LOGIN_BASE = "https://account.srgssr.ch"


def log(msg):
    sys.stderr.write(f"[*] {msg}\n")
    sys.stderr.flush()


def error(msg):
    sys.stderr.write(f"[ERROR] {msg}\n")
    sys.stderr.flush()
    sys.exit(1)


USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
SEC_CH_UA = '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"'


def browser_headers(accept, referer, dest, mode, site, origin=None, content_type=None, navigation=False):
    """Builds a Chrome 120-like header set for one PKCE flow step (to match the TLS impersonation)."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": accept,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
    }
    if content_type:
        headers["Content-Type"] = content_type
    if origin:
        headers["Origin"] = origin
    headers["Referer"] = referer
    headers.update({
        "Sec-Ch-Ua": SEC_CH_UA,
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Linux"',
        "Sec-Fetch-Dest": dest,
        "Sec-Fetch-Mode": mode,
        "Sec-Fetch-Site": site,
    })
    if navigation:
        headers["Sec-Fetch-User"] = "?1"
        headers["Upgrade-Insecure-Requests"] = "1"
    return headers


def getpass_masked(prompt="[*] Enter Play Suisse Password: ", mask="*"):
    sys.stderr.write(prompt)
    sys.stderr.flush()
    password = []

    try:
        import msvcrt
        while True:
            ch = msvcrt.getch()
            if ch in (b'\r', b'\n'):
                sys.stderr.write('\n')
                sys.stderr.flush()
                break
            elif ch in (b'\x7f', b'\x08'):
                if password:
                    password.pop()
                    sys.stderr.write('\b \b')
                    sys.stderr.flush()
            elif ch == b'\x03':
                raise KeyboardInterrupt
            else:
                password.append(ch.decode('utf-8', errors='ignore'))
                sys.stderr.write(mask)
                sys.stderr.flush()
        return "".join(password)
    except ImportError:
        import termios
        import tty

        fd = sys.stdin.fileno()
        if not os.isatty(fd):
            import getpass
            return getpass.getpass(prompt="", stream=sys.stderr)

        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while True:
                ch = sys.stdin.read(1)
                if ch in ('\r', '\n'):
                    sys.stderr.write('\r\n')
                    sys.stderr.flush()
                    break
                elif ch in ('\x7f', '\x08'):
                    if password:
                        password.pop()
                        sys.stderr.write('\b \b')
                        sys.stderr.flush()
                elif ch == '\x03':
                    raise KeyboardInterrupt
                else:
                    password.append(ch)
                    sys.stderr.write(mask)
                    sys.stderr.flush()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return "".join(password)


def main():
    description = "Generate Play Suisse session tokens securely on a PC."
    epilog = """
Password Input Methods (to prevent shell-escaping issues with special characters):

  1. SECURE INTERACTIVE PROMPT (Recommended & 100% Shell-Immune):
     Omit --password and --password-file. The script will prompt you privately:
     ./gen_session.py --username="your_email@example.com" > session.json

  2. PASSWORD FILE (100% Shell-Immune):
     Write your password exactly as-is into a local file and pass its path:
     ./gen_session.py --username="your_email@example.com" --password-file="pass.txt" > session.json

  3. ENVIRONMENT VARIABLE (100% Shell-Immune):
     Export your password to PLAYSUISSE_PASSWORD before running:
     export PLAYSUISSE_PASSWORD="your_password"
     ./gen_session.py --username="your_email@example.com" > session.json

  4. SINGLE QUOTES:
     If passing on the command line, wrap it in single quotes to disable shell expansions:
     ./gen_session.py --username="your_email@example.com" --password='your_password' > session.json
"""
    parser = argparse.ArgumentParser(
        description=description,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--username", required=True, help="Play Suisse account email")
    parser.add_argument("--password", required=False, help="Play Suisse account password")
    parser.add_argument("--password-file", required=False, help="Path to a text file containing the password as-is")
    args = parser.parse_args()

    email = args.username
    password = None

    # Resolve password input with maximum robustness against shell escaping
    if args.password:
        password = args.password
    elif args.password_file:
        if not os.path.exists(args.password_file):
            error(f"Password file not found at: {args.password_file}")
        try:
            with open(args.password_file, "r", encoding="utf-8", errors="ignore") as f:
                password = f.read().rstrip("\r\n")
            log(f"Loaded password from file: {args.password_file}")
        except Exception as e:
            error(f"Failed to read password file: {e}")
    else:
        # Check environment variable
        env_pass = os.environ.get("PLAYSUISSE_PASSWORD")
        if env_pass:
            password = env_pass
            log("Loaded password from environment variable PLAYSUISSE_PASSWORD")
        else:
            # Secure interactive prompt fallback (completely immune to shell escaping!)
            # sys.stderr is used for the prompt so that your redirected stdout (> session.json) remains pristine!
            try:
                password = getpass_masked(prompt="[*] Enter Play Suisse Password (masked): ")
            except Exception as e:
                error(f"Failed to read password from secure prompt: {e}")

    if not password:
        error("Password is required. Provide it via --password, --password-file, PLAYSUISSE_PASSWORD env, or interactively.")

    log("Generating PKCE Challenge...")
    code_verifier = uuid.uuid4().hex + uuid.uuid4().hex + uuid.uuid4().hex
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode().rstrip('=')

    if curl_requests:
        log("Detected curl_cffi library! Using Chrome 120 impersonation to bypass Cloudflare...")
        session = curl_requests.Session(impersonate="chrome120")
    else:
        log("Using standard requests library...")
        session = requests.Session()

    # Step 1: Initial authz request
    log("Step 1: Contacting authorization server...")
    authz_url = f"{LOGIN_BASE}/authz-srv/authz"
    params = {
        'client_id': CLIENT_ID,
        'redirect_uri': 'https://www.playsuisse.ch/auth',
        'scope': 'email profile openid offline_access',
        'response_type': 'code',
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256',
        'view_type': 'login',
    }
    session.headers.clear()
    session.headers.update(browser_headers(
        accept="text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        referer="https://www.playsuisse.ch/",
        dest="document", mode="navigate", site="cross-site", navigation=True,
    ))
    res = session.get(authz_url, params=params, timeout=15)
    parsed_query = parse_qs(urlparse(res.url).query)
    request_id = parsed_query.get('requestId', [None])[0]
    if not request_id:
        error(f"Step 1 failed (AUTHZ_FAILED). Status: {res.status_code}")

    # Step 2: Submit username
    log("Step 2: Submitting username...")
    init_url = f"{LOGIN_BASE}/verification-srv/v2/authenticate/initiate/password"
    payload = {
        'usage_type': 'INITIAL_AUTHENTICATION',
        'request_id': request_id,
        'medium_id': 'PASSWORD',
        'type': 'password',
        'identifier': email,
    }
    session.headers.clear()
    session.headers.update(browser_headers(
        accept="application/json, text/plain, */*",
        referer=res.url,
        origin="https://account.srgssr.ch",
        content_type="application/json",
        dest="empty", mode="cors", site="same-origin",
    ))
    res = session.post(init_url, json=payload, timeout=15)
    res_json = res.json()
    exchange_id = res_json.get('data', {}).get('exchange_id', {}).get('exchange_id')
    if not exchange_id:
        error("Step 2 failed (USERNAME_INVALID). Please verify your email.")

    # Step 3: Submit password
    log("Step 3: Submitting password...")
    auth_url = f"{LOGIN_BASE}/verification-srv/v2/authenticate/authenticate/password"
    payload = {
        'requestId': request_id,
        'exchange_id': exchange_id,
        'type': 'password',
        'password': password,
    }
    session.headers.clear()
    session.headers.update(browser_headers(
        accept="application/json, text/plain, */*",
        referer=res.url,
        origin="https://account.srgssr.ch",
        content_type="application/json",
        dest="empty", mode="cors", site="same-origin",
    ))
    res = session.post(auth_url, json=payload, timeout=15)
    res_json = res.json()
    login_data = res_json.get('data')
    if not login_data:
        error("Step 3 failed (PASSWORD_INVALID). Please verify your password.")

    # Step 4: Finalize verification
    log("Step 4: Finalizing verification...")
    verify_url = f"{LOGIN_BASE}/login-srv/verification/login"
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
    session.headers.update(browser_headers(
        accept="text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        referer=res.url,
        origin="https://account.srgssr.ch",
        content_type="application/x-www-form-urlencoded",
        dest="document", mode="navigate", site="same-origin", navigation=True,
    ))
    res = session.post(verify_url, data=payload, timeout=15)
    parsed_query = parse_qs(urlparse(res.url).query)
    authorization_code = parsed_query.get('code', [None])[0]
    if not authorization_code:
        error("Step 4 failed (VERIFICATION_FAILED).")

    # Step 5: Trade auth code for tokens
    log("Step 5: Exchanging authorization code for tokens...")
    token_url = f"{LOGIN_BASE}/proxy/token"
    params = {
        'client_id': CLIENT_ID,
        'redirect_uri': 'https://www.playsuisse.ch/auth',
        'code': authorization_code,
        'code_verifier': code_verifier,
        'grant_type': 'authorization_code',
    }
    session.headers.clear()
    session.headers.update(browser_headers(
        accept="application/json, text/plain, */*",
        referer="https://www.playsuisse.ch/",
        origin="https://www.playsuisse.ch",
        dest="empty", mode="cors", site="cross-site",
    ))
    res = session.post(token_url, params=params, timeout=15)
    res_json = res.json()
    id_token = res_json.get('id_token')
    refresh_token = res_json.get('refresh_token')
    if not id_token:
        error("Step 5 failed (TOKEN_TRADE_FAILED).")

    # Step 6: Pre-fetch active profile_id
    log("Step 6: Fetching active profile ID...")
    profile_id = None
    try:
        graphql_url = "https://www.playsuisse.ch/api/graphql?complex_subs=true&stipo_env=production2&discontinuity=true"
        query_payload = [
            {
                "operationName": "AppConfig",
                "variables": {},
                "extensions": {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": "3cdb8a136dccdaee568e872c55c2d30578a919a3f02656b335bec80a88129d89"
                    }
                }
            },
            {
                "operationName": "UserProfileWithPreferencesAndUserInfo",
                "variables": {},
                "extensions": {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": "93b24b6d887b532304d2fbc6a422b52092d853edf17cf33488ccf0218f8c6e3c"
                    }
                }
            }
        ]
        headers = {
            "Authorization": f"Bearer {id_token}",
            "Content-Type": "application/json",
            "x-playsuisse-app": "id=web&version=1.1.27",
            "x-playsuisse-locale": "fr"
        }
        graphql_res = session.post(graphql_url, json=query_payload, headers=headers, timeout=15)
        if graphql_res.status_code == 200:
            res_data = graphql_res.json()
            if res_data and isinstance(res_data, list) and len(res_data) > 1:
                profile_data = res_data[1].get("data", {}).get("userProfile", {})
                profile_id = profile_data.get("profileId")
                if profile_id:
                    log(f"Active profile ID pre-fetched: {profile_id}")
    except Exception as e:
        log(f"Warning: Could not pre-fetch profile ID: {e}")

    # Output clean JSON to stdout for piping
    output_data = {
        "id_token": id_token,
        "refresh_token": refresh_token,
        "timestamp": time.time()
    }
    if profile_id:
        output_data["profile_id"] = profile_id

    sys.stdout.write(json.dumps(output_data, indent=2) + "\n")
    sys.stdout.flush()
    log("Session generation successful!")


if __name__ == "__main__":
    main()
