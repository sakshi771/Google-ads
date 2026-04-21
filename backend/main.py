import re
import sys
import os
import time
import threading
from collections import OrderedDict
from datetime import date, timedelta
from calendar import monthrange
from typing import Optional, Dict

import requests
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import gspread
from google.oauth2.credentials import Credentials

CACHE_TTL = 300          # 5 minutes for Google Ads / Sheets data
HUBSPOT_CACHE_TTL = 3600  # 1 hour for HubSpot
HUBSPOT_DISK_CACHE = os.path.join(os.path.dirname(__file__), ".hubspot_cache.json")


class _TTLLRUCache:
    """Thread-safe LRU cache with TTL eviction and max-size cap."""

    def __init__(self, maxsize: int = 512):
        self._data: OrderedDict = OrderedDict()
        self._maxsize = maxsize
        self._lock = threading.Lock()

    def get(self, key: str):
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            self._data.move_to_end(key)
            return entry

    def set(self, key: str, value: dict):
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = value
            # Evict LRU entries beyond maxsize
            while len(self._data) > self._maxsize:
                self._data.popitem(last=False)

    def clear_expired(self, ttl: float):
        """Purge entries older than ttl seconds (call periodically)."""
        cutoff = time.time() - ttl
        with self._lock:
            stale = [k for k, v in self._data.items() if v.get("ts", 0) < cutoff]
            for k in stale:
                del self._data[k]

    def __len__(self):
        with self._lock:
            return len(self._data)


_cache = _TTLLRUCache(maxsize=512)

# Pending-request dedup: prevents thundering herd on identical concurrent calls
_pending: Dict[str, threading.Event] = {}
_pending_lock = threading.Lock()


def _cache_get_or_fetch(cache_key: str, ttl: float, fetch_fn):
    """
    Thread-safe: return cached value if fresh, otherwise call fetch_fn once
    and share the result with any concurrent callers waiting on the same key.
    """
    cached = _cache.get(cache_key)
    if cached and time.time() - cached["ts"] < ttl:
        return cached["data"]

    # Check if another thread is already fetching this key
    with _pending_lock:
        if cache_key in _pending:
            event = _pending[cache_key]
        else:
            event = threading.Event()
            _pending[cache_key] = event
            event = None  # We are the fetcher

    if event is not None:
        # Wait for the fetcher thread to finish (max 30 s)
        event.wait(timeout=30)
        cached = _cache.get(cache_key)
        if cached:
            return cached["data"]
        # Fetcher failed — fall through and try ourselves
        return fetch_fn()

    # We are the fetcher
    try:
        data = fetch_fn()
        _cache.set(cache_key, {"data": data, "ts": time.time()})
        return data
    finally:
        with _pending_lock:
            ev = _pending.pop(cache_key, None)
        if ev:
            ev.set()

# Import config from parent directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import get_google_ads_client, get_customer_id, get_us_customer_id, get_us_login_customer_id, get_groq_api_key, _get_secret

SHEET_ID = "1k4lq7RHVEhPhr5uWSanyK1VJnWCJy4dGnS7hLnec1W0"
SHEET_TAB = "Data"
US_SHEET_TAB = "US - data"

# HubSpot pipeline stages (Client Acquisition pipeline)
HUBSPOT_SAL_STAGE = "1047744293"
HUBSPOT_SQL_STAGES = {"244798990", "249283938", "244798994", "244798992", "244798995"}
# SAL++ = SAL and beyond (stages 3+)
HUBSPOT_SAL_PLUS_STAGES = {HUBSPOT_SAL_STAGE} | HUBSPOT_SQL_STAGES
HUBSPOT_PIPELINE = "default"

app = FastAPI(title="Google Ads Dashboard API")

# Allow localhost in dev + any production frontend URL set via env
_allowed_origins = ["http://localhost:5173", "http://localhost:4173"]
_frontend_url = os.getenv("FRONTEND_URL", "")
if _frontend_url:
    _allowed_origins.append(_frontend_url.rstrip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Optional password gate — set APP_PASSWORD env var to enable
# ---------------------------------------------------------------------------
from fastapi import Request
from fastapi.responses import JSONResponse

_APP_PASSWORD = os.getenv("APP_PASSWORD", "")

@app.middleware("http")
async def _password_gate(request: Request, call_next):
    if not _APP_PASSWORD:
        return await call_next(request)
    # Health check always passes
    if request.url.path in ("/", "/health"):
        return await call_next(request)
    token = request.headers.get("X-App-Password", "")
    if token != _APP_PASSWORD:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    return await call_next(request)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.on_event("startup")
def _warmup_cache():
    """Preload HubSpot deal data at startup and start periodic cache janitor."""
    def _load():
        try:
            sal_names, sql_names = _fetch_hubspot_deals()
            print(f"[startup] HubSpot cache warmed: {len(sal_names)} SAL+, {len(sql_names)} SQL+ names")
        except Exception as e:
            print(f"[startup] HubSpot warmup failed: {e}")

    def _janitor():
        """Evict expired entries every 10 minutes to keep memory bounded."""
        while True:
            time.sleep(600)
            _cache.clear_expired(CACHE_TTL)
            print(f"[janitor] cache size: {len(_cache)} entries")

    threading.Thread(target=_load, daemon=True).start()
    threading.Thread(target=_janitor, daemon=True).start()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_data(query: str, account: str = "india"):
    """Fetch data from Google Ads API with 5-min TTL cache and request dedup."""
    cache_key = f"gads_{account}_{hash(query)}"

    def _do_fetch():
        if account == "us":
            client = get_google_ads_client(login_customer_id=get_us_login_customer_id())
            customer_id = get_us_customer_id()
        else:
            client = get_google_ads_client()
            customer_id = get_customer_id()
        ga_service = client.get_service("GoogleAdsService")
        return list(ga_service.search(customer_id=customer_id, query=query))

    return _cache_get_or_fetch(cache_key, CACHE_TTL, _do_fetch)


def _build_date_clause(start_date: str, end_date: str) -> str:
    return f"segments.date BETWEEN '{start_date}' AND '{end_date}'"


def _get_conversion_action(account: str) -> str:
    if account == "us":
        return "Nurix US Website (web) form_submit_us-2026"
    return "Landing Page (web) form_submit_2025"


def _build_status_clause(status: Optional[str]) -> str:
    if status and status in ("ENABLED", "PAUSED"):
        return f"AND campaign.status = '{status}'"
    return "AND campaign.status != 'REMOVED'"


# Region patterns based on actual campaign naming conventions
_INDIA_PATTERN = re.compile(r'(?i)\b(ind|india)\b|^(IND|Ind|India)[_\-]')
_US_PATTERN = re.compile(r'(?i)^US[_\-]|\bUS\b')
_ALL_REGIONS_PATTERN = re.compile(r'(?i)^All[_\-]Regions')


def _matches_region(campaign_name: str, region: str) -> bool:
    """Check if a campaign name belongs to the given region."""
    if region == "All":
        return True
    # "All-Regions" campaigns show under India
    if _ALL_REGIONS_PATTERN.search(campaign_name):
        return region == "India"
    if region == "India":
        return bool(_INDIA_PATTERN.search(campaign_name))
    if region == "US":
        return bool(_US_PATTERN.search(campaign_name))
    return True


# ---------------------------------------------------------------------------
# Google Sheets MQL helper
# ---------------------------------------------------------------------------

def _get_sheets_client():
    creds = Credentials(
        token=None,
        refresh_token=_get_secret("GOOGLE_ADS_REFRESH_TOKEN"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=_get_secret("GOOGLE_ADS_CLIENT_ID"),
        client_secret=_get_secret("GOOGLE_ADS_CLIENT_SECRET"),
    )
    return gspread.authorize(creds)


_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_sheet_date(raw: str) -> Optional[date]:
    """Parse sheet date formats: '2 Jun' (2025 Jun-Jul, 2026 Jan+) or ISO timestamp."""
    raw = raw.strip()
    if not raw:
        return None

    # ISO format: 2025-12-22T04:12:08.871Z
    if "T" in raw and len(raw) > 10:
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            return None

    # "d Mon" format: e.g. "2 Jun", "15 Dec"
    parts = raw.split()
    if len(parts) == 2:
        try:
            day = int(parts[0])
            month = _MONTH_MAP.get(parts[1].lower()[:3])
            if month is None:
                return None
            # Sheet is chronological: Jun-Dec = 2025, Jan onwards = 2026
            year = 2026 if month <= 5 else 2025
            return date(year, month, day)
        except (ValueError, KeyError):
            return None

    return None


def _fetch_mqls(start_date: str, end_date: str, tab: str = SHEET_TAB):
    """Fetch MQL data from Google Sheet, filtered by date range.
    Returns dict keyed by normalized campaign name.
    Each value: {"count": int, "leads": [list of lead names]}
    Results are cached for 5 minutes per (tab, date range).
    """
    cache_key = f"mqls_{tab}_{start_date}_{end_date}"
    cached = _cache.get(cache_key)
    if cached and time.time() - cached["ts"] < CACHE_TTL:
        return cached["data"]

    gc = _get_sheets_client()
    sh = gc.open_by_key(SHEET_ID)
    ws = sh.worksheet(tab)
    all_rows = ws.get_all_values()

    filter_start = date.fromisoformat(start_date)
    filter_end = date.fromisoformat(end_date)

    # Column indices (0-based)
    LEAD_COL = 0         # Lead name
    DATE_COL = 1         # Date
    CAMPAIGN_COL = 5     # Campaign Name
    INTEREST_COL = 10    # Initial Interest

    mql_by_campaign: dict = {}  # normalized_name -> {"count": int, "leads": []}
    mql_by_id: dict = {}        # campaign_id -> {"count": int, "leads": []}
    # Date-level MQLs for keyword/search term matching: (date_str, normalized_campaign) -> [lead_names]
    mql_by_date_campaign: dict = {}

    for row in all_rows[1:]:
        if len(row) <= INTEREST_COL:
            continue
        interest = row[INTEREST_COL].strip().lower()
        if interest != "yes":
            continue

        # Date filter
        row_date = _parse_sheet_date(row[DATE_COL]) if len(row) > DATE_COL else None
        if row_date is None:
            continue
        if row_date < filter_start or row_date > filter_end:
            continue

        lead_name = row[LEAD_COL].strip() if len(row) > LEAD_COL else ""
        campaign_raw = row[CAMPAIGN_COL].strip()
        if not campaign_raw:
            continue

        # Check if it looks like a campaign ID (all digits)
        if campaign_raw.isdigit():
            entry = mql_by_id.setdefault(campaign_raw, {"count": 0, "leads": []})
            normalized = campaign_raw
        else:
            # Normalize: strip whitespace, tabs, trailing punctuation
            normalized = re.sub(r'[\s\t]+', ' ', campaign_raw).strip().rstrip('.-')
            entry = mql_by_campaign.setdefault(normalized, {"count": 0, "leads": []})

        # Deduplicate leads within each campaign (case-insensitive)
        existing_lower = {l.lower() for l in entry["leads"]}
        if lead_name and lead_name.lower() not in existing_lower:
            entry["count"] += 1
            entry["leads"].append(lead_name)
        elif not lead_name:
            entry["count"] += 1

        # Store date-level for keyword/search term matching
        date_key = (str(row_date), normalized)
        mql_by_date_campaign.setdefault(date_key, [])
        if lead_name and lead_name not in mql_by_date_campaign[date_key]:
            mql_by_date_campaign[date_key].append(lead_name)

    result = (mql_by_campaign, mql_by_id, mql_by_date_campaign)
    _cache.set(cache_key, {"data": result, "ts": time.time()})
    return result


def _match_campaign_mqls(campaign_name: str, mql_by_campaign: dict) -> dict:
    """Find MQL entry that best matches a campaign name (strict matching)."""
    # Try exact match first
    if campaign_name in mql_by_campaign:
        return mql_by_campaign[campaign_name]

    # Try case-insensitive exact match
    lower = campaign_name.lower()
    for key, val in mql_by_campaign.items():
        if key.lower() == lower:
            return val

    return {"count": 0, "leads": []}


# ---------------------------------------------------------------------------
# HubSpot SQL helper
# ---------------------------------------------------------------------------

def _normalize_deal(name: str) -> str:
    """Normalize a HubSpot deal name for matching."""
    return re.sub(
        r"\s*[-_]\s*(new deal|poc|renewal|ai voice.*|chat.*|voice agent.*)$",
        "", name.strip(), flags=re.I,
    ).strip().lower()


def _fetch_hubspot_deals() -> tuple:
    """Fetch all deal names that have *ever* reached SAL+ or SQL+ stage in HubSpot.

    Returns (sal_names, sql_names) where sal_names is SAL++ (SAL or beyond)
    and sql_names is the SQL+ subset.

    Fast approach: searches deals currently in each SAL+/SQL+ stage.
    Then kicks off a background thread to check Dormant/Lost deals
    for historical stages, updating the cache when done.

    Caching: 1-hour in-memory + disk cache survives restarts.
    """
    # Check in-memory cache
    cached = _cache.get("hubspot_deals")
    if cached and time.time() - cached["ts"] < HUBSPOT_CACHE_TTL:
        return cached["data"]

    # Check disk cache
    try:
        if os.path.exists(HUBSPOT_DISK_CACHE):
            import json
            with open(HUBSPOT_DISK_CACHE, "r") as f:
                disk = json.load(f)
            if time.time() - disk.get("ts", 0) < HUBSPOT_CACHE_TTL:
                sal_names = set(disk.get("sal_names", []))
                sql_names = set(disk.get("sql_names", disk.get("names", [])))
                _cache.set("hubspot_deals", {"data": (sal_names, sql_names), "ts": disk["ts"]})
                return sal_names, sql_names
    except Exception:
        pass

    token = _get_secret("HUBSPOT_API_TOKEN")
    if not token:
        return set(), set()

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    sal_names = set()  # SAL++ (SAL and beyond)
    sql_names = set()  # SQL+ subset

    # Fast path: search deals currently in each SAL+ stage
    for stage_id in HUBSPOT_SAL_PLUS_STAGES:
        after = "0"
        while True:
            body = {
                "filterGroups": [{"filters": [
                    {"propertyName": "pipeline", "operator": "EQ", "value": HUBSPOT_PIPELINE},
                    {"propertyName": "dealstage", "operator": "EQ", "value": stage_id},
                ]}],
                "properties": ["dealname"],
                "limit": 100,
                "after": after,
            }
            r = requests.post(
                "https://api.hubapi.com/crm/v3/objects/deals/search",
                headers=headers, json=body,
            )
            if r.status_code != 200:
                break
            data = r.json()
            for deal in data.get("results", []):
                norm = _normalize_deal(deal["properties"].get("dealname", ""))
                sal_names.add(norm)
                if stage_id in HUBSPOT_SQL_STAGES:
                    sql_names.add(norm)
            after = data.get("paging", {}).get("next", {}).get("after")
            if not after:
                break

    # Save fast results immediately
    _save_hubspot_cache(sal_names, sql_names)

    # Background: check Dormant/Lost/Revisit for historical SAL/SQL stages
    import threading
    threading.Thread(target=_hubspot_history_check, args=(headers, sal_names, sql_names), daemon=True).start()

    return sal_names, sql_names


def _hubspot_history_check(headers: dict, sal_names: set, sql_names: set):
    """Background check of Dormant/Lost/Revisit deals for historical SAL/SQL stages."""
    post_stages = {"244798996", "249323383", "1099643979"}  # Deal Lost, Dormant, Revisit
    extra_sal = set()
    extra_sql = set()
    for stage_id in post_stages:
        after = "0"
        while True:
            body = {
                "filterGroups": [{"filters": [
                    {"propertyName": "pipeline", "operator": "EQ", "value": HUBSPOT_PIPELINE},
                    {"propertyName": "dealstage", "operator": "EQ", "value": stage_id},
                ]}],
                "properties": ["dealname"],
                "limit": 100,
                "after": after,
            }
            r = requests.post(
                "https://api.hubapi.com/crm/v3/objects/deals/search",
                headers=headers, json=body,
            )
            if r.status_code != 200:
                break
            data = r.json()
            deal_ids = [d["id"] for d in data.get("results", [])]
            if deal_ids:
                br = requests.post(
                    "https://api.hubapi.com/crm/v3/objects/deals/batch/read",
                    headers=headers,
                    json={
                        "inputs": [{"id": did} for did in deal_ids],
                        "properties": ["dealname", "dealstage"],
                        "propertiesWithHistory": ["dealstage"],
                    },
                )
                if br.status_code == 200:
                    for deal in br.json().get("results", []):
                        history = deal.get("propertiesWithHistory", {}).get("dealstage", [])
                        norm = _normalize_deal(deal["properties"].get("dealname", ""))
                        if any(h.get("value") in HUBSPOT_SAL_PLUS_STAGES for h in history):
                            if norm not in sal_names:
                                extra_sal.add(norm)
                        if any(h.get("value") in HUBSPOT_SQL_STAGES for h in history):
                            if norm not in sql_names:
                                extra_sql.add(norm)
            after = data.get("paging", {}).get("next", {}).get("after")
            if not after:
                break

    if extra_sal or extra_sql:
        sal_names.update(extra_sal)
        sql_names.update(extra_sql)
        _save_hubspot_cache(sal_names, sql_names)


def _save_hubspot_cache(sal_names: set, sql_names: set):
    """Save HubSpot SAL/SQL names to in-memory + disk cache."""
    now = time.time()
    _cache.set("hubspot_deals", {"data": (sal_names, sql_names), "ts": now})
    try:
        import json
        with open(HUBSPOT_DISK_CACHE, "w") as f:
            json.dump({"sal_names": list(sal_names), "sql_names": list(sql_names), "ts": now}, f)
    except Exception:
        pass


def _strip_alpha(s: str) -> str:
    """Strip everything except letters and digits, lowercase."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _is_match(lead_name: str, deal_names: set) -> bool:
    """Check if an MQL lead name matches any HubSpot deal in the given set."""
    norm = lead_name.strip().lower()
    if norm in deal_names:
        return True
    # Partial match: lead name is contained in deal name or vice versa
    for sn in deal_names:
        if len(norm) >= 3 and len(sn) >= 3 and (norm in sn or sn in norm):
            return True
    # Stripped match: remove spaces, dots, special chars and compare
    stripped = _strip_alpha(lead_name)
    if len(stripped) >= 3:
        for sn in deal_names:
            sn_stripped = _strip_alpha(sn)
            if len(sn_stripped) >= 3 and (stripped in sn_stripped or sn_stripped in stripped):
                return True
    return False


def _is_sql(lead_name: str, sql_names: set) -> bool:
    """Check if an MQL lead name matches any HubSpot SQL deal."""
    return _is_match(lead_name, sql_names)


def _is_sal(lead_name: str, sal_names: set) -> bool:
    """Check if an MQL lead name matches any HubSpot SAL+ deal."""
    return _is_match(lead_name, sal_names)


@app.post("/api/clear-cache")
def clear_cache():
    """Clear all cached data (HubSpot SQLs, MQLs) to force a fresh fetch."""
    _cache.clear()
    return {"status": "ok", "message": "Cache cleared"}




# ---------------------------------------------------------------------------
# GET /api/campaigns
# ---------------------------------------------------------------------------

@app.get("/api/campaigns")
def get_campaigns(
    start_date: str = Query(default=None),
    end_date: str = Query(default=None),
    status: Optional[str] = Query(default=None),
    region: Optional[str] = Query(default="All"),
    account: str = Query(default="india"),
):
    if not start_date or not end_date:
        today = date.today()
        end_date = str(today)
        start_date = str(today - timedelta(days=30))

    date_clause = _build_date_clause(start_date, end_date)
    status_clause = _build_status_clause(status)

    query_traffic = f"""
        SELECT
            campaign.name,
            campaign.status,
            metrics.impressions,
            metrics.clicks,
            metrics.ctr,
            metrics.average_cpc,
            metrics.cost_micros
        FROM campaign
        WHERE {date_clause}
            {status_clause}
        ORDER BY metrics.cost_micros DESC
    """

    query_conv = f"""
        SELECT
            campaign.name,
            segments.conversion_action_name,
            metrics.all_conversions
        FROM campaign
        WHERE {date_clause}
            {status_clause}
            AND segments.conversion_action_name = '{_get_conversion_action(account)}'
    """

    # Run data fetches in parallel
    from concurrent.futures import ThreadPoolExecutor, as_completed
    sheet_tab = US_SHEET_TAB if account == "us" else SHEET_TAB
    if account == "us":
        with ThreadPoolExecutor(max_workers=4) as pool:
            f_traffic = pool.submit(_fetch_data, query_traffic, account)
            f_conv = pool.submit(_fetch_data, query_conv, account)
            f_mqls = pool.submit(lambda: _fetch_mqls(start_date, end_date, sheet_tab))
            f_deals = pool.submit(_fetch_hubspot_deals)
        rows_traffic = f_traffic.result()
        rows_conv = f_conv.result()
        try:
            mql_by_campaign, mql_by_id, _ = f_mqls.result()
        except Exception:
            mql_by_campaign, mql_by_id = {}, {}
        try:
            sal_names, sql_names = f_deals.result()
        except Exception:
            sal_names, sql_names = set(), set()
    else:
        with ThreadPoolExecutor(max_workers=4) as pool:
            f_traffic = pool.submit(_fetch_data, query_traffic, account)
            f_conv = pool.submit(_fetch_data, query_conv, account)
            f_mqls = pool.submit(lambda: _fetch_mqls(start_date, end_date))
            f_deals = pool.submit(_fetch_hubspot_deals)
        rows_traffic = f_traffic.result()
        rows_conv = f_conv.result()
        try:
            mql_by_campaign, mql_by_id, _ = f_mqls.result()
        except Exception:
            mql_by_campaign, mql_by_id = {}, {}
        try:
            sal_names, sql_names = f_deals.result()
        except Exception:
            sal_names, sql_names = set(), set()

    conv_by_campaign: dict = {}
    for row in rows_conv:
        name = row.campaign.name
        conv_by_campaign.setdefault(name, 0)
        conv_by_campaign[name] += row.metrics.all_conversions

    campaigns = []
    for row in rows_traffic:
        cost = row.metrics.cost_micros / 1_000_000
        conversions = conv_by_campaign.get(row.campaign.name, 0)
        mql_info = _match_campaign_mqls(row.campaign.name, mql_by_campaign)

        # Identify which MQL leads are SALs and SQLs in HubSpot
        sal_leads = [l for l in mql_info["leads"] if _is_sal(l, sal_names)]
        sql_leads = [l for l in mql_info["leads"] if _is_sql(l, sql_names)]
        sal_count = len(sal_leads)
        sql_count = len(sql_leads)
        mql_count = mql_info["count"]

        campaigns.append({
            "Campaign": row.campaign.name,
            "Status": row.campaign.status.name,
            "Impressions": row.metrics.impressions,
            "Clicks": row.metrics.clicks,
            "CTR": row.metrics.ctr,
            "Avg CPC": row.metrics.average_cpc / 1_000_000,
            "Cost": cost,
            "Conversions": conversions,
            "CPA": cost / conversions if conversions > 0 else 0,
            "MQLs": mql_count,
            "MQL Leads": mql_info["leads"],
            "SALs": sal_count,
            "SAL Leads": sal_leads,
            "SQLs": sql_count,
            "SQL Leads": sql_leads,
            "Cost/MQL": cost / mql_count if mql_count > 0 else 0,
            "Cost/SAL": cost / sal_count if sal_count > 0 else 0,
            "Cost/SQL": cost / sql_count if sql_count > 0 else 0,
        })

    # Region filter (skip for US account — all campaigns are already US)
    if account != "us" and region and region != "All":
        campaigns = [c for c in campaigns if _matches_region(c["Campaign"], region)]

    return {"campaigns": campaigns}


# ---------------------------------------------------------------------------
# GET /api/keywords
# ---------------------------------------------------------------------------

@app.get("/api/keywords")
def get_keywords(
    start_date: str = Query(default=None),
    end_date: str = Query(default=None),
    status: Optional[str] = Query(default=None),
    region: Optional[str] = Query(default="All"),
    campaigns: Optional[str] = Query(default=None),
    account: str = Query(default="india"),
):
    if not start_date or not end_date:
        today = date.today()
        end_date = str(today)
        start_date = str(today - timedelta(days=30))

    date_clause = _build_date_clause(start_date, end_date)
    status_clause = _build_status_clause(status)
    selected = campaigns.split(",") if campaigns else []

    query_traffic = f"""
        SELECT
            ad_group_criterion.keyword.text,
            ad_group_criterion.keyword.match_type,
            campaign.name,
            ad_group.name,
            metrics.impressions,
            metrics.clicks,
            metrics.ctr,
            metrics.average_cpc,
            metrics.cost_micros
        FROM keyword_view
        WHERE {date_clause}
            {status_clause}
        ORDER BY metrics.cost_micros DESC
        LIMIT 200
    """

    query_conv = f"""
        SELECT
            ad_group_criterion.keyword.text,
            campaign.name,
            ad_group.name,
            segments.conversion_action_name,
            metrics.all_conversions
        FROM keyword_view
        WHERE {date_clause}
            {status_clause}
            AND segments.conversion_action_name = '{_get_conversion_action(account)}'
    """

    # Run data fetches in parallel (including HubSpot for SAL/SQL)
    from concurrent.futures import ThreadPoolExecutor
    sheet_tab = US_SHEET_TAB if account == "us" else SHEET_TAB
    with ThreadPoolExecutor(max_workers=4) as pool:
        f_traffic = pool.submit(_fetch_data, query_traffic, account)
        f_conv = pool.submit(_fetch_data, query_conv, account)
        f_mqls = pool.submit(lambda: _fetch_mqls(start_date, end_date, sheet_tab))
        f_hs = pool.submit(_fetch_hubspot_deals)
    rows_traffic = f_traffic.result()
    rows_conv = f_conv.result()
    try:
        mql_by_campaign, mql_by_id, _ = f_mqls.result()
    except Exception:
        mql_by_campaign, mql_by_id = {}, {}
    try:
        sal_names, sql_names = f_hs.result()
    except Exception:
        sal_names, sql_names = set(), set()

    kw_conv_lookup: dict = {}
    for row in rows_conv:
        key = (row.ad_group_criterion.keyword.text, row.campaign.name, row.ad_group.name)
        kw_conv_lookup[key] = kw_conv_lookup.get(key, 0) + row.metrics.all_conversions

    kw_data = []
    for row in rows_traffic:
        camp_name = row.campaign.name
        if selected and camp_name not in selected:
            continue
        if account != "us" and region and region != "All" and not _matches_region(camp_name, region):
            continue

        cost = row.metrics.cost_micros / 1_000_000
        key = (row.ad_group_criterion.keyword.text, camp_name, row.ad_group.name)
        conversions = kw_conv_lookup.get(key, 0)
        mql_info = _match_campaign_mqls(camp_name, mql_by_campaign)
        sal_leads = [l for l in mql_info["leads"] if _is_sal(l, sal_names)]
        sql_leads = [l for l in mql_info["leads"] if _is_sql(l, sql_names)]
        kw_data.append({
            "Keyword": row.ad_group_criterion.keyword.text,
            "Match Type": row.ad_group_criterion.keyword.match_type.name,
            "Campaign": camp_name,
            "Ad Group": row.ad_group.name,
            "Clicks": row.metrics.clicks,
            "Impressions": row.metrics.impressions,
            "CTR": row.metrics.ctr,
            "CPC": row.metrics.average_cpc / 1_000_000,
            "Cost": cost,
            "Conversions": conversions,
            "CPA": cost / conversions if conversions > 0 else 0,
            "Campaign MQLs": mql_info["count"],
            "Campaign SALs": len(sal_leads),
            "Campaign SQLs": len(sql_leads),
            "MQL Leads": mql_info["leads"],
            "SAL Leads": sal_leads,
            "SQL Leads": sql_leads,
        })

    return {"keywords": kw_data}


# ---------------------------------------------------------------------------
# GET /api/search-terms
# ---------------------------------------------------------------------------

@app.get("/api/search-terms")
def get_search_terms(
    start_date: str = Query(default=None),
    end_date: str = Query(default=None),
    status: Optional[str] = Query(default=None),
    region: Optional[str] = Query(default="All"),
    campaigns: Optional[str] = Query(default=None),
    account: str = Query(default="india"),
):
    if not start_date or not end_date:
        today = date.today()
        end_date = str(today)
        start_date = str(today - timedelta(days=30))

    date_clause = _build_date_clause(start_date, end_date)
    status_clause = _build_status_clause(status)
    selected = campaigns.split(",") if campaigns else []

    query_traffic = f"""
        SELECT
            search_term_view.search_term,
            campaign.name,
            metrics.impressions,
            metrics.clicks,
            metrics.ctr,
            metrics.cost_micros
        FROM search_term_view
        WHERE {date_clause}
            {status_clause}
        ORDER BY metrics.cost_micros DESC
        LIMIT 200
    """

    query_conv = f"""
        SELECT
            search_term_view.search_term,
            campaign.name,
            segments.conversion_action_name,
            metrics.all_conversions
        FROM search_term_view
        WHERE {date_clause}
            {status_clause}
            AND segments.conversion_action_name = '{_get_conversion_action(account)}'
    """

    # Run data fetches in parallel (including HubSpot for SAL/SQL)
    from concurrent.futures import ThreadPoolExecutor
    sheet_tab = US_SHEET_TAB if account == "us" else SHEET_TAB
    with ThreadPoolExecutor(max_workers=4) as pool:
        f_traffic = pool.submit(_fetch_data, query_traffic, account)
        f_conv = pool.submit(_fetch_data, query_conv, account)
        f_mqls = pool.submit(lambda: _fetch_mqls(start_date, end_date, sheet_tab))
        f_hs = pool.submit(_fetch_hubspot_deals)
    rows_traffic = f_traffic.result()
    rows_conv = f_conv.result()
    try:
        mql_by_campaign, mql_by_id, _ = f_mqls.result()
    except Exception:
        mql_by_campaign, mql_by_id = {}, {}
    try:
        sal_names, sql_names = f_hs.result()
    except Exception:
        sal_names, sql_names = set(), set()

    st_conv_lookup: dict = {}
    for row in rows_conv:
        key = (row.search_term_view.search_term, row.campaign.name)
        st_conv_lookup[key] = st_conv_lookup.get(key, 0) + row.metrics.all_conversions

    st_data = []
    for row in rows_traffic:
        camp_name = row.campaign.name
        if selected and camp_name not in selected:
            continue
        if account != "us" and region and region != "All" and not _matches_region(camp_name, region):
            continue

        cost = row.metrics.cost_micros / 1_000_000
        key = (row.search_term_view.search_term, camp_name)
        conversions = st_conv_lookup.get(key, 0)
        mql_info = _match_campaign_mqls(camp_name, mql_by_campaign)
        sal_leads = [l for l in mql_info["leads"] if _is_sal(l, sal_names)]
        sql_leads = [l for l in mql_info["leads"] if _is_sql(l, sql_names)]
        st_data.append({
            "Search Term": row.search_term_view.search_term,
            "Campaign": camp_name,
            "Clicks": row.metrics.clicks,
            "Impressions": row.metrics.impressions,
            "CTR": row.metrics.ctr,
            "Cost": cost,
            "Conversions": conversions,
            "CPA": cost / conversions if conversions > 0 else 0,
            "Campaign MQLs": mql_info["count"],
            "Campaign SALs": len(sal_leads),
            "Campaign SQLs": len(sql_leads),
            "MQL Leads": mql_info["leads"],
            "SAL Leads": sal_leads,
            "SQL Leads": sql_leads,
        })

    return {"search_terms": st_data}


# ---------------------------------------------------------------------------
# GET /api/comparison  (Period-on-Period, month halves)
# ---------------------------------------------------------------------------

def _get_half_month_ranges(start_date: Optional[str] = None, end_date: Optional[str] = None, num_periods: int = 12):
    """Return list of (label, start_date, end_date) for month-halves.

    Each month is split into two periods: 1st-15th and 16th-end.
    If start_date/end_date are provided, returns all half-month periods in that range.
    Otherwise, returns the last num_periods half-months ending at today.
    """
    today = date.today()

    if start_date and end_date:
        range_start = date.fromisoformat(start_date)
        range_end = date.fromisoformat(end_date)
    else:
        range_end = today
        # Go back roughly num_periods half-months
        range_start = today - timedelta(days=num_periods * 16)

    periods = []
    # Start from the half-month containing range_start
    y, m = range_start.year, range_start.month
    while True:
        # First half: 1-15
        h1_start = date(y, m, 1)
        h1_end = date(y, m, 15)
        if h1_end >= range_start and h1_start <= range_end:
            actual_start = max(h1_start, range_start) if start_date else h1_start
            actual_end = min(h1_end, range_end)
            label = f"{h1_start.strftime('%b')} 1-15"
            periods.append((label, str(actual_start), str(actual_end)))

        # Second half: 16-end
        last_day = monthrange(y, m)[1]
        h2_start = date(y, m, 16)
        h2_end = date(y, m, last_day)
        if h2_end >= range_start and h2_start <= range_end:
            actual_start = max(h2_start, range_start) if start_date else h2_start
            actual_end = min(h2_end, range_end)
            label = f"{h2_start.strftime('%b')} 16-{last_day}"
            periods.append((label, str(actual_start), str(actual_end)))

        # Next month
        m += 1
        if m > 12:
            m = 1
            y += 1
        if date(y, m, 1) > range_end:
            break

    # If no custom range, trim to last num_periods
    if not start_date:
        periods = periods[-num_periods:]

    return periods


@app.get("/api/comparison")
def get_comparison(
    periods: int = Query(default=12, ge=2, le=24),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    account: str = Query(default="india"),
):
    """Period-on-period campaign comparison (month halves, ENABLED only) grouped by region."""
    cache_key = f"comparison_{account}_{periods}_{start_date}_{end_date}"
    cached = _cache.get(cache_key)
    if cached and time.time() - cached["ts"] < CACHE_TTL:
        return cached["data"]

    period_ranges = _get_half_month_ranges(start_date, end_date, periods)
    # Only show ENABLED campaigns
    status_clause = "AND campaign.status = 'ENABLED'"

    from concurrent.futures import ThreadPoolExecutor

    def fetch_period(label, start, end):
        query_traffic = f"""
            SELECT
                campaign.name,
                campaign.status,
                metrics.impressions,
                metrics.clicks,
                metrics.ctr,
                metrics.average_cpc,
                metrics.cost_micros
            FROM campaign
            WHERE segments.date BETWEEN '{start}' AND '{end}'
                {status_clause}
            ORDER BY metrics.cost_micros DESC
        """
        query_conv = f"""
            SELECT
                campaign.name,
                segments.conversion_action_name,
                metrics.all_conversions
            FROM campaign
            WHERE segments.date BETWEEN '{start}' AND '{end}'
                {status_clause}
                AND segments.conversion_action_name = '{_get_conversion_action(account)}'
        """
        rows_traffic = _fetch_data(query_traffic, account)
        rows_conv = _fetch_data(query_conv, account)

        conv_map = {}
        for row in rows_conv:
            conv_map[row.campaign.name] = conv_map.get(row.campaign.name, 0) + row.metrics.all_conversions

        # MQL + SAL/SQL data
        sheet_tab = US_SHEET_TAB if account == "us" else SHEET_TAB
        try:
            mql_by_campaign, _, _ = _fetch_mqls(start, end, sheet_tab)
        except Exception:
            mql_by_campaign = {}
        try:
            sal_names, sql_names = _fetch_hubspot_deals()
        except Exception:
            sal_names, sql_names = set(), set()

        campaigns = {}
        for row in rows_traffic:
            name = row.campaign.name
            cost = row.metrics.cost_micros / 1_000_000
            conversions = conv_map.get(name, 0)
            mql_info = _match_campaign_mqls(name, mql_by_campaign)
            sal_leads = [l for l in mql_info["leads"] if _is_sal(l, sal_names)]
            sql_leads = [l for l in mql_info["leads"] if _is_sql(l, sql_names)]
            mql_count = mql_info["count"]
            sal_count = len(sal_leads)
            sql_count = len(sql_leads)

            campaigns[name] = {
                "Impressions": row.metrics.impressions,
                "Clicks": row.metrics.clicks,
                "CTR": row.metrics.ctr,
                "Spend": cost,
                "Avg CPC": row.metrics.average_cpc / 1_000_000,
                "Conversions": conversions,
                "CVR": row.metrics.clicks > 0 and conversions / row.metrics.clicks or 0,
                "CPL": cost / conversions if conversions > 0 else 0,
                "MQLs": mql_count,
                "Cost/MQL": cost / mql_count if mql_count > 0 else 0,
                "SALs": sal_count,
                "Cost/SAL": cost / sal_count if sal_count > 0 else 0,
                "SQLs": sql_count,
                "Cost/SQL": cost / sql_count if sql_count > 0 else 0,
                "mql_leads": mql_info["leads"],
                "sal_leads": sal_leads,
                "sql_leads": sql_leads,
            }
        return label, campaigns

    # Fetch all periods in parallel
    num_workers = min(len(period_ranges), 6)
    with ThreadPoolExecutor(max_workers=num_workers) as pool:
        futures = [pool.submit(fetch_period, lbl, s, e) for lbl, s, e in period_ranges]

    period_data = {}  # label -> {campaign_name -> metrics}
    for f in futures:
        label, campaigns = f.result()
        period_data[label] = campaigns

    # Preserve chronological order
    period_labels = [lbl for lbl, _, _ in period_ranges]

    # Collect all campaign names across all periods
    all_campaigns = set()
    for campaigns in period_data.values():
        all_campaigns.update(campaigns.keys())

    # Classify campaigns by region
    us_campaigns = sorted([c for c in all_campaigns if _matches_region(c, "US")])
    india_campaigns = sorted([c for c in all_campaigns if _matches_region(c, "India")])

    # Build response grouped by region
    empty_metrics = {
        "Impressions": 0, "Clicks": 0, "CTR": 0, "Spend": 0, "Avg CPC": 0,
        "Conversions": 0, "CVR": 0, "CPL": 0, "MQLs": 0, "Cost/MQL": 0,
        "SALs": 0, "Cost/SAL": 0, "SQLs": 0, "Cost/SQL": 0,
        "mql_leads": [], "sal_leads": [], "sql_leads": [],
    }

    def build_region_data(campaign_list):
        rows = []
        for camp in campaign_list:
            row = {"Campaign": camp, "periods": {}}
            for label in period_labels:
                row["periods"][label] = period_data.get(label, {}).get(camp, dict(empty_metrics))
            rows.append(row)
        return rows

    def compute_totals(campaign_list):
        """Compute period totals for a list of campaigns."""
        totals = {}
        for label in period_labels:
            t = {k: v for k, v in empty_metrics.items() if k not in ("mql_leads", "sal_leads", "sql_leads")}
            for camp in campaign_list:
                m = period_data.get(label, {}).get(camp, empty_metrics)
                t["Impressions"] += m["Impressions"]
                t["Clicks"] += m["Clicks"]
                t["Spend"] += m["Spend"]
                t["Conversions"] += m["Conversions"]
                t["MQLs"] += m["MQLs"]
                t["SALs"] += m["SALs"]
                t["SQLs"] += m["SQLs"]
            # Derived metrics from totals
            t["CTR"] = t["Clicks"] / t["Impressions"] if t["Impressions"] > 0 else 0
            t["Avg CPC"] = t["Spend"] / t["Clicks"] if t["Clicks"] > 0 else 0
            t["CVR"] = t["Conversions"] / t["Clicks"] if t["Clicks"] > 0 else 0
            t["CPL"] = t["Spend"] / t["Conversions"] if t["Conversions"] > 0 else 0
            t["Cost/MQL"] = t["Spend"] / t["MQLs"] if t["MQLs"] > 0 else 0
            t["Cost/SAL"] = t["Spend"] / t["SALs"] if t["SALs"] > 0 else 0
            t["Cost/SQL"] = t["Spend"] / t["SQLs"] if t["SQLs"] > 0 else 0
            totals[label] = t
        return totals

    result = {
        "period_labels": period_labels,
        "regions": {
            "US": {
                "campaigns": build_region_data(us_campaigns),
                "totals": compute_totals(us_campaigns),
            },
            "India": {
                "campaigns": build_region_data(india_campaigns),
                "totals": compute_totals(india_campaigns),
            },
        },
    }

    _cache.set(cache_key, {"data": result, "ts": time.time()})
    return result


# ---------------------------------------------------------------------------
# POST /api/chat
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# GET /api/keyword-ideas
# ---------------------------------------------------------------------------

# Geo target resource names for KeywordPlanIdeaService
_GEO_TARGETS = {
    "India": "geoTargetConstants/2356",
    "US": "geoTargetConstants/2840",
}
_LANGUAGE_ENGLISH = "languageConstants/1000"


def _get_geo_targets(region: str) -> list:
    """Return geo target constants for a region."""
    if region == "India":
        return [_GEO_TARGETS["India"]]
    elif region == "US":
        return [_GEO_TARGETS["US"]]
    else:
        return [_GEO_TARGETS["India"], _GEO_TARGETS["US"]]


def _generate_ideas_for_seeds(seed_keywords: list, region: str, client=None, customer_id=None):
    """Call KeywordPlanIdeaService for a list of seed keywords. Returns list of idea dicts."""
    if not client:
        client = get_google_ads_client()
    if not customer_id:
        customer_id = get_customer_id()

    kw_idea_service = client.get_service("KeywordPlanIdeaService")
    request = client.get_type("GenerateKeywordIdeasRequest")
    request.customer_id = customer_id
    request.language = _LANGUAGE_ENGLISH
    for geo in _get_geo_targets(region):
        request.geo_target_constants.append(geo)
    request.keyword_seed.keywords.extend(seed_keywords)

    response = kw_idea_service.generate_keyword_ideas(request=request)
    ideas = []
    for idea in response:
        metrics = idea.keyword_idea_metrics
        ideas.append({
            "Keyword": idea.text,
            "Avg Monthly Searches": metrics.avg_monthly_searches,
            "Competition": metrics.competition.name if metrics.competition else "UNKNOWN",
            "Low CPC": metrics.low_top_of_page_bid_micros / 1_000_000 if metrics.low_top_of_page_bid_micros else 0,
            "High CPC": metrics.high_top_of_page_bid_micros / 1_000_000 if metrics.high_top_of_page_bid_micros else 0,
        })
    return ideas


@app.get("/api/keyword-ideas")
def get_keyword_ideas(
    start_date: str = Query(default=None),
    end_date: str = Query(default=None),
    status: Optional[str] = Query(default=None),
    region: Optional[str] = Query(default="All"),
    campaigns: Optional[str] = Query(default=None),
    account: str = Query(default="india"),
):
    """Campaign-grouped keyword suggestions. Top 5 keywords per campaign as seeds."""
    if not start_date or not end_date:
        today = date.today()
        end_date = str(today)
        start_date = str(today - timedelta(days=30))

    cache_key = f"kw_ideas_v2_{account}_{start_date}_{end_date}_{status}_{region}_{campaigns}"
    cached = _cache.get(cache_key)
    if cached and time.time() - cached["ts"] < CACHE_TTL:
        return cached["data"]

    date_clause = _build_date_clause(start_date, end_date)
    status_clause = _build_status_clause(status)
    selected = campaigns.split(",") if campaigns else []

    # Step 1: Get all keywords grouped by campaign (top 200 by spend)
    query_kw = f"""
        SELECT
            ad_group_criterion.keyword.text,
            campaign.name,
            metrics.cost_micros
        FROM keyword_view
        WHERE {date_clause}
            {status_clause}
        ORDER BY metrics.cost_micros DESC
        LIMIT 500
    """
    rows = _fetch_data(query_kw, account)

    # Group keywords by campaign and collect all existing account keywords
    campaign_keywords = {}  # campaign -> [(keyword, spend)]
    campaign_spend = {}     # campaign -> total spend
    all_account_keywords = set()

    for row in rows:
        camp = row.campaign.name
        if selected and camp not in selected:
            continue
        if account != "us" and region and region != "All" and not _matches_region(camp, region):
            continue
        kw = row.ad_group_criterion.keyword.text.lower()
        spend = row.metrics.cost_micros / 1_000_000
        all_account_keywords.add(kw)
        campaign_keywords.setdefault(camp, []).append((kw, spend))
        campaign_spend[camp] = campaign_spend.get(camp, 0) + spend

    if not campaign_keywords:
        return {"campaigns": []}

    # Step 2: Top 10 campaigns by spend, top 5 keywords each
    top_campaigns = sorted(campaign_spend.keys(), key=lambda c: campaign_spend[c], reverse=True)[:10]

    campaign_seeds = {}
    for camp in top_campaigns:
        kws = campaign_keywords[camp]
        # Already sorted by spend (from GAQL ORDER BY), deduplicate
        seen = set()
        seeds = []
        for kw, _ in kws:
            if kw not in seen:
                seen.add(kw)
                seeds.append(kw)
                if len(seeds) >= 5:
                    break
        campaign_seeds[camp] = seeds

    # Step 3: Parallel keyword idea generation per campaign
    client = get_google_ads_client()
    customer_id = get_customer_id()

    from concurrent.futures import ThreadPoolExecutor

    def fetch_ideas_for_campaign(camp_name):
        seeds = campaign_seeds[camp_name]
        camp_kw_set = {kw for kw, _ in campaign_keywords[camp_name]}
        try:
            raw_ideas = _generate_ideas_for_seeds(seeds, region, client, customer_id)
        except Exception as e:
            err_str = str(e)
            if "DEVELOPER_TOKEN_NOT_APPROVED" in err_str or "not allowed for use with explorer" in err_str.lower():
                return {"campaign": camp_name, "seed_keywords": seeds, "ideas": [], "access_error": True,
                        "error": "Keyword Planner API requires Basic or Standard access."}
            return {"campaign": camp_name, "seed_keywords": seeds, "ideas": [], "error": err_str}

        ideas = []
        for idea in raw_ideas:
            kw_lower = idea["Keyword"].lower()
            idea["In Campaign"] = kw_lower in camp_kw_set
            idea["In Account"] = kw_lower in all_account_keywords
            ideas.append(idea)

        # Sort: not-in-campaign first, then by search volume desc
        ideas.sort(key=lambda x: (x["In Campaign"], -x["Avg Monthly Searches"]))
        return {"campaign": camp_name, "seed_keywords": seeds, "ideas": ideas}

    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(fetch_ideas_for_campaign, top_campaigns))

    # Check if first result has access_error (all will have same issue)
    if results and results[0].get("access_error"):
        return {
            "access_error": True,
            "error": results[0]["error"],
            "campaigns": results,
        }

    result = {"campaigns": results}
    _cache.set(cache_key, {"data": result, "ts": time.time()})
    return result


# ---------------------------------------------------------------------------
# GET /api/competitor-keywords  (SEMrush-powered)
# ---------------------------------------------------------------------------

COMPETITOR_CACHE_TTL = 86400  # 24 hours — competitor data rarely changes

# SEMrush database codes per region
_SEMRUSH_DATABASES = {
    "India": "in",
    "US": "us",
    "All": "us",  # default to US for broadest coverage
}


def _fetch_semrush_paid_keywords(domain: str, database: str = "us", limit: int = 40):
    """Fetch paid keywords for a domain from SEMrush API.

    Uses the domain_adwords endpoint.
    Response is semicolon-delimited CSV with columns:
      Ph=keyword, Po=position, Nq=search volume, Cp=CPC,
      Tr=traffic%, Tc=traffic cost, Co=competition, Nr=results
    """
    api_key = _get_secret("SEMRUSH_API_KEY")
    if not api_key:
        return None, "SEMRUSH_API_KEY not configured. Add it to your .env file (find it at semrush.com > Subscription Info > API units)."

    url = "https://api.semrush.com/"
    params = {
        "type": "domain_adwords",
        "key": api_key,
        "domain": domain,
        "database": database,
        "display_limit": limit,
        "export_columns": "Ph,Po,Nq,Cp,Tr,Tc,Co,Nr",
        "display_sort": "tr_desc",  # sort by traffic share descending
    }

    try:
        resp = requests.get(url, params=params, timeout=30)
    except requests.RequestException as e:
        return None, f"SEMrush request failed: {e}"

    text = resp.text.strip()
    if not text:
        return [], None

    # SEMrush error responses
    if text.startswith("ERROR"):
        error_map = {
            "ERROR 50": "SEMrush: Nothing found for this domain in paid search.",
            "ERROR 120": "SEMrush: API limit exceeded. Check your API unit balance.",
            "ERROR 40": "SEMrush: API access denied. Verify your SEMRUSH_API_KEY.",
        }
        for code, msg in error_map.items():
            if text.startswith(code):
                return None, msg
        return None, f"SEMrush error: {text}"

    # Parse semicolon-delimited response (headers use full names)
    lines = text.replace("\r\n", "\n").split("\n")
    if len(lines) < 2:
        return [], None

    headers = lines[0].split(";")
    results = []
    for line in lines[1:]:
        if not line.strip():
            continue
        values = line.split(";")
        if len(values) < len(headers):
            continue
        row = dict(zip(headers, values))
        try:
            results.append({
                "Keyword": row.get("Keyword", ""),
                "Position": int(row.get("Position", 0)),
                "Avg Monthly Searches": int(row.get("Search Volume", 0)),
                "CPC": float(row.get("CPC", 0)),
                "Traffic %": float(row.get("Traffic (%)", 0)),
                "Traffic Cost": float(row.get("Traffic Cost (%)", 0)),
                "Competition": float(row.get("Competition", 0)),
            })
        except (ValueError, TypeError):
            continue

    # Deduplicate: same keyword at multiple ad positions → keep best position, sum traffic
    seen = {}
    for r in results:
        kw = r["Keyword"].lower()
        if kw in seen:
            existing = seen[kw]
            existing["Traffic %"] += r["Traffic %"]
            existing["Traffic Cost"] += r["Traffic Cost"]
            if r["Position"] < existing["Position"]:
                existing["Position"] = r["Position"]
        else:
            seen[kw] = dict(r)
    deduped = sorted(seen.values(), key=lambda x: -x["Traffic %"])

    return deduped, None


@app.get("/api/competitor-keywords")
def get_competitor_keywords(
    domain: str = Query(..., description="Competitor domain to analyze"),
    region: Optional[str] = Query(default="All"),
    start_date: str = Query(default=None),
    end_date: str = Query(default=None),
    status: Optional[str] = Query(default=None),
):
    """Get competitor's paid keywords via SEMrush, cross-referenced with your account."""
    cache_key = f"competitor_v2_{domain}_{region}"
    cached = _cache.get(cache_key)
    if cached and time.time() - cached["ts"] < COMPETITOR_CACHE_TTL:
        return cached["data"]

    # Fetch existing account keywords for cross-referencing
    if not start_date or not end_date:
        today = date.today()
        end_date = str(today)
        start_date = str(today - timedelta(days=30))

    date_clause = _build_date_clause(start_date, end_date)
    status_clause = _build_status_clause(status)

    query_kw = f"""
        SELECT ad_group_criterion.keyword.text, metrics.cost_micros
        FROM keyword_view
        WHERE {date_clause} {status_clause}
        ORDER BY metrics.cost_micros DESC
        LIMIT 500
    """
    rows = _fetch_data(query_kw)
    all_account_keywords = {row.ad_group_criterion.keyword.text.lower() for row in rows}

    # Fetch from SEMrush
    database = _SEMRUSH_DATABASES.get(region, "us")
    ideas, error = _fetch_semrush_paid_keywords(domain, database=database)

    if error:
        return {
            "error": error,
            "ideas": [],
            "domain": domain,
            "source": "semrush",
            "known_competitors": _detect_competitor_domains(),
        }

    # Cross-reference with account keywords
    for idea in ideas:
        idea["In Account"] = idea["Keyword"].lower() in all_account_keywords

    # Sort: not-in-account first, then by search volume desc
    ideas.sort(key=lambda x: (x["In Account"], -x["Avg Monthly Searches"]))

    known_competitors = _detect_competitor_domains()
    result = {"ideas": ideas, "domain": domain, "source": "semrush", "known_competitors": known_competitors}
    _cache.set(cache_key, {"data": result, "ts": time.time()})
    return result


# ---------------------------------------------------------------------------
# GET /api/auction-insights  (Free — Google Ads API)
# ---------------------------------------------------------------------------

@app.get("/api/auction-insights")
def get_auction_insights(
    start_date: str = Query(default=None),
    end_date: str = Query(default=None),
    region: Optional[str] = Query(default="All"),
    campaigns: Optional[str] = Query(default=None),
    account: str = Query(default="india"),
):
    """Get Auction Insights — see which competitors overlap with your campaigns."""
    if not start_date or not end_date:
        today = date.today()
        end_date = str(today)
        start_date = str(today - timedelta(days=30))

    cache_key = f"auction_insights_{account}_{start_date}_{end_date}_{region}_{campaigns}"
    cached = _cache.get(cache_key)
    if cached and time.time() - cached["ts"] < CACHE_TTL:
        return cached["data"]

    date_clause = _build_date_clause(start_date, end_date)
    selected = campaigns.split(",") if campaigns else []

    # Auction insights query — grouped by competitor domain and campaign
    query = f"""
        SELECT
            campaign.name,
            auction_insight.display_domain,
            metrics.auction_insight_search_impression_share,
            metrics.auction_insight_search_overlap_rate,
            metrics.auction_insight_search_position_above_rate,
            metrics.auction_insight_search_top_impression_percentage,
            metrics.auction_insight_search_outranking_share
        FROM auction_insight
        WHERE {date_clause}
    """

    try:
        rows = _fetch_data(query, account)
    except Exception as e:
        return {"error": str(e), "competitors": []}

    # Aggregate by competitor domain
    competitor_data = {}
    for row in rows:
        camp_name = row.campaign.name
        if selected and camp_name not in selected:
            continue
        if account != "us" and region and region != "All" and not _matches_region(camp_name, region):
            continue

        domain = row.auction_insight.display_domain
        if not domain:
            continue

        entry = competitor_data.setdefault(domain, {
            "domain": domain,
            "impression_share_sum": 0,
            "overlap_rate_sum": 0,
            "position_above_rate_sum": 0,
            "top_impression_pct_sum": 0,
            "outranking_share_sum": 0,
            "count": 0,
            "campaigns": set(),
        })
        entry["impression_share_sum"] += row.metrics.auction_insight_search_impression_share or 0
        entry["overlap_rate_sum"] += row.metrics.auction_insight_search_overlap_rate or 0
        entry["position_above_rate_sum"] += row.metrics.auction_insight_search_position_above_rate or 0
        entry["top_impression_pct_sum"] += row.metrics.auction_insight_search_top_impression_percentage or 0
        entry["outranking_share_sum"] += row.metrics.auction_insight_search_outranking_share or 0
        entry["count"] += 1
        entry["campaigns"].add(camp_name)

    # Build response with averages
    competitors = []
    for domain, d in competitor_data.items():
        n = d["count"]
        if n == 0:
            continue
        competitors.append({
            "Domain": domain,
            "Impression Share": round(d["impression_share_sum"] / n, 4),
            "Overlap Rate": round(d["overlap_rate_sum"] / n, 4),
            "Position Above Rate": round(d["position_above_rate_sum"] / n, 4),
            "Top Impression %": round(d["top_impression_pct_sum"] / n, 4),
            "Outranking Share": round(d["outranking_share_sum"] / n, 4),
            "Campaigns Overlapping": len(d["campaigns"]),
        })

    # Sort by overlap rate descending
    competitors.sort(key=lambda x: -x["Overlap Rate"])

    result = {"competitors": competitors}
    _cache.set(cache_key, {"data": result, "ts": time.time()})
    return result


def _detect_competitor_domains():
    """Known competitor domains from campaign naming conventions."""
    return [
        {"name": "ElevenLabs", "domain": "elevenlabs.io"},
        {"name": "Cartesia", "domain": "cartesia.ai"},
        {"name": "Poly.ai", "domain": "poly.ai"},
    ]


# ---------------------------------------------------------------------------
# POST /api/chat
# ---------------------------------------------------------------------------

def _select_groq_model(message: str, history: list) -> str:
    """
    Route to the cheapest/fastest model that can handle the query.

    Groq rate limits (free tier):
      llama-3.1-8b-instant   — 6 000 req/min,  500 K TPM  (fast)
      llama-3.3-70b-versatile — 6 000 req/day,  100 K TPM  (capable)

    Heuristic: use 8b for simple lookups; escalate to 70b for analysis.
    """
    msg = message.lower().strip()
    words = len(msg.split())
    turns = len(history)

    complex_signals = [
        "analyz", "compar", "trend", "why", "explain", "recommend",
        "strateg", "optim", "predict", "forecast", "pattern", "correlat",
        "should i", "what should", "how can i", "help me", "deep dive",
        "breakdown", "improve", "insight", "opportunit",
    ]
    simple_signals = [
        "what is", "how much", "total", "how many", "which campaign",
        "best campaign", "worst", "highest", "lowest", "show me", "list",
        "top ", "what was", "what were",
    ]

    is_complex = (
        any(sig in msg for sig in complex_signals)
        or words > 25
        or turns > 6        # Long conversations benefit from smarter model
    )
    is_simple = any(sig in msg for sig in simple_signals) and words < 15 and turns <= 2

    if is_complex:
        return "llama-3.3-70b-versatile"  # Best reasoning, use sparingly
    if is_simple:
        return "llama-3.1-8b-instant"     # Very fast, great for fact lookups
    return "llama-3.1-8b-instant"         # Default to fast; handles most queries


class ChatRequest(BaseModel):
    message: str
    history: list = []
    context: Optional[str] = None
    account: str = "india"


@app.post("/api/chat")
def chat(req: ChatRequest):
    currency = "USD ($)" if req.account == "us" else "INR (₹)"
    sym = "$" if req.account == "us" else "₹"
    conversion_action = _get_conversion_action(req.account)
    system_prompt = (
        f"You are a Google Ads analyst assistant. You answer questions about the user's Google Ads account data.\n"
        f"Be concise, specific, and actionable. Use the actual numbers from the data. Currency is {currency}; "
        f"format monetary values with the '{sym}' symbol.\n"
        f"All conversion data is filtered to the '{conversion_action}' conversion action only.\n"
        "If the user asks something not covered by the data, say so honestly.\n"
    )
    if req.context:
        system_prompt += f"\nHere is the current account data:\n{req.context}"

    messages = []
    for m in req.history:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": req.message})

    # Try Groq (free) first, fall back to Anthropic
    groq_key = _get_secret("GROQ_API_KEY")
    anthropic_key = _get_secret("ANTHROPIC_API_KEY")

    if groq_key:
        try:
            from groq import Groq
            model = _select_groq_model(req.message, req.history)
            client = Groq(api_key=groq_key)
            groq_messages = [{"role": "system", "content": system_prompt}] + messages
            resp = client.chat.completions.create(
                model=model,
                messages=groq_messages,
                max_tokens=1024,
            )
            return {"response": resp.choices[0].message.content, "model": model}
        except Exception as e:
            # Fall through to Anthropic if Groq fails
            if not anthropic_key:
                return {"error": f"Groq error: {e}"}

    if anthropic_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_key)
            resp = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1024,
                system=system_prompt,
                messages=messages,
            )
            return {"response": resp.content[0].text}
        except Exception as e:
            return {"error": str(e)}

    return {"error": "No AI API key configured. Add GROQ_API_KEY (free at console.groq.com) or ANTHROPIC_API_KEY to your .env file."}
