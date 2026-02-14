import streamlit as st
import pandas as pd
from config import get_google_ads_client, get_customer_id

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
    date_range = st.selectbox("📅 Date Range", [
        "LAST_7_DAYS", "LAST_14_DAYS", "LAST_30_DAYS", "LAST_90_DAYS",
    ], index=2, format_func=lambda x: x.replace("_", " ").title())
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
        WHERE segments.date DURING {date_range}
            AND campaign.status != 'REMOVED'
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
        c1.metric("Total Spend", f"${total_spend:,.2f}")
        c2.metric("Clicks", f"{total_clicks:,}")
        c3.metric("Impressions", f"{total_impressions:,}")
        c4.metric("CTR", f"{overall_ctr:.2%}")
        c5.metric("Avg CPC", f"${overall_cpc:.2f}")
        c6.metric("Conversions", f"{total_conversions:,.0f}")

        st.markdown("")
    else:
        st.warning("No campaign data found for this date range.")

    # =============================================
    # TABS
    # =============================================
    tab_overview, tab_trends, tab_kw_analysis = st.tabs([
        "🏠 Overview", "📈 Daily Trends", "🔍 Keyword & Search Term Analysis"
    ])

    # =============================================
    # TAB 1: OVERVIEW
    # =============================================
    with tab_overview:

        if not df_campaigns.empty:
            # Campaign performance table
            st.subheader("Campaign Performance")
            display_df = df_campaigns.copy()
            display_df["CTR"] = display_df["CTR"].apply(lambda x: f"{x:.2%}")
            display_df["Avg CPC"] = display_df["Avg CPC"].apply(lambda x: f"${x:.2f}")
            display_df["Cost"] = display_df["Cost"].apply(lambda x: f"${x:,.2f}")
            display_df["Cost/Conv"] = display_df["Cost/Conv"].apply(lambda x: f"${x:.2f}" if x > 0 else "-")
            st.dataframe(display_df, width="stretch", hide_index=True)

            # Charts side by side
            col_left, col_right = st.columns(2)
            with col_left:
                st.subheader("Spend by Campaign")
                chart_spend = df_campaigns[["Campaign", "Cost"]].set_index("Campaign").sort_values("Cost")
                st.bar_chart(chart_spend)
            with col_right:
                st.subheader("Clicks by Campaign")
                chart_clicks = df_campaigns[["Campaign", "Clicks"]].set_index("Campaign").sort_values("Clicks")
                st.bar_chart(chart_clicks)

            # Quick insights
            st.subheader("Quick Insights")
            best_ctr = df_campaigns.loc[df_campaigns["CTR"].idxmax()]
            worst_ctr = df_campaigns.loc[df_campaigns[df_campaigns["Clicks"] > 0]["CTR"].idxmin()] if (df_campaigns["Clicks"] > 0).any() else None
            biggest_spender = df_campaigns.loc[df_campaigns["Cost"].idxmax()]

            st.markdown(f'<div class="good-box">🏆 <strong>Best CTR:</strong> {best_ctr["Campaign"]} at {best_ctr["CTR"]:.2%}</div>', unsafe_allow_html=True)
            if worst_ctr is not None:
                st.markdown(f'<div class="bad-box">⚠️ <strong>Lowest CTR:</strong> {worst_ctr["Campaign"]} at {worst_ctr["CTR"]:.2%} — consider revising ad copy</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="insight-box">💰 <strong>Biggest spender:</strong> {biggest_spender["Campaign"]} at ${biggest_spender["Cost"]:,.2f}</div>', unsafe_allow_html=True)

    # =============================================
    # TAB 2: DAILY TRENDS
    # =============================================
    with tab_trends:

        query_daily = f"""
            SELECT
                segments.date,
                metrics.cost_micros,
                metrics.clicks,
                metrics.impressions,
                metrics.conversions
            FROM campaign
            WHERE segments.date DURING {date_range}
                AND campaign.status != 'REMOVED'
            ORDER BY segments.date ASC
        """
        rows_daily = fetch_data(query_daily)

        daily_data = {}
        for row in rows_daily:
            date = row.segments.date
            if date not in daily_data:
                daily_data[date] = {"Cost": 0, "Clicks": 0, "Impressions": 0, "Conversions": 0}
            daily_data[date]["Cost"] += row.metrics.cost_micros / 1_000_000
            daily_data[date]["Clicks"] += row.metrics.clicks
            daily_data[date]["Impressions"] += row.metrics.impressions
            daily_data[date]["Conversions"] += row.metrics.conversions

        if daily_data:
            df_daily = pd.DataFrame.from_dict(daily_data, orient="index")
            df_daily.index = pd.to_datetime(df_daily.index)
            df_daily = df_daily.sort_index()

            # Summary row
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Avg Daily Spend", f"${df_daily['Cost'].mean():,.2f}")
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

            # Peak day analysis
            st.subheader("Peak Days")
            peak_spend_day = df_daily["Cost"].idxmax().strftime("%A, %b %d")
            peak_clicks_day = df_daily["Clicks"].idxmax().strftime("%A, %b %d")
            pc1, pc2 = st.columns(2)
            pc1.markdown(f'<div class="insight-box">💰 <strong>Highest spend day:</strong> {peak_spend_day} (${df_daily["Cost"].max():,.2f})</div>', unsafe_allow_html=True)
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
            WHERE segments.date DURING {date_range}
                AND campaign.status != 'REMOVED'
            ORDER BY metrics.cost_micros DESC
            LIMIT 50
        """
        rows_kw = fetch_data(query_keywords)

        kw_data = []
        for row in rows_kw:
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
            WHERE segments.date DURING {date_range}
                AND campaign.status != 'REMOVED'
            ORDER BY metrics.cost_micros DESC
            LIMIT 100
        """
        rows_st = fetch_data(query_search)

        st_data = []
        for row in rows_st:
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

        # --- KPI row for this section ---
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
                # Filter by match type
                match_types = ["All"] + sorted(df_kw["Match Type"].unique().tolist())
                selected_match = st.selectbox("Filter by Match Type", match_types)

                filtered_kw = df_kw if selected_match == "All" else df_kw[df_kw["Match Type"] == selected_match]

                display_kw = filtered_kw.copy()
                display_kw["CTR"] = display_kw["CTR"].apply(lambda x: f"{x:.2%}")
                display_kw["CPC"] = display_kw["CPC"].apply(lambda x: f"${x:.2f}")
                display_kw["Cost"] = display_kw["Cost"].apply(lambda x: f"${x:,.2f}")
                display_kw["CPA"] = display_kw["CPA"].apply(lambda x: f"${x:.2f}" if x > 0 else "-")
                st.dataframe(display_kw, width="stretch", hide_index=True)

                # Match type breakdown
                st.subheader("Spend by Match Type")
                match_summary = df_kw.groupby("Match Type").agg(
                    Keywords=("Keyword", "count"),
                    Clicks=("Clicks", "sum"),
                    Cost=("Cost", "sum"),
                    Conversions=("Conversions", "sum"),
                ).reset_index()
                match_summary["Avg CPC"] = match_summary.apply(lambda r: f"${r['Cost']/r['Clicks']:.2f}" if r["Clicks"] > 0 else "-", axis=1)
                match_summary["Cost"] = match_summary["Cost"].apply(lambda x: f"${x:,.2f}")
                st.dataframe(match_summary, width="stretch", hide_index=True)
            else:
                st.info("No keyword data found for this date range.")

        # ---- Search Terms ----
        with kw_tab2:
            if not df_st.empty:
                # Search filter
                search_filter = st.text_input("🔍 Search for a term", placeholder="Type to filter search terms...")
                filtered_st = df_st
                if search_filter:
                    filtered_st = df_st[df_st["Search Term"].str.contains(search_filter, case=False, na=False)]

                display_st = filtered_st.copy()
                display_st["CTR"] = display_st["CTR"].apply(lambda x: f"{x:.2%}")
                display_st["Cost"] = display_st["Cost"].apply(lambda x: f"${x:,.2f}")
                display_st["CPA"] = display_st["CPA"].apply(lambda x: f"${x:.2f}" if x > 0 else "-")
                st.dataframe(display_st, width="stretch", hide_index=True)

                # Top converting search terms
                converting = df_st[df_st["Conversions"] > 0].sort_values("Conversions", ascending=False).head(10)
                if not converting.empty:
                    st.subheader("🏆 Top Converting Search Terms")
                    for _, row in converting.iterrows():
                        st.markdown(
                            f'<div class="good-box"><strong>{row["Search Term"]}</strong> — '
                            f'{row["Conversions"]:.0f} conversions, ${row["Cost"]:,.2f} spend, '
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
                    wc1.metric("Wasted Spend", f"${total_wasted:,.2f}")
                    wc2.metric("Wasted Clicks", f"{total_wasted_clicks:,}")
                    wc3.metric("% of Total Spend", f"{pct_wasted:.1f}%")

                    st.markdown("")

                    if pct_wasted > 30:
                        st.markdown(f'<div class="bad-box">🚨 <strong>{pct_wasted:.0f}% of your spend</strong> goes to non-converting search terms. Adding negative keywords could save you <strong>${total_wasted:,.2f}</strong>.</div>', unsafe_allow_html=True)
                    elif pct_wasted > 15:
                        st.markdown(f'<div class="insight-box">⚠️ <strong>{pct_wasted:.0f}% of your spend</strong> goes to non-converting terms. Review the list below for potential negative keywords.</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="good-box">✅ Only <strong>{pct_wasted:.0f}%</strong> of spend is non-converting — your targeting looks solid!</div>', unsafe_allow_html=True)

                    st.markdown("")
                    st.subheader("🚫 Suggested Negative Keywords")
                    st.caption("These search terms spent the most without converting:")

                    display_wasted = wasted.head(20).copy()
                    display_wasted["CTR"] = display_wasted["CTR"].apply(lambda x: f"{x:.2%}")
                    display_wasted["Cost"] = display_wasted["Cost"].apply(lambda x: f"${x:,.2f}")
                    display_wasted = display_wasted.drop(columns=["CPA"])
                    st.dataframe(display_wasted, width="stretch", hide_index=True)
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
                # Tip: High CPC keywords
                high_cpc = df_kw[df_kw["CPC"] > df_kw["CPC"].mean() * 1.5]
                if not high_cpc.empty:
                    kw_list = ", ".join(high_cpc["Keyword"].head(3).tolist())
                    tips.append(("insight-box", "💰", "High CPC Keywords", f"These keywords cost significantly more than average: <strong>{kw_list}</strong>. Consider lowering bids or improving Quality Score with better ad copy and landing pages."))

                # Tip: Low CTR keywords
                low_ctr = df_kw[(df_kw["CTR"] < 0.02) & (df_kw["Impressions"] > 100)]
                if not low_ctr.empty:
                    kw_list = ", ".join(low_ctr["Keyword"].head(3).tolist())
                    tips.append(("bad-box", "⚠️", "Low CTR Keywords", f"These keywords have CTR below 2%: <strong>{kw_list}</strong>. Your ads may not be relevant enough — try writing more specific ad copy or tightening match types."))

                # Tip: Keywords with clicks but no conversions
                no_conv = df_kw[(df_kw["Clicks"] > 5) & (df_kw["Conversions"] == 0)]
                if not no_conv.empty:
                    wasted_amount = no_conv["Cost"].sum()
                    kw_list = ", ".join(no_conv["Keyword"].head(3).tolist())
                    tips.append(("bad-box", "🔥", "Money Burning Keywords", f"Keywords with clicks but zero conversions: <strong>{kw_list}</strong>. Total spend: <strong>${wasted_amount:,.2f}</strong>. Consider pausing these or improving landing pages."))

                # Tip: Top performers
                top_perf = df_kw[(df_kw["Conversions"] > 0)].sort_values("CPA")
                if not top_perf.empty:
                    best = top_perf.iloc[0]
                    tips.append(("good-box", "🏆", "Best Performer", f"<strong>{best['Keyword']}</strong> has the lowest cost per conversion at <strong>${best['CPA']:.2f}</strong>. Consider increasing budget for this keyword."))

                # Tip: Match type optimization
                broad_kw = df_kw[df_kw["Match Type"] == "BROAD"]
                if not broad_kw.empty and len(broad_kw) > len(df_kw) * 0.5:
                    tips.append(("insight-box", "🎯", "Match Type Mix", f"Over half your keywords use Broad match. Consider testing Phrase or Exact match for your top-spending keywords to improve targeting precision."))

            if not df_st.empty:
                # Tip: Search term relevance
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

except Exception as e:
    st.error(f"Error connecting to Google Ads: {e}")
    with st.expander("Error details"):
        st.code(str(e))
    st.info("Please check your credentials in the .env file and make sure the Google Ads API is enabled in Google Cloud Console.")
