"""
Helper script to generate a Google Ads API refresh token.

Run this AFTER you have your Client ID and Client Secret from Google Cloud Console.

Usage:
    python get_refresh_token.py

It will open your browser to authorize the app, then print your refresh token.
Add the refresh token to your .env file.
"""

import os
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/adwords",
    "https://www.googleapis.com/auth/analytics.readonly",
]


def main():
    client_id = os.getenv("GOOGLE_ADS_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_ADS_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("ERROR: Please set GOOGLE_ADS_CLIENT_ID and GOOGLE_ADS_CLIENT_SECRET")
        print("in your .env file before running this script.")
        return

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    credentials = flow.run_local_server(port=8080)

    print("\n" + "=" * 50)
    print("SUCCESS! Here is your refresh token:")
    print("=" * 50)
    print(credentials.refresh_token)
    print("=" * 50)
    print("\nCopy this token and paste it as GOOGLE_ADS_REFRESH_TOKEN in your .env file.")


if __name__ == "__main__":
    main()
