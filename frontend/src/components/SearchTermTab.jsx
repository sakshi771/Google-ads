import { useState, useEffect } from 'react';
import { fetchSearchTerms } from '../api';
import KPIRow from './KPIRow';
import InsightBox from './InsightBox';

const pct = (v) => `${(v * 100).toFixed(2)}%`;
const num = (v) => typeof v === 'number' ? v.toLocaleString() : v;

function SortableTable({ data, columns }) {
  const [sortCol, setSortCol] = useState(null);
  const [sortAsc, setSortAsc] = useState(true);

  const sorted = [...data];
  if (sortCol !== null) {
    sorted.sort((a, b) => {
      const av = a[sortCol], bv = b[sortCol];
      if (typeof av === 'number' && typeof bv === 'number') return sortAsc ? av - bv : bv - av;
      return sortAsc ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
    });
  }

  const handleSort = (col) => {
    if (sortCol === col) setSortAsc(!sortAsc);
    else { setSortCol(col); setSortAsc(false); }
  };

  return (
    <div className="data-table-wrapper">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map(col => (
              <th key={col.key} onClick={() => handleSort(col.key)}>
                {col.label} {sortCol === col.key ? (sortAsc ? '↑' : '↓') : ''}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => (
            <tr key={i}>
              {columns.map(col => (
                <td key={col.key}>{col.format ? col.format(row[col.key]) : row[col.key]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function SearchTermTab({ filters }) {
  const fmt = filters.account === 'us'
    ? (v) => `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    : (v) => `₹${v.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  const allColumns = [
    { key: 'Search Term', label: 'Search Term' },
    { key: 'Campaign', label: 'Campaign' },
    { key: 'Clicks', label: 'Clicks', format: num },
    { key: 'Impressions', label: 'Impressions', format: num },
    { key: 'CTR', label: 'CTR', format: pct },
    { key: 'Cost', label: 'Cost', format: fmt },
    { key: 'Conversions', label: 'Conversions', format: v => v.toFixed(0) },
    { key: 'CPA', label: 'CPA', format: v => v > 0 ? fmt(v) : '-' },
    { key: 'Campaign MQLs', label: 'Campaign MQLs', format: num },
    { key: 'Campaign SALs', label: 'Campaign SALs', format: num },
    { key: 'Campaign SQLs', label: 'Campaign SQLs', format: num },
  ];
  const wastedColumns = allColumns.filter(c => c.key !== 'CPA');

  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedCampaign, setExpandedCampaign] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchSearchTerms(filters)
      .then(res => setData(res.search_terms || []))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [filters]);

  if (loading) return <div className="loading">Loading search term data...</div>;
  if (error) return <div className="error-msg">Error: {error}</div>;
  if (data.length === 0) return <div className="empty-msg">No search term data found for this date range and filters.</div>;

  const converting = data.filter(r => r.Conversions > 0).sort((a, b) => b.Conversions - a.Conversions);
  const wasted = data.filter(r => r.Conversions === 0).sort((a, b) => b.Cost - a.Cost);
  const totalSpend = data.reduce((s, r) => s + r.Cost, 0);
  const totalWasted = wasted.reduce((s, r) => s + r.Cost, 0);
  const totalWastedClicks = wasted.reduce((s, r) => s + r.Clicks, 0);
  const pctWasted = totalSpend > 0 ? (totalWasted / totalSpend) * 100 : 0;

  // Aggregate MQLs by campaign (deduplicate since multiple search terms share a campaign)
  const mqlByCampaign = {};
  for (const row of data) {
    const camp = row.Campaign;
    if (!mqlByCampaign[camp] && (row['Campaign MQLs'] || 0) > 0) {
      mqlByCampaign[camp] = {
        count: row['Campaign MQLs'],
        leads: row['MQL Leads'] || [],
      };
    }
  }
  const mqlCampaigns = Object.entries(mqlByCampaign).sort((a, b) => b[1].count - a[1].count);

  return (
    <div>
      <h2>Search Term Performance {filters.account === 'us' ? '(form_submit_us-2026)' : '(form_submit_2025)'}</h2>
      <SortableTable data={data} columns={allColumns} />

      {converting.length > 0 && (
        <>
          <h2>Top Converting Search Terms</h2>
          {converting.slice(0, 10).map((row, i) => (
            <InsightBox key={i} type="good">
              <strong>{row['Search Term']}</strong> — {row.Conversions.toFixed(0)} conversions, {fmt(row.Cost)} spend, {pct(row.CTR)} CTR
            </InsightBox>
          ))}
        </>
      )}

      {mqlCampaigns.length > 0 && (
        <>
          <h2>MQLs by Campaign</h2>
          {mqlCampaigns.map(([camp, info], i) => (
            <div key={i} style={{ marginBottom: 4 }}>
              <InsightBox type="good">
                <div
                  style={{ cursor: 'pointer' }}
                  onClick={() => setExpandedCampaign(expandedCampaign === camp ? null : camp)}
                >
                  <strong>{camp}</strong> — {info.count} MQL{info.count !== 1 ? 's' : ''}
                  <span style={{ marginLeft: 8, fontSize: '0.85rem', color: '#555' }}>
                    {expandedCampaign === camp ? '▼ hide leads' : '▶ show leads'}
                  </span>
                </div>
                {expandedCampaign === camp && info.leads.length > 0 && (
                  <div style={{ marginTop: 8, paddingLeft: 16, fontSize: '0.9rem' }}>
                    {info.leads.map((lead, j) => (
                      <div key={j} style={{ padding: '2px 0' }}>• {lead}</div>
                    ))}
                  </div>
                )}
              </InsightBox>
            </div>
          ))}
        </>
      )}

      {wasted.length > 0 && (
        <>
          <h2>Wasted Spend (No Conversions)</h2>
          <KPIRow metrics={[
            { label: 'Wasted Spend', value: fmt(totalWasted) },
            { label: 'Wasted Clicks', value: totalWastedClicks.toLocaleString() },
            { label: '% of Total Spend', value: `${pctWasted.toFixed(1)}%` },
          ]} />

          {pctWasted > 30 ? (
            <InsightBox type="bad">
              <strong>{pctWasted.toFixed(0)}% of your spend</strong> goes to non-converting search terms. Adding negative keywords could save you <strong>{fmt(totalWasted)}</strong>.
            </InsightBox>
          ) : pctWasted > 15 ? (
            <InsightBox type="insight">
              <strong>{pctWasted.toFixed(0)}% of your spend</strong> goes to non-converting terms. Review the list below for potential negative keywords.
            </InsightBox>
          ) : (
            <InsightBox type="good">
              Only <strong>{pctWasted.toFixed(0)}%</strong> of spend is non-converting — your targeting looks solid!
            </InsightBox>
          )}

          <h2>Suggested Negative Keywords</h2>
          <p style={{ color: '#888', fontSize: '0.85rem', marginBottom: 8 }}>
            These search terms spent the most without converting:
          </p>
          <SortableTable data={wasted.slice(0, 20)} columns={wastedColumns} />
        </>
      )}
    </div>
  );
}
