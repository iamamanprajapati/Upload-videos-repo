import os
import time

import requests

from .common import ProgressFile, api_version, check, env, graph_url


def is_configured():
    if not (env("FB_PAGE_ID") and env("FB_PAGE_TOKEN")):
        return False, "Setup baaki hai: python setup_meta.py chalao"
    return True, ""


def upload(path, meta, progress):
    if meta["facebook_mode"] == "reel":
        return _upload_reel(path, meta, progress)
    return _upload_video(path, meta, progress)


def _upload_video(path, meta, progress):
    """Normal Page video: Resumable Upload API (user token) se file, phir Page token se publish."""
    page_id, page_token = env("FB_PAGE_ID"), env("FB_PAGE_TOKEN")
    app_id, user_token = env("META_APP_ID"), env("META_USER_TOKEN")
    if not (app_id and user_token):
        raise RuntimeError("META_APP_ID / META_USER_TOKEN missing — python setup_meta.py chalao")

    size = os.path.getsize(path)
    progress(1, "Upload session bana rahe hain…")
    r = check(requests.post(
        graph_url(f"{app_id}/uploads"),
        params={
            "file_name": os.path.basename(path),
            "file_length": size,
            "file_type": "video/mp4",
            "access_token": user_token,
        },
        timeout=60,
    ))
    session = r["id"]  # "upload:<session-id>"

    with ProgressFile(path, lambda f: progress(2 + f * 88, "Facebook pe bhej rahe hain…")) as body:
        r = check(requests.post(
            graph_url(session),
            headers={"Authorization": f"OAuth {user_token}", "file_offset": "0"},
            data=body,
            timeout=None,
        ))
    handle = r["h"]

    progress(92, "Page pe publish kar rahe hain…")
    r = check(requests.post(
        graph_url(f"{page_id}/videos"),
        data={
            "access_token": page_token,
            "title": meta["title"],
            "description": meta["description"],
            "fbuploader_video_file_chunk": handle,
        },
        timeout=600,
    ))
    return f"https://www.facebook.com/{page_id}/videos/{r['id']}"


def _upload_reel(path, meta, progress):
    """Facebook Page Reel (3-90 sec, vertical 9:16). Sirf Page token chahiye."""
    page_id, page_token = env("FB_PAGE_ID"), env("FB_PAGE_TOKEN")
    duration = meta.get("duration")
    if duration and not (3 <= duration <= 90):
        raise RuntimeError(f"Facebook Reel 3-90 second ka hona chahiye (ye {duration:.0f}s hai) — 'Video' mode chuno")

    size = os.path.getsize(path)
    progress(1, "Reel session bana rahe hain…")
    r = check(requests.post(
        graph_url(f"{page_id}/video_reels"),
        data={"upload_phase": "start", "access_token": page_token},
        timeout=60,
    ))
    video_id = r["video_id"]

    with ProgressFile(path, lambda f: progress(2 + f * 83, "Facebook pe bhej rahe hain…")) as body:
        check(requests.post(
            f"https://rupload.facebook.com/video-upload/{api_version()}/{video_id}",
            headers={"Authorization": f"OAuth {page_token}", "offset": "0", "file_size": str(size)},
            data=body,
            timeout=None,
        ))

    progress(88, "Reel publish kar rahe hain…")
    check(requests.post(
        graph_url(f"{page_id}/video_reels"),
        data={
            "access_token": page_token,
            "video_id": video_id,
            "upload_phase": "finish",
            "video_state": "PUBLISHED",
            "title": meta["title"],
            "description": meta["description"],
        },
        timeout=120,
    ))

    # Processing/publishing poora hone tak wait
    deadline = time.time() + 15 * 60
    while time.time() < deadline:
        s = check(requests.get(
            graph_url(video_id),
            params={"fields": "status", "access_token": page_token},
            timeout=60,
        )).get("status", {})
        vs = s.get("video_status")
        if vs in ("error", "expired", "upload_failed"):
            raise RuntimeError(f"Facebook ne Reel reject kar diya: {s}")
        if vs == "ready" or s.get("publishing_phase", {}).get("status") in ("complete", "completed"):
            break
        progress(92, f"Facebook process kar raha hai ({vs})…")
        time.sleep(5)
    return f"https://www.facebook.com/reel/{video_id}"
