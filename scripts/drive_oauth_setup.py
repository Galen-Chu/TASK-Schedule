#!/usr/bin/env python3
"""One-time helper: obtain a Google OAuth refresh token for Drive upload.

Free-Gmail path (no Workspace shared drive needed): files uploaded with this
token are owned by YOUR account, which has storage quota.

Prerequisites (GCP console, same project as the service account):
1. APIs & Services → OAuth consent screen → External → fill App name/email
   → add your own Gmail as a Test user (or publish to production).
2. APIs & Services → Credentials → Create credentials → OAuth client ID
   → Application type "Desktop app" → copy the Client ID and Secret.

Then run:
    python scripts/drive_oauth_setup.py <CLIENT_ID> <CLIENT_SECRET>

A browser window opens; sign in with the Gmail that owns the target Drive
folder and approve. The refresh token is printed at the end — store it as
the GitHub secret ``GOOGLE_REFRESH_TOKEN`` (plus ``GOOGLE_OAUTH_CLIENT_ID``
and ``GOOGLE_OAUTH_CLIENT_SECRET``).

Note: while the consent screen is in "Testing" mode Google expires refresh
tokens after 7 days. For unattended daily runs, publish the app to
"In production" (unverified is fine for personal use) and re-run this once.
"""
import sys


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    client_id, client_secret = sys.argv[1], sys.argv[2]
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("請先安裝依賴：pip install google-auth-oauthlib")
        sys.exit(1)

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(
        client_config, scopes=["https://www.googleapis.com/auth/drive.file"])
    print("瀏覽器將開啟 Google 登入頁——請用「要收報告的那個 Gmail」登入並同意。")
    creds = flow.run_local_server(port=0)
    print("\n=========== REFRESH TOKEN ===========")
    print(creds.refresh_token)
    print("=====================================")
    print("存到 GitHub Secrets：GOOGLE_REFRESH_TOKEN（另需 GOOGLE_OAUTH_CLIENT_ID / _SECRET）")


if __name__ == "__main__":
    main()
