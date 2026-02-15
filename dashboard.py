import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
from config import get_google_ads_client, get_customer_id, get_ga4_client, get_ga4_property_id, get_openai_api_key

st.set_page_config(page_title="Google Ads Dashboard", page_icon="📊", layout="wide")

# --- Custom styling ---
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
    [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    [data-testid="stMetricLabel"] { font-size: 0.85rem; color: #555555 !important; }
    [data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 700; color: #1a1a1a !important; }
    h1 { font-size: 2rem !important; }
    h2 { font-size: 1.4rem !important; margin-top: 1rem !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        background: #f8f9fa;
        border-radius: 8px;
        padding: 8px 20px;
    }
    .insight-box {
        background: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin: 8px 0;
    }
    .good-box {
        background: #d4edda;
        border-left: 4px solid #28a745;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin: 8px 0;
    }
    .bad-box {
        background: #f8d7da;
        border-left: 4px solid #dc3545;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin: 8px 0;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)
def fetch_data(query):
    client = get_google_ads_client()
    customer_id = get_customer_id()
    ga_service = client.get_service("GoogleAdsService")
    return list(ga_service.search(customer_id=customer_id, query=query))


# --- Sidebar ---
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/c/c7/Google_Ads_logo.svg/1200px-Google_Ads_logo.svg.png", width=180)
    st.markdown("---")

    # Date range
    date_mode = st.radio("📅 Date Range", ["Preset", "Custom"], horizontal=True)
    if date_mode == "Preset":
        preset = st.selectbox("Select range", [
            "Last 7 Days", "Last 14 Days", "Last 30 Days",
            "Last 60 Days", "Last 90 Days",
        ], index=2)
        days_map = {
            "Last 7 Days": 7, "Last 14 Days": 14, "Last 30 Days": 30,
            "Last 60 Days": 60, "Last 90 Days": 90,
        }
        end_date = date.today()
        start_date = end_date - timedelta(days=days_map[preset])
    else:
        default_end = date.today()
        default_start = default_end - timedelta(days=30)
        date_range_input = st.date_input(
            "Select dates",
            value=(default_start, default_end),
        )
        if isinstance(date_range_input, (list, tuple)) and len(date_range_input) == 2:
            start_date, end_date = date_range_input
        else:
            start_date, end_date = default_start, default_end

    date_clause = f"segments.date BETWEEN '{start_date}' AND '{end_date}'"
    st.caption(f"📆 {start_date.strftime('%b %d, %Y')} — {end_date.strftime('%b %d, %Y')}")

    st.markdown("---")

    # Status filter
    status_filter = st.multiselect(
        "📋 Campaign Status",
        ["ENABLED", "PAUSED"],
        default=["ENABLED", "PAUSED"],
    )
    if len(status_filter) == 1:
        status_clause = f"AND campaign.status = '{status_filter[0]}'"
    else:
        status_clause = "AND campaign.status != 'REMOVED'"

    st.markdown("---")
    st.caption("Dashboard refreshes every 5 minutes.\nClick 'R' to refresh manually.")

st.title("📊 Google Ads Dashboard")

try:
    # =============================================
    # FETCH CAMPAIGN DATA (used across tabs)
    # =============================================
    query_campaigns = f"""
        SELECT
            campaign.name,
            campaign.status,
            metrics.impressions,
            metrics.clicks,
            metrics.ctr,
            metrics.average_cpc,
            metrics.cost_micros,
            metrics.conversions,
            metrics.cost_per_conversion
        FROM campaign
        WHERE {date_clause}
            {status_clause}
        ORDER BY metrics.cost_micros DESC
    """
    rows = fetch_data(query_campaigns)

    campaigns = []
    for row in rows:
        cost = row.metrics.cost_micros / 1_000_000
        conversions = row.metrics.conversions
        campaigns.append({
            "Campaign": row.campaign.name,
            "Status": row.campaign.status.name,
            "Impressions": row.metrics.impressions,
            "Clicks": row.metrics.clicks,
            "CTR": row.metrics.ctr,
            "Avg CPC": row.metrics.average_cpc / 1_000_000,
            "Cost": cost,
            "Conversions": conversions,
            "Cost/Conv": row.metrics.cost_per_conversion / 1_000_000 if conversions > 0 else 0,
        })

    df_campaigns = pd.DataFrame(campaigns)

    # =============================================
    # CAMPAIGN NAME FILTER
    # =============================================
    if not df_campaigns.empty:
        all_campaign_names = sorted(df_campaigns["Campaign"].unique().tolist())
        campaign_options = ["All Campaigns"] + all_campaign_names
        selected_campaign = st.selectbox("🎯 Filter by Campaign", campaign_options)
        if selected_campaign == "All Campaigns":
            selected_campaigns = all_campaign_names
        else:
            selected_campaigns = [selected_campaign]
            df_campaigns = df_campaigns[df_campaigns["Campaign"].isin(selected_campaigns)]
    else:
        selected_campaigns = []

    # =============================================
    # TOP-LEVEL KPIs (always visible)
    # =============================================
    if not df_campaigns.empty:
        total_spend = df_campaigns["Cost"].sum()
        total_clicks = df_campaigns["Clicks"].sum()
        total_impressions = df_campaigns["Impressions"].sum()
        total_conversions = df_campaigns["Conversions"].sum()
        overall_ctr = total_clicks / total_impressions if total_impressions > 0 else 0
        overall_cpc = total_spend / total_clicks if total_clicks > 0 else 0

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Total Spend", f"₹{total_spend:,.2f}")
        c2.metric("Clicks", f"{total_clicks:,}")
        c3.metric("Impressions", f"{total_impressions:,}")
        c4.metric("CTR", f"{overall_ctr:.2%}")
        c5.metric("Avg CPC", f"₹{overall_cpc:.2f}")
        c6.metric("Conversions", f"{total_conversions:,.0f}")

        st.markdown("")
    else:
        st.warning("No campaign data found for the selected filters.")

    # =============================================
    # TABS
    # =============================================
    tab_overview, tab_trends, tab_kw_analysis, tab_competitors, tab_opportunities, tab_landing, tab_chat = st.tabs([
        "🏠 Overview",
        "📈 Daily Trends",
        "🔍 Keyword Analysis",
        "🏆 Competitors",
        "💎 Keyword Opportunities",
        "🌐 Landing Pages",
        "💬 Ask AI",
    ])

    # =============================================
    # TAB 1: OVERVIEW
    # =============================================
    with tab_overview:

        if not df_campaigns.empty:
            st.subheader("Campaign Performance")
            display_df = df_campaigns.copy()
            display_df["CTR"] = display_df["CTR"].apply(lambda x: f"{x:.2%}")
            display_df["Avg CPC"] = display_df["Avg CPC"].apply(lambda x: f"₹{x:.2f}")
            display_df["Cost"] = display_df["Cost"].apply(lambda x: f"₹{x:,.2f}")
            display_df["Cost/Conv"] = display_df["Cost/Conv"].apply(lambda x: f"₹{x:.2f}" if x > 0 else "-")
            st.dataframe(display_df, use_container_width=True, hide_index=True)

            col_left, col_right = st.columns(2)
            with col_left:
                st.subheader("Spend by Campaign")
                chart_spend = df_campaigns[["Campaign", "Cost"]].set_index("Campaign").sort_values("Cost")
                st.bar_chart(chart_spend)
            with col_right:
                st.subheader("Clicks by Campaign")
                chart_clicks = df_campaigns[["Campaign", "Clicks"]].set_index("Campaign").sort_values("Clicks")
                st.bar_chart(chart_clicks)

            st.subheader("Quick Insights")
            best_ctr = df_campaigns.loc[df_campaigns["CTR"].idxmax()]
            worst_ctr = df_campaigns.loc[df_campaigns[df_campaigns["Clicks"] > 0]["CTR"].idxmin()] if (df_campaigns["Clicks"] > 0).any() else None
            biggest_spender = df_campaigns.loc[df_campaigns["Cost"].idxmax()]

            st.markdown(f'<div class="good-box">🏆 <strong>Best CTR:</strong> {best_ctr["Campaign"]} at {best_ctr["CTR"]:.2%}</div>', unsafe_allow_html=True)
            if worst_ctr is not None:
                st.markdown(f'<div class="bad-box">⚠️ <strong>Lowest CTR:</strong> {worst_ctr["Campaign"]} at {worst_ctr["CTR"]:.2%} — consider revising ad copy</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="insight-box">💰 <strong>Biggest spender:</strong> {biggest_spender["Campaign"]} at ₹{biggest_spender["Cost"]:,.2f}</div>', unsafe_allow_html=True)

    # =============================================
    # TAB 2: DAILY TRENDS
    # =============================================
    with tab_trends:

        query_daily = f"""
            SELECT
                segments.date,
                campaign.name,
                metrics.cost_micros,
                metrics.clicks,
                metrics.impressions,
                metrics.conversions
            FROM campaign
            WHERE {date_clause}
                {status_clause}
            ORDER BY segments.date ASC
        """
        rows_daily = fetch_data(query_daily)

        daily_data = {}
        for row in rows_daily:
            if selected_campaigns and row.campaign.name not in selected_campaigns:
                continue
            d = row.segments.date
            if d not in daily_data:
                daily_data[d] = {"Cost": 0, "Clicks": 0, "Impressions": 0, "Conversions": 0}
            daily_data[d]["Cost"] += row.metrics.cost_micros / 1_000_000
            daily_data[d]["Clicks"] += row.metrics.clicks
            daily_data[d]["Impressions"] += row.metrics.impressions
            daily_data[d]["Conversions"] += row.metrics.conversions

        if daily_data:
            df_daily = pd.DataFrame.from_dict(daily_data, orient="index")
            df_daily.index = pd.to_datetime(df_daily.index)
            df_daily = df_daily.sort_index()

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Avg Daily Spend", f"₹{df_daily['Cost'].mean():,.2f}")
            c2.metric("Avg Daily Clicks", f"{df_daily['Clicks'].mean():,.0f}")
            c3.metric("Avg Daily Impressions", f"{df_daily['Impressions'].mean():,.0f}")
            c4.metric("Avg Daily Conversions", f"{df_daily['Conversions'].mean():,.1f}")

            st.markdown("")

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("💵 Daily Spend")
                st.area_chart(df_daily["Cost"], color="#FF6B6B")
            with col2:
                st.subheader("👆 Daily Clicks")
                st.area_chart(df_daily["Clicks"], color="#4ECDC4")

            col3, col4 = st.columns(2)
            with col3:
                st.subheader("👀 Daily Impressions")
                st.area_chart(df_daily["Impressions"], color="#45B7D1")
            with col4:
                st.subheader("🎯 Daily Conversions")
                st.area_chart(df_daily["Conversions"], color="#96CEB4")

            st.subheader("Peak Days")
            peak_spend_day = df_daily["Cost"].idxmax().strftime("%A, %b %d")
            peak_clicks_day = df_daily["Clicks"].idxmax().strftime("%A, %b %d")
            pc1, pc2 = st.columns(2)
            pc1.markdown(f'<div class="insight-box">💰 <strong>Highest spend day:</strong> {peak_spend_day} (₹{df_daily["Cost"].max():,.2f})</div>', unsafe_allow_html=True)
            pc2.markdown(f'<div class="good-box">👆 <strong>Most clicks day:</strong> {peak_clicks_day} ({df_daily["Clicks"].max():,} clicks)</div>', unsafe_allow_html=True)
        else:
            st.info("No daily data found for this date range.")

    # =============================================
    # TAB 3: KEYWORD & SEARCH TERM ANALYSIS
    # =============================================
    with tab_kw_analysis:

        st.markdown("Analyze how your keywords and search terms perform to find optimization opportunities.")

        # --- Fetch keyword data ---
        query_keywords = f"""
            SELECT
                ad_group_criterion.keyword.text,
                ad_group_criterion.keyword.match_type,
                campaign.name,
                ad_group.name,
                metrics.impressions,
                metrics.clicks,
                metrics.ctr,
                metrics.average_cpc,
                metrics.cost_micros,
                metrics.conversions,
                metrics.cost_per_conversion
            FROM keyword_view
            WHERE {date_clause}
                {status_clause}
            ORDER BY metrics.cost_micros DESC
            LIMIT 50
        """
        rows_kw = fetch_data(query_keywords)

        kw_data = []
        for row in rows_kw:
            if selected_campaigns and row.campaign.name not in selected_campaigns:
                continue
            cost = row.metrics.cost_micros / 1_000_000
            conversions = row.metrics.conversions
            cpc = row.metrics.average_cpc / 1_000_000
            cpa = row.metrics.cost_per_conversion / 1_000_000 if conversions > 0 else 0
            kw_data.append({
                "Keyword": row.ad_group_criterion.keyword.text,
                "Match Type": row.ad_group_criterion.keyword.match_type.name,
                "Campaign": row.campaign.name,
                "Ad Group": row.ad_group.name,
                "Impressions": row.metrics.impressions,
                "Clicks": row.metrics.clicks,
                "CTR": row.metrics.ctr,
                "CPC": cpc,
                "Cost": cost,
                "Conversions": conversions,
                "CPA": cpa,
            })

        df_kw = pd.DataFrame(kw_data)

        # --- Fetch search term data ---
        query_search = f"""
            SELECT
                search_term_view.search_term,
                campaign.name,
                metrics.impressions,
                metrics.clicks,
                metrics.ctr,
                metrics.cost_micros,
                metrics.conversions
            FROM search_term_view
            WHERE {date_clause}
                {status_clause}
            ORDER BY metrics.cost_micros DESC
            LIMIT 100
        """
        rows_st = fetch_data(query_search)

        st_data = []
        for row in rows_st:
            if selected_campaigns and row.campaign.name not in selected_campaigns:
                continue
            cost = row.metrics.cost_micros / 1_000_000
            conversions = row.metrics.conversions
            st_data.append({
                "Search Term": row.search_term_view.search_term,
                "Campaign": row.campaign.name,
                "Impressions": row.metrics.impressions,
                "Clicks": row.metrics.clicks,
                "CTR": row.metrics.ctr,
                "Cost": cost,
                "Conversions": conversions,
                "CPA": cost / conversions if conversions > 0 else 0,
            })

        df_st = pd.DataFrame(st_data)

        # --- KPI row ---
        if not df_kw.empty or not df_st.empty:
            kc1, kc2, kc3, kc4 = st.columns(4)
            if not df_kw.empty:
                kc1.metric("Total Keywords", len(df_kw))
                converting_kws = len(df_kw[df_kw["Conversions"] > 0])
                kc2.metric("Converting Keywords", f"{converting_kws} / {len(df_kw)}")
            if not df_st.empty:
                kc3.metric("Search Terms Tracked", len(df_st))
                wasted_pct = (df_st[df_st["Conversions"] == 0]["Cost"].sum() / df_st["Cost"].sum() * 100) if df_st["Cost"].sum() > 0 else 0
                kc4.metric("Wasted Spend %", f"{wasted_pct:.1f}%")

            st.markdown("")

        # --- Sub-tabs ---
        kw_tab1, kw_tab2, kw_tab3, kw_tab4 = st.tabs([
            "📋 Keyword Performance",
            "🔎 Search Terms",
            "🚨 Wasted Spend",
            "💡 Optimization Tips",
        ])

        # ---- Keyword Performance ----
        with kw_tab1:
            if not df_kw.empty:
                match_types = ["All"] + sorted(df_kw["Match Type"].unique().tolist())
                selected_match = st.selectbox("Filter by Match Type", match_types)

                filtered_kw = df_kw if selected_match == "All" else df_kw[df_kw["Match Type"] == selected_match]

                display_kw = filtered_kw.copy()
                display_kw["CTR"] = display_kw["CTR"].apply(lambda x: f"{x:.2%}")
                display_kw["CPC"] = display_kw["CPC"].apply(lambda x: f"₹{x:.2f}")
                display_kw["Cost"] = display_kw["Cost"].apply(lambda x: f"₹{x:,.2f}")
                display_kw["CPA"] = display_kw["CPA"].apply(lambda x: f"₹{x:.2f}" if x > 0 else "-")
                st.dataframe(display_kw, use_container_width=True, hide_index=True)

                st.subheader("Spend by Match Type")
                match_summary = df_kw.groupby("Match Type").agg(
                    Keywords=("Keyword", "count"),
                    Clicks=("Clicks", "sum"),
                    Cost=("Cost", "sum"),
                    Conversions=("Conversions", "sum"),
                ).reset_index()
                match_summary["Avg CPC"] = match_summary.apply(lambda r: f"₹{r['Cost']/r['Clicks']:.2f}" if r["Clicks"] > 0 else "-", axis=1)
                match_summary["Cost"] = match_summary["Cost"].apply(lambda x: f"₹{x:,.2f}")
                st.dataframe(match_summary, use_container_width=True, hide_index=True)
            else:
                st.info("No keyword data found for this date range.")

        # ---- Search Terms ----
        with kw_tab2:
            if not df_st.empty:
                search_filter = st.text_input("🔍 Search for a term", placeholder="Type to filter search terms...")
                filtered_st = df_st
                if search_filter:
                    filtered_st = df_st[df_st["Search Term"].str.contains(search_filter, case=False, na=False)]

                display_st = filtered_st.copy()
                display_st["CTR"] = display_st["CTR"].apply(lambda x: f"{x:.2%}")
                display_st["Cost"] = display_st["Cost"].apply(lambda x: f"₹{x:,.2f}")
                display_st["CPA"] = display_st["CPA"].apply(lambda x: f"₹{x:.2f}" if x > 0 else "-")
                st.dataframe(display_st, use_container_width=True, hide_index=True)

                converting = df_st[df_st["Conversions"] > 0].sort_values("Conversions", ascending=False).head(10)
                if not converting.empty:
                    st.subheader("🏆 Top Converting Search Terms")
                    for _, row in converting.iterrows():
                        st.markdown(
                            f'<div class="good-box"><strong>{row["Search Term"]}</strong> — '
                            f'{row["Conversions"]:.0f} conversions, ₹{row["Cost"]:,.2f} spend, '
                            f'{row["CTR"]:.2%} CTR</div>',
                            unsafe_allow_html=True,
                        )
            else:
                st.info("No search term data found for this date range.")

        # ---- Wasted Spend ----
        with kw_tab3:
            if not df_st.empty:
                st.markdown("Search terms that cost money but **didn't convert**. Consider adding these as **negative keywords**.")
                st.markdown("")

                wasted = df_st[df_st["Conversions"] == 0].sort_values("Cost", ascending=False)

                if not wasted.empty:
                    total_wasted = wasted["Cost"].sum()
                    total_wasted_clicks = wasted["Clicks"].sum()
                    pct_wasted = (total_wasted / df_st["Cost"].sum() * 100) if df_st["Cost"].sum() > 0 else 0

                    wc1, wc2, wc3 = st.columns(3)
                    wc1.metric("Wasted Spend", f"₹{total_wasted:,.2f}")
                    wc2.metric("Wasted Clicks", f"{total_wasted_clicks:,}")
                    wc3.metric("% of Total Spend", f"{pct_wasted:.1f}%")

                    st.markdown("")

                    if pct_wasted > 30:
                        st.markdown(f'<div class="bad-box">🚨 <strong>{pct_wasted:.0f}% of your spend</strong> goes to non-converting search terms. Adding negative keywords could save you <strong>₹{total_wasted:,.2f}</strong>.</div>', unsafe_allow_html=True)
                    elif pct_wasted > 15:
                        st.markdown(f'<div class="insight-box">⚠️ <strong>{pct_wasted:.0f}% of your spend</strong> goes to non-converting terms. Review the list below for potential negative keywords.</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="good-box">✅ Only <strong>{pct_wasted:.0f}%</strong> of spend is non-converting — your targeting looks solid!</div>', unsafe_allow_html=True)

                    st.markdown("")
                    st.subheader("🚫 Suggested Negative Keywords")
                    st.caption("These search terms spent the most without converting:")

                    display_wasted = wasted.head(20).copy()
                    display_wasted["CTR"] = display_wasted["CTR"].apply(lambda x: f"{x:.2%}")
                    display_wasted["Cost"] = display_wasted["Cost"].apply(lambda x: f"₹{x:,.2f}")
                    display_wasted = display_wasted.drop(columns=["CPA"])
                    st.dataframe(display_wasted, use_container_width=True, hide_index=True)
                else:
                    st.markdown('<div class="good-box">🎉 All your search terms have at least one conversion. Great job!</div>', unsafe_allow_html=True)
            else:
                st.info("No search term data found for this date range.")

        # ---- Optimization Tips ----
        with kw_tab4:
            st.markdown("Auto-generated tips based on your account data.")
            st.markdown("")

            tips = []

            if not df_kw.empty:
                high_cpc = df_kw[df_kw["CPC"] > df_kw["CPC"].mean() * 1.5]
                if not high_cpc.empty:
                    kw_list = ", ".join(high_cpc["Keyword"].head(3).tolist())
                    tips.append(("insight-box", "💰", "High CPC Keywords", f"These keywords cost significantly more than average: <strong>{kw_list}</strong>. Consider lowering bids or improving Quality Score with better ad copy and landing pages."))

                low_ctr = df_kw[(df_kw["CTR"] < 0.02) & (df_kw["Impressions"] > 100)]
                if not low_ctr.empty:
                    kw_list = ", ".join(low_ctr["Keyword"].head(3).tolist())
                    tips.append(("bad-box", "⚠️", "Low CTR Keywords", f"These keywords have CTR below 2%: <strong>{kw_list}</strong>. Your ads may not be relevant enough — try writing more specific ad copy or tightening match types."))

                no_conv = df_kw[(df_kw["Clicks"] > 5) & (df_kw["Conversions"] == 0)]
                if not no_conv.empty:
                    wasted_amount = no_conv["Cost"].sum()
                    kw_list = ", ".join(no_conv["Keyword"].head(3).tolist())
                    tips.append(("bad-box", "🔥", "Money Burning Keywords", f"Keywords with clicks but zero conversions: <strong>{kw_list}</strong>. Total spend: <strong>₹{wasted_amount:,.2f}</strong>. Consider pausing these or improving landing pages."))

                top_perf = df_kw[(df_kw["Conversions"] > 0)].sort_values("CPA")
                if not top_perf.empty:
                    best = top_perf.iloc[0]
                    tips.append(("good-box", "🏆", "Best Performer", f"<strong>{best['Keyword']}</strong> has the lowest cost per conversion at <strong>₹{best['CPA']:.2f}</strong>. Consider increasing budget for this keyword."))

                broad_kw = df_kw[df_kw["Match Type"] == "BROAD"]
                if not broad_kw.empty and len(broad_kw) > len(df_kw) * 0.5:
                    tips.append(("insight-box", "🎯", "Match Type Mix", f"Over half your keywords use Broad match. Consider testing Phrase or Exact match for your top-spending keywords to improve targeting precision."))

            if not df_st.empty:
                low_ctr_st = df_st[(df_st["CTR"] < 0.01) & (df_st["Impressions"] > 50)]
                if not low_ctr_st.empty:
                    terms = ", ".join(low_ctr_st["Search Term"].head(3).tolist())
                    tips.append(("insight-box", "🔍", "Irrelevant Search Terms", f"These search terms get impressions but very few clicks: <strong>{terms}</strong>. They may not be relevant — consider adding as negative keywords."))

            if tips:
                for box_class, icon, title, description in tips:
                    st.markdown(f'<div class="{box_class}">{icon} <strong>{title}:</strong> {description}</div>', unsafe_allow_html=True)
                    st.markdown("")
            else:
                st.markdown('<div class="good-box">✅ No major issues detected. Your account looks healthy!</div>', unsafe_allow_html=True)

    # =============================================
    # TAB 4: COMPETITORS (Impression Share & Gaps)
    # =============================================
    with tab_competitors:

        st.markdown("Analyze your competitive position using **keyword-level impression share** and **auction insights**.")
        st.markdown("")

        try:
            query_kw_is = f"""
                SELECT
                    ad_group_criterion.keyword.text,
                    ad_group_criterion.keyword.match_type,
                    campaign.name,
                    metrics.search_impression_share,
                    metrics.search_top_impression_share,
                    metrics.search_absolute_top_impression_share,
                    metrics.search_rank_lost_impression_share,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.ctr,
                    metrics.cost_micros,
                    metrics.conversions
                FROM keyword_view
                WHERE {date_clause}
                    {status_clause}
                    AND metrics.impressions > 0
                ORDER BY metrics.impressions DESC
                LIMIT 100
            """
            rows_kw_is = fetch_data(query_kw_is)

            kw_is_data = []
            for row in rows_kw_is:
                if selected_campaigns and row.campaign.name not in selected_campaigns:
                    continue
                imp_share = row.metrics.search_impression_share or 0
                kw_is_data.append({
                    "Keyword": row.ad_group_criterion.keyword.text,
                    "Match Type": row.ad_group_criterion.keyword.match_type.name,
                    "Campaign": row.campaign.name,
                    "Impression Share": imp_share,
                    "Top IS": row.metrics.search_top_impression_share or 0,
                    "Abs Top IS": row.metrics.search_absolute_top_impression_share or 0,
                    "Lost IS (Rank)": row.metrics.search_rank_lost_impression_share or 0,
                    "Impressions": row.metrics.impressions,
                    "Clicks": row.metrics.clicks,
                    "CTR": row.metrics.ctr or 0,
                    "Cost": row.metrics.cost_micros / 1_000_000,
                    "Conversions": row.metrics.conversions,
                })

            df_kw_is = pd.DataFrame(kw_is_data)

            # Filter to >10% impression share
            if not df_kw_is.empty:
                df_kw_visible = df_kw_is[df_kw_is["Impression Share"] >= 0.10].sort_values("Impression Share", ascending=False)
            else:
                df_kw_visible = pd.DataFrame()

            # Sub-tabs
            comp_tab_auction, comp_tab1, comp_tab2, comp_tab3 = st.tabs([
                "🔍 Auction Insights",
                "📊 Impression Share by Keyword",
                "⚡ Competitive Gaps",
                "🎯 Where to Invest",
            ])

            # ---- Auction Insights (CSV Upload) ----
            with comp_tab_auction:
                st.markdown("Upload your **Auction Insights** report from Google Ads to see **who your competitors are** and how you stack up against them.")
                st.markdown("")

                with st.expander("📥 How to download Auction Insights from Google Ads", expanded=True):
                    st.markdown("""
1. Go to [ads.google.com](https://ads.google.com)
2. Click **Campaigns** in the left menu
3. Select the campaign(s) you want to analyze
4. Click the **Auction insights** tab at the top
5. Set your desired date range
6. Click the **Download** button (⬇) → choose **CSV** or **.csv**
7. Upload the file below
                    """)

                uploaded_file = st.file_uploader("Upload Auction Insights CSV", type=["csv"], key="auction_csv")

                if uploaded_file is not None:
                    try:
                        df_auction = pd.read_csv(uploaded_file)

                        # Find the domain column
                        domain_col = None
                        for col in df_auction.columns:
                            col_lower = col.lower()
                            if 'domain' in col_lower or 'display url' in col_lower or 'display_url' in col_lower:
                                domain_col = col
                                break
                        if domain_col is None:
                            domain_col = df_auction.columns[0]

                        # Find percentage metric columns (everything except domain)
                        metric_cols = [c for c in df_auction.columns if c != domain_col]

                        # Parse percentage values
                        for col in metric_cols:
                            df_auction[col] = (
                                df_auction[col]
                                .astype(str)
                                .str.replace('%', '', regex=False)
                                .str.replace('--', '', regex=False)
                                .str.replace('< 10', '5', regex=False)
                                .str.strip()
                            )
                            df_auction[col] = pd.to_numeric(df_auction[col], errors='coerce')

                        # Separate "You" row from competitors
                        you_mask = df_auction[domain_col].str.lower().str.strip().isin(['you', 'your', 'me'])
                        you_data = df_auction[you_mask]
                        df_competitors = df_auction[~you_mask].dropna(subset=[domain_col])
                        df_competitors = df_competitors[df_competitors[domain_col].str.strip() != '']

                        if df_competitors.empty:
                            st.warning("No competitor data found in the uploaded file. Make sure it's an Auction Insights CSV from Google Ads.")
                        else:
                            # Rename domain column for display
                            df_competitors = df_competitors.rename(columns={domain_col: "Competitor"})
                            if not you_data.empty:
                                you_data = you_data.rename(columns={domain_col: "Competitor"})
                                you_data["Competitor"] = "You (Your Ads)"

                            # Detect which metric columns exist
                            is_col = None
                            overlap_col = None
                            pos_above_col = None
                            top_col = None
                            abs_top_col = None
                            outranking_col = None

                            for col in df_competitors.columns:
                                col_lower = col.lower()
                                if col == "Competitor":
                                    continue
                                if 'outranking' in col_lower:
                                    outranking_col = col
                                elif 'overlap' in col_lower:
                                    overlap_col = col
                                elif 'position above' in col_lower or 'position_above' in col_lower:
                                    pos_above_col = col
                                elif 'abs' in col_lower and 'top' in col_lower:
                                    abs_top_col = col
                                elif 'top' in col_lower and 'page' in col_lower:
                                    top_col = col
                                elif 'impression' in col_lower and 'share' in col_lower:
                                    is_col = col

                            # KPIs
                            num_competitors = len(df_competitors)
                            ac1, ac2, ac3 = st.columns(3)
                            ac1.metric("Competitors Found", num_competitors)
                            if is_col and not df_competitors[is_col].isna().all():
                                avg_comp_is = df_competitors[is_col].mean()
                                ac2.metric("Avg Competitor IS", f"{avg_comp_is:.1f}%")
                                if not you_data.empty and not you_data[is_col].isna().all():
                                    your_is = you_data[is_col].iloc[0]
                                    ac3.metric("Your Impression Share", f"{your_is:.1f}%")
                            st.markdown("")

                            # Your position vs competitors
                            if not you_data.empty and is_col:
                                your_is_val = you_data[is_col].iloc[0] if not you_data[is_col].isna().all() else None
                                if your_is_val is not None:
                                    beating_you = df_competitors[df_competitors[is_col] > your_is_val]
                                    you_beating = df_competitors[df_competitors[is_col] <= your_is_val]
                                    if not beating_you.empty:
                                        names = ", ".join(beating_you["Competitor"].head(5).tolist())
                                        st.markdown(f'<div class="bad-box">🥊 <strong>{len(beating_you)} competitor(s)</strong> have higher impression share than you: <strong>{names}</strong></div>', unsafe_allow_html=True)
                                    if not you_beating.empty:
                                        names = ", ".join(you_beating["Competitor"].head(5).tolist())
                                        st.markdown(f'<div class="good-box">✅ You\'re <strong>ahead of {len(you_beating)} competitor(s)</strong>: <strong>{names}</strong></div>', unsafe_allow_html=True)
                                    st.markdown("")

                            # Biggest threat
                            if overlap_col and not df_competitors[overlap_col].isna().all():
                                top_overlap = df_competitors.sort_values(overlap_col, ascending=False).iloc[0]
                                st.markdown(f'<div class="insight-box">🎯 <strong>Biggest competitor:</strong> <strong>{top_overlap["Competitor"]}</strong> — overlaps with your ads {top_overlap[overlap_col]:.1f}% of the time</div>', unsafe_allow_html=True)
                                st.markdown("")

                            # Full competitor table
                            st.subheader("All Competitors")
                            display_auction = df_competitors.copy()
                            if not you_data.empty:
                                display_auction = pd.concat([you_data, display_auction], ignore_index=True)

                            # Format percentage columns for display
                            for col in display_auction.columns:
                                if col != "Competitor":
                                    display_auction[col] = display_auction[col].apply(
                                        lambda x: f"{x:.1f}%" if pd.notna(x) else "-"
                                    )
                            st.dataframe(display_auction, use_container_width=True, hide_index=True)

                            # Bar chart - Impression Share comparison
                            if is_col:
                                st.subheader("Impression Share Comparison")
                                chart_data = df_competitors[["Competitor", is_col]].dropna().copy()
                                if not you_data.empty and not you_data[is_col].isna().all():
                                    you_row = pd.DataFrame({"Competitor": ["You"], is_col: [you_data[is_col].iloc[0]]})
                                    chart_data = pd.concat([you_row, chart_data], ignore_index=True)
                                chart_data = chart_data.set_index("Competitor").sort_values(is_col, ascending=True)
                                st.bar_chart(chart_data)

                            # Overlap Rate chart
                            if overlap_col and not df_competitors[overlap_col].isna().all():
                                st.subheader("Overlap Rate (how often you compete)")
                                overlap_chart = df_competitors[["Competitor", overlap_col]].dropna().set_index("Competitor").sort_values(overlap_col, ascending=True)
                                st.bar_chart(overlap_chart)

                            # Position Above Rate chart
                            if pos_above_col and not df_competitors[pos_above_col].isna().all():
                                st.subheader("Position Above Rate (how often they outrank you)")
                                pos_chart = df_competitors[["Competitor", pos_above_col]].dropna().set_index("Competitor").sort_values(pos_above_col, ascending=True)
                                st.bar_chart(pos_chart)

                            # Per-competitor analysis
                            st.subheader("Competitor Deep Dive")
                            for _, comp in df_competitors.iterrows():
                                name = comp["Competitor"]
                                details = []
                                if is_col and pd.notna(comp.get(is_col)):
                                    details.append(f"IS: {comp[is_col]:.1f}%")
                                if overlap_col and pd.notna(comp.get(overlap_col)):
                                    details.append(f"Overlap: {comp[overlap_col]:.1f}%")
                                if pos_above_col and pd.notna(comp.get(pos_above_col)):
                                    details.append(f"Above you: {comp[pos_above_col]:.1f}%")
                                if outranking_col and pd.notna(comp.get(outranking_col)):
                                    details.append(f"Outranking: {comp[outranking_col]:.1f}%")

                                detail_str = " | ".join(details) if details else "No data"

                                # Determine threat level
                                threat = "insight-box"
                                if pos_above_col and pd.notna(comp.get(pos_above_col)) and comp[pos_above_col] > 50:
                                    threat = "bad-box"
                                elif is_col and pd.notna(comp.get(is_col)) and comp[is_col] > 40:
                                    threat = "insight-box"
                                else:
                                    threat = "good-box"

                                st.markdown(
                                    f'<div class="{threat}">🏢 <strong>{name}</strong> — {detail_str}</div>',
                                    unsafe_allow_html=True,
                                )

                    except Exception as upload_err:
                        st.error(f"Error reading file: {upload_err}")
                        st.caption("Make sure you uploaded a valid Auction Insights CSV from Google Ads.")
                else:
                    st.info("Upload your Auction Insights CSV above to see competitor analysis.")

            # ---- Keyword Impression Share ----
            with comp_tab1:
                if not df_kw_visible.empty:
                    kc1, kc2, kc3, kc4 = st.columns(4)
                    kc1.metric("Keywords Tracked", len(df_kw_visible))
                    kc2.metric("Avg Impression Share", f"{df_kw_visible['Impression Share'].mean():.1%}")
                    kc3.metric("Avg Top IS", f"{df_kw_visible['Top IS'].mean():.1%}")
                    kc4.metric("Avg Abs Top IS", f"{df_kw_visible['Abs Top IS'].mean():.1%}")

                    st.markdown("")

                    low_is = df_kw_visible[df_kw_visible["Impression Share"] < 0.50]
                    if not low_is.empty:
                        st.markdown(f'<div class="insight-box">⚠️ <strong>{len(low_is)} keywords</strong> have impression share below 50% — competitors are showing up more than you for these terms.</div>', unsafe_allow_html=True)
                        st.markdown("")

                    display_kw_is = df_kw_visible.copy()
                    display_kw_is["Impression Share"] = display_kw_is["Impression Share"].apply(lambda x: f"{x:.1%}")
                    display_kw_is["Top IS"] = display_kw_is["Top IS"].apply(lambda x: f"{x:.1%}")
                    display_kw_is["Abs Top IS"] = display_kw_is["Abs Top IS"].apply(lambda x: f"{x:.1%}")
                    display_kw_is["Lost IS (Rank)"] = display_kw_is["Lost IS (Rank)"].apply(lambda x: f"{x:.1%}")
                    display_kw_is["CTR"] = display_kw_is["CTR"].apply(lambda x: f"{x:.2%}")
                    display_kw_is["Cost"] = display_kw_is["Cost"].apply(lambda x: f"₹{x:,.2f}")
                    st.dataframe(display_kw_is, use_container_width=True, hide_index=True)

                    st.subheader("Impression Share by Keyword")
                    chart_is = df_kw_visible[["Keyword", "Impression Share"]].head(20).set_index("Keyword").sort_values("Impression Share")
                    st.bar_chart(chart_is)
                else:
                    if df_kw_is.empty:
                        st.info("No keyword impression share data found. Try expanding the date range.")
                    else:
                        st.info("No keywords with >10% impression share found. Try expanding the date range.")

            # ---- Competitive Gaps ----
            with comp_tab2:
                st.markdown("Keywords where **competitors are beating you** — sorted by how much impression share you're losing.")
                st.markdown("")

                if not df_kw_visible.empty:
                    gaps = df_kw_visible[df_kw_visible["Impression Share"] < 0.70].sort_values("Impression Share")

                    if not gaps.empty:
                        gaps = gaps.copy()
                        gaps["Lost IS"] = 1 - gaps["Impression Share"]
                        gaps["Est. Missed Clicks"] = (gaps["Clicks"] * gaps["Lost IS"] / gaps["Impression Share"]).apply(lambda x: max(0, int(x)))

                        gc1, gc2, gc3 = st.columns(3)
                        gc1.metric("Keywords with Gaps", len(gaps))
                        gc2.metric("Est. Total Missed Clicks", f"{gaps['Est. Missed Clicks'].sum():,}")
                        avg_lost = gaps["Lost IS"].mean()
                        gc3.metric("Avg Lost Impression Share", f"{avg_lost:.1%}")

                        st.markdown("")

                        rank_lost = gaps[gaps["Lost IS (Rank)"] > 0.10]

                        if not rank_lost.empty:
                            st.markdown(f'<div class="bad-box">🥊 <strong>{len(rank_lost)} keywords</strong> are losing to competitors due to <strong>ad rank</strong> (your bids or Quality Score are too low). Improve ad copy, landing pages, or increase bids.</div>', unsafe_allow_html=True)

                        st.markdown("")

                        for _, row in gaps.iterrows():
                            lost_pct = row["Lost IS"]
                            rank_loss = row["Lost IS (Rank)"]
                            budget_loss = max(0, lost_pct - rank_loss)
                            reason = "Rank" if rank_loss >= budget_loss else "Budget"
                            severity = "bad-box" if lost_pct > 0.5 else "insight-box"
                            st.markdown(
                                f'<div class="{severity}">🔑 <strong>{row["Keyword"]}</strong> ({row["Campaign"]}) — '
                                f'Your IS: {row["Impression Share"]:.1%} | '
                                f'Lost: {lost_pct:.1%} ({reason}) | '
                                f'~{row["Est. Missed Clicks"]:,} missed clicks</div>',
                                unsafe_allow_html=True,
                            )
                    else:
                        st.markdown('<div class="good-box">✅ Your keywords have strong impression share (>70%). You\'re dominating the competition!</div>', unsafe_allow_html=True)
                else:
                    st.info("No keyword data available for gap analysis.")

            # ---- Where to Invest ----
            with comp_tab3:
                st.markdown("Keywords with the **best opportunity** to gain more traffic by increasing bids or budget.")
                st.markdown("")

                if not df_kw_visible.empty:
                    # Score keywords by opportunity: high impressions + low IS + conversions
                    invest = df_kw_visible.copy()
                    invest["Lost IS"] = 1 - invest["Impression Share"]
                    invest["Est. Missed Clicks"] = (invest["Clicks"] * invest["Lost IS"] / invest["Impression Share"]).apply(lambda x: max(0, int(x)))
                    invest["Has Conversions"] = invest["Conversions"] > 0

                    # Priority 1: Converting keywords with low IS
                    converting_gaps = invest[(invest["Has Conversions"]) & (invest["Impression Share"] < 0.70)].sort_values("Conversions", ascending=False)

                    # Priority 2: High-traffic keywords with low IS
                    traffic_gaps = invest[(~invest["Has Conversions"]) & (invest["Impression Share"] < 0.70) & (invest["Clicks"] >= 5)].sort_values("Est. Missed Clicks", ascending=False)

                    if not converting_gaps.empty:
                        st.subheader("🎯 Priority 1: Converting Keywords with Low IS")
                        st.caption("These keywords already convert — investing more here will directly increase conversions.")
                        st.markdown("")
                        for _, row in converting_gaps.iterrows():
                            st.markdown(
                                f'<div class="good-box">🎯 <strong>{row["Keyword"]}</strong> — '
                                f'{row["Conversions"]:.0f} conversions | IS: {row["Impression Share"]:.1%} | '
                                f'~{row["Est. Missed Clicks"]:,} missed clicks | '
                                f'Lost to rank: {row["Lost IS (Rank)"]:.1%}</div>',
                                unsafe_allow_html=True,
                            )
                        st.markdown("")

                    if not traffic_gaps.empty:
                        st.subheader("📈 Priority 2: High-Traffic Keywords to Scale")
                        st.caption("These keywords get good traffic but aren't converting yet — worth testing with more budget.")
                        st.markdown("")
                        for _, row in traffic_gaps.head(10).iterrows():
                            st.markdown(
                                f'<div class="insight-box">📈 <strong>{row["Keyword"]}</strong> — '
                                f'{row["Clicks"]} clicks | IS: {row["Impression Share"]:.1%} | '
                                f'~{row["Est. Missed Clicks"]:,} missed clicks | '
                                f'CTR: {row["CTR"]:.2%}</div>',
                                unsafe_allow_html=True,
                            )

                    if converting_gaps.empty and traffic_gaps.empty:
                        st.markdown('<div class="good-box">✅ Your impression share is strong across all keywords. You\'re well-positioned!</div>', unsafe_allow_html=True)

                    st.markdown("")
                    st.markdown("---")
                    st.caption("💡 **Tip:** To see specific competitor domains, go to Google Ads > Campaigns > Auction Insights. This data isn't available via the API but gives you detailed competitor breakdowns.")
                else:
                    st.info("No keyword data available.")

        except Exception as comp_error:
            st.error(f"Error loading competitive data: {comp_error}")
            with st.expander("Error details"):
                st.code(str(comp_error))

    # =============================================
    # TAB 5: KEYWORD OPPORTUNITIES
    # =============================================
    with tab_opportunities:

        st.markdown("Discover search terms driving traffic that **aren't in your keyword list** — these are potential new keywords to add to your campaigns.")
        st.markdown("")

        # Fetch all search terms with broader limit
        query_all_search = f"""
            SELECT
                search_term_view.search_term,
                search_term_view.status,
                campaign.name,
                ad_group.name,
                metrics.impressions,
                metrics.clicks,
                metrics.ctr,
                metrics.cost_micros,
                metrics.conversions
            FROM search_term_view
            WHERE {date_clause}
                {status_clause}
            ORDER BY metrics.impressions DESC
            LIMIT 200
        """
        # Fetch all keywords
        query_all_kw = f"""
            SELECT
                ad_group_criterion.keyword.text,
                ad_group_criterion.keyword.match_type
            FROM keyword_view
            WHERE {date_clause}
                {status_clause}
        """

        try:
            rows_all_st = fetch_data(query_all_search)
            rows_all_kw = fetch_data(query_all_kw)

            # Build set of existing keywords (lowercase for comparison)
            existing_keywords = set()
            for row in rows_all_kw:
                existing_keywords.add(row.ad_group_criterion.keyword.text.lower().strip())

            # Find search terms not matching existing keywords
            opportunities = []
            already_targeted = []
            for row in rows_all_st:
                if selected_campaigns and row.campaign.name not in selected_campaigns:
                    continue
                term = row.search_term_view.search_term
                cost = row.metrics.cost_micros / 1_000_000
                conversions = row.metrics.conversions
                is_new = term.lower().strip() not in existing_keywords

                entry = {
                    "Search Term": term,
                    "Campaign": row.campaign.name,
                    "Ad Group": row.ad_group.name,
                    "Impressions": row.metrics.impressions,
                    "Clicks": row.metrics.clicks,
                    "CTR": row.metrics.ctr,
                    "Cost": cost,
                    "Conversions": conversions,
                    "CPA": cost / conversions if conversions > 0 else 0,
                }

                if is_new:
                    opportunities.append(entry)
                else:
                    already_targeted.append(entry)

            df_opps = pd.DataFrame(opportunities)
            df_targeted = pd.DataFrame(already_targeted)

            # Sub-tabs
            opp_tab1, opp_tab2, opp_tab3 = st.tabs([
                "🌟 High-Value Opportunities",
                "📊 All Untargeted Terms",
                "✅ Already Targeted",
            ])

            with opp_tab1:
                if not df_opps.empty:
                    # High-value = has conversions OR high clicks with decent CTR
                    high_value = df_opps[
                        (df_opps["Conversions"] > 0) |
                        ((df_opps["Clicks"] >= 3) & (df_opps["CTR"] >= 0.02))
                    ].sort_values(
                        ["Conversions", "Clicks"], ascending=[False, False]
                    )

                    if not high_value.empty:
                        oc1, oc2, oc3 = st.columns(3)
                        oc1.metric("High-Value Opportunities", len(high_value))
                        converting_opps = len(high_value[high_value["Conversions"] > 0])
                        oc2.metric("Already Converting", converting_opps)
                        oc3.metric("Potential Extra Clicks", f"{high_value['Clicks'].sum():,}")

                        st.markdown("")
                        st.markdown('<div class="good-box">💡 <strong>These search terms are performing well but aren\'t targeted as keywords.</strong> Adding them could give you more control over bids and ad copy.</div>', unsafe_allow_html=True)
                        st.markdown("")

                        # Converting opportunities first
                        converting_opps_df = high_value[high_value["Conversions"] > 0]
                        if not converting_opps_df.empty:
                            st.subheader("🎯 Converting — Add These First!")
                            st.caption("These search terms are already converting without being targeted. Adding them as exact match keywords gives you more control.")
                            for _, row in converting_opps_df.iterrows():
                                st.markdown(
                                    f'<div class="good-box">🎯 <strong>{row["Search Term"]}</strong> — '
                                    f'{row["Conversions"]:.0f} conversions, {row["Clicks"]} clicks, '
                                    f'{row["CTR"]:.2%} CTR, ₹{row["Cost"]:,.2f} cost '
                                    f'(in {row["Campaign"]})</div>',
                                    unsafe_allow_html=True,
                                )
                            st.markdown("")

                        # High-click opportunities
                        click_opps = high_value[high_value["Conversions"] == 0]
                        if not click_opps.empty:
                            st.subheader("👆 High Traffic — Worth Testing")
                            st.caption("Good click volume and CTR. Add as keywords and monitor for conversions.")
                            display_click = click_opps.copy()
                            display_click["CTR"] = display_click["CTR"].apply(lambda x: f"{x:.2%}")
                            display_click["Cost"] = display_click["Cost"].apply(lambda x: f"₹{x:,.2f}")
                            display_click = display_click.drop(columns=["CPA"])
                            st.dataframe(display_click, use_container_width=True, hide_index=True)
                    else:
                        st.info("No high-value opportunities found. Try expanding the date range for more data.")
                else:
                    st.info("No untargeted search terms found.")

            with opp_tab2:
                if not df_opps.empty:
                    st.markdown(f"Found **{len(df_opps)} search terms** that triggered your ads but aren't in your keyword list.")
                    st.markdown("")

                    # Search filter
                    opp_filter = st.text_input("🔍 Filter opportunities", placeholder="Type to search...", key="opp_filter")
                    filtered_opps = df_opps
                    if opp_filter:
                        filtered_opps = df_opps[df_opps["Search Term"].str.contains(opp_filter, case=False, na=False)]

                    display_opps = filtered_opps.copy()
                    display_opps["CTR"] = display_opps["CTR"].apply(lambda x: f"{x:.2%}")
                    display_opps["Cost"] = display_opps["Cost"].apply(lambda x: f"₹{x:,.2f}")
                    display_opps["CPA"] = display_opps["CPA"].apply(lambda x: f"₹{x:.2f}" if x > 0 else "-")
                    st.dataframe(display_opps, use_container_width=True, hide_index=True)
                else:
                    st.info("All search terms are already targeted as keywords. Great coverage!")

            with opp_tab3:
                if not df_targeted.empty:
                    st.markdown(f"**{len(df_targeted)} search terms** are already matched to your keywords.")
                    st.markdown("")
                    display_targeted = df_targeted.copy()
                    display_targeted["CTR"] = display_targeted["CTR"].apply(lambda x: f"{x:.2%}")
                    display_targeted["Cost"] = display_targeted["Cost"].apply(lambda x: f"₹{x:,.2f}")
                    display_targeted["CPA"] = display_targeted["CPA"].apply(lambda x: f"₹{x:.2f}" if x > 0 else "-")
                    st.dataframe(display_targeted, use_container_width=True, hide_index=True)
                else:
                    st.info("No matched search terms found.")

        except Exception as opp_error:
            st.error(f"Error loading keyword opportunities: {opp_error}")

    # =============================================
    # TAB 6: LANDING PAGES (Ads + Google Analytics)
    # =============================================
    with tab_landing:

        st.markdown("Analyze **landing page performance from your ads** — combining Google Ads spend data with Google Analytics engagement metrics.")
        st.markdown("")

        try:
            from google.analytics.data_v1beta.types import (
                RunReportRequest,
                DateRange,
                Dimension,
                Metric,
                OrderBy,
                FilterExpression,
                Filter,
            )
            from urllib.parse import urlparse

            ga4_client = get_ga4_client()
            ga4_property = get_ga4_property_id()

            if not ga4_property:
                st.warning("GA4 Property ID not configured. Add GA4_PROPERTY_ID to your .env or Streamlit secrets.")
            else:
                ga_start = start_date.strftime("%Y-%m-%d")
                ga_end = end_date.strftime("%Y-%m-%d")

                # ----- 1. Google Ads: Landing page spend data -----
                query_lp_ads = f"""
                    SELECT
                        landing_page_view.unexpanded_final_url,
                        campaign.name,
                        campaign.status,
                        ad_group.name,
                        metrics.clicks,
                        metrics.impressions,
                        metrics.cost_micros,
                        metrics.conversions,
                        metrics.cost_per_conversion
                    FROM landing_page_view
                    WHERE {date_clause}
                        {status_clause}
                    ORDER BY metrics.cost_micros DESC
                    LIMIT 100
                """
                rows_lp_ads = fetch_data(query_lp_ads)

                ads_lp_data = []
                for row in rows_lp_ads:
                    if selected_campaigns and row.campaign.name not in selected_campaigns:
                        continue
                    url = row.landing_page_view.unexpanded_final_url
                    cost = row.metrics.cost_micros / 1_000_000
                    conversions = row.metrics.conversions
                    path = urlparse(url).path or "/"
                    ads_lp_data.append({
                        "Landing Page": url,
                        "Campaign": row.campaign.name,
                        "Ad Group": row.ad_group.name,
                        "Path": path,
                        "Ad Clicks": row.metrics.clicks,
                        "Ad Impressions": row.metrics.impressions,
                        "Ad Spend": cost,
                        "Ad Conversions": conversions,
                        "Ad CPA": row.metrics.cost_per_conversion / 1_000_000 if conversions > 0 else 0,
                    })

                df_ads_lp = pd.DataFrame(ads_lp_data)

                # ----- 2. GA4: Paid search landing page engagement -----
                ga_request = RunReportRequest(
                    property=f"properties/{ga4_property}",
                    dimensions=[
                        Dimension(name="landingPage"),
                    ],
                    metrics=[
                        Metric(name="sessions"),
                        Metric(name="bounceRate"),
                        Metric(name="averageSessionDuration"),
                        Metric(name="engagedSessions"),
                        Metric(name="conversions"),
                    ],
                    date_ranges=[DateRange(start_date=ga_start, end_date=ga_end)],
                    dimension_filter=FilterExpression(
                        filter=Filter(
                            field_name="sessionDefaultChannelGroup",
                            string_filter=Filter.StringFilter(
                                value="Paid Search",
                                match_type=Filter.StringFilter.MatchType.EXACT,
                            ),
                        ),
                    ),
                    order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
                    limit=100,
                )

                ga_response = ga4_client.run_report(ga_request)

                ga_lp_data = {}
                for row in ga_response.rows:
                    page = row.dimension_values[0].value
                    if page == "(not set)":
                        continue
                    sess = int(row.metric_values[0].value)
                    if sess == 0:
                        continue
                    bounce = float(row.metric_values[1].value)
                    avg_dur = float(row.metric_values[2].value)
                    engaged = int(row.metric_values[3].value)
                    ga_conv = int(float(row.metric_values[4].value))

                    ga_lp_data[page] = {
                        "GA Sessions": sess,
                        "Bounce Rate": bounce,
                        "Avg Duration (s)": round(avg_dur, 1),
                        "Engagement Rate": engaged / sess if sess > 0 else 0,
                        "GA Conversions": ga_conv,
                    }

                # ----- 3. Merge Ads + GA4 data -----
                if not df_ads_lp.empty:
                    # Match on path
                    for ga_path, ga_metrics in ga_lp_data.items():
                        mask = df_ads_lp["Path"] == ga_path
                        for col, val in ga_metrics.items():
                            df_ads_lp.loc[mask, col] = val

                    # Fill missing GA columns
                    for col in ["GA Sessions", "Bounce Rate", "Avg Duration (s)", "Engagement Rate", "GA Conversions"]:
                        if col not in df_ads_lp.columns:
                            df_ads_lp[col] = 0
                        df_ads_lp[col] = df_ads_lp[col].fillna(0)

                    df_ads_lp["Cost per Session"] = df_ads_lp.apply(
                        lambda r: r["Ad Spend"] / r["GA Sessions"] if r["GA Sessions"] > 0 else 0, axis=1
                    )

                    # Sub-tabs
                    lp_tab1, lp_tab2, lp_tab3 = st.tabs([
                        "📊 Ads Landing Page Performance",
                        "🚨 Wasted Ad Spend",
                        "💡 Optimization Tips",
                    ])

                    with lp_tab1:
                        # KPIs
                        lc1, lc2, lc3, lc4, lc5 = st.columns(5)
                        lc1.metric("Landing Pages", len(df_ads_lp))
                        lc2.metric("Total Ad Spend", f"₹{df_ads_lp['Ad Spend'].sum():,.2f}")
                        lc3.metric("Total Ad Clicks", f"{df_ads_lp['Ad Clicks'].sum():,}")
                        avg_bounce = df_ads_lp[df_ads_lp["Bounce Rate"] > 0]["Bounce Rate"].mean()
                        lc4.metric("Avg Bounce Rate", f"{avg_bounce:.1%}" if avg_bounce > 0 else "-")
                        lc5.metric("Ad Conversions", f"{df_ads_lp['Ad Conversions'].sum():,.0f}")

                        st.markdown("")

                        # Combined table
                        st.subheader("Landing Page Performance (Ads + Analytics)")
                        display_lp = df_ads_lp.drop(columns=["Path"]).copy()
                        display_lp["Ad Spend"] = display_lp["Ad Spend"].apply(lambda x: f"₹{x:,.2f}")
                        display_lp["Ad CPA"] = display_lp["Ad CPA"].apply(lambda x: f"₹{x:.2f}" if x > 0 else "-")
                        display_lp["Bounce Rate"] = display_lp["Bounce Rate"].apply(lambda x: f"{x:.1%}" if x > 0 else "-")
                        display_lp["Engagement Rate"] = display_lp["Engagement Rate"].apply(lambda x: f"{x:.1%}" if x > 0 else "-")
                        display_lp["Avg Duration (s)"] = display_lp["Avg Duration (s)"].apply(lambda x: f"{x:.0f}s" if x > 0 else "-")
                        display_lp["Cost per Session"] = display_lp["Cost per Session"].apply(lambda x: f"₹{x:.2f}" if x > 0 else "-")
                        display_lp["GA Sessions"] = display_lp["GA Sessions"].astype(int)
                        display_lp["GA Conversions"] = display_lp["GA Conversions"].astype(int)
                        st.dataframe(display_lp, use_container_width=True, hide_index=True)

                        # Charts
                        col1, col2 = st.columns(2)
                        with col1:
                            st.subheader("Ad Spend by Landing Page")
                            chart_spend = df_ads_lp[["Landing Page", "Ad Spend"]].head(15).set_index("Landing Page").sort_values("Ad Spend")
                            st.bar_chart(chart_spend)
                        with col2:
                            st.subheader("Bounce Rate by Landing Page")
                            chart_bounce = df_ads_lp[df_ads_lp["Bounce Rate"] > 0][["Landing Page", "Bounce Rate"]].head(15).set_index("Landing Page").sort_values("Bounce Rate")
                            if not chart_bounce.empty:
                                st.bar_chart(chart_bounce)
                            else:
                                st.info("No bounce rate data available from GA4 for paid traffic.")

                    with lp_tab2:
                        st.markdown("Landing pages where you're **spending ad money** but visitors are **bouncing or not converting**.")
                        st.markdown("")

                        # Pages with high spend + high bounce
                        wasted = df_ads_lp[
                            (df_ads_lp["Bounce Rate"] > 0.50) &
                            (df_ads_lp["Ad Spend"] > 0)
                        ].sort_values("Ad Spend", ascending=False)

                        if not wasted.empty:
                            total_wasted_spend = wasted["Ad Spend"].sum()
                            wc1, wc2, wc3 = st.columns(3)
                            wc1.metric("Pages with High Bounce", len(wasted))
                            wc2.metric("Spend on High-Bounce Pages", f"₹{total_wasted_spend:,.2f}")
                            est_waste = total_wasted_spend * wasted["Bounce Rate"].mean()
                            wc3.metric("Est. Wasted Spend", f"₹{est_waste:,.2f}")

                            st.markdown("")
                            st.markdown(f'<div class="bad-box">🚨 You\'re spending <strong>₹{total_wasted_spend:,.2f}</strong> sending ad traffic to pages where over half the visitors bounce immediately.</div>', unsafe_allow_html=True)
                            st.markdown("")

                            for _, row in wasted.iterrows():
                                severity = "bad-box" if row["Bounce Rate"] > 0.70 else "insight-box"
                                st.markdown(
                                    f'<div class="{severity}">💸 <strong>{row["Landing Page"]}</strong><br>'
                                    f'<small>Campaign: {row["Campaign"]} | Ad Group: {row["Ad Group"]}</small><br>'
                                    f'Spend: ₹{row["Ad Spend"]:,.2f} | '
                                    f'{row["Ad Clicks"]:,} clicks | '
                                    f'Bounce: {row["Bounce Rate"]:.0%} | '
                                    f'Avg duration: {row["Avg Duration (s)"]:.0f}s | '
                                    f'Conversions: {row["Ad Conversions"]:.0f}</div>',
                                    unsafe_allow_html=True,
                                )
                        else:
                            st.markdown('<div class="good-box">✅ No major wasted spend detected. Your landing pages have acceptable bounce rates.</div>', unsafe_allow_html=True)

                        # High spend, zero conversions
                        st.markdown("")
                        no_conv = df_ads_lp[
                            (df_ads_lp["Ad Conversions"] == 0) &
                            (df_ads_lp["Ad Spend"] > 0)
                        ].sort_values("Ad Spend", ascending=False)

                        if not no_conv.empty:
                            st.subheader("Spending But Not Converting")
                            st.caption("These pages receive ad traffic and spend but haven't generated any conversions.")
                            total_no_conv_spend = no_conv["Ad Spend"].sum()
                            st.markdown(f'<div class="insight-box">💰 <strong>₹{total_no_conv_spend:,.2f}</strong> spent on pages with zero conversions. Review landing page content, CTAs, and ad-to-page relevance.</div>', unsafe_allow_html=True)
                            st.markdown("")

                            for _, row in no_conv.head(10).iterrows():
                                dur_str = f"{row['Avg Duration (s)']:.0f}s" if row["Avg Duration (s)"] > 0 else "no GA data"
                                bounce_str = f"{row['Bounce Rate']:.0%}" if row["Bounce Rate"] > 0 else "no GA data"
                                st.markdown(
                                    f'<div class="bad-box">🔥 <strong>{row["Landing Page"]}</strong><br>'
                                    f'<small>Campaign: {row["Campaign"]} | Ad Group: {row["Ad Group"]}</small><br>'
                                    f'Spend: ₹{row["Ad Spend"]:,.2f} | '
                                    f'{row["Ad Clicks"]:,} clicks | '
                                    f'Bounce: {bounce_str} | Duration: {dur_str}</div>',
                                    unsafe_allow_html=True,
                                )

                    with lp_tab3:
                        st.markdown("Actionable recommendations to improve your ad landing page ROI.")
                        st.markdown("")

                        tips = []

                        # Best page to scale
                        converting_pages = df_ads_lp[df_ads_lp["Ad Conversions"] > 0].sort_values("Ad CPA")
                        if not converting_pages.empty:
                            best = converting_pages.iloc[0]
                            tips.append(("good-box", "🚀", "Scale Your Best Landing Page",
                                f"<strong>{best['Landing Page']}</strong> "
                                f"(Campaign: {best['Campaign']} → {best['Ad Group']}) "
                                f"has the lowest CPA at <strong>₹{best['Ad CPA']:.2f}</strong> "
                                f"with {best['Ad Conversions']:.0f} conversions. Send more ad traffic here."))

                        # High bounce + high spend
                        if not wasted.empty:
                            worst = wasted.iloc[0]
                            tips.append(("bad-box", "🚪", "Fix or Replace Your Leakiest Page",
                                f"<strong>{worst['Landing Page']}</strong> "
                                f"(Campaign: {worst['Campaign']} → {worst['Ad Group']}) — "
                                f"you're spending <strong>₹{worst['Ad Spend']:,.2f}</strong> "
                                f"but <strong>{worst['Bounce Rate']:.0%}</strong> of visitors bounce. "
                                f"Either improve this page (speed, content, CTA) or redirect ads to a better-performing page."))

                        # High engagement but no conversions
                        engaged_no_conv = df_ads_lp[
                            (df_ads_lp["Engagement Rate"] > 0.50) &
                            (df_ads_lp["Ad Conversions"] == 0) &
                            (df_ads_lp["Ad Spend"] > 0)
                        ].sort_values("Ad Spend", ascending=False)
                        if not engaged_no_conv.empty:
                            page = engaged_no_conv.iloc[0]
                            tips.append(("insight-box", "🤔", "Engaged Visitors Not Converting",
                                f"<strong>{page['Landing Page']}</strong> "
                                f"(Campaign: {page['Campaign']} → {page['Ad Group']}) — "
                                f"visitors spend {page['Avg Duration (s)']:.0f}s on page "
                                f"(good engagement) but aren't converting. The CTA may be weak or hard to find. "
                                f"Try A/B testing the page with a stronger call-to-action."))

                        # Ad-to-page mismatch (high clicks, very low duration)
                        mismatch = df_ads_lp[
                            (df_ads_lp["Avg Duration (s)"] > 0) &
                            (df_ads_lp["Avg Duration (s)"] < 10) &
                            (df_ads_lp["Ad Clicks"] >= 10)
                        ].sort_values("Ad Spend", ascending=False)
                        if not mismatch.empty:
                            page = mismatch.iloc[0]
                            tips.append(("bad-box", "⚡", "Ad-to-Page Mismatch",
                                f"<strong>{page['Landing Page']}</strong> "
                                f"(Campaign: {page['Campaign']} → {page['Ad Group']}) — "
                                f"visitors leave within {page['Avg Duration (s)']:.0f}s despite "
                                f"{page['Ad Clicks']:,} ad clicks. Your ad copy may be promising something the landing page doesn't deliver. "
                                f"Align your ad messaging with the page content."))

                        # Cost per session analysis
                        if df_ads_lp["Cost per Session"].max() > 0:
                            expensive = df_ads_lp[df_ads_lp["Cost per Session"] > 0].sort_values("Cost per Session", ascending=False)
                            if not expensive.empty:
                                most_expensive = expensive.iloc[0]
                                cheapest_converting = converting_pages.sort_values("Cost per Session").iloc[0] if not converting_pages.empty and "Cost per Session" in converting_pages.columns else None
                                if cheapest_converting is not None and most_expensive["Cost per Session"] > cheapest_converting["Cost per Session"] * 2:
                                    tips.append(("insight-box", "💰", "Cost Efficiency Gap",
                                        f"Your most expensive page costs <strong>₹{most_expensive['Cost per Session']:.2f}/session</strong> "
                                        f"(<strong>{most_expensive['Landing Page']}</strong>) while your cheapest converting page is only "
                                        f"<strong>₹{cheapest_converting['Cost per Session']:.2f}/session</strong>. Consider shifting budget."))

                        if tips:
                            for box_class, icon, title, description in tips:
                                st.markdown(f'<div class="{box_class}">{icon} <strong>{title}:</strong> {description}</div>', unsafe_allow_html=True)
                                st.markdown("")
                        else:
                            st.markdown('<div class="good-box">✅ Your ad landing pages look healthy! No major issues detected.</div>', unsafe_allow_html=True)

                else:
                    st.info("No landing page data found from Google Ads for this date range.")

        except ImportError:
            st.warning("Google Analytics library not installed. Run: `pip install google-analytics-data`")
        except Exception as ga_error:
            st.error(f"Error loading landing page data: {ga_error}")
            with st.expander("Error details"):
                st.code(str(ga_error))
            st.caption("Make sure your refresh token has Google Analytics permissions. You may need to re-run `python get_refresh_token.py` to re-authorize.")

    # =============================================
    # TAB 7: ASK AI (Chat with your data)
    # =============================================
    with tab_chat:

        st.markdown("Ask questions about your Google Ads data and get **AI-powered answers**.")
        st.markdown("")

        openai_key = get_openai_api_key()

        if not openai_key:
            st.warning("OpenAI API key not configured. Add `OPENAI_API_KEY` to your .env or Streamlit secrets.")
            st.markdown("""
**How to get your OpenAI API key:**
1. Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Click **Create new secret key**
3. Copy the key and add it to your secrets
            """)
        else:
            try:
                from openai import OpenAI

                oai_client = OpenAI(api_key=openai_key)

                # Build context from all loaded data
                context_parts = []
                context_parts.append(f"Date range: {start_date} to {end_date}")

                if not df_campaigns.empty:
                    context_parts.append(f"\n--- CAMPAIGN DATA ({len(df_campaigns)} campaigns) ---")
                    for _, row in df_campaigns.iterrows():
                        context_parts.append(
                            f"Campaign: {row['Campaign']} | Status: {row['Status']} | "
                            f"Spend: ₹{row['Cost']:,.2f} | Clicks: {row['Clicks']:,} | "
                            f"Impressions: {row['Impressions']:,} | CTR: {row['CTR']:.2%} | "
                            f"CPC: ₹{row['Avg CPC']:.2f} | Conversions: {row['Conversions']:.0f} | "
                            f"CPA: ₹{row['Cost/Conv']:.2f}"
                        )
                    context_parts.append(
                        f"\nTOTALS: Spend=₹{df_campaigns['Cost'].sum():,.2f}, "
                        f"Clicks={df_campaigns['Clicks'].sum():,}, "
                        f"Impressions={df_campaigns['Impressions'].sum():,}, "
                        f"Conversions={df_campaigns['Conversions'].sum():.0f}"
                    )

                try:
                    if not df_kw.empty:
                        context_parts.append(f"\n--- KEYWORD DATA (top {len(df_kw)} keywords) ---")
                        for _, row in df_kw.head(30).iterrows():
                            context_parts.append(
                                f"Keyword: {row['Keyword']} | Match: {row['Match Type']} | "
                                f"Campaign: {row['Campaign']} | Clicks: {row['Clicks']} | "
                                f"CTR: {row['CTR']:.2%} | CPC: ₹{row['CPC']:.2f} | "
                                f"Cost: ₹{row['Cost']:,.2f} | Conversions: {row['Conversions']:.0f}"
                            )
                except NameError:
                    pass

                try:
                    if not df_st.empty:
                        context_parts.append(f"\n--- SEARCH TERM DATA (top {len(df_st)} terms) ---")
                        for _, row in df_st.head(30).iterrows():
                            context_parts.append(
                                f"Search Term: {row['Search Term']} | Campaign: {row['Campaign']} | "
                                f"Clicks: {row['Clicks']} | CTR: {row['CTR']:.2%} | "
                                f"Cost: ₹{row['Cost']:,.2f} | Conversions: {row['Conversions']:.0f}"
                            )
                except NameError:
                    pass

                try:
                    if not df_ads_lp.empty:
                        context_parts.append(f"\n--- LANDING PAGE DATA ({len(df_ads_lp)} pages) ---")
                        for _, row in df_ads_lp.head(20).iterrows():
                            context_parts.append(
                                f"URL: {row['Landing Page']} | Campaign: {row['Campaign']} | "
                                f"Ad Group: {row['Ad Group']} | Spend: ₹{row['Ad Spend']:,.2f} | "
                                f"Clicks: {row['Ad Clicks']} | Conversions: {row['Ad Conversions']:.0f} | "
                                f"Bounce Rate: {row.get('Bounce Rate', 0):.1%}"
                            )
                except NameError:
                    pass

                data_context = "\n".join(context_parts)

                system_prompt = (
                    "You are a Google Ads analyst assistant. You answer questions about the user's Google Ads account data.\n"
                    "Be concise, specific, and actionable. Use the actual numbers from the data. Currency is INR (₹).\n"
                    "If the user asks something not covered by the data, say so honestly.\n\n"
                    f"Here is the current account data:\n{data_context}"
                )

                # Initialize chat history
                if "chat_history" not in st.session_state:
                    st.session_state.chat_history = []

                # Display chat history
                for msg in st.session_state.chat_history:
                    with st.chat_message(msg["role"]):
                        st.markdown(msg["content"])

                # Helper to call OpenAI and store response
                def get_ai_response(user_question):
                    st.session_state.chat_history.append({"role": "user", "content": user_question})
                    messages = [{"role": "system", "content": system_prompt}]
                    for m in st.session_state.chat_history:
                        messages.append({"role": m["role"], "content": m["content"]})
                    try:
                        resp = oai_client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=messages,
                        )
                        answer = resp.choices[0].message.content
                    except Exception as api_err:
                        answer = f"Error: {api_err}"
                    st.session_state.chat_history.append({"role": "assistant", "content": answer})

                # Suggested questions (only when no history)
                if not st.session_state.chat_history:
                    st.markdown("**Try asking:**")
                    suggestions = [
                        "Which campaign is performing best?",
                        "Where am I wasting the most money?",
                        "What keywords should I pause?",
                        "Summarize my account performance",
                    ]
                    sc1, sc2 = st.columns(2)
                    for i, suggestion in enumerate(suggestions):
                        col = sc1 if i % 2 == 0 else sc2
                        if col.button(suggestion, key=f"suggest_{i}", use_container_width=True):
                            get_ai_response(suggestion)
                            st.rerun()

                # Chat form (works reliably inside tabs)
                with st.form("chat_form", clear_on_submit=True):
                    user_input = st.text_input("Your question:", placeholder="Ask about your ads data...", label_visibility="collapsed")
                    submitted = st.form_submit_button("Send", use_container_width=True)

                if submitted and user_input.strip():
                    get_ai_response(user_input.strip())
                    st.rerun()

                # Clear chat button
                if st.session_state.chat_history:
                    if st.button("🗑️ Clear chat", key="clear_chat"):
                        st.session_state.chat_history = []
                        st.rerun()

            except ImportError:
                st.warning("OpenAI library not installed. Run: `pip install openai`")
            except Exception as chat_error:
                st.error(f"Error with AI chat: {chat_error}")
                with st.expander("Error details"):
                    st.code(str(chat_error))

except Exception as e:
    st.error(f"Error connecting to Google Ads: {e}")
    with st.expander("Error details"):
        st.code(str(e))
    st.info("Please check your credentials in the .env file and make sure the Google Ads API is enabled in Google Cloud Console.")
