"""
One-time YouTube authorization.

Run this on a machine with a browser. It opens the Google consent screen once
and prints a refresh token that never needs a browser again — put that token in
your .env (local runs) or in repository secrets (GitHub Actions).

    python authorize_youtube.py --client-id XXX --client-secret YYY

Get the client id/secret from Google Cloud Console → APIs & Services →
Credentials → Create OAuth client ID → Desktop app, with the YouTube Data API v3
enabled for the project.
"""
import argparse
import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

from modules.publisher import SCOPES


def main():
    parser = argparse.ArgumentParser(description="Mint a YouTube refresh token.")
    parser.add_argument("--client-id", default=os.getenv("YOUTUBE_CLIENT_ID"),
                        help="OAuth client id (or set YOUTUBE_CLIENT_ID).")
    parser.add_argument("--client-secret", default=os.getenv("YOUTUBE_CLIENT_SECRET"),
                        help="OAuth client secret (or set YOUTUBE_CLIENT_SECRET).")
    args = parser.parse_args()

    if not args.client_id or not args.client_secret:
        parser.error("--client-id and --client-secret are required.")

    client_config = {
        "installed": {
            "client_id": args.client_id,
            "client_secret": args.client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    # prompt='consent' forces Google to return a refresh token even if this
    # account already granted the scope on a previous run.
    credentials = flow.run_local_server(port=0, prompt="consent", access_type="offline")

    if not credentials.refresh_token:
        print("❌ Google did not return a refresh token. Revoke the app's access at "
              "https://myaccount.google.com/permissions and run this again.")
        return 1

    print("\n✅ Authorized. Add these to your .env (or to repository secrets):\n")
    print(f"YOUTUBE_CLIENT_ID={args.client_id}")
    print(f"YOUTUBE_CLIENT_SECRET={args.client_secret}")
    print(f"YOUTUBE_REFRESH_TOKEN={credentials.refresh_token}")
    print("\n⚠️ While the Google Cloud project is in 'Testing' mode this token "
          "expires after 7 days. Publish the app (Testing → In production) to "
          "make it long-lived.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
