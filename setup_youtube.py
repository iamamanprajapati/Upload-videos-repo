"""YouTube login (ek baar). Browser khulega, apne channel wale Google account se allow karo."""
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

from uploaders.youtube import CLIENT_SECRET, SCOPES, TOKEN

if not CLIENT_SECRET.exists():
    sys.exit(
        f"\n✗ {CLIENT_SECRET} nahi mila.\n"
        "  Google Cloud Console se OAuth client (type: Desktop app) ka JSON download karke\n"
        "  is naam se credentials/ folder mein rakho. Steps README.md mein hain.\n"
    )

flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
TOKEN.write_text(creds.to_json())
print(f"\n✓ YouTube login save ho gaya: {TOKEN}\n")
