#!/usr/bin/env python3
"""
Terrarium — Fishtank LIVE Tool
Requires: pip install requests  |  ffmpeg in PATH
"""

import os, sys, time, subprocess, requests, urllib.parse, json, getpass
import threading, socket
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

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
    "user-agent":   "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
}

session           = requests.Session()
session.headers.update(HEADERS)
access_token      = None
refresh_token_val = None
live_stream_token = None
user_email        = None
user_password     = None
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
    global access_token, refresh_token_val, live_stream_token
    resp = session.post(
        "https://api.fishtank.live/v1/auth/log-in",
        json={"email": email, "password": password},
        timeout=15,
    )
    resp.raise_for_status()
    s = resp.json()["session"]
    access_token      = s["access_token"]
    refresh_token_val = s["refresh_token"]
    live_stream_token = s["live_stream_token"]
    session.headers["authorization"] = f"Bearer {access_token}"
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


# ── Recording ─────────────────────────────────────────────────────

def start_recording(name, cam_code, save_dir, chunk_hours):
    os.makedirs(save_dir, exist_ok=True)
    url = get_stream_url(cam_code)
    if not url:
        print(f"  ✗ {name} — offline/unreachable")
        return None
    pattern = os.path.join(save_dir, f"{name}_%Y-%m-%d_%H-%M-%S.ts")
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
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    print(f"  ✓ {name} -> {save_dir}")
    return proc


def stop_recording(name):
    proc = processes.pop(name, None)
    if proc and proc.poll() is None:
        proc.terminate()
        try:    proc.wait(timeout=5)
        except: proc.kill()


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
            # Clear URL cache so fresh JWT gets used
            with cache_lock:
                url_cache.clear()
            if do_record:
                restart_recordings(selected_cams, save_dir, chunk_hours)
        except Exception as e:
            print(f"[{ts()}] Token refresh error: {e}")


# ── Snapshot + stream URL cache ───────────────────────────────────

snap_cache    = {}   # name -> bytes
url_cache     = {}   # cam_code -> url
cache_lock    = threading.Lock()


def warm_cache(selected_cams):
    """Pre-fetch stream URLs and snapshots for all cams in background."""
    def _warm():
        # First pass: get all stream URLs fast
        for name, cam_code in selected_cams:
            url = get_stream_url(cam_code)
            if url:
                with cache_lock:
                    url_cache[cam_code] = url

        # Second pass: grab snapshots using cached URLs
        for name, cam_code in selected_cams:
            _refresh_snap(name, cam_code)

    threading.Thread(target=_warm, daemon=True).start()


def _refresh_snap(name, cam_code):
    with cache_lock:
        url = url_cache.get(cam_code)
    if not url:
        url = get_stream_url(cam_code)
        if not url:
            return
        with cache_lock:
            url_cache[cam_code] = url
    try:
        cmd = [
            "ffmpeg", "-y",
            "-i", url,
            "-vframes", "1",
            "-f", "image2",
            "-vcodec", "mjpeg",
            "pipe:1"
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        if result.returncode == 0 and result.stdout:
            with cache_lock:
                snap_cache[name] = result.stdout
    except Exception:
        pass


def snap_refresh_loop(selected_cams):
    """Refresh all snapshots every 10 seconds."""
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
        {"name": name, "stream": f"http://{ip}:{port}/cam/{urllib.parse.quote(name)}",
         "snap": f"http://{ip}:{port}/snap/{urllib.parse.quote(name)}"}
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
    min-height: 100vh;
  }
  header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px 20px;
    background: #111114;
    border-bottom: 1px solid #222;
    position: sticky;
    top: 0;
    z-index: 100;
  }
  header h1 { font-size: 18px; font-weight: 700; letter-spacing: -0.3px; }
  header .sub { font-size: 12px; color: #555; }
  header .count { font-size: 13px; color: #555; margin-left: auto; }

  #grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 10px;
    padding: 16px;
  }
  .cam-card {
    background: #111114;
    border: 1px solid #1e1e22;
    border-radius: 10px;
    overflow: hidden;
    cursor: pointer;
    transition: border-color 0.15s, transform 0.15s;
  }
  .cam-card:hover { border-color: #5865f2; transform: scale(1.015); }
  .cam-card img {
    width: 100%;
    aspect-ratio: 16/9;
    background: #0a0a0c;
    display: block;
    object-fit: cover;
  }
  .cam-card .label {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    font-size: 13px;
    font-weight: 600;
  }
  .dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: #22c55e;
  }
  .dot.off { background: #333; }

  #overlay {
    display: none;
    position: fixed;
    inset: 0;
    background: #000;
    z-index: 200;
    flex-direction: column;
  }
  #overlay.open { display: flex; }
  #overlay-bar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background: rgba(0,0,0,0.7);
    position: absolute;
    top: 0; left: 0; right: 0;
    z-index: 10;
    opacity: 0;
    transition: opacity 0.2s;
  }
  #overlay:hover #overlay-bar { opacity: 1; }
  #overlay-title { font-size: 16px; font-weight: 700; }
  #overlay-close {
    margin-left: auto;
    background: rgba(255,255,255,0.1);
    border: none; color: #fff;
    padding: 6px 14px;
    border-radius: 6px;
    cursor: pointer; font-size: 13px;
  }
  #overlay-close:hover { background: rgba(255,255,255,0.2); }
  #overlay video { width: 100%; height: 100%; object-fit: contain; }
  #cam-bar {
    position: absolute;
    bottom: 0; left: 0; right: 0;
    display: flex;
    gap: 6px;
    padding: 10px 14px;
    background: rgba(0,0,0,0.7);
    overflow-x: auto;
    scrollbar-width: none;
    opacity: 0;
    transition: opacity 0.2s;
    z-index: 10;
  }
  #overlay:hover #cam-bar { opacity: 1; }
  .pill {
    flex-shrink: 0;
    background: rgba(255,255,255,0.1);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 20px;
    padding: 5px 12px;
    font-size: 12px;
    cursor: pointer;
    white-space: nowrap;
    transition: background 0.1s;
    color: #fff;
  }
  .pill:hover, .pill.active { background: #5865f2; border-color: #5865f2; }
</style>
</head>
<body>

<header>
  <h1>Terrarium</h1>
  <span class="sub">Fishtank LIVE</span>
  <span class="count" id="count"></span>
</header>

<div id="grid"></div>

<div id="overlay">
  <div id="overlay-bar">
    <span id="overlay-title"></span>
    <button id="overlay-close">✕ Close</button>
  </div>
  <video id="overlay-video" autoplay playsinline controls></video>
  <div id="cam-bar"></div>
</div>

<script>
const CAMS = """ + cam_json + """;
let activeHls = null;
let activeIdx = null;

function loadSnap(img, snapUrl) {
  const tmp = new Image();
  tmp.onload = () => { img.src = tmp.src; img.closest('.cam-card').querySelector('.dot').classList.remove('off'); };
  tmp.onerror = () => { img.closest('.cam-card').querySelector('.dot').classList.add('off'); };
  tmp.src = snapUrl + '?t=' + Date.now();
}

function openCam(idx) {
  activeIdx = idx;
  const cam = CAMS[idx];
  document.getElementById('overlay-title').textContent = cam.name;
  document.getElementById('overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
  document.querySelectorAll('.pill').forEach((p, i) => p.classList.toggle('active', i === idx));
  const video = document.getElementById('overlay-video');
  if (activeHls) { activeHls.destroy(); activeHls = null; }
  if (Hls.isSupported()) {
    activeHls = new Hls();
    activeHls.loadSource(cam.stream);
    activeHls.attachMedia(video);
    video.play().catch(() => {});
  } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
    video.src = cam.stream;
    video.play().catch(() => {});
  }
}

function closeCam() {
  document.getElementById('overlay').classList.remove('open');
  document.body.style.overflow = '';
  if (activeHls) { activeHls.destroy(); activeHls = null; }
  document.getElementById('overlay-video').src = '';
  activeIdx = null;
}

const grid   = document.getElementById('grid');
const camBar = document.getElementById('cam-bar');
document.getElementById('count').textContent = CAMS.length + ' cameras';

CAMS.forEach((cam, idx) => {
  const card = document.createElement('div');
  card.className = 'cam-card';
  card.innerHTML = '<img alt="' + cam.name + '"><div class="label"><span>' + cam.name + '</span><span class="dot off"></span></div>';
  card.addEventListener('click', () => openCam(idx));
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
                    self._text(503, b"Snapshot not ready yet")
                return

            if path.startswith("cam/"):
                name = urllib.parse.unquote(path[4:])
                code = cam_map.get(name)
                if not code:
                    self._text(404, f"Unknown camera: {name}".encode())
                    return
                url = get_cached_stream_url(code)
                if not url:
                    self._text(503, b"Camera offline")
                    return
                try:
                    # Proxy the m3u8 playlist, rewriting segment URLs to
                    # go through us so the token stays fresh
                    r = requests.get(url, timeout=8)
                    if r.status_code != 200:
                        self._text(503, b"Stream unavailable")
                        return
                    ip = get_local_ip()
                    base = f"http://{ip}:{port}/seg/{urllib.parse.quote(name)}/"
                    lines = []
                    for line in r.text.splitlines():
                        if line.startswith("#") or not line.strip():
                            lines.append(line)
                        else:
                            # Rewrite relative segment URLs to go through proxy
                            lines.append(base + urllib.parse.quote(line, safe=""))
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
                seg   = urllib.parse.unquote(rest[slash+1:])
                code  = cam_map.get(name)
                if not code:
                    self._text(404, b"Unknown camera")
                    return
                stream_url = get_cached_stream_url(code)
                if not stream_url:
                    self._text(503, b"Camera offline")
                    return
                # Resolve seg relative to the master playlist directory
                master_base = stream_url.rsplit("/", 1)[0] + "/"
                seg_url     = master_base + seg
                try:
                    r = requests.get(seg_url, timeout=15, stream=True)
                    ct = r.headers.get("Content-Type", "")

                    if "mpegurl" in ct or seg.split("?")[0].endswith(".m3u8"):
                        # Use THIS playlist's base so relative .ts URLs resolve correctly
                        this_base = seg_url.split("?")[0].rsplit("/", 1)[0] + "/"
                        ip        = get_local_ip()
                        prx_base  = f"http://{ip}:{port}/seg/{urllib.parse.quote(name)}/"
                        lines     = []
                        for line in r.text.splitlines():
                            stripped = line.strip()
                            if not stripped or stripped.startswith("#"):
                                lines.append(line)
                            else:
                                # Build full Fishtank URL then encode it for our proxy
                                full = this_base + stripped if not stripped.startswith("http") else stripped
                                # Strip master_base prefix to get a path relative to master
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
                        # Raw .ts segment — stream straight through
                        # seg_url already correctly resolved above
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

        def _text(self, code, body):
            self.send_response(code)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def start_proxy(selected_cams, port):
    handler = make_handler(selected_cams, port)
    srv = HTTPServer(("0.0.0.0", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    # Warm cache immediately in background
    warm_cache(selected_cams)
    # Keep refreshing snapshots every 10s
    threading.Thread(target=lambda: snap_refresh_loop(selected_cams), daemon=True).start()
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
    try:   return int(raw) if raw else 6
    except: return 6


def pick_proxy_port():
    print("\n  Proxy port (Enter for 8888):")
    raw = input("  Port: ").strip()
    try:   return int(raw) if raw else 8888
    except: return 8888


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

    # ── Login ────────────────────────────────────────────────────
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

    # ── Mode ─────────────────────────────────────────────────────
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

    # ── Camera selection ─────────────────────────────────────────
    print()
    divider("─")
    print("  Camera Selection\n")
    selected_cams = pick_cameras()

    if not selected_cams:
        print("  No cameras selected — exiting.")
        sys.exit(0)

    print(f"  Selected: {', '.join(n for n, _ in selected_cams)}\n")

    # ── Options ──────────────────────────────────────────────────
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

    # ── Start ────────────────────────────────────────────────────
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
        daemon=True
    ).start()

    if do_record:
        threading.Thread(
            target=lambda: watchdog(selected_cams, save_dir, chunk_hours),
            daemon=True
        ).start()

    print(f"\n[{ts()}] Running. Ctrl+C to stop.\n")
    while not stop_event.is_set():
        time.sleep(1)