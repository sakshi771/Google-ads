import { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { fetchCampaigns } from '../api';
import KPIRow from './KPIRow';
import InsightBox from './InsightBox';

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
                <td key={col.key}>{col.render ? col.render(row) : col.format ? col.format(row[col.key]) : row[col.key]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const pct = (v) => `${(v * 100).toFixed(2)}%`;
const num = (v) => typeof v === 'number' ? v.toLocaleString() : v;

function makeFmt(account) {
  if (account === 'us') {
    return (v) => `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
  return (v) => `₹${v.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function CampaignTab({ filters }) {
  const fmt = makeFmt(filters.account);
  const isUS = filters.account === 'us';

  const columns = [
    { key: 'Campaign', label: 'Campaign' },
    { key: 'Status', label: 'Status' },
    { key: 'Impressions', label: 'Impressions', format: num },
    { key: 'Clicks', label: 'Clicks', format: num },
    { key: 'CTR', label: 'CTR', format: pct },
    { key: 'Avg CPC', label: 'Avg CPC', format: fmt },
    { key: 'Cost', label: 'Cost', format: fmt },
    { key: 'Conversions', label: 'Conversions', format: v => v.toFixed(0) },
    { key: 'CPA', label: 'CPA', format: v => v > 0 ? fmt(v) : '-' },
    { key: 'MQLs', label: 'MQLs', format: num },
    { key: 'SALs', label: 'SALs', format: num },
    { key: 'SQLs', label: 'SQLs', format: num },
    { key: 'Cost/MQL', label: 'Cost/MQL', format: v => v > 0 ? fmt(v) : '-' },
    { key: 'Cost/SAL', label: 'Cost/SAL', format: v => v > 0 ? fmt(v) : '-' },
    { key: 'Cost/SQL', label: 'Cost/SQL', format: v => v > 0 ? fmt(v) : '-' },
  ];

  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedCampaign, setExpandedCampaign] = useState(null);
  const [expandedSALCampaign, setExpandedSALCampaign] = useState(null);
  const [expandedSQLCampaign, setExpandedSQLCampaign] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchCampaigns(filters)
      .then(res => setData(res.campaigns || []))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [filters]);

  if (loading) return <div className="loading">Loading campaign data...</div>;
  if (error) return <div className="error-msg">Error: {error}</div>;
  if (data.length === 0) return <div className="empty-msg">No campaign data found for the selected filters.</div>;

  const totalSpend = data.reduce((s, c) => s + c.Cost, 0);
  const totalClicks = data.reduce((s, c) => s + c.Clicks, 0);
  const totalImpressions = data.reduce((s, c) => s + c.Impressions, 0);
  const totalConversions = data.reduce((s, c) => s + c.Conversions, 0);
  const totalMQLs = data.reduce((s, c) => s + (c.MQLs || 0), 0);
  const totalSALs = data.reduce((s, c) => s + (c.SALs || 0), 0);
  const totalSQLs = data.reduce((s, c) => s + (c.SQLs || 0), 0);
  const overallCTR = totalImpressions > 0 ? totalClicks / totalImpressions : 0;
  const overallCPA = totalConversions > 0 ? totalSpend / totalConversions : 0;
  const overallCostPerMQL = totalMQLs > 0 ? totalSpend / totalMQLs : 0;
  const overallCostPerSAL = totalSALs > 0 ? totalSpend / totalSALs : 0;
  const overallCostPerSQL = totalSQLs > 0 ? totalSpend / totalSQLs : 0;

  const bestCTR = data.reduce((best, c) => c.CTR > best.CTR ? c : best, data[0]);
  const biggestSpender = data.reduce((best, c) => c.Cost > best.Cost ? c : best, data[0]);
  const converting = data.filter(c => c.Conversions > 0);
  const bestCPA = converting.length > 0
    ? converting.reduce((best, c) => c.CPA < best.CPA ? c : best, converting[0])
    : null;
  const topMQL = data.filter(c => (c.MQLs || 0) > 0).sort((a, b) => b.MQLs - a.MQLs);
  const topSAL = data.filter(c => (c.SALs || 0) > 0).sort((a, b) => b.SALs - a.SALs);
  const topSQL = data.filter(c => (c.SQLs || 0) > 0).sort((a, b) => b.SQLs - a.SQLs);

  const chartData = [...data].sort((a, b) => a.Cost - b.Cost);

  return (
    <div>
      <KPIRow metrics={[
        { label: 'Total Spend', value: fmt(totalSpend) },
        { label: 'Clicks', value: totalClicks.toLocaleString() },
        { label: 'Impressions', value: totalImpressions.toLocaleString() },
        { label: 'Conversions', value: totalConversions.toFixed(0) },
        { label: 'MQLs', value: totalMQLs.toLocaleString() },
        { label: 'SALs', value: totalSALs.toLocaleString() },
        { label: 'SQLs', value: totalSQLs.toLocaleString() },
        { label: 'CPA', value: totalConversions > 0 ? fmt(overallCPA) : '-' },
        { label: 'Cost/MQL', value: overallCostPerMQL > 0 ? fmt(overallCostPerMQL) : '-' },
        { label: 'Cost/SAL', value: overallCostPerSAL > 0 ? fmt(overallCostPerSAL) : '-' },
        { label: 'Cost/SQL', value: overallCostPerSQL > 0 ? fmt(overallCostPerSQL) : '-' },
        { label: 'CTR', value: pct(overallCTR) },
      ]} />

      <h2>Campaign Performance</h2>
      <SortableTable data={data} columns={columns} />

      {/* MQL breakdown by campaign */}
      {topMQL.length > 0 && (
        <>
          <h2>MQLs by Campaign (Initial Interest = Yes)</h2>
          {topMQL.map((c, i) => (
            <div key={i} style={{ marginBottom: 4 }}>
              <InsightBox type="good">
                <div
                  style={{ cursor: 'pointer' }}
                  onClick={() => setExpandedCampaign(expandedCampaign === c.Campaign ? null : c.Campaign)}
                >
                  <strong>{c.Campaign}</strong> — {c.MQLs} MQL{c.MQLs !== 1 ? 's' : ''}
                  <span style={{ marginLeft: 8, fontSize: '0.85rem', color: '#555' }}>
                    {expandedCampaign === c.Campaign ? '▼ hide leads' : '▶ show leads'}
                  </span>
                </div>
                {expandedCampaign === c.Campaign && c['MQL Leads'] && c['MQL Leads'].length > 0 && (
                  <div style={{ marginTop: 8, paddingLeft: 16, fontSize: '0.9rem' }}>
                    {c['MQL Leads'].map((lead, j) => (
                      <div key={j} style={{ padding: '2px 0' }}>• {lead}</div>
                    ))}
                  </div>
                )}
              </InsightBox>
            </div>
          ))}
        </>
      )}

      {/* SAL breakdown by campaign */}
      {topSAL.length > 0 && (
        <>
          <h2>SALs by Campaign (HubSpot — SAL stage)</h2>
          {topSAL.map((c, i) => (
            <div key={i} style={{ marginBottom: 4 }}>
              <InsightBox type="insight">
                <div
                  style={{ cursor: 'pointer' }}
                  onClick={() => setExpandedSALCampaign(expandedSALCampaign === c.Campaign ? null : c.Campaign)}
                >
                  <strong>{c.Campaign}</strong> — {c.SALs} SAL{c.SALs !== 1 ? 's' : ''}
                  {c.MQLs > 0 && <span style={{ marginLeft: 8, fontSize: '0.85rem', color: '#666' }}>({((c.SALs / c.MQLs) * 100).toFixed(0)}% MQL→SAL)</span>}
                  <span style={{ marginLeft: 8, fontSize: '0.85rem', color: '#555' }}>
                    {expandedSALCampaign === c.Campaign ? '▼ hide leads' : '▶ show leads'}
                  </span>
                </div>
                {expandedSALCampaign === c.Campaign && c['SAL Leads'] && c['SAL Leads'].length > 0 && (
                  <div style={{ marginTop: 8, paddingLeft: 16, fontSize: '0.9rem' }}>
                    {c['SAL Leads'].map((lead, j) => (
                      <div key={j} style={{ padding: '2px 0' }}>• {lead}</div>
                    ))}
                  </div>
                )}
              </InsightBox>
            </div>
          ))}
        </>
      )}

      {/* SQL breakdown by campaign */}
      {topSQL.length > 0 && (
        <>
          <h2>SQLs by Campaign (HubSpot)</h2>
          {topSQL.map((c, i) => (
            <div key={i} style={{ marginBottom: 4 }}>
              <InsightBox type="good">
                <div
                  style={{ cursor: 'pointer' }}
                  onClick={() => setExpandedSQLCampaign(expandedSQLCampaign === c.Campaign ? null : c.Campaign)}
                >
                  <strong>{c.Campaign}</strong> — {c.SQLs} SQL{c.SQLs !== 1 ? 's' : ''}
                  {c.MQLs > 0 && <span style={{ marginLeft: 8, fontSize: '0.85rem', color: '#666' }}>({((c.SQLs / c.MQLs) * 100).toFixed(0)}% MQL→SQL)</span>}
                  <span style={{ marginLeft: 8, fontSize: '0.85rem', color: '#555' }}>
                    {expandedSQLCampaign === c.Campaign ? '▼ hide leads' : '▶ show leads'}
                  </span>
                </div>
                {expandedSQLCampaign === c.Campaign && c['SQL Leads'] && c['SQL Leads'].length > 0 && (
                  <div style={{ marginTop: 8, paddingLeft: 16, fontSize: '0.9rem' }}>
                    {c['SQL Leads'].map((lead, j) => (
                      <div key={j} style={{ padding: '2px 0' }}>• {lead}</div>
                    ))}
                  </div>
                )}
              </InsightBox>
            </div>
          ))}
        </>
      )}

      <h2>Spend by Campaign</h2>
      <div className="chart-container">
        <ResponsiveContainer width="100%" height={Math.max(300, chartData.length * 40)}>
          <BarChart data={chartData} layout="vertical" margin={{ left: 180, right: 20 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" tickFormatter={v => fmt(v / 1000).replace(/\.00$/, '') + 'k'} />
            <YAxis type="category" dataKey="Campaign" width={170} tick={{ fontSize: 12 }} />
            <Tooltip formatter={v => fmt(v)} />
            <Bar dataKey="Cost" fill="#4285F4" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <h2>Quick Insights</h2>
      <InsightBox type="good">
        <strong>Best CTR:</strong> {bestCTR.Campaign} at {pct(bestCTR.CTR)}
      </InsightBox>
      <InsightBox type="insight">
        <strong>Biggest spender:</strong> {biggestSpender.Campaign} at {fmt(biggestSpender.Cost)}
      </InsightBox>
      {bestCPA && (
        <InsightBox type="good">
          <strong>Best CPA:</strong> {bestCPA.Campaign} at {fmt(bestCPA.CPA)}
        </InsightBox>
      )}
      {overallCostPerMQL > 0 && (
        <InsightBox type="insight">
          <strong>Cost/MQL:</strong> {fmt(overallCostPerMQL)} across all campaigns
        </InsightBox>
      )}
      {overallCostPerSAL > 0 && (
        <InsightBox type="insight">
          <strong>Cost/SAL:</strong> {fmt(overallCostPerSAL)} across all campaigns
          {totalMQLs > 0 && <> — <strong>{((totalSALs / totalMQLs) * 100).toFixed(0)}%</strong> MQL→SAL conversion rate</>}
        </InsightBox>
      )}
      {overallCostPerSQL > 0 && (
        <InsightBox type="insight">
          <strong>Cost/SQL:</strong> {fmt(overallCostPerSQL)} across all campaigns
          {totalSALs > 0 && <> — <strong>{((totalSQLs / totalSALs) * 100).toFixed(0)}%</strong> SAL→SQL conversion rate</>}
        </InsightBox>
      )}
    </div>
  );
}
