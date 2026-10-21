import json
import os
import subprocess
import time
from pathlib import Path

import requests

from .common import ProgressFile, api_version, check, env, graph_url

# Instagram Reels API ki limits (isse bada video "ProcessingFailedError" deta hai)
MAX_SIDE = 1920
MAX_BITRATE = 25_000_000
MAX_FPS = 60
MAX_BYTES = 280 * 1024 * 1024  # 300MB limit se thoda neeche


def _probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration,bit_rate,size:stream=codec_type,codec_name,width,height,r_frame_rate",
         "-of", "json", path],
        capture_output=True, text=True, timeout=60,
    )
    data = json.loads(out.stdout or "{}")
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    audio = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    num, _, den = (video.get("r_frame_rate") or "0/1").partition("/")
    fmt = data.get("format", {})
    return {
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "fps": float(num) / float(den or 1) if float(den or 1) else 0,
        "vcodec": video.get("codec_name"),
        "acodec": audio.get("codec_name") if audio else None,
        "duration": float(fmt.get("duration") or 0),
        "bitrate": int(fmt.get("bit_rate") or 0),
        "size": int(fmt.get("size") or 0),
    }


def _prepare(path, progress):
    """Video Instagram ki limit se bada ho to ek chhoti (max 1920px, H.264/AAC) copy banao."""
    try:
        info = _probe(path)
    except Exception:
        return path  # ffprobe na chale to original hi try karo
    too_big = (
        max(info["width"], info["height"]) > MAX_SIDE
        or info["bitrate"] > MAX_BITRATE
        or info["fps"] > MAX_FPS + 0.5
        or info["size"] > MAX_BYTES
        or info["vcodec"] not in ("h264", "hevc")
        or info["acodec"] not in (None, "aac")
    )
    if not too_big:
        return path

    out = Path(path).with_name(Path(path).stem + "_ig.mp4")
    if out.exists():
        return str(out)

    duration = info["duration"] or 1
    # Bitrate itni rakho ki file 280MB se chhoti rahe, aur 20 Mbps se zyada na ho
    maxrate = int(min(20_000_000, MAX_BYTES * 8 / duration - 192_000))
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", path]
    if max(info["width"], info["height"]) > MAX_SIDE:
        cmd += ["-vf", f"scale={MAX_SIDE}:{MAX_SIDE}:force_original_aspect_ratio=decrease:force_divisible_by=2"]
    if info["fps"] > MAX_FPS + 0.5:
        cmd += ["-r", "30"]
    cmd += [
        # Instagram baad mein khud compress karta hai, isliye yahan high quality (CRF 18) rakho
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-maxrate", str(maxrate), "-bufsize", str(maxrate * 2),
        "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", "-progress", "pipe:1", "-nostats", str(out) + ".part.mp4",
    ]
    progress(1, "Instagram ke liye video chhota kar rahe hain…")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for line in proc.stdout:
        if line.startswith("out_time_us="):
            try:
                done = int(line.split("=", 1)[1]) / 1e6
                progress(1 + min(done / duration, 1) * 24, f"Instagram ke liye video chhota kar rahe hain… {min(done / duration, 1) * 100:.0f}%")
            except ValueError:
                pass
    if proc.wait() != 0:
        raise RuntimeError(f"Video convert nahi ho paaya: {proc.stderr.read()[-300:]}")
    os.replace(str(out) + ".part.mp4", out)
    return str(out)


def is_configured():
    if not (env("IG_USER_ID") and env("FB_PAGE_TOKEN")):
        return False, "Setup baaki hai: Instagram Professional account ko FB Page se link karke python setup_meta.py chalao"
    return True, ""


def upload(path, meta, progress):
    """Instagram Reel: container banao -> rupload pe file bhejo -> processing ka wait -> publish."""
    ig_id, token = env("IG_USER_ID"), env("FB_PAGE_TOKEN")
    path = _prepare(path, progress)
    size = os.path.getsize(path)

    progress(26, "Instagram container bana rahe hain…")
    r = check(requests.post(
        graph_url(f"{ig_id}/media"),
        data={
            "media_type": "REELS",
            "upload_type": "resumable",
            "caption": meta["description"][:2200],
            "access_token": token,
        },
        timeout=60,
    ))
    container_id = r["id"]
    upload_uri = r.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{api_version()}/{container_id}"

    with ProgressFile(path, lambda f: progress(27 + f * 55, "Instagram pe bhej rahe hain…")) as body:
        try:
            check(requests.post(
                upload_uri,
                headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size)},
                data=body,
                timeout=None,
            ))
        except RuntimeError as e:
            if "ProcessingFailedError" in str(e):
                raise RuntimeError(
                    "Instagram ne video reject kar diya (format/size). "
                    "MP4, H.264, max 1920px, 3 sec–15 min wala video try karo."
                ) from e
            raise

    deadline = time.time() + 20 * 60
    while True:
        s = check(requests.get(
            graph_url(container_id),
            params={"fields": "status_code,status", "access_token": token},
            timeout=60,
        ))
        code = s.get("status_code")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram processing fail: {s.get('status') or code}")
        if time.time() > deadline:
            raise RuntimeError("Instagram 20 min mein video process nahi kar paaya")
        progress(85, "Instagram video process kar raha hai…")
        time.sleep(5)

    progress(95, "Instagram pe publish kar rahe hain…")
    r = check(requests.post(
        graph_url(f"{ig_id}/media_publish"),
        data={"creation_id": container_id, "access_token": token},
        timeout=120,
    ))
    media_id = r["id"]
    try:
        link = check(requests.get(
            graph_url(media_id),
            params={"fields": "permalink", "access_token": token},
            timeout=30,
        )).get("permalink")
    except Exception:
        link = None
    return link or "https://www.instagram.com/"
