import os
from dotenv import load_dotenv
from google.ads.googleads.client import GoogleAdsClient
from google.oauth2.credentials import Credentials

load_dotenv()


def _get_secret(key):
    """Read from Streamlit secrets (cloud) or .env (local)."""
    try:
        import streamlit as st
        if key in st.secrets:
            return str(st.secrets[key]).strip()
    except Exception:
        pass
    val = os.getenv(key)
    return val.strip() if val else val


def get_google_ads_client():
    """Create and return an authenticated Google Ads API client."""
    client_id = _get_secret("GOOGLE_ADS_CLIENT_ID")
    client_secret = _get_secret("GOOGLE_ADS_CLIENT_SECRET")
    refresh_token = _get_secret("GOOGLE_ADS_REFRESH_TOKEN")
    developer_token = _get_secret("GOOGLE_ADS_DEVELOPER_TOKEN")

    oauth_creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
    )

    return GoogleAdsClient(
        credentials=oauth_creds,
        developer_token=developer_token,
        use_proto_plus=True,
    )


def get_customer_id():
    """Return the Google Ads customer ID (without dashes)."""
    return _get_secret("GOOGLE_ADS_CUSTOMER_ID")
