import os
from dotenv import load_dotenv
from google.ads.googleads.client import GoogleAdsClient

load_dotenv()


def _get_secret(key):
    """Read from Streamlit secrets (cloud) or .env (local)."""
    try:
        import streamlit as st
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key)


def get_google_ads_client():
    """Create and return an authenticated Google Ads API client."""
    credentials = {
        "developer_token": _get_secret("GOOGLE_ADS_DEVELOPER_TOKEN"),
        "client_id": _get_secret("GOOGLE_ADS_CLIENT_ID"),
        "client_secret": _get_secret("GOOGLE_ADS_CLIENT_SECRET"),
        "refresh_token": _get_secret("GOOGLE_ADS_REFRESH_TOKEN"),
        "token_uri": "https://oauth2.googleapis.com/token",
        "use_proto_plus": True,
    }
    return GoogleAdsClient.load_from_dict(credentials)


def get_customer_id():
    """Return the Google Ads customer ID (without dashes)."""
    return _get_secret("GOOGLE_ADS_CUSTOMER_ID")
