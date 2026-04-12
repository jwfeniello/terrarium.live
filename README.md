<img width="1280" height="720" alt="New Project (10)" src="https://github.com/user-attachments/assets/8e00ef7f-e4c1-4f7a-a6da-c89f2ed57acc" />


A tool for recording and watching [fishtank.live](https://fishtank.live) streams locally.

> **You need your own Fishtank account with a valid Season Pass. This does not bypass any paywalls.**

---
<sub><sup>If anyone on the ft team has issues with this, just email me and we can get it figured out. jwfeniello@gmail.com</sup></sub> 

## What it does

- Record any camera (or all of them at once) to disk in 6-hour chunks
- Self-host a local web viewer — works in any browser, smart TV, or IPTV app
- Generate an M3U playlist you can load into VLC, Plex, or anything that supports it
- Tokens refresh automatically so recordings don't stop after 30 minutes
- Built-in live chat in the web viewer, interfacing with the official site
---

## Requirements

- Python 3.10+
- curl-cffi
- msgpack
- [ffmpeg](https://ffmpeg.org/download.html) in your PATH
- A Fishtank account with Season Pass

```bash
pip install requests curl-cffi msgpack
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

When running in mode 1 or 3, open the URL printed in the terminal in any browser on your network. The server binds to your local IP, so it works on any device on the same network.

Thumbnails update every 10 seconds, and clicking a camera opens it fullscreen.

Arrow keys switch between cameras
ESC closes the player

The web viewer includes live chat synced with the official site.

Multi-cam mode — select up to 4 cameras for a split-screen view, click any cell to switch audio

The same URL can also be used as an IPTV source in smart TVs, Plex, TiviMate, etc (video only, no chat).



---

## Notes

- Recordings are saved as `.ts` files and split into chunks (default 6 hours)
- If a camera goes offline, the watchdog will restart it automatically when it comes back
- Credentials are stored in `~/.terrarium_session` as plain text





## Screenshots

<img width="1902" height="851" alt="image" src="https://github.com/user-attachments/assets/5c61f8aa-e489-42c6-823f-67f406fd09f1" />
<img width="1913" height="870" alt="s" src="https://github.com/user-attachments/assets/026364e4-501b-4d09-8fa3-0f0a2095efc0" />


