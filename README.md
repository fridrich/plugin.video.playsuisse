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

### Method B: Non-Interactive Setup (Samba / SSH / Headless)
If typing a complex password using a standard television remote control is too cumbersome, you can use our secure non-interactive setup:
1. Create a plain-text file named **`credentials.json`** on your computer.
2. Populate the file with your login credentials in the following JSON format:
   ```json
   {
     "email": "your_email@example.com",
     "password": "your_secure_password"
   }
   ```
3. Copy this file into your Kodi profile userdata directory:
   * **Linux:** `~/.kodi/userdata/addon_data/plugin.video.playsuisse/credentials.json`
   * **CoreELEC / LibreELEC:** `/storage/.kodi/userdata/addon_data/plugin.video.playsuisse/credentials.json`
   * **Android:** `/sdcard/Android/data/org.xbmc.kodi/files/.kodi/userdata/addon_data/plugin.video.playsuisse/credentials.json`
4. Launch any video or click "Authenticate" inside Play Suisse. 
5. The add-on instantly reads `credentials.json`, authenticates with SRG SSR, generates your secure session tokens, and **immediately deletes the plaintext `credentials.json` file from your disk**.

### Method C: Session Transfer (Workaround for Cloudflare Blocks on Raspberry Pi / OSMC)
If you are running Kodi on a device with an older Python/OpenSSL stack (such as **OSMC on a Raspberry Pi**), Cloudflare may protect the login portal with a `"Just a moment..."` browser challenge and block direct connection handshakes with a **403 Forbidden** error. 

Because we use standard **OAuth2 Refresh Tokens**, you can easily bypass this security check by generating the session on your PC and copying it over:
1. Install and log in to the Play Suisse add-on on your **PC / Laptop** (where standard browser-level TLS fingerprints are accepted).
2. Locate the generated **`session.json`** file inside your PC's userdata folder:
   * **Windows:** `%APPDATA%\Kodi\userdata\addon_data\plugin.video.playsuisse\session.json`
   * **macOS:** `~/Library/Application Support/Kodi/userdata/addon_data/plugin.video.playsuisse/session.json`
   * **Linux:** `~/.kodi/userdata/addon_data/plugin.video.playsuisse/session.json`
3. Copy this **`session.json`** file directly into your Raspberry Pi's profile userdata folder (under `addon_data/plugin.video.playsuisse/`).
4. **Result:** The add-on on your Raspberry Pi will immediately load and validate the session tokens, allowing you to stream seamlessly without ever needing to perform the blocked login handshake on the Pi itself!

---

## 📜 License

This project is licensed under the **GNU General Public License v3.0 (GPL-3.0)**. See the `LICENSE` file for more details.
