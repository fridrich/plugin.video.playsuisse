# Unofficial Play+Suisse Kodi Addon

An unofficial, third-party Kodi add-on to browse and stream content from **Play+Suisse**, the streaming platform of the Swiss Broadcasting Corporation (SRG SSR).

---

## ⚠️ Important Legal Disclaimer

**This add-on is NOT official, NOT endorsed, and NOT affiliated in any way with SRG SSR, Play+Suisse, or any of their partners.**

* **No Affiliation:** This is a community-developed, open-source project created solely for personal convenience and educational purposes. All product names, logos, trademarks, and brands are the property of their respective owners.
* **DRM & Geo-Blocking Compliance:** This add-on **does not bypass, disable, or circumvent** any Digital Rights Management (DRM) protections, geo-blocking, or content restrictions. It does not provide unauthorized access to any media. To stream any content, users must log in using their own legitimate, verified **Play+Suisse account** and satisfy the platform's geographical geolocation/residency requirements. The account must be officially verified as a Swiss resident; streaming in the European Union (EU) is strictly a temporary portability arrangement for verified Swiss residents traveling abroad, not a method to bypass residency (playback is natively restricted to Switzerland if unauthenticated).
* **Official Flow Integration:** Authentication is handled by executing the official, multi-step standard OAuth2 PKCE login handshake in pure Python directly with SRG SSR account servers (`account.srgssr.ch`), exactly like the official mobile and web clients.
* **No Content Hosting:** This add-on does not host, store, mirror, or distribute any media files, video streams, audio, or subtitles. It is a client-side parser that reads publicly accessible GraphQL metadata and links directly to official SRG SSR CDNs.
* **Non-Commercial:** This project is strictly non-commercial and free. It does not contain ads, trackers, monetization, or donation links.
* **Limitation of Liability:** Under the terms of the GNU General Public License v3.0, this program is distributed in the hope that it will be useful, but **WITHOUT ANY WARRANTY**; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. Use of this add-on is entirely at your own risk. The authors assume no liability for account suspensions, technical issues, or service interruptions.

---

## 🚀 Key Features

* **High-Fidelity Layout:** Access the complete catalog exactly like the official web portal (Home, Fiction, Documentaries, Categories, and Search).
* **Secure Login:** Plaintext passwords are discarded immediately. The add-on only caches standard OAuth2 session tokens on your device.
* **Auto Audio & Subtitles:** Set your preferred languages in the settings. The add-on automatically selects matching tracks and intelligently skips short intro logos to apply your preferences directly to the main feature.

---

## ⚙️ Installation & Setup

### Option A: Standard Login (Recommended)
1. Install the add-on ZIP package in Kodi.
2. Open the add-on settings (**Configure**).
3. On the **General** tab, select **Authenticate / Log in**.
4. Enter your Play+Suisse **Email** and **Password** when prompted.

### Option B: Offline Session Transfer
If typing on a TV screen is difficult, you can generate your session securely on a PC and copy it:
1. Run the helper script on any PC with Python 3:
   ```bash
   python3 gen_session.py --username="your_email@example.com" > session.json
   ```
2. Copy the generated `session.json` to your Kodi device's addon userdata directory:
   * **Linux:** `~/.kodi/userdata/addon_data/plugin.video.playsuisse/session.json`
   * **CoreELEC / LibreELEC:** `/storage/.kodi/userdata/addon_data/plugin.video.playsuisse/session.json`
   * **Android:** `/sdcard/Android/data/org.xbmc.kodi/files/.kodi/userdata/addon_data/plugin.video.playsuisse/session.json`

---

## ⚡ Troubleshooting (Cloudflare / 403 Forbidden)

If you are using an older OS/Python environment (such as **OSMC on a Raspberry Pi**) and encounter a **403 Forbidden** error or Cloudflare challenge during login, you can resolve this by installing `curl_cffi` on your device:

```bash
pip3 install "curl_cffi<=0.13.0" --extra-index-url https://bjia56.github.io/armv7l-wheels/
```

Once installed, the add-on will automatically use it to bypass the browser challenge.

---

## 📜 License

This project is licensed under the **GNU General Public License v3.0 (GPL-3.0)**. See the `LICENSE` file for more details.
