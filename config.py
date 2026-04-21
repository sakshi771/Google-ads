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


def _get_oauth_creds():
    """Build OAuth credentials reusable by both Google Ads and GA4."""
    return Credentials(
        token=None,
        refresh_token=_get_secret("GOOGLE_ADS_REFRESH_TOKEN"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=_get_secret("GOOGLE_ADS_CLIENT_ID"),
        client_secret=_get_secret("GOOGLE_ADS_CLIENT_SECRET"),
    )


def get_google_ads_client(login_customer_id=None):
    """Create and return an authenticated Google Ads API client."""
    kwargs = dict(
        credentials=_get_oauth_creds(),
        developer_token=_get_secret("GOOGLE_ADS_DEVELOPER_TOKEN"),
        use_proto_plus=True,
    )
    if login_customer_id:
        kwargs["login_customer_id"] = str(login_customer_id)
    return GoogleAdsClient(**kwargs)


def get_customer_id():
    """Return the Google Ads customer ID (without dashes)."""
    return _get_secret("GOOGLE_ADS_CUSTOMER_ID")


def get_us_customer_id():
    """Return the US Google Ads customer ID (without dashes)."""
    return _get_secret("US_GOOGLE_ADS_CUSTOMER_ID")


def get_us_login_customer_id():
    """Return the Manager (MCC) account ID used to access the US client account."""
    return _get_secret("US_LOGIN_CUSTOMER_ID")


def get_ga4_client():
    """Create and return an authenticated GA4 Data API client."""
    from google.analytics.data_v1beta import BetaAnalyticsDataClient

    return BetaAnalyticsDataClient(credentials=_get_oauth_creds())


def get_ga4_property_id():
    """Return the GA4 property ID."""
    return _get_secret("GA4_PROPERTY_ID")


def get_groq_api_key():
    """Return the Groq API key."""
    return _get_secret("GROQ_API_KEY")
