import json
import shutil
import subprocess
import threading
import time
import uuid
import webbrowser
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / ".env")

from uploaders import facebook, instagram, youtube  # noqa: E402  (.env load hone ke baad)
from uploaders.common import env  # noqa: E402

UPLOAD_DIR = BASE / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
PORT = 5050

PLATFORMS = {
    "youtube": ("YouTube", youtube),
    "facebook": ("Facebook", facebook),
    "instagram": ("Instagram", instagram),
}

app = Flask(__name__)
jobs = {}
job_inputs = {}  # job_id -> (path, meta), retry ke liye
lock = threading.Lock()


def platform_config():
    cfg = {}
    for key, (label, mod) in PLATFORMS.items():
        ok, reason = mod.is_configured()
        cfg[key] = {"label": label, "ok": ok, "reason": reason}

    # Meta ka login (Facebook + Instagram dono) ~90 din mein renew karna padta hai
    expires = env("META_USER_TOKEN_EXPIRES")
    if expires:
        days = (datetime.fromisoformat(expires) - datetime.now()).days
        if days < 0:
            warning = "Meta login expire ho gaya — python setup_meta.py dobara chalao"
        elif days <= 7:
            warning = f"Meta login {days} din mein expire hoga — python setup_meta.py dobara chalao"
        else:
            warning = None
        for key in ("facebook", "instagram"):
            if warning and cfg[key]["ok"]:
                cfg[key]["warning"] = warning
    return cfg


def probe(path):
    """ffprobe se duration aur resolution nikaalo (optional — na mile to khaali)."""
    if not shutil.which("ffprobe"):
        return {}
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height:format=duration", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=60,
        )
        data = json.loads(out.stdout)
        stream = data["streams"][0]
        return {
            "duration": float(data["format"]["duration"]),
            "width": stream["width"],
            "height": stream["height"],
        }
    except Exception:
        return {}


def ensure_mp4(path):
    """.mov/.mkv waghera ko bina re-encode kiye .mp4 mein badlo (Meta sirf mp4 maangta hai)."""
    if path.suffix.lower() == ".mp4" or not shutil.which("ffmpeg"):
        return path
    out = path.with_suffix(".mp4")
    r = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(path), "-c", "copy", "-movflags", "+faststart", str(out)],
        capture_output=True,
    )
    if r.returncode == 0 and out.exists():
        path.unlink()
        return out
    return path


def set_state(job_id, platform, **kw):
    with lock:
        jobs[job_id]["platforms"][platform].update(kw)


def run_upload(job_id, platform, path, meta):
    def progress(pct, msg=None):
        update = {"progress": round(min(pct, 99), 1)}
        if msg:
            update["message"] = msg
        set_state(job_id, platform, **update)

    set_state(job_id, platform, state="uploading", message="Shuru kar rahe hain…", started=time.time())
    try:
        url = PLATFORMS[platform][1].upload(str(path), meta, progress)
        set_state(job_id, platform, state="done", progress=100, message="Upload ho gaya ✓", url=url)
    except Exception as e:
        app.logger.exception("%s upload fail", platform)
        set_state(job_id, platform, state="error", message=str(e))


@app.get("/")
def index():
    return render_template("index.html", config=platform_config())


@app.get("/api/config")
def api_config():
    return jsonify(platform_config())


@app.post("/api/upload")
def api_upload():
    file = request.files.get("video")
    if not file or not file.filename:
        return jsonify(error="Video file chuno"), 400

    selected = [p for p in request.form.getlist("platforms") if p in PLATFORMS]
    if not selected:
        return jsonify(error="Kam se kam ek platform chuno"), 400
    cfg = platform_config()
    not_ready = [cfg[p]["label"] for p in selected if not cfg[p]["ok"]]
    if not_ready:
        return jsonify(error=f"Ye setup nahi hue: {', '.join(not_ready)}"), 400

    job_id = uuid.uuid4().hex[:10]
    name = secure_filename(file.filename) or "video.mp4"
    path = UPLOAD_DIR / f"{job_id}_{name}"
    file.save(path)
    path = ensure_mp4(path)
    info = probe(path)

    title = request.form.get("title", "").strip() or Path(file.filename).stem
    meta = {
        "title": title,
        "description": request.form.get("description", "").strip(),
        "tags": [t.strip().lstrip("#") for t in request.form.get("tags", "").split(",") if t.strip()],
        "youtube_privacy": request.form.get("youtube_privacy", "public"),
        "made_for_kids": request.form.get("made_for_kids") == "on",
        "facebook_mode": request.form.get("facebook_mode", "video"),
        "duration": info.get("duration"),
    }

    with lock:
        jobs[job_id] = {
            "id": job_id,
            "file": path.name,
            "info": info,
            "created": time.time(),
            "platforms": {
                p: {"label": PLATFORMS[p][0], "state": "queued", "progress": 0, "message": "Line mein hai…", "url": None}
                for p in selected
            },
        }
        job_inputs[job_id] = (path, meta)
    for p in selected:
        threading.Thread(target=run_upload, args=(job_id, p, path, meta), daemon=True).start()
    return jsonify(job_id=job_id, info=info)


@app.get("/api/jobs/<job_id>")
def api_job(job_id):
    with lock:
        job = jobs.get(job_id)
        if not job:
            return jsonify(error="Job nahi mila"), 404
        return jsonify(json.loads(json.dumps(job)))


@app.post("/api/jobs/<job_id>/retry/<platform>")
def api_retry(job_id, platform):
    with lock:
        job = jobs.get(job_id)
        if not job or platform not in job["platforms"] or job_id not in job_inputs:
            return jsonify(error="Job nahi mila"), 404
        if job["platforms"][platform]["state"] != "error":
            return jsonify(error="Sirf fail hua upload dobara ho sakta hai"), 400
        job["platforms"][platform].update(state="queued", progress=0, message="Dobara try kar rahe hain…", url=None)
        path, meta = job_inputs[job_id]
    threading.Thread(target=run_upload, args=(job_id, platform, path, meta), daemon=True).start()
    return jsonify(ok=True)


if __name__ == "__main__":
    url = f"http://127.0.0.1:{PORT}"
    print(f"\n  Social Uploader chal raha hai: {url}\n  Band karne ke liye Ctrl+C\n")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=PORT, threaded=True, debug=False)
