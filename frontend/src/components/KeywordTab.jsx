import { useState, useEffect } from 'react';
import { fetchKeywords } from '../api';
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

export default function KeywordTab({ filters }) {
  const fmt = filters.account === 'us'
    ? (v) => `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    : (v) => `₹${v.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  const allColumns = [
    { key: 'Keyword', label: 'Keyword' },
    { key: 'Match Type', label: 'Match Type' },
    { key: 'Campaign', label: 'Campaign' },
    { key: 'Ad Group', label: 'Ad Group' },
    { key: 'Clicks', label: 'Clicks', format: num },
    { key: 'Impressions', label: 'Impressions', format: num },
    { key: 'CTR', label: 'CTR', format: pct },
    { key: 'CPC', label: 'CPC', format: fmt },
    { key: 'Cost', label: 'Cost', format: fmt },
    { key: 'Conversions', label: 'Conversions', format: v => v.toFixed(0) },
    { key: 'CPA', label: 'CPA', format: v => v > 0 ? fmt(v) : '-' },
    { key: 'Campaign MQLs', label: 'Campaign MQLs', format: num },
    { key: 'Campaign SALs', label: 'Campaign SALs', format: num },
    { key: 'Campaign SQLs', label: 'Campaign SQLs', format: num },
  ];
  const ncColumns = allColumns.filter(c => c.key !== 'CPA');

  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedCampaign, setExpandedCampaign] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchKeywords(filters)
      .then(res => setData(res.keywords || []))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [filters]);

  if (loading) return <div className="loading">Loading keyword data...</div>;
  if (error) return <div className="error-msg">Error: {error}</div>;
  if (data.length === 0) return <div className="empty-msg">No keyword data found for this date range and filters.</div>;

  const converting = data.filter(k => k.Conversions > 0).sort((a, b) => b.Conversions - a.Conversions);
  const nonConverting = data.filter(k => k.Conversions === 0 && k.Cost > 0).sort((a, b) => b.Cost - a.Cost);
  const totalWasted = nonConverting.reduce((s, k) => s + k.Cost, 0);

  // Aggregate MQLs by campaign (deduplicate since multiple keywords share a campaign)
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
      <h2>Keyword Performance {filters.account === 'us' ? '(form_submit_us-2026)' : '(form_submit_2025)'}</h2>
      <SortableTable data={data} columns={allColumns} />

      {converting.length > 0 && (
        <>
          <h2>Top Converting Keywords</h2>
          {converting.slice(0, 10).map((row, i) => (
            <InsightBox key={i} type="good">
              <strong>{row.Keyword}</strong> ({row['Match Type']}) — {row.Conversions.toFixed(0)} conversions, {fmt(row.Cost)} spend, CPA: {fmt(row.CPA)}
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

      {nonConverting.length > 0 && (
        <>
          <h2>Non-Converting Keywords with Spend</h2>
          <InsightBox type="bad">
            <strong>{fmt(totalWasted)}</strong> spent on keywords with zero form_submit_2025 conversions.
          </InsightBox>
          <SortableTable data={nonConverting.slice(0, 15)} columns={ncColumns} />
        </>
      )}
    </div>
  );
}
