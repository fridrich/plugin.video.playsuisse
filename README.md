# Unofficial Play Suisse Kodi Addon

An unofficial third-party Kodi add-on for browsing and streaming content from **Play Suisse**, the streaming platform of the Swiss Broadcasting Corporation (SRG SSR).

---

## ⚠️ Important Legal Disclaimer

**This add-on is NOT official, NOT endorsed, and NOT affiliated in any way with SRG SSR, Play Suisse, or any of their partners.**

* **No Affiliation:** This is a community-developed, open-source project created solely for personal convenience and educational purposes. All product names, logos, trademarks, and brands are the property of their respective owners.
* **DRM & Geo-Blocking Compliance:** This add-on **does not bypass, disable, or circumvent** any Digital Rights Management (DRM) protections, geo-blocking, or content restrictions. It does not provide unauthorized access to any media. To stream any content, users must log in using their own legitimate, verified **Play Suisse account** and satisfy the platform's geographical geolocation/residency requirements. The account must be officially verified as a Swiss resident; streaming in the European Union (EU) is strictly a temporary portability arrangement for verified Swiss residents traveling abroad, not a method to bypass residency (playback is natively restricted to Switzerland if unauthenticated).
* **Official Flow Integration:** Authentication is handled by executing the official, multi-step standard OAuth2 PKCE login handshake in pure Python directly with SRG SSR account servers (`account.srgssr.ch`), exactly like the official mobile and web clients.
* **No Content Hosting:** This add-on does not host, store, mirror, or distribute any media files, video streams, audio, or subtitles. It is a client-side parser that reads publicly accessible GraphQL metadata and links directly to official SRG SSR CDNs.
* **Non-Commercial:** This project is strictly non-commercial and free. It does not contain ads, trackers, monetization, or donation links.
* **Limitation of Liability:** Under the terms of the GNU General Public License v3.0, this program is distributed in the hope that it will be useful, but **WITHOUT ANY WARRANTY**; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. Use of this add-on is entirely at your own risk. The authors assume no liability for account suspensions, technical issues, or service interruptions.

---

## 🚀 Key Features

* **High-Fidelity Web Layout:** Mirroring the navigation, sections, and catalog structure of the official `www.playsuisse.ch` web portal (Highlights/Home, Fiction, Documentaries, Categories, and Search).
* **Modern OAuth2 Session Cache (Secure):** After initial authentication, plain-text passwords are **immediately discarded and never stored** on your disk. Instead, the add-on securely caches standard OAuth2 `id_token` and `refresh_token` payloads to maintain your login session.
* **Asynchronous Playback Monitor:** Configures your language preferences instantly in the background, ensuring **zero-delay, instant video startup** (unlike older blocking plugins).
* **Smart Intro/Logo Skipping:** Automatically identifies and skips short preceding intro logos (e.g., `< 25` seconds) so that your preferred audio and subtitle settings are only applied to the main video.
* **Original Audio Tagging:** Uses Kodi’s native `inputstream.adaptive` properties to automatically append a `(original)` tag to the stream's original language track.
* **Granular Video, Audio & Subtitle Settings:**
  * **Video:** Toggle preferred HD quality.
  * **Audio:** Choose your preferred language (Auto, French, German, Italian, Romansh). Choosing `Auto` automatically selects the video's original language. Tracks matching your selection are chosen first, falling back smoothly to the original language if unavailable, while actively avoiding silent commentary or descriptive audio (AD) streams.
  * **Subtitles:** Choose your preferred language (Off, French, German, Italian, Romansh).

---

## ⚙️ Setup and Installation

### Method A: Graphical Authentication (Standard)
1. Install the add-on zip package on your Kodi device.
2. Open the add-on settings screen (right-click or long-press on the add-on icon -> **Configure**).
3. On the **General** tab, select **"Authenticate / Log in"**.
4. Enter your Play Suisse **Email** and **Password** in the on-screen keyboards.
5. The add-on completes the PKCE handshake, creates your secure tokens, and immediately clears your password from the screen and settings.

### Method B: Session Transfer (Non-Interactive Setup / PC Generation)
If typing a complex password using a standard television remote control is too cumbersome, or if you do not want to install any packages on your Kodi device, you can generate your session on a regular computer instead and copy it over. This never writes your plaintext password to the Kodi device at all.

1. On any PC with **Python 3** and the `requests` library installed (`pip install requests`), run the included `gen_session.py` script from this repository:
   ```
   python3 gen_session.py --username="your_email@example.com" > session.json
   ```
   You will be prompted for your password securely (masked input, never echoed or stored in your shell history). See the script's `--help` for alternative password input methods (password file or environment variable) if you prefer to avoid the interactive prompt.
2. Copy the resulting **`session.json`** file into your Kodi device's profile userdata directory:
   * **Linux:** `~/.kodi/userdata/addon_data/plugin.video.playsuisse/session.json`
   * **CoreELEC / LibreELEC:** `/storage/.kodi/userdata/addon_data/plugin.video.playsuisse/session.json`
   * **Android:** `/sdcard/Android/data/org.xbmc.kodi/files/.kodi/userdata/addon_data/plugin.video.playsuisse/session.json`
3. **Result:** The add-on will immediately load and validate the session tokens, allowing you to stream seamlessly without ever needing to type your password on the device or perform the login handshake there.

### ⚡ Bypassing Cloudflare Blocks on OSMC / Raspberry Pi (Direct Kodi Login!)
If you are running Kodi on a device with an older Python/OpenSSL stack (such as **OSMC on a Raspberry Pi**) where Cloudflare protects the login portal with a `"Just a moment..."` browser challenge and blocks standard connection handshakes with a **403 Forbidden** error, you can enable direct graphical login (Method A) and direct CLI execution right on the device by installing **`curl_cffi`**.

`curl_cffi` mimics modern browser TLS/JA3 handshakes perfectly, which allows both the graphical Kodi addon login and the local `gen_session.py` script to bypass Cloudflare.

To install `curl_cffi` on OSMC (ARMv7l) running Python 3.9:

```bash
pip3 install "curl_cffi<=0.13.0" --extra-index-url https://bjia56.github.io/armv7l-wheels/
```

Once `curl_cffi` is installed, direct login in Kodi (Method A) and executing `python3 gen_session.py` directly on the Raspberry Pi will work seamlessly.

---

## 📜 License

This project is licensed under the **GNU General Public License v3.0 (GPL-3.0)**. See the `LICENSE` file for more details.
