# Terrarium

A tool for recording and watching [Fishtank LIVE](https://fishtank.live) streams locally.

> **You need your own Fishtank account with a valid Season Pass. This does not bypass any paywalls.**

---

## What it does

- Record any camera (or all of them at once) to disk in 6-hour chunks
- Self-host a local web viewer — works in any browser, smart TV, or IPTV app
- Generate an M3U playlist you can load into VLC, Plex, or anything that supports it
- Tokens refresh automatically so recordings don't stop after 30 minutes

---

## Requirements

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/download.html) in your PATH
- A Fishtank account with Season Pass

```bash
pip install requests
```

---

## Usage

```bash
python terrarium.py
```

On first run it asks for your Fishtank email and password, then saves them so you don't have to type them again. From there you pick a mode:

| Mode | What it does |
|------|-------------|
| 1 | Self-hosted web viewer + M3U playlist, no recording |
| 2 | Record to disk, no web viewer |
| 3 | Both |

You can record all cameras at once or pick specific ones by number.

---

## Web viewer

When running in mode 1 or 3, open the URL printed in the terminal in any browser on your network. Thumbnails update every 10 seconds and clicking a camera opens it fullscreen. Arrow keys switch between cameras.

The same URL works as an IPTV source on smart TVs, Plex, TiviMate, etc.

---

## Notes

- Recordings are saved as `.ts` files and split into chunks (default 6 hours)
- If a camera goes offline, the watchdog will restart it automatically when it comes back
- Credentials are stored in `~/.terrarium_session` as plain text
