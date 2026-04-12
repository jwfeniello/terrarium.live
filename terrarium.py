#!/usr/bin/env python3
"""
Terrarium — Fishtank LIVE Tool
Requires: pip install requests curl-cffi msgpack  |  ffmpeg in PATH
"""

import os, sys, time, subprocess, requests, urllib.parse, json, getpass
import threading, socket, queue
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

try:
    from curl_cffi import requests as cf_requests
    from curl_cffi import CurlWsFlag
    import msgpack
    HAS_WS = True
except ImportError:
    HAS_WS = False

# ═══════════════════════════════════════════════════════════════════
# CAMERAS
# ═══════════════════════════════════════════════════════════════════

CAMERAS = {
    "1":  ("Director",     "dirc"),
    "2":  ("Dorm",         "dmrm"),
    "3":  ("Closet",       "dmcl"),
    "4":  ("Bar",          "brrr"),
    "5":  ("Kitchen",      "ktch"),
    "6":  ("Hallway",      "hwdn"),
    "7":  ("Laundry",      "jckz"),
    "8":  ("Bar PTZ",      "brpz"),
    "9":  ("Dining Room",  "dnrm"),
    "10": ("Market",       "mrke"),
    "11": ("Foyer",        "foyr"),
    "12": ("Glassroom",    "gsrm"),
    "13": ("Computer Lab", "bbcl"),
    "14": ("Arena",        "bare"),
    "15": ("Confessional", "cfsl"),
    "16": ("Corridor",     "codr"),
    "17": ("West Wing",    "hwup"),
    "18": ("East Wing",    "bkny"),
    "19": ("Jungle Room",  "br4j"),
}

SEASON       = 5
SERVERS      = list("abcdefghi")
SESSION_FILE = os.path.join(os.path.expanduser("~"), ".terrarium_session")
CHAT_ROOMS   = ["Global", "Season Pass"]

# Base64-encoded JPEG thumbnail for offline/broken cameras
# Generate: ffmpeg -i broken.png -vf scale=320:180 -q:v 8 broken_thumb.jpg
# Then: certutil -encode broken_thumb.jpg tmp.txt
# Paste the base64 content below (line breaks are fine):
OFFLINE_THUMB_B64 = """
"""
import base64 as _b64
OFFLINE_THUMB = _b64.b64decode(OFFLINE_THUMB_B64.replace("\n", "").strip()) if OFFLINE_THUMB_B64.strip() else None

# ═══════════════════════════════════════════════════════════════════

LOGO = (
    "\n"
    "  _______                            __                \n"
    " |       .-----.----.----.---.-.----|__.--.--.--------.\n"
    " |.|   | |  -__|   _|   _|  _  |   _|  |  |  |        |\n"
    " `-|.  |-|_____|__| |__| |___._|__| |__|_____|__|__|__|\n"
    "   |:  |                                               \n"
    "   |::.|           a fishtank.live tool                \n"
    "   `---'                                               \n"
)

HEADERS = {
    "accept":       "application/json, text/plain, */*",
    "content-type": "application/json",
    "origin":       "https://www.fishtank.live",
    "referer":      "https://www.fishtank.live/",
    "user-agent":   "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
}

session           = requests.Session()
session.headers.update(HEADERS)
access_token      = None
refresh_token_val = None
live_stream_token = None
user_email        = None
user_password     = None
user_display_name = None
stop_event        = threading.Event()
processes         = {}


def ts():
    return datetime.now().strftime("%H:%M:%S")


def divider(char="═", width=52):
    print(char * width)


def print_header():
    print(LOGO)
    divider()
    print("  Terrarium — Fishtank LIVE Tool")
    divider()
    print()


# ── Credentials ───────────────────────────────────────────────────

def save_credentials(email, password):
    try:
        with open(SESSION_FILE, "w") as f:
            json.dump({"email": email, "password": password}, f)
    except Exception:
        pass


def load_credentials():
    try:
        with open(SESSION_FILE) as f:
            data = json.load(f)
            return data.get("email"), data.get("password")
    except Exception:
        return None, None


def clear_credentials():
    try:
        os.remove(SESSION_FILE)
    except Exception:
        pass


# ── Auth ──────────────────────────────────────────────────────────

def login(email, password):
    global access_token, refresh_token_val, live_stream_token, user_display_name
    resp = session.post(
        "https://api.fishtank.live/v1/auth/log-in",
        json={"email": email, "password": password},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    s = data["session"]
    access_token      = s["access_token"]
    refresh_token_val = s["refresh_token"]
    live_stream_token = s["live_stream_token"]
    session.headers["authorization"] = f"Bearer {access_token}"
    user_display_name = data.get("user", {}).get("displayName")
    if not user_display_name:
        try:
            uid = data.get("user", {}).get("id") or s.get("user_id")
            if uid:
                pr = session.get(f"https://api.fishtank.live/v1/profile/{uid}", timeout=10)
                if pr.ok:
                    user_display_name = pr.json().get("displayName")
        except Exception:
            pass
    if user_display_name:
        print(f"  OK  Logged in as {user_display_name} ({email})")
    else:
        print(f"  OK  Logged in as {email}")


def refresh_tokens():
    global access_token, refresh_token_val, live_stream_token
    try:
        resp = session.post(
            "https://api.fishtank.live/v1/auth/refresh",
            json={"refresh_token": refresh_token_val},
            timeout=15,
        )
        resp.raise_for_status()
        s = resp.json()["session"]
        access_token      = s["access_token"]
        refresh_token_val = s["refresh_token"]
        live_stream_token = s["live_stream_token"]
        session.headers["authorization"] = f"Bearer {access_token}"
        print(f"[{ts()}] Tokens refreshed OK")
    except Exception:
        print(f"[{ts()}] Refresh failed — re-logging in...")
        login(user_email, user_password)


# ── Stream URL ────────────────────────────────────────────────────

def get_stream_url(cam_code):
    result = [None]
    found  = threading.Event()

    def try_server(letter):
        if found.is_set():
            return
        url = (
            f"https://streams-{letter}.fishtank.live"
            f"/hls/live+{cam_code}-{SEASON}/index.m3u8"
            f"?jwt={live_stream_token}&video=maxbps"
        )
        try:
            r = requests.head(url, timeout=3)
            if r.status_code == 200 and not found.is_set():
                result[0] = url
                found.set()
        except requests.RequestException:
            pass

    threads = [threading.Thread(target=try_server, args=(l,), daemon=True) for l in SERVERS]
    for t in threads:
        t.start()
    found.wait(timeout=5)
    return result[0]


# ── Cache ─────────────────────────────────────────────────────────

snap_cache = {}
snap_failed = set()
url_cache  = {}
cache_lock = threading.Lock()


def warm_cache(selected_cams):
    def _warm():
        for name, cam_code in selected_cams:
            url = get_stream_url(cam_code)
            if url:
                with cache_lock:
                    url_cache[cam_code] = url
        for name, cam_code in selected_cams:
            _refresh_snap(name, cam_code)
    threading.Thread(target=_warm, daemon=True).start()


def _refresh_snap(name, cam_code):
    with cache_lock:
        url = url_cache.get(cam_code)
    if not url:
        url = get_stream_url(cam_code)
        if not url:
            with cache_lock:
                snap_failed.add(name)
            return
        with cache_lock:
            url_cache[cam_code] = url
    try:
        cmd = ["ffmpeg", "-y", "-i", url, "-vframes", "1",
               "-f", "image2", "-vcodec", "mjpeg", "pipe:1"]
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        if result.returncode == 0 and result.stdout:
            with cache_lock:
                snap_cache[name] = result.stdout
                snap_failed.discard(name)
        else:
            with cache_lock:
                snap_failed.add(name)
    except Exception:
        with cache_lock:
            snap_failed.add(name)


def snap_refresh_loop(selected_cams):
    while not stop_event.is_set():
        for name, cam_code in selected_cams:
            if stop_event.is_set():
                break
            _refresh_snap(name, cam_code)
        stop_event.wait(10)


def get_cached_stream_url(cam_code):
    with cache_lock:
        url = url_cache.get(cam_code)
    if url:
        return url
    url = get_stream_url(cam_code)
    if url:
        with cache_lock:
            url_cache[cam_code] = url
    return url


# ── Chat ──────────────────────────────────────────────────────────

chat_messages     = []
chat_lock         = threading.Lock()
chat_seen_ids     = set()
chat_counter      = 0
MAX_MESSAGES      = 500
chat_sockets      = {}
chat_sockets_lock = threading.Lock()


def _pack_sio(type_id, data):
    return msgpack.packb(
        {"type": type_id, "data": data, "nsp": "/"},
        use_bin_type=True,
    )


def _handle_binary(data, ws, room_name=None):
    """Decode msgpack binary frame(s) and process them."""
    for skip in range(min(4, len(data))):
        try:
            unpacker = msgpack.Unpacker(raw=False, strict_map_key=False)
            unpacker.feed(data[skip:])
            decoded_any = False
            for m in unpacker:
                if isinstance(m, dict) and "type" in m:
                    decoded_any = True
                    _process_sio_packet(m, ws, room_name)
                elif isinstance(m, list) and len(m) > 0 and isinstance(m[0], dict) and "type" in m[0]:
                    decoded_any = True
                    _process_sio_packet(m[0], ws, room_name)
            if decoded_any:
                return
        except Exception:
            continue
    preview = data[:60].hex() if data else "(empty)"
    print(f"  [WS] undecoded frame ({len(data)}b): {preview}")


def _process_sio_packet(m, ws, room_name):
    """Handle a single decoded Socket.IO packet."""
    global chat_counter
    typ     = m.get("type")
    payload = m.get("data")

    if typ == 0 and isinstance(payload, dict):
        sid = payload.get("sid")
        pid = payload.get("pid")
        if sid and pid:
            tag = f" [{room_name}]" if room_name else ""
            print(f"  [WS]{tag} authenticated (sid={sid[:8]}…)")
            if room_name and room_name != "Global":
                ws.send(_pack_sio(2, ["chat:room", room_name]), CurlWsFlag.BINARY)
                print(f"  [WS]{tag} subscribed to room")

    elif typ == 2 and isinstance(payload, list) and len(payload) >= 2:
        event      = payload[0]
        event_data = payload[1]
        msgs = event_data if isinstance(event_data, list) else [event_data]

        if event == "chat:message":
            for p in msgs:
                if not isinstance(p, dict):
                    continue
                user = p.get("user", {})
                cm = {
                    "id":       str(p.get("id", "")),
                    "text":     str(p.get("message", "")),
                    "username": str(user.get("displayName", "unknown")),
                    "color":    str(user.get("customUsernameColor") or "#ffffff"),
                    "isAdmin":  bool(p.get("admin", False)),
                    "isMod":    bool((p.get("metadata") or {}).get("isMod", False)),
                    "room":     room_name or "Global",
                    "type":     "chat",
                }
                if cm["text"]:
                    with chat_lock:
                        if cm["id"] not in chat_seen_ids:
                            chat_seen_ids.add(cm["id"])
                            chat_counter += 1
                            cm["_seq"] = chat_counter
                            chat_messages.append(cm)
                            if len(chat_messages) > MAX_MESSAGES:
                                removed = chat_messages.pop(0)
                                chat_seen_ids.discard(removed["id"])

        elif event in ("tts:insert", "tts:update"):
            for p in msgs:
                if not isinstance(p, dict):
                    continue
                tts_id = str(p.get("id", ""))
                cm = {
                    "id":       f"tts-{tts_id}",
                    "text":     str(p.get("message", "")),
                    "username": str(p.get("displayName", "unknown")),
                    "color":    "#ffaa00",
                    "isAdmin":  False,
                    "isMod":    False,
                    "room":     room_name or "Global",
                    "type":     "tts",
                    "voice":    str(p.get("voice", "")),
                    "ttsRoom":  str(p.get("room", "")),
                }
                if cm["text"]:
                    with chat_lock:
                        if cm["id"] not in chat_seen_ids:
                            chat_seen_ids.add(cm["id"])
                            chat_counter += 1
                            cm["_seq"] = chat_counter
                            chat_messages.append(cm)
                            if len(chat_messages) > MAX_MESSAGES:
                                removed = chat_messages.pop(0)
                                chat_seen_ids.discard(removed["id"])


def chat_connect(bearer, room_name=None):
    """Connect to Fishtank chat via curl-cffi with recv() in a queue thread."""
    ws_url = "wss://ws.fishtank.live/socket.io/?EIO=4&transport=websocket"
    tag = f" [{room_name}]" if room_name else ""

    sess = cf_requests.Session(impersonate="chrome120")
    ws = sess.ws_connect(
        ws_url,
        headers={
            "Origin": "https://classic.fishtank.live",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        },
        timeout=30,
    )
    print(f"  [WS]{tag} connected")

    with chat_sockets_lock:
        chat_sockets[room_name or "Global"] = ws

    recv_q = queue.Queue()

    def _recv_loop():
        try:
            while True:
                d, f = ws.recv()
                recv_q.put((d, f))
        except Exception as exc:
            recv_q.put(exc)

    threading.Thread(target=_recv_loop, daemon=True).start()

    last_recv = time.time()

    while not stop_event.is_set():
        try:
            item = recv_q.get(timeout=2)
        except queue.Empty:
            if time.time() - last_recv > 10:
                print(f"  [WS]{tag} heartbeat timeout, reconnecting")
                try:
                    ws.close()
                except Exception:
                    pass
                return
            continue

        if isinstance(item, Exception):
            print(f"  [WS]{tag} recv error: {item}")
            break

        data, flags = item
        last_recv = time.time()

        is_text   = (flags & CurlWsFlag.TEXT) != 0
        is_binary = (flags & CurlWsFlag.BINARY) != 0

        if is_text:
            text = data.decode("utf-8") if isinstance(data, bytes) else data
            if text.startswith("0"):
                print(f"  [WS]{tag} handshake, authenticating...")
                ws.send(_pack_sio(0, {"token": bearer}), CurlWsFlag.BINARY)
            elif text == "2":
                ws.send(b"3", CurlWsFlag.TEXT)
            continue

        if is_binary and data:
            _handle_binary(data, ws, room_name)


def start_chat(bearer):
    if not HAS_WS:
        print("  ! Chat disabled — run: pip install curl-cffi msgpack")
        return

    for room in CHAT_ROOMS:
        def _loop(r=room):
            while not stop_event.is_set():
                try:
                    chat_connect(bearer, room_name=r)
                except Exception as e:
                    print(f"  [WS] [{r}] error: {e}")
                with chat_sockets_lock:
                    chat_sockets.pop(r, None)
                if not stop_event.is_set():
                    print(f"  [WS] [{r}] disconnected, retrying in 5s...")
                    stop_event.wait(5)

        threading.Thread(target=_loop, daemon=True).start()

    print(f"  ✓ Chat connecting ({', '.join(CHAT_ROOMS)})...")


def send_chat_message(text, room="Global"):
    """Send a chat message through the appropriate websocket."""
    with chat_sockets_lock:
        ws = chat_sockets.get(room)
    if not ws:
        print(f"  [WS] no socket for room: {room}")
        return False
    try:
        ws.send(_pack_sio(2, ["chat:message", {"message": text}]), CurlWsFlag.BINARY)
        return True
    except Exception as e:
        print(f"  [WS] send error: {e}")
        return False


# ── Recording ─────────────────────────────────────────────────────

def start_recording(name, cam_code, save_dir, chunk_hours):
    os.makedirs(save_dir, exist_ok=True)
    url = get_stream_url(cam_code)
    if not url:
        print(f"  ✗ {name} — offline/unreachable")
        return None
    pattern  = os.path.join(save_dir, f"{name}_%Y-%m-%d_%H-%M-%S.ts")
    log_path = os.path.join(save_dir, f"{name}.log")
    cmd = [
        "ffmpeg", "-y",
        "-reconnect",          "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max","30",
        "-rw_timeout",         "15000000",
        "-i",                  url,
        "-c",                  "copy",
        "-f",                  "segment",
        "-segment_time",       str(chunk_hours * 3600),
        "-reset_timestamps",   "1",
        "-strftime",           "1",
        pattern,
    ]
    log_file = open(log_path, "w")
    proc = subprocess.Popen(cmd, stdout=log_file, stderr=log_file)
    print(f"  ✓ {name} -> {save_dir}  (log: {name}.log)")
    return proc


def stop_recording(name):
    proc = processes.pop(name, None)
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


def restart_recordings(selected_cams, save_dir, chunk_hours):
    print(f"[{ts()}] Restarting recordings...")
    for name, cam_code in selected_cams:
        stop_recording(name)
        proc = start_recording(name, cam_code, save_dir, chunk_hours)
        if proc:
            processes[name] = proc


def watchdog(selected_cams, save_dir, chunk_hours):
    while not stop_event.is_set():
        stop_event.wait(30)
        for name, cam_code in selected_cams:
            proc = processes.get(name)
            if proc and proc.poll() is not None:
                print(f"[{ts()}] [{name}] crashed — restarting")
                proc = start_recording(name, cam_code, save_dir, chunk_hours)
                if proc:
                    processes[name] = proc


def token_refresh_loop(selected_cams, save_dir, chunk_hours, do_record):
    while not stop_event.is_set():
        stop_event.wait(25 * 60)
        if stop_event.is_set():
            break
        try:
            refresh_tokens()
            with cache_lock:
                url_cache.clear()
            if do_record:
                restart_recordings(selected_cams, save_dir, chunk_hours)
        except Exception as e:
            print(f"[{ts()}] Token refresh error: {e}")


# ── Network ───────────────────────────────────────────────────────

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ── Web viewer ────────────────────────────────────────────────────

def build_site(selected_cams, port):
    ip = get_local_ip()
    cam_list = [
        {
            "name":   name,
            "stream": f"http://{ip}:{port}/cam/{urllib.parse.quote(name)}",
            "snap":   f"http://{ip}:{port}/snap/{urllib.parse.quote(name)}",
        }
        for name, _ in selected_cams
    ]
    cam_json = json.dumps(cam_list)

    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Terrarium — Fishtank LIVE</title>
<script src="https://cdn.jsdelivr.net/npm/hls.js@1.4.12/dist/hls.min.js"></script>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: #0a0a0c;
  color: #e0e0e0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 18px;
  background: #111114;
  border-bottom: 1px solid #222;
  flex-shrink: 0;
}
header h1 { font-size: 16px; font-weight: 700; }
header .sub { font-size: 11px; color: #555; }
header .count { font-size: 12px; color: #555; margin-left: auto; }
#main { display: flex; flex: 1; overflow: hidden; }
#content { flex: 1; overflow-y: auto; }
#grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 10px;
  padding: 14px;
}
.cam-card {
  background: #111114;
  border: 1px solid #1e1e22;
  border-radius: 10px;
  overflow: hidden;
  cursor: pointer;
  transition: border-color 0.15s, transform 0.15s;
  position: relative;
}
.cam-card:hover { border-color: #5865f2; transform: scale(1.015); }
.cam-card:has(.dot.off) img { filter: brightness(0.35) grayscale(0.4); }
.cam-card:has(.dot.off) .cam-label { opacity: 0.45; }
.cam-card img {
  width: 100%;
  aspect-ratio: 16/9;
  background: #0a0a0c;
  display: block;
  object-fit: cover;
}
.cam-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 600;
}
.dot { width: 8px; height: 8px; border-radius: 50%; background: #22c55e; }
.dot.off { background: #333; }
#chat-sidebar {
  width: 290px;
  flex-shrink: 0;
  background: #0e0e10;
  border-left: 1px solid #1e1e22;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
#chat-head {
  padding: 0;
  font-size: 12px;
  font-weight: 700;
  border-bottom: 1px solid #1e1e22;
  display: flex;
  align-items: stretch;
  flex-shrink: 0;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  color: #555;
}
.chat-tab {
  flex: 1;
  padding: 9px 6px;
  text-align: center;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: color 0.15s, border-color 0.15s;
  font-size: 10px;
  white-space: nowrap;
}
.chat-tab:hover { color: #aaa; }
.chat-tab.active { color: #e0e0e0; border-bottom-color: #5865f2; }
.chat-btn {
  background: none;
  border: none;
  color: #555;
  cursor: pointer;
  padding: 0 8px;
  font-size: 14px;
  display: flex;
  align-items: center;
  transition: color 0.15s;
  flex-shrink: 0;
}
.chat-btn:hover { color: #e0e0e0; }
#chat-msgs {
  flex: 1;
  overflow-y: auto;
  padding: 6px 4px;
  display: flex;
  flex-direction: column;
  gap: 1px;
  scrollbar-width: thin;
  scrollbar-color: #2a2a2e transparent;
}
.msg {
  padding: 3px 10px;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.5;
  word-break: break-word;
}
.msg:hover { background: rgba(255,255,255,0.04); }
.msg.mention { background: rgba(88,101,242,0.15); border-left: 2px solid #5865f2; }
.msg.tts-msg { background: rgba(255,170,0,0.08); border-left: 2px solid #ffaa00; font-size: 13px; padding: 5px 10px; }
.msg-name { font-weight: 700; margin-right: 4px; cursor: pointer; }
.msg-name:hover { text-decoration: underline; }
.tts-badge { font-size: 9px; color: #ffaa00; background: rgba(255,170,0,0.15); border-radius: 3px; padding: 1px 4px; margin-right: 4px; font-weight: 700; vertical-align: middle; }
.tts-voice { font-size: 10px; color: #888; margin-left: 4px; }
.msg-text { color: #bbb; font-weight: 300; }
.msg-room { font-size: 9px; color: #555; background: #1a1a1e; border-radius: 3px; padding: 1px 4px; margin-right: 4px; vertical-align: middle; }
.chat-input-wrap {
  display: flex;
  padding: 6px 8px;
  border-top: 1px solid #1e1e22;
  flex-shrink: 0;
  gap: 6px;
}
.chat-input-wrap input {
  flex: 1;
  background: #1a1a1e;
  border: 1px solid #2a2a2e;
  border-radius: 6px;
  padding: 6px 10px;
  color: #e0e0e0;
  font-size: 12px;
  outline: none;
}
.chat-input-wrap input:focus { border-color: #5865f2; }
.chat-input-wrap button {
  background: #5865f2;
  border: none;
  color: #fff;
  border-radius: 6px;
  padding: 0 12px;
  font-size: 16px;
  cursor: pointer;
  font-weight: 700;
}
.chat-input-wrap button:hover { background: #4752c4; }
#overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: #000;
  z-index: 200;
}
#overlay.open { display: flex; }
#overlay-main { flex: 1; position: relative; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
#overlay-bar {
  position: absolute;
  top: 0; left: 0; right: 0;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: rgba(0,0,0,0.7);
  z-index: 10;
  opacity: 0;
  transition: opacity 0.2s;
}
#overlay-main:hover #overlay-bar { opacity: 1; }
#overlay-title { font-size: 15px; font-weight: 700; }
#overlay-multi-toggle {
  background: rgba(255,255,255,0.1);
  border: none; color: #fff;
  padding: 5px 14px;
  border-radius: 6px;
  cursor: pointer; font-size: 12px;
}
#overlay-multi-toggle:hover { background: rgba(255,255,255,0.2); }
#overlay-multi-toggle.active { background: #5865f2; }
#overlay-chat-toggle {
  background: rgba(255,255,255,0.1);
  border: none; color: #fff;
  padding: 5px 14px;
  border-radius: 6px;
  cursor: pointer; font-size: 12px;
}
#overlay-chat-toggle:hover { background: rgba(255,255,255,0.2); }
#vol-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
}
#vol-btn {
  background: none;
  border: none;
  color: #fff;
  cursor: pointer;
  font-size: 15px;
  padding: 2px 0;
  line-height: 1;
}
#vol-slider {
  width: 72px;
  height: 3px;
  cursor: pointer;
  accent-color: #5865f2;
  vertical-align: middle;
}
#fs-btn {
  background: rgba(255,255,255,0.1);
  border: none; color: #fff;
  padding: 5px 12px;
  border-radius: 6px;
  cursor: pointer; font-size: 13px;
}
#fs-btn:hover { background: rgba(255,255,255,0.2); }
#fs-btn.active { background: #5865f2; }
#overlay-close {
  margin-left: auto;
  background: rgba(255,255,255,0.1);
  border: none; color: #fff;
  padding: 5px 14px;
  border-radius: 6px;
  cursor: pointer; font-size: 13px;
}
#overlay-close:hover { background: rgba(255,255,255,0.2); }
#overlay-video { flex: 1; width: 100%; height: 0; min-height: 0; object-fit: contain; background: #000; }
/* Multi-cam grid */
#multi-grid {
  display: none;
  flex: 1;
  min-height: 0;
  gap: 2px;
  background: #000;
}
#multi-grid.active { display: grid; }
#multi-grid.cols-2 { grid-template-columns: 1fr 1fr; grid-template-rows: 1fr; }
#multi-grid.cols-3, #multi-grid.cols-4 { grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; }
.multi-cell {
  position: relative;
  background: #000;
  overflow: hidden;
  cursor: pointer;
  min-height: 0;
}
.multi-cell video {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.multi-cell-label {
  position: absolute;
  top: 8px; left: 10px;
  font-size: 12px;
  font-weight: 700;
  background: rgba(0,0,0,0.6);
  padding: 3px 8px;
  border-radius: 4px;
  z-index: 5;
  pointer-events: none;
}
.multi-cell-audio {
  position: absolute;
  top: 8px; right: 10px;
  font-size: 14px;
  background: rgba(0,0,0,0.6);
  padding: 3px 8px;
  border-radius: 4px;
  z-index: 5;
  pointer-events: none;
}
.multi-cell.has-audio { outline: 2px solid #5865f2; outline-offset: -2px; }
#cam-bar {
  position: absolute;
  bottom: 0; left: 0; right: 0;
  display: flex;
  gap: 5px;
  padding: 28px 10px 8px;
  background: linear-gradient(transparent, rgba(0,0,0,0.8));
  overflow-x: auto;
  scrollbar-width: none;
  z-index: 10;
  opacity: 0;
  transition: opacity 0.2s;
  pointer-events: none;
}
#cam-bar::-webkit-scrollbar { display: none; }
#overlay-main:hover #cam-bar { opacity: 1; pointer-events: auto; }
#overlay-chat {
  width: 300px;
  background: #0e0e10;
  border-left: 1px solid #1e1e22;
  display: none;
  flex-direction: column;
  flex-shrink: 0;
  overflow: hidden;
}
#overlay-chat.show { display: flex; }
#overlay-chat-head {
  padding: 0;
  display: flex;
  align-items: stretch;
  border-bottom: 1px solid #1e1e22;
  flex-shrink: 0;
}
#overlay-chat-head .chat-tab {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  color: #555;
}
#overlay-chat-msgs {
  flex: 1;
  overflow-y: auto;
  padding: 6px 4px;
  display: flex;
  flex-direction: column;
  gap: 1px;
  scrollbar-width: thin;
  scrollbar-color: #2a2a2e transparent;
}
.pill {
  flex-shrink: 0;
  background: rgba(0,0,0,0.5);
  border: 1px solid rgba(255,255,255,0.2);
  border-radius: 20px;
  padding: 3px 10px;
  font-size: 11px;
  cursor: pointer;
  white-space: nowrap;
  color: #ddd;
  transition: background 0.1s, color 0.1s;
}
.pill:hover, .pill.active { background: #5865f2; border-color: #5865f2; }
/* Multi-cam header buttons */
#multi-btn {
  background: rgba(255,255,255,0.08);
  border: 1px solid #2a2a2e;
  color: #e0e0e0;
  padding: 5px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  flex-shrink: 0;
}
#multi-btn:hover { background: rgba(255,255,255,0.18); }
#multi-btn.active { background: #5865f2; border-color: #5865f2; }
#watch-btn {
  display: none;
  background: #22c55e;
  border: none;
  color: #fff;
  padding: 5px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}
#watch-btn.show { display: inline-block; }
/* Selection mode checkmark overlays */
.cc-chk {
  display: none;
  position: absolute;
  inset: 0;
  background: rgba(0,0,0,0.35);
  align-items: center;
  justify-content: center;
  pointer-events: none;
  z-index: 5;
}
.cc-chk-inner {
  width: 38px; height: 38px;
  border-radius: 50%;
  border: 3px solid rgba(255,255,255,0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  color: transparent;
  background: rgba(0,0,0,0.3);
  transition: background 0.1s, border-color 0.1s, color 0.1s;
}
body.pick .cc-chk { display: flex; }
body.pick .cam-card:hover { transform: none; border-color: #888; }
body.pick .cam-card.selected { border-color: #22c55e; }
body.pick .cam-card.selected .cc-chk-inner {
  background: #22c55e;
  border-color: #22c55e;
  color: #fff;
}
</style>
</head>
<body>
<header>
  <h1>Terrarium</h1>
  <span class="sub">Fishtank LIVE</span>
  <span class="count" id="count"></span>
  <button id="multi-btn">&#x25A6; Multi-Cam</button>
  <button id="watch-btn">Watch 0 cams</button>
</header>
<div id="main">
  <div id="content">
    <div id="grid"></div>
  </div>
  <div id="chat-sidebar">
    <div id="chat-head">
      <div class="chat-tab active" data-room="All">All</div>
      <div class="chat-tab" data-room="Global">Global</div>
      <div class="chat-tab" data-room="Season Pass">Season Pass</div>
      <button class="chat-btn" id="chat-popout" title="Pop out chat">&#x29C9;</button>
    </div>
    <div id="chat-msgs"></div>
    <div class="chat-input-wrap">
      <input type="text" id="chat-input" placeholder="Send a message..." autocomplete="off">
      <button id="chat-send">&#x203A;</button>
    </div>
  </div>
</div>
<div id="overlay">
  <div id="overlay-main">
    <div id="overlay-bar">
      <span id="overlay-title"></span>
      <button id="overlay-multi-toggle" title="Multi-cam view">&#x25A6; Multi</button>
      <button id="overlay-chat-toggle">&#x1F4AC; Chat</button>
      <span id="vol-wrap">
        <button id="vol-btn" title="Mute/unmute">&#x1F50A;</button>
        <input type="range" id="vol-slider" min="0" max="1" step="0.05" value="1">
      </span>
      <button id="fs-btn" title="Fullscreen">&#x26F6;</button>
      <button id="overlay-close">&#x2715; Close</button>
    </div>
    <video id="overlay-video" autoplay playsinline controls></video>
    <div id="multi-grid"></div>
    <div id="cam-bar"></div>
  </div>
  <div id="overlay-chat">
    <div id="overlay-chat-head">
      <div class="chat-tab active" data-room="All">All</div>
      <div class="chat-tab" data-room="Global">Global</div>
      <div class="chat-tab" data-room="Season Pass">SP</div>
    </div>
    <div id="overlay-chat-msgs"></div>
    <div class="chat-input-wrap">
      <input type="text" id="overlay-chat-input" placeholder="Send a message..." autocomplete="off">
      <button id="overlay-chat-send">&#x203A;</button>
    </div>
  </div>
</div>
<script>
const CAMS = """ + cam_json + """;
let activeHls = null;
let activeIdx = null;
let chatPopout = null;
let selMode = false;
let selectedIdxs = [];
let multiHlsArr = [];

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function loadSnap(img, snapUrl) {
  const tmp = new Image();
  tmp.onload = () => {
    img.src = tmp.src;
    img.closest('.cam-card').querySelector('.dot').classList.remove('off');
  };
  tmp.onerror = () => {
    img.closest('.cam-card').querySelector('.dot').classList.add('off');
  };
  tmp.src = snapUrl + '?t=' + Date.now();
}

function openCam(idx) {
  activeIdx = idx;
  const cam = CAMS[idx];
  document.getElementById('overlay-title').textContent = cam.name;
  document.getElementById('overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
  document.querySelectorAll('#cam-bar .pill').forEach((p, i) => p.classList.toggle('active', i === idx));
  const video = document.getElementById('overlay-video');
  if (activeHls) { activeHls.destroy(); activeHls = null; }
  if (Hls.isSupported()) {
    activeHls = new Hls({
      liveSyncDurationCount: 3,
      liveMaxLatencyDurationCount: 10,
      liveDurationInfinity: true,
    });
    activeHls.loadSource(cam.stream);
    activeHls.attachMedia(video);
    activeHls.on(Hls.Events.MANIFEST_PARSED, () => {
      video.volume = volMuted ? 0 : volLevel;
      video.muted = volMuted;
      video.play().catch(() => {});
    });
  } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
    video.src = cam.stream;
    video.volume = volMuted ? 0 : volLevel;
    video.muted = volMuted;
    video.play().catch(() => {});
  }
  syncOverlayChat();
}

function closeCam() {
  document.getElementById('overlay').classList.remove('open');
  document.body.style.overflow = '';
  if (activeHls) { activeHls.destroy(); activeHls = null; }
  document.getElementById('overlay-video').src = '';
  document.getElementById('overlay-video').style.display = '';
  // Clean up multi-grid
  multiHlsArr.forEach(h => { try { if (h) h.destroy(); } catch {} });
  multiHlsArr = [];
  const mgrid = document.getElementById('multi-grid');
  mgrid.innerHTML = '';
  mgrid.className = '';
  activeIdx = null;
}

const grid   = document.getElementById('grid');
const camBar = document.getElementById('cam-bar');
document.getElementById('count').textContent = CAMS.length + ' cameras';

CAMS.forEach((cam, idx) => {
  const card = document.createElement('div');
  card.className = 'cam-card';
  card.innerHTML =
    '<img alt="' + esc(cam.name) + '">' +
    '<div class="cam-label"><span>' + esc(cam.name) + '</span>' +
    '<span class="dot off"></span></div>' +
    '<div class="cc-chk"><div class="cc-chk-inner">&#x2713;</div></div>';
  card.addEventListener('click', () => {
    if (selMode) {
      const pos = selectedIdxs.indexOf(idx);
      if (pos === -1) {
        if (selectedIdxs.length < 4) {
          selectedIdxs.push(idx);
          card.classList.add('selected');
        }
      } else {
        selectedIdxs.splice(pos, 1);
        card.classList.remove('selected');
      }
      updateWatchBtn();
    } else {
      openCam(idx);
    }
  });
  grid.appendChild(card);
  const img = card.querySelector('img');
  loadSnap(img, cam.snap);
  setInterval(() => loadSnap(img, cam.snap), 10000);
  const pill = document.createElement('button');
  pill.className = 'pill';
  pill.textContent = cam.name;
  pill.addEventListener('click', () => openCam(idx));
  camBar.appendChild(pill);
});

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeCam();
  if (e.key === 'ArrowRight' && activeIdx !== null) openCam((activeIdx + 1) % CAMS.length);
  if (e.key === 'ArrowLeft'  && activeIdx !== null) openCam((activeIdx - 1 + CAMS.length) % CAMS.length);
});
document.getElementById('overlay-close').addEventListener('click', closeCam);

// Fullscreen
document.getElementById('fs-btn').addEventListener('click', () => {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch(() => {});
  } else {
    document.exitFullscreen().catch(() => {});
  }
});
document.addEventListener('fullscreenchange', () => {
  const active = !!document.fullscreenElement;
  document.getElementById('fs-btn').classList.toggle('active', active);
  document.getElementById('fs-btn').title = active ? 'Exit fullscreen' : 'Fullscreen';
});

// Drift correction — only snap if very far behind live (>30s)
setInterval(() => {
  const video = document.getElementById('overlay-video');
  if (!video || !activeHls || video.paused) return;
  const buffered = video.buffered;
  if (buffered.length > 0) {
    const liveEdge = buffered.end(buffered.length - 1);
    if (liveEdge - video.currentTime > 30) {
      video.currentTime = liveEdge - 3;
    }
  }
}, 10000);

// ── Chat state ──────────────────────────────────────────────────
const allMessages = [];
const seenIds = new Set();
let sidebarRoom = 'All';
let overlayRoom = 'All';
let myUsername = '';

const chatEl = document.getElementById('chat-msgs');
const overlayChatEl = document.getElementById('overlay-chat-msgs');

// Fetch our username
fetch('/me').then(r => r.json()).then(d => { myUsername = (d.displayName || '').toLowerCase(); }).catch(() => {});

// Mention sound
function playMentionSound() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.type = 'sine';
    osc.frequency.value = 880;
    gain.gain.value = 0.15;
    osc.start();
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
    osc.stop(ctx.currentTime + 0.3);
  } catch {}
}

function isMentioned(text) {
  if (!myUsername) return false;
  return text.toLowerCase().includes('@' + myUsername);
}

function mentionUser(username) {
  const inputs = [
    document.getElementById('overlay-chat-input'),
    document.getElementById('chat-input'),
  ];
  for (const inp of inputs) {
    if (inp && inp.offsetParent !== null) {
      const cur = inp.value;
      inp.value = (cur ? cur.trimEnd() + ' ' : '') + '@' + username + ' ';
      inp.focus();
      return;
    }
  }
  const inp = document.getElementById('chat-input');
  if (inp) {
    inp.value = (inp.value ? inp.value.trimEnd() + ' ' : '') + '@' + username + ' ';
    inp.focus();
  }
}

// Sidebar tabs
document.querySelectorAll('#chat-head .chat-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('#chat-head .chat-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    sidebarRoom = tab.dataset.room;
    renderTo(chatEl, sidebarRoom);
  });
});

// Overlay tabs
document.querySelectorAll('#overlay-chat-head .chat-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('#overlay-chat-head .chat-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    overlayRoom = tab.dataset.room;
    renderTo(overlayChatEl, overlayRoom);
  });
});

// ── Volume control ───────────────────────────────────────────────
let volLevel = 1;
let volMuted = false;

function getActiveVideo() {
  const mgrid = document.getElementById('multi-grid');
  if (mgrid.classList.contains('active')) {
    return mgrid.querySelector('.multi-cell.has-audio video');
  }
  return document.getElementById('overlay-video');
}

function applyVolume() {
  const vid = getActiveVideo();
  if (!vid) return;
  vid.volume = volMuted ? 0 : volLevel;
  vid.muted = volMuted;
  document.getElementById('vol-btn').textContent = volMuted || volLevel === 0 ? '\U0001F507' : '\U0001F50A';
}

document.getElementById('vol-slider').addEventListener('input', e => {
  volLevel = parseFloat(e.target.value);
  volMuted = (volLevel === 0);
  applyVolume();
});

document.getElementById('vol-btn').addEventListener('click', () => {
  volMuted = !volMuted;
  applyVolume();
});

// Overlay chat toggle
document.getElementById('overlay-chat-toggle').addEventListener('click', () => {
  const panel = document.getElementById('overlay-chat');
  panel.classList.toggle('show');
  if (panel.classList.contains('show')) syncOverlayChat();
});

function syncOverlayChat() {
  renderTo(overlayChatEl, overlayRoom);
}

function renderTo(el, room) {
  el.innerHTML = '';
  const filtered = room === 'All' ? allMessages : allMessages.filter(m => m.room === room);
  filtered.forEach(m => el.appendChild(makeMsgDiv(m, room)));
  el.scrollTop = el.scrollHeight;
}

function makeMsgDiv(m, roomFilter) {
  const div = document.createElement('div');
  const mentioned = isMentioned(m.text);
  const isTts = m.type === 'tts';
  div.className = 'msg' + (mentioned ? ' mention' : '') + (isTts ? ' tts-msg' : '');

  const roomBadge = (roomFilter === 'All' && m.room && m.room !== 'Global')
    ? '<span class="msg-room">' + esc(m.room) + '</span>' : '';
  const ttsBadge = isTts ? '<span class="tts-badge">TTS</span>' : '';
  const voiceTag = isTts && m.voice ? '<span class="tts-voice">(' + esc(m.voice) + ')</span>' : '';

  div.innerHTML =
    roomBadge + ttsBadge +
    '<span class="msg-name" style="color:' + esc(m.color) + '" data-username="' + esc(m.username) + '">' + esc(m.username) + '</span>' +
    voiceTag +
    '<span class="msg-text">' + esc(m.text) + '</span>';

  const nameEl = div.querySelector('.msg-name');
  if (nameEl) {
    nameEl.addEventListener('click', (e) => {
      e.stopPropagation();
      mentionUser(nameEl.dataset.username);
    });
  }

  return div;
}

function appendToEl(el, m, roomFilter) {
  if (roomFilter !== 'All' && m.room !== roomFilter) return;
  const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  el.appendChild(makeMsgDiv(m, roomFilter));
  while (el.children.length > 200) el.removeChild(el.firstChild);
  if (atBottom) el.scrollTop = el.scrollHeight;
}

function appendMsg(m) {
  if (seenIds.has(m.id)) return;
  seenIds.add(m.id);
  allMessages.push(m);
  while (allMessages.length > 200) {
    const removed = allMessages.shift();
    seenIds.delete(removed.id);
  }
  if (isMentioned(m.text)) playMentionSound();
  appendToEl(chatEl, m, sidebarRoom);
  if (document.getElementById('overlay-chat').classList.contains('show')) {
    appendToEl(overlayChatEl, m, overlayRoom);
  }
  if (chatPopout && !chatPopout.closed) {
    try { chatPopout.appendMsg(m); } catch {}
  }
}

// ── Pop-out chat ────────────────────────────────────────────────
document.getElementById('chat-popout').addEventListener('click', () => {
  if (chatPopout && !chatPopout.closed) { chatPopout.focus(); return; }
  chatPopout = window.open('', 'terrarium_chat', 'width=340,height=600');
  const doc = chatPopout.document;
  doc.write('<!DOCTYPE html><html><head><title>Chat</title><style>' +
    '* { box-sizing: border-box; margin: 0; padding: 0; }' +
    'body { background: #0e0e10; color: #e0e0e0; font-family: -apple-system, sans-serif; display: flex; flex-direction: column; height: 100vh; }' +
    '#tabs { display: flex; border-bottom: 1px solid #1e1e22; flex-shrink: 0; }' +
    '.tab { flex: 1; padding: 8px; text-align: center; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .5px; color: #555; cursor: pointer; border-bottom: 2px solid transparent; }' +
    '.tab:hover { color: #aaa; }' +
    '.tab.active { color: #e0e0e0; border-bottom-color: #5865f2; }' +
    '#msgs { flex: 1; overflow-y: auto; padding: 6px 4px; display: flex; flex-direction: column; gap: 1px; scrollbar-width: thin; scrollbar-color: #2a2a2e transparent; }' +
    '.msg { padding: 3px 10px; border-radius: 4px; font-size: 12px; line-height: 1.5; word-break: break-word; }' +
    '.msg:hover { background: rgba(255,255,255,0.04); }' +
    '.msg.mention { background: rgba(88,101,242,0.15); border-left: 2px solid #5865f2; }' +
    '.msg.tts-msg { background: rgba(255,170,0,0.08); border-left: 2px solid #ffaa00; font-size: 13px; padding: 5px 10px; }' +
    '.msg-name { font-weight: 700; margin-right: 4px; cursor: pointer; }' +
    '.msg-name:hover { text-decoration: underline; }' +
    '.tts-badge { font-size: 9px; color: #ffaa00; background: rgba(255,170,0,0.15); border-radius: 3px; padding: 1px 4px; margin-right: 4px; font-weight: 700; }' +
    '.tts-voice { font-size: 10px; color: #888; margin-left: 4px; }' +
    '.msg-text { color: #bbb; font-weight: 300; }' +
    '.msg-room { font-size: 9px; color: #555; background: #1a1a1e; border-radius: 3px; padding: 1px 4px; margin-right: 4px; }' +
    '.input-wrap { display: flex; padding: 6px 8px; border-top: 1px solid #1e1e22; gap: 6px; }' +
    '.input-wrap input { flex: 1; background: #1a1a1e; border: 1px solid #2a2a2e; border-radius: 6px; padding: 6px 10px; color: #e0e0e0; font-size: 12px; outline: none; }' +
    '.input-wrap input:focus { border-color: #5865f2; }' +
    '.input-wrap button { background: #5865f2; border: none; color: #fff; border-radius: 6px; padding: 0 12px; font-size: 16px; cursor: pointer; font-weight: 700; }' +
    '</style></head><body>' +
    '<div id="tabs">' +
    '<div class="tab active" data-room="All">All</div>' +
    '<div class="tab" data-room="Global">Global</div>' +
    '<div class="tab" data-room="Season Pass">Season Pass</div>' +
    '</div>' +
    '<div id="msgs"></div>' +
    '<div class="input-wrap">' +
    '<input type="text" id="pop-input" placeholder="Send a message..." autocomplete="off">' +
    '<button id="pop-send">&#x203A;</button>' +
    '</div>' +
    '</body></html>');
  doc.close();

  const popMsgs = chatPopout.document.getElementById('msgs');
  let popRoom = 'All';

  function esc2(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

  function makePopDiv(m, roomFilter) {
    const div = doc.createElement('div');
    const mentioned = myUsername && m.text.toLowerCase().includes('@' + myUsername);
    const isTts = m.type === 'tts';
    div.className = 'msg' + (mentioned ? ' mention' : '') + (isTts ? ' tts-msg' : '');

    const roomBadge = (roomFilter === 'All' && m.room && m.room !== 'Global')
      ? '<span class="msg-room">' + esc2(m.room) + '</span>' : '';
    const ttsBadge = isTts ? '<span class="tts-badge">TTS</span>' : '';
    const voiceTag = isTts && m.voice ? '<span class="tts-voice">(' + esc2(m.voice) + ')</span>' : '';

    div.innerHTML =
      roomBadge + ttsBadge +
      '<span class="msg-name" style="color:' + esc2(m.color) + '" data-username="' + esc2(m.username) + '">' + esc2(m.username) + '</span>' +
      voiceTag +
      '<span class="msg-text">' + esc2(m.text) + '</span>';

    const nameEl = div.querySelector('.msg-name');
    if (nameEl) {
      nameEl.addEventListener('click', (e) => {
        e.stopPropagation();
        const inp = doc.getElementById('pop-input');
        if (inp) {
          inp.value = (inp.value ? inp.value.trimEnd() + ' ' : '') + '@' + nameEl.dataset.username + ' ';
          inp.focus();
        }
      });
    }
    return div;
  }

  function renderPop() {
    popMsgs.innerHTML = '';
    const filtered = popRoom === 'All' ? allMessages : allMessages.filter(m => m.room === popRoom);
    filtered.forEach(m => popMsgs.appendChild(makePopDiv(m, popRoom)));
    popMsgs.scrollTop = popMsgs.scrollHeight;
  }

  chatPopout.document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      chatPopout.document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      popRoom = tab.dataset.room;
      renderPop();
    });
  });

  chatPopout.appendMsg = function(m) {
    if (popRoom !== 'All' && m.room !== popRoom) return;
    const atBottom = popMsgs.scrollHeight - popMsgs.scrollTop - popMsgs.clientHeight < 80;
    popMsgs.appendChild(makePopDiv(m, popRoom));
    while (popMsgs.children.length > 200) popMsgs.removeChild(popMsgs.firstChild);
    if (atBottom) popMsgs.scrollTop = popMsgs.scrollHeight;
  };

  renderPop();

  // Wire popout send
  const popInput = doc.getElementById('pop-input');
  const popBtn = doc.getElementById('pop-send');
  popBtn.addEventListener('click', () => {
    sendMessage(popInput.value, popRoom === 'All' ? 'Global' : popRoom);
    popInput.value = '';
    popInput.focus();
  });
  popInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(popInput.value, popRoom === 'All' ? 'Global' : popRoom);
      popInput.value = '';
    }
  });
});

// ── Send messages ───────────────────────────────────────────────
async function sendMessage(text, room) {
  if (!text.trim()) return;
  try {
    await fetch('/chat/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text.trim(), room: room }),
    });
  } catch (e) { console.error('Send failed:', e); }
}

function wireInput(inputEl, btnEl, roomFn) {
  btnEl.addEventListener('click', () => {
    sendMessage(inputEl.value, roomFn());
    inputEl.value = '';
    inputEl.focus();
  });
  inputEl.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(inputEl.value, roomFn());
      inputEl.value = '';
    }
  });
}

wireInput(
  document.getElementById('chat-input'),
  document.getElementById('chat-send'),
  () => sidebarRoom === 'All' ? 'Global' : sidebarRoom
);

wireInput(
  document.getElementById('overlay-chat-input'),
  document.getElementById('overlay-chat-send'),
  () => overlayRoom === 'All' ? 'Global' : overlayRoom
);

// ── Multi-cam ────────────────────────────────────────────────────
function updateWatchBtn() {
  const btn = document.getElementById('watch-btn');
  if (selectedIdxs.length >= 2) {
    btn.textContent = 'Watch ' + selectedIdxs.length + ' cams';
    btn.classList.add('show');
  } else {
    btn.classList.remove('show');
  }
}

function enterSelMode() {
  selMode = true;
  selectedIdxs = [];
  document.body.classList.add('pick');
  document.getElementById('multi-btn').classList.add('active');
  document.getElementById('watch-btn').classList.remove('show');
  document.querySelectorAll('.cam-card').forEach(c => c.classList.remove('selected'));
}

function exitSelMode() {
  selMode = false;
  selectedIdxs = [];
  document.body.classList.remove('pick');
  document.getElementById('multi-btn').classList.remove('active');
  document.getElementById('watch-btn').classList.remove('show');
  document.querySelectorAll('.cam-card').forEach(c => c.classList.remove('selected'));
}

function openMultiCam() {
  const cams = selectedIdxs.map(i => CAMS[i]);
  exitSelMode();

  const overlay = document.getElementById('overlay');
  const video   = document.getElementById('overlay-video');
  const mgrid   = document.getElementById('multi-grid');

  // Destroy any existing single-cam HLS
  if (activeHls) { activeHls.destroy(); activeHls = null; }
  video.src = '';
  video.style.display = 'none';

  overlay.classList.add('open');
  document.body.style.overflow = 'hidden';
  document.getElementById('overlay-title').textContent = 'Multi-Cam (' + cams.length + ')';
  document.getElementById('overlay-multi-toggle').classList.add('active');

  // Destroy any previous multi HLS
  multiHlsArr.forEach(h => { try { if (h) h.destroy(); } catch {} });
  multiHlsArr = [];
  mgrid.innerHTML = '';

  const n = cams.length;
  mgrid.className = 'active cols-' + (n <= 2 ? '2' : '4');

  cams.forEach((cam, ci) => {
    const cell = document.createElement('div');
    cell.className = 'multi-cell' + (ci === 0 ? ' has-audio' : '');

    const vid = document.createElement('video');
    vid.autoplay = true;
    vid.playsInline = true;
    vid.muted = (ci !== 0);

    const lbl = document.createElement('div');
    lbl.className = 'multi-cell-label';
    lbl.textContent = cam.name;

    const aud = document.createElement('div');
    aud.className = 'multi-cell-audio';
    aud.textContent = ci === 0 ? '\U0001F50A' : '\U0001F507';

    cell.appendChild(vid);
    cell.appendChild(lbl);
    cell.appendChild(aud);
    mgrid.appendChild(cell);

    let hls = null;
    if (Hls.isSupported()) {
      hls = new Hls({
        liveSyncDurationCount: 3,
        liveMaxLatencyDurationCount: 10,
        liveDurationInfinity: true,
        maxBufferLength: 12,
        maxMaxBufferLength: 20,
      });
      hls.loadSource(cam.stream);
      hls.attachMedia(vid);
      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        if (ci === 0) { vid.volume = volMuted ? 0 : volLevel; vid.muted = volMuted; }
        vid.play().catch(() => {});
      });
    } else if (vid.canPlayType('application/vnd.apple.mpegurl')) {
      vid.src = cam.stream;
      if (ci === 0) { vid.volume = volMuted ? 0 : volLevel; vid.muted = volMuted; }
      vid.play().catch(() => {});
    }
    multiHlsArr.push(hls);

    cell.addEventListener('click', () => {
      mgrid.querySelectorAll('.multi-cell').forEach((c, i) => {
        const v = c.querySelector('video');
        const a = c.querySelector('.multi-cell-audio');
        const active = (i === ci);
        c.classList.toggle('has-audio', active);
        v.muted = active ? volMuted : true;
        if (!active) v.volume = 0;
        else { v.volume = volMuted ? 0 : volLevel; }
        if (a) a.textContent = active ? '\U0001F50A' : '\U0001F507';
      });
    });
  });
}

document.getElementById('multi-btn').addEventListener('click', () => {
  if (selMode) {
    exitSelMode();
  } else {
    closeCam();
    enterSelMode();
  }
});

document.getElementById('watch-btn').addEventListener('click', openMultiCam);

document.getElementById('overlay-multi-toggle').addEventListener('click', () => {
  closeCam();
  enterSelMode();
});

// ── Polling ─────────────────────────────────────────────────────
let chatCursor = 0;

async function pollChat() {
  try {
    const r = await fetch('/chat?since=' + chatCursor);
    if (r.ok) {
      const data = await r.json();
      data.msgs.forEach(appendMsg);
      chatCursor = data.total;
    }
  } catch {}
  setTimeout(pollChat, 200);
}
pollChat();
</script>
</body>
</html>"""


def build_playlist(selected_cams, port):
    ip    = get_local_ip()
    lines = ["#EXTM3U"]
    for name, _ in selected_cams:
        url = f"http://{ip}:{port}/cam/{urllib.parse.quote(name)}"
        lines.append(f'#EXTINF:-1 tvg-name="{name}",{name}')
        lines.append(url)
    return "\n".join(lines) + "\n"


def make_handler(selected_cams, port):
    cam_map = {name: code for name, code in selected_cams}

    class Handler(BaseHTTPRequestHandler):

        def log_message(self, fmt, *args):
            pass

        def do_GET(self):
            path = self.path.strip("/").split("?")[0]

            if path in ("", "index.html"):
                body = build_site(selected_cams, port).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if path == "health":
                self._text(200, b"ok")
                return

            if path == "me":
                body = json.dumps({"displayName": user_display_name or ""}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
                return

            if path == "chat":
                since = 0
                if "?" in self.path:
                    qs = urllib.parse.parse_qs(self.path.split("?", 1)[1])
                    try:
                        since = int(qs.get("since", [0])[0])
                    except Exception:
                        pass
                with chat_lock:
                    if since == 0:
                        msgs = list(chat_messages)
                    else:
                        msgs = [m for m in chat_messages if m.get("_seq", 0) > since]
                    seq = chat_counter
                body = json.dumps({"msgs": msgs, "total": seq}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(body)
                return

            if path in ("playlist.m3u", "playlist"):
                body = build_playlist(selected_cams, port).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
                return

            if path.startswith("snap/"):
                name = urllib.parse.unquote(path[5:])
                with cache_lock:
                    body = snap_cache.get(name)
                if body:
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    with cache_lock:
                        failed = name in snap_failed
                    if failed and OFFLINE_THUMB:
                        self.send_response(200)
                        self.send_header("Content-Type", "image/jpeg")
                        self.send_header("Content-Length", str(len(OFFLINE_THUMB)))
                        self.send_header("Cache-Control", "no-cache")
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.end_headers()
                        self.wfile.write(OFFLINE_THUMB)
                    else:
                        self._text(503, b"Snapshot not ready")
                return

            if path.startswith("cam/"):
                name = urllib.parse.unquote(path[4:])
                code = cam_map.get(name)
                if not code:
                    self._text(404, f"Unknown camera: {name}".encode())
                    return
                stream_url = get_cached_stream_url(code)
                if not stream_url:
                    self._text(503, b"Camera offline")
                    return
                try:
                    r = requests.get(stream_url, timeout=8)
                    if r.status_code != 200:
                        self._text(503, b"Stream unavailable")
                        return
                    ip       = get_local_ip()
                    prx_base = f"http://{ip}:{port}/seg/{urllib.parse.quote(name)}/"
                    lines    = []
                    for line in r.text.splitlines():
                        stripped = line.strip()
                        if not stripped or stripped.startswith("#"):
                            lines.append(line)
                        else:
                            lines.append(prx_base + urllib.parse.quote(stripped, safe=""))
                    body = "\n".join(lines).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    self.wfile.write(body)
                except Exception as e:
                    self._text(503, f"Proxy error: {e}".encode())
                return

            if path.startswith("seg/"):
                rest  = path[4:]
                slash = rest.index("/")
                name  = urllib.parse.unquote(rest[:slash])
                seg   = urllib.parse.unquote(rest[slash + 1:])
                code  = cam_map.get(name)
                if not code:
                    self._text(404, b"Unknown camera")
                    return
                stream_url = get_cached_stream_url(code)
                if not stream_url:
                    self._text(503, b"Camera offline")
                    return
                master_base = stream_url.rsplit("/", 1)[0] + "/"
                seg_url     = master_base + seg
                try:
                    r = requests.get(seg_url, timeout=15, stream=True)
                    ct = r.headers.get("Content-Type", "")
                    if "mpegurl" in ct or seg.split("?")[0].endswith(".m3u8"):
                        this_base = seg_url.split("?")[0].rsplit("/", 1)[0] + "/"
                        ip        = get_local_ip()
                        prx_base  = f"http://{ip}:{port}/seg/{urllib.parse.quote(name)}/"
                        lines     = []
                        for line in r.text.splitlines():
                            stripped = line.strip()
                            if not stripped or stripped.startswith("#"):
                                lines.append(line)
                            else:
                                full = this_base + stripped if not stripped.startswith("http") else stripped
                                rel  = full[len(master_base):] if full.startswith(master_base) else full
                                lines.append(prx_base + urllib.parse.quote(rel, safe=""))
                        body = "\n".join(lines).encode()
                        self.send_response(200)
                        self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                        self.send_header("Content-Length", str(len(body)))
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.send_header("Cache-Control", "no-cache")
                        self.end_headers()
                        self.wfile.write(body)
                    else:
                        self.send_response(200)
                        self.send_header("Content-Type", "video/mp2t")
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.end_headers()
                        try:
                            for chunk in r.iter_content(65536):
                                self.wfile.write(chunk)
                        except (ConnectionAbortedError, BrokenPipeError):
                            pass
                except (ConnectionAbortedError, BrokenPipeError):
                    pass
                except Exception as e:
                    try:
                        self._text(503, f"Segment error: {e}".encode())
                    except Exception:
                        pass
                return

            self._text(404, b"Not found")

        def do_POST(self):
            path = self.path.strip("/").split("?")[0]

            if path == "chat/send":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                try:
                    data = json.loads(body)
                    text = data.get("message", "").strip()
                    room = data.get("room", "Global")
                    if not text:
                        self._text(400, b"Empty message")
                        return
                    ok = send_chat_message(text, room)
                    if ok:
                        self._text(200, b"sent")
                    else:
                        self._text(503, b"No socket for room")
                except Exception as e:
                    self._text(500, f"Error: {e}".encode())
                return

            self._text(404, b"Not found")

        def do_OPTIONS(self):
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def _text(self, code, body):
            try:
                self.send_response(code)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
            except (ConnectionAbortedError, BrokenPipeError):
                pass

    return Handler


def start_proxy(selected_cams, port):
    handler = make_handler(selected_cams, port)
    srv = ThreadingHTTPServer(("0.0.0.0", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    warm_cache(selected_cams)
    threading.Thread(target=lambda: snap_refresh_loop(selected_cams), daemon=True).start()
    start_chat(access_token)
    ip = get_local_ip()
    print(f"  ✓ Web viewer   -> http://{ip}:{port}")
    print(f"  ✓ Playlist URL -> http://{ip}:{port}/playlist.m3u")
    print(f"  (Thumbnails warming up in background...)\n")


# ── UI helpers ────────────────────────────────────────────────────

def pick_cameras():
    print("  Available cameras:\n")
    for num, (name, code) in CAMERAS.items():
        print(f"    [{num:>2}] {name}")
    print()
    print("  Enter camera numbers separated by commas,")
    print("  or press Enter for ALL cameras:")
    print()
    raw = input("  Cameras: ").strip()
    print()
    if not raw:
        return list(CAMERAS.values())
    selected = []
    for part in raw.split(","):
        key = part.strip()
        if key in CAMERAS:
            selected.append(CAMERAS[key])
        else:
            print(f"  ! Unknown number: {key} — skipping")
    return selected


def pick_save_dir():
    default = os.path.join(os.path.expanduser("~"), "terrarium_recordings")
    print(f"  Save directory (Enter for {default}):")
    raw = input("  Path: ").strip()
    return raw if raw else default


def pick_chunk_hours():
    print("\n  Chunk size in hours (Enter for 6):")
    raw = input("  Hours: ").strip()
    try:
        return int(raw) if raw else 6
    except Exception:
        return 6


def pick_proxy_port():
    print("\n  Proxy port (Enter for 8888):")
    raw = input("  Port: ").strip()
    try:
        return int(raw) if raw else 8888
    except Exception:
        return 8888


def cleanup(sig=None, frame=None):
    print(f"\n[{ts()}] Shutting down...")
    stop_event.set()
    for name in list(processes):
        stop_recording(name)
    sys.exit(0)


# ── Main ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import signal
    signal.signal(signal.SIGINT,  cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    print_header()

    print("  Login\n")
    saved_email, saved_password = load_credentials()

    if saved_email and saved_password:
        print(f"  Saved account: {saved_email}")
        use_saved = input("  Use saved account? (Y/n): ").strip().lower()
        if use_saved in ("", "y", "yes"):
            user_email    = saved_email
            user_password = saved_password
        else:
            clear_credentials()
            user_email    = input("  Email:    ").strip()
            user_password = getpass.getpass("  Password: ")
    else:
        user_email    = input("  Email:    ").strip()
        user_password = getpass.getpass("  Password: ")

    print()
    try:
        login(user_email, user_password)
        save_credentials(user_email, user_password)
    except Exception as e:
        print(f"\n  ! Login failed: {e}")
        clear_credentials()
        sys.exit(1)

    print()
    divider("─")
    print("  Mode\n")
    print("  [1]  Watch in VLC / TV / Browser   (proxy only)")
    print("  [2]  Record to disk                (no proxy)")
    print("  [3]  Watch + Record                (proxy + record)")
    print()
    while True:
        mode = input("  Choose (1/2/3): ").strip()
        if mode in ("1", "2", "3"):
            break
        print("  Please enter 1, 2, or 3.")

    do_proxy  = mode in ("1", "3")
    do_record = mode in ("2", "3")

    print()
    divider("─")
    print("  Camera Selection\n")
    selected_cams = pick_cameras()

    if not selected_cams:
        print("  No cameras selected — exiting.")
        sys.exit(0)

    print(f"  Selected: {', '.join(n for n, _ in selected_cams)}\n")

    save_dir    = None
    chunk_hours = 6
    proxy_port  = 8888

    if do_record:
        divider("─")
        print("  Recording Options\n")
        save_dir    = pick_save_dir()
        chunk_hours = pick_chunk_hours()

    if do_proxy:
        divider("─")
        print("  Proxy Options\n")
        proxy_port = pick_proxy_port()

    print()
    divider()

    if do_proxy:
        start_proxy(selected_cams, proxy_port)

    if do_record:
        print(f"[{ts()}] Starting recordings -> {save_dir}\n")
        for name, cam_code in selected_cams:
            proc = start_recording(name, cam_code, save_dir, chunk_hours)
            if proc:
                processes[name] = proc

    threading.Thread(
        target=lambda: token_refresh_loop(selected_cams, save_dir, chunk_hours, do_record),
        daemon=True,
    ).start()

    if do_record:
        threading.Thread(
            target=lambda: watchdog(selected_cams, save_dir, chunk_hours),
            daemon=True,
        ).start()

    print(f"\n[{ts()}] Running. Ctrl+C to stop.\n")
    while not stop_event.is_set():
        time.sleep(1)
