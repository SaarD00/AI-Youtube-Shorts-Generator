"""
Mobile-friendly web UI for AutoShorts AI.

Starts generation jobs, streams their log, and lists the finished videos for
download — so a short can be produced and saved from a phone.

    python webapp.py --host 0.0.0.0 --port 8000

Set APP_PASSWORD to expose it beyond localhost. Without it the server refuses
any host but 127.0.0.1: an open instance lets anyone burn your Gemini and
Pexels quota.
"""
import argparse
import os
import secrets
import subprocess
import sys
import threading
from datetime import datetime
from functools import wraps

from dotenv import load_dotenv
from flask import (Flask, abort, redirect, render_template, request,
                   send_file, session, url_for)

load_dotenv()

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
FINAL_DIR = os.path.join(PROJECT_ROOT, "assets", "final")

VOICES = [
    ("en-US-AvaNeural", "Ava — US female"),
    ("en-US-AndrewNeural", "Andrew — US male"),
    ("en-GB-SoniaNeural", "Sonia — UK female"),
    ("en-GB-RyanNeural", "Ryan — UK male"),
    ("en-AU-NatashaNeural", "Natasha — AU female"),
    ("pt-BR-FranciscaNeural", "Francisca — BR female"),
    ("pt-BR-AntonioNeural", "Antonio — BR male"),
]

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32)


class Job:
    """
    Tracks the one generation run allowed at a time. Rendering saturates the
    CPU, so a second concurrent run would only make both slower.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.process = None
        self.lines = []
        self.started_at = None
        self.finished_at = None
        self.returncode = None
        self.command = None

    @property
    def running(self):
        return self.process is not None and self.process.poll() is None

    def start(self, argv):
        with self.lock:
            if self.running:
                return False
            self.lines = []
            self.started_at = datetime.now()
            self.finished_at = None
            self.returncode = None
            self.command = " ".join(argv[1:])
            self.process = subprocess.Popen(
                argv,
                cwd=PROJECT_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                # Unbuffered child output, otherwise the log only appears at the end.
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )

        threading.Thread(target=self._drain, daemon=True).start()
        return True

    def _drain(self):
        process = self.process
        for line in process.stdout:
            line = line.rstrip()
            # ffmpeg's progress carriage-returns would flood the log.
            if not line or line.startswith("frame=") or line.startswith("["):
                continue
            self.lines.append(line)
            # Keep memory bounded on long batches.
            if len(self.lines) > 2000:
                del self.lines[:500]
        process.wait()
        self.returncode = process.returncode
        self.finished_at = datetime.now()

    def stop(self):
        with self.lock:
            if self.running:
                self.process.terminate()
                self.lines.append("🛑 Stopped by user.")
                return True
        return False

    def snapshot(self):
        return {
            "running": self.running,
            "lines": list(self.lines),
            "returncode": self.returncode,
            "command": self.command,
            "started_at": self.started_at.strftime("%H:%M:%S") if self.started_at else None,
        }


job = Job()


def password_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not os.getenv("APP_PASSWORD") or session.get("authed"):
            return view(*args, **kwargs)
        return redirect(url_for("login", next=request.path))
    return wrapper


def list_videos():
    if not os.path.isdir(FINAL_DIR):
        return []

    videos = []
    for name in os.listdir(FINAL_DIR):
        if not name.endswith(".mp4"):
            continue
        path = os.path.join(FINAL_DIR, name)
        stat = os.stat(path)
        videos.append({
            "name": name,
            "size_mb": round(stat.st_size / (1024 * 1024), 1),
            "created": datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m %H:%M"),
            "mtime": stat.st_mtime,
        })

    videos.sort(key=lambda v: v["mtime"], reverse=True)
    return videos


def safe_video_path(name):
    """
    Resolves name inside FINAL_DIR, refusing anything that escapes it.
    """
    path = os.path.abspath(os.path.join(FINAL_DIR, name))
    if os.path.dirname(path) != os.path.abspath(FINAL_DIR) or not os.path.exists(path):
        abort(404)
    return path


@app.route("/login", methods=["GET", "POST"])
def login():
    expected = os.getenv("APP_PASSWORD")
    if not expected:
        return redirect(url_for("index"))

    error = None
    if request.method == "POST":
        # Constant-time compare so the password cannot be guessed by timing.
        if secrets.compare_digest(request.form.get("password", ""), expected):
            session["authed"] = True
            return redirect(request.args.get("next") or url_for("index"))
        error = "Wrong password."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@password_required
def index():
    return render_template(
        "index.html",
        voices=VOICES,
        videos=list_videos(),
        protected=bool(os.getenv("APP_PASSWORD")),
    )


@app.route("/generate", methods=["POST"])
@password_required
def generate():
    if job.running:
        return {"ok": False, "error": "A run is already in progress."}, 409

    argv = [sys.executable, "main.py"]

    topic = (request.form.get("topic") or "").strip()
    if topic:
        argv += ["--topic", topic]

    voice = request.form.get("voice") or "en-US-AvaNeural"
    if voice not in dict(VOICES):
        return {"ok": False, "error": "Unknown voice."}, 400
    argv += ["--voice", voice]

    try:
        runs = max(1, min(10, int(request.form.get("runs", 1))))
    except ValueError:
        runs = 1
    argv += ["--runs", str(runs)]

    if not job.start(argv):
        return {"ok": False, "error": "A run is already in progress."}, 409
    return {"ok": True}


@app.route("/stop", methods=["POST"])
@password_required
def stop():
    return {"ok": job.stop()}


@app.route("/api/status")
@password_required
def status():
    payload = job.snapshot()
    payload["videos"] = list_videos()
    return payload


@app.route("/videos/<path:name>")
@password_required
def video(name):
    return send_file(safe_video_path(name), mimetype="video/mp4", conditional=True)


@app.route("/download/<path:name>")
@password_required
def download(name):
    return send_file(safe_video_path(name), as_attachment=True, download_name=name)


@app.route("/delete/<path:name>", methods=["POST"])
@password_required
def delete(name):
    os.remove(safe_video_path(name))
    return {"ok": True}


def main():
    parser = argparse.ArgumentParser(description="Web UI for AutoShorts AI.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1).")
    parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000).")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    if args.host != "127.0.0.1" and not os.getenv("APP_PASSWORD"):
        parser.error(
            "Refusing to listen on a public address without APP_PASSWORD set. "
            "Anyone who finds the URL could spend your Gemini and Pexels quota. "
            "Set APP_PASSWORD in your .env and try again."
        )

    if not os.getenv("FLASK_SECRET_KEY"):
        print("⚠️ FLASK_SECRET_KEY not set — using a random key, so logins drop on restart.")

    print(f"🌐 http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)


if __name__ == "__main__":
    main()
