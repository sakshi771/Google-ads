import os
from dotenv import load_dotenv
from google.ads.googleads.client import GoogleAdsClient

load_dotenv()


def get_google_ads_client():
    """Create and return an authenticated Google Ads API client."""
    credentials = {
        "developer_token": os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN"),
        "client_id": os.getenv("GOOGLE_ADS_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_ADS_CLIENT_SECRET"),
        "refresh_token": os.getenv("GOOGLE_ADS_REFRESH_TOKEN"),
        "use_proto_plus": True,
    }
    credentials["use_rest"] = True
    return GoogleAdsClient.load_from_dict(credentials)


def get_customer_id():
    """Return the Google Ads customer ID (without dashes)."""
    return os.getenv("GOOGLE_ADS_CUSTOMER_ID")
