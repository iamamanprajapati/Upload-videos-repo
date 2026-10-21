"""Facebook Page + Instagram setup (ek baar, aur 'Video' mode ke liye har ~60 din mein).

Graph API Explorer se short-lived User token lo, ye script use:
  1. 60-din wale long-lived user token mein badlegi
  2. aapke Pages dikhayegi, aap ek chunoge
  3. us Page ka (kabhi expire na hone wala) Page token aur linked Instagram account ID .env mein save karegi
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv, set_key

from uploaders.common import check

ENV = Path(__file__).resolve().parent / ".env"
ENV.touch(exist_ok=True)
load_dotenv(ENV)


def ask(name, prompt):
    val = os.getenv(name, "").strip()
    if val:
        print(f"{prompt}: (.env se) {val[:6]}…")
        return val
    return input(f"{prompt}: ").strip()


ver = os.getenv("META_API_VERSION", "").strip() or "v26.0"
graph = f"https://graph.facebook.com/{ver}"

app_id = ask("META_APP_ID", "Meta App ID")
app_secret = ask("META_APP_SECRET", "Meta App Secret")
short_token = input("Graph API Explorer wala User Access Token paste karo: ").strip()
if not (app_id and app_secret and short_token):
    sys.exit("✗ App ID, App Secret aur token teeno chahiye")

r = check(requests.get(f"{graph}/oauth/access_token", params={
    "grant_type": "fb_exchange_token",
    "client_id": app_id,
    "client_secret": app_secret,
    "fb_exchange_token": short_token,
}, timeout=30))
user_token = r["access_token"]
expires = datetime.now() + timedelta(seconds=int(r.get("expires_in") or 60 * 24 * 3600))

pages = check(requests.get(f"{graph}/me/accounts", params={
    "fields": "id,name,access_token,instagram_business_account{id,username}",
    "access_token": user_token,
    "limit": 100,
}, timeout=30)).get("data", [])

if not pages:
    sys.exit(
        "✗ Koi Page nahi mila. Token banate waqt ye permissions select ki thi?\n"
        "  pages_show_list, pages_read_engagement, pages_manage_posts,\n"
        "  instagram_basic, instagram_content_publish, business_management\n"
        "  Aur login dialog mein apna Page select karna mat bhoolna."
    )

print("\nAapke Pages:")
for i, p in enumerate(pages, 1):
    ig = p.get("instagram_business_account")
    ig_txt = f"Instagram: @{ig.get('username', ig['id'])}" if ig else "Instagram linked nahi"
    print(f"  {i}. {p['name']}  ({ig_txt})")
choice = input("\nKaunsa Page? number likho [1]: ").strip() or "1"
page = pages[int(choice) - 1]

# Asli expiry: token ki expiry aur Meta ki 90-din wali "data access" expiry mein jo pehle aaye
for tok in (user_token, page["access_token"]):
    d = check(requests.get(f"{graph}/debug_token", params={
        "input_token": tok, "access_token": f"{app_id}|{app_secret}",
    }, timeout=30)).get("data", {})
    for ts in (d.get("expires_at"), d.get("data_access_expires_at")):
        if ts:
            expires = min(expires, datetime.fromtimestamp(ts))

values = {
    "META_API_VERSION": ver,
    "META_APP_ID": app_id,
    "META_APP_SECRET": app_secret,
    "META_USER_TOKEN": user_token,
    "META_USER_TOKEN_EXPIRES": expires.date().isoformat(),
    "FB_PAGE_ID": page["id"],
    "FB_PAGE_TOKEN": page["access_token"],
    "IG_USER_ID": (page.get("instagram_business_account") or {}).get("id", ""),
}
for k, v in values.items():
    set_key(str(ENV), k, v)

print(f"\n✓ Facebook Page '{page['name']}' save ho gaya")
if values["IG_USER_ID"]:
    print(f"✓ Instagram account ({values['IG_USER_ID']}) save ho gaya")
else:
    print("! Is Page se koi Instagram Professional account linked nahi — Instagram upload kaam nahi karega")
print(f"  Facebook/Instagram login {values['META_USER_TOKEN_EXPIRES']} tak valid hai — uske pehle ye script dobara chala dena\n")
