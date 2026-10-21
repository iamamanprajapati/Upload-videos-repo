from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from .common import env

BASE = Path(__file__).resolve().parent.parent
CLIENT_SECRET = BASE / "credentials" / "client_secret.json"
TOKEN = BASE / "credentials" / "youtube_token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def is_configured():
    if not TOKEN.exists():
        return False, "Setup baaki hai: python setup_youtube.py chalao"
    return True, ""


def _creds():
    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            TOKEN.write_text(creds.to_json())
        else:
            raise RuntimeError("YouTube login expire ho gaya — python setup_youtube.py dobara chalao")
    return creds


def upload(path, meta, progress):
    try:
        yt = build("youtube", "v3", credentials=_creds(), cache_discovery=False)
    except Exception as e:
        if "invalid_grant" in str(e):
            raise RuntimeError("YouTube login expire ho gaya — python setup_youtube.py dobara chalao") from e
        raise

    # YouTube title mein < > allowed nahi, aur max 100 characters
    title = meta["title"].replace("<", "").replace(">", "")[:100] or "Untitled"
    body = {
        "snippet": {
            "title": title,
            "description": meta["description"].replace("<", "").replace(">", "")[:5000],
            "tags": meta["tags"],
            "categoryId": env("YOUTUBE_CATEGORY_ID", "22"),
        },
        "status": {
            "privacyStatus": meta["youtube_privacy"],
            "selfDeclaredMadeForKids": meta["made_for_kids"],
        },
    }
    media = MediaFileUpload(path, chunksize=8 * 1024 * 1024, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)

    progress(1, "YouTube pe bhej rahe hain…")
    resp = None
    while resp is None:
        status, resp = req.next_chunk(num_retries=5)
        if status:
            progress(status.progress() * 98, "YouTube pe bhej rahe hain…")
    return f"https://youtu.be/{resp['id']}"
