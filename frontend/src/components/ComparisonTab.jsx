import { useState, useEffect } from 'react';
import { fetchComparison } from '../api';

const pct = (v) => `${(v * 100).toFixed(2)}%`;
const num = (v) => typeof v === 'number' ? v.toLocaleString() : v;

function makeMetrics(fmt, fmtDec) {
  return [
    { key: 'Impressions', label: 'Impressions', format: num },
    { key: 'Clicks', label: 'Clicks', format: num },
    { key: 'CTR', label: 'CTR', format: pct },
    { key: 'Spend', label: 'Spend', format: fmt },
    { key: 'Avg CPC', label: 'Avg CPC', format: fmtDec },
    { key: 'Conversions', label: 'Conversions', format: v => v.toFixed(0) },
    { key: 'CVR', label: 'CVR%', format: pct },
    { key: 'CPL', label: 'CPL', format: v => v > 0 ? fmt(v) : '-' },
    { key: 'MQLs', label: 'MQLs', format: num },
    { key: 'Cost/MQL', label: 'Cost/MQL', format: v => v > 0 ? fmt(v) : '-' },
    { key: 'SALs', label: 'SALs', format: num },
    { key: 'Cost/SAL', label: 'Cost/SAL', format: v => v > 0 ? fmt(v) : '-' },
    { key: 'SQLs', label: 'SQLs', format: num },
    { key: 'Cost/SQL', label: 'Cost/SQL', format: v => v > 0 ? fmt(v) : '-' },
  ];
}

const ZERO_DASH_KEYS = ['CPL', 'Cost/MQL', 'Cost/SAL', 'Cost/SQL', 'CVR'];

function popChange(curr, prev) {
  if (!prev || prev === 0) return curr > 0 ? '+∞' : null;
  const change = ((curr - prev) / prev) * 100;
  const sign = change >= 0 ? '+' : '';
  return `${sign}${change.toFixed(1)}%`;
}

function popColor(curr, prev, key) {
  if (!prev || prev === 0) return {};
  const change = ((curr - prev) / prev) * 100;
  const lowerIsBetter = ['Spend', 'Avg CPC', 'CPL', 'Cost/MQL', 'Cost/SAL', 'Cost/SQL'].includes(key);
  const isGood = lowerIsBetter ? change < 0 : change > 0;
  if (Math.abs(change) < 1) return { color: '#888' };
  return { color: isGood ? '#0d7d2c' : '#d93025' };
}

function LeadsList({ leads, type }) {
  if (!leads || leads.length === 0) return <span style={{ color: '#aaa', fontSize: '0.75rem' }}>-</span>;
  const colors = { sql: '#1a73e8', sal: '#e8710a', mql: '#34a853' };
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
      {leads.map((l, i) => (
        <span key={i} style={{
          fontSize: '0.7rem',
          padding: '1px 6px',
          borderRadius: 10,
          background: `${colors[type]}15`,
          color: colors[type],
          border: `1px solid ${colors[type]}40`,
        }}>
          {l}
        </span>
      ))}
    </div>
  );
}

function CampaignCard({ camp, periodLabels, defaultExpanded, metrics, fmt }) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [showLeads, setShowLeads] = useState(null); // period label or null

  // Check if campaign has any activity
  const hasActivity = periodLabels.some(label => {
    const d = camp.periods[label];
    return d && (d.Clicks > 0 || d.MQLs > 0 || d.SALs > 0 || d.SQLs > 0);
  });

  return (
    <div style={{
      border: '1px solid #e0e0e0',
      borderRadius: 8,
      marginBottom: 12,
      background: '#fff',
      overflow: 'hidden',
    }}>
      {/* Card header */}
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          padding: '10px 16px',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: expanded ? '#f0f4ff' : '#fafafa',
          borderBottom: expanded ? '1px solid #e0e0e0' : 'none',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: '0.7rem', color: '#888' }}>{expanded ? '▼' : '▶'}</span>
          <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{camp.Campaign}</span>
          {!hasActivity && (
            <span style={{ fontSize: '0.7rem', color: '#aaa', fontStyle: 'italic' }}>no activity</span>
          )}
        </div>
        {/* Quick summary badges for latest period */}
        {!expanded && hasActivity && (() => {
          const latest = camp.periods[periodLabels[periodLabels.length - 1]] || {};
          return (
            <div style={{ display: 'flex', gap: 12, fontSize: '0.78rem' }}>
              {latest.Spend > 0 && <span>Spend: {fmt(latest.Spend)}</span>}
              {latest.MQLs > 0 && <span style={{ color: '#34a853' }}>MQLs: {latest.MQLs}</span>}
              {latest.SALs > 0 && <span style={{ color: '#e8710a' }}>SALs: {latest.SALs}</span>}
              {latest.SQLs > 0 && <span style={{ color: '#1a73e8' }}>SQLs: {latest.SQLs}</span>}
            </div>
          );
        })()}
      </div>

      {/* Card body - periods as rows */}
      {expanded && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', fontSize: '0.8rem', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#f8f9fa' }}>
                <th style={{ padding: '6px 12px', textAlign: 'left', position: 'sticky', left: 0, background: '#f8f9fa', zIndex: 1, minWidth: 100 }}>
                  Period
                </th>
                {metrics.map(m => (
                  <th key={m.key} style={{ padding: '6px 8px', textAlign: 'right', whiteSpace: 'nowrap', fontSize: '0.75rem' }}>
                    {m.label}
                  </th>
                ))}
                <th style={{ padding: '6px 8px', textAlign: 'center', fontSize: '0.75rem' }}>Leads</th>
              </tr>
            </thead>
            <tbody>
              {periodLabels.map((label, pi) => {
                const d = camp.periods[label] || {};
                const prev = pi > 0 ? (camp.periods[periodLabels[pi - 1]] || {}) : null;
                const isShowingLeads = showLeads === label;
                const hasMqlLeads = (d.mql_leads || []).length > 0;
                const hasSalLeads = (d.sal_leads || []).length > 0;
                const hasSqlLeads = (d.sql_leads || []).length > 0;
                const hasLeads = hasMqlLeads || hasSalLeads || hasSqlLeads;

                return (
                  <>
                    <tr key={label} style={{
                      borderTop: '1px solid #f0f0f0',
                      background: pi % 2 === 0 ? '#fff' : '#fafcff',
                    }}>
                      <td style={{
                        padding: '6px 12px',
                        fontWeight: 500,
                        position: 'sticky',
                        left: 0,
                        background: pi % 2 === 0 ? '#fff' : '#fafcff',
                        zIndex: 1,
                        whiteSpace: 'nowrap',
                      }}>
                        {label}
                      </td>
                      {metrics.map(m => {
                        const val = d[m.key] ?? 0;
                        const prevVal = prev ? (prev[m.key] ?? 0) : null;
                        const change = prevVal !== null ? popChange(val, prevVal) : null;
                        const changeColor = prevVal !== null ? popColor(val, prevVal, m.key) : {};

                        return (
                          <td key={m.key} style={{ padding: '6px 8px', textAlign: 'right', whiteSpace: 'nowrap' }}>
                            <div>{val === 0 && ZERO_DASH_KEYS.includes(m.key) ? '-' : m.format(val)}</div>
                            {change && (
                              <div style={{ fontSize: '0.65rem', ...changeColor }}>{change}</div>
                            )}
                          </td>
                        );
                      })}
                      <td style={{ padding: '6px 8px', textAlign: 'center' }}>
                        {hasLeads ? (
                          <button
                            onClick={(e) => { e.stopPropagation(); setShowLeads(isShowingLeads ? null : label); }}
                            style={{
                              fontSize: '0.7rem',
                              padding: '2px 8px',
                              borderRadius: 4,
                              border: '1px solid #ccc',
                              background: isShowingLeads ? '#e8f0fe' : '#fff',
                              cursor: 'pointer',
                              color: '#1a73e8',
                            }}
                          >
                            {isShowingLeads ? 'Hide' : 'View'}
                          </button>
                        ) : (
                          <span style={{ color: '#ccc', fontSize: '0.7rem' }}>-</span>
                        )}
                      </td>
                    </tr>
                    {isShowingLeads && (
                      <tr key={`${label}-leads`}>
                        <td colSpan={metrics.length + 2} style={{
                          padding: '8px 16px 12px',
                          background: '#f8faf8',
                          borderTop: '1px dashed #ddd',
                        }}>
                          <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap' }}>
                            <div style={{ minWidth: 120 }}>
                              <div style={{ fontWeight: 600, fontSize: '0.72rem', marginBottom: 4, color: '#34a853' }}>
                                MQL ({(d.mql_leads || []).length})
                              </div>
                              <LeadsList leads={d.mql_leads} type="mql" />
                            </div>
                            <div style={{ minWidth: 120 }}>
                              <div style={{ fontWeight: 600, fontSize: '0.72rem', marginBottom: 4, color: '#e8710a' }}>
                                SAL ({(d.sal_leads || []).length})
                              </div>
                              <LeadsList leads={d.sal_leads} type="sal" />
                            </div>
                            <div style={{ minWidth: 120 }}>
                              <div style={{ fontWeight: 600, fontSize: '0.72rem', marginBottom: 4, color: '#1a73e8' }}>
                                SQL ({(d.sql_leads || []).length})
                              </div>
                              <LeadsList leads={d.sql_leads} type="sql" />
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function TotalsCard({ regionName, totals, periodLabels, metrics }) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div style={{
      border: '2px solid #1a73e8',
      borderRadius: 8,
      marginBottom: 16,
      background: '#fff',
      overflow: 'hidden',
    }}>
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          padding: '10px 16px',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          background: '#e8f0fe',
          borderBottom: expanded ? '1px solid #c5d7f7' : 'none',
        }}
      >
        <span style={{ fontSize: '0.7rem', color: '#1a73e8' }}>{expanded ? '▼' : '▶'}</span>
        <span style={{ fontWeight: 700, fontSize: '0.9rem', color: '#1a73e8' }}>{regionName} Totals</span>
      </div>

      {expanded && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', fontSize: '0.8rem', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#f0f4ff' }}>
                <th style={{ padding: '6px 12px', textAlign: 'left', position: 'sticky', left: 0, background: '#f0f4ff', zIndex: 1, minWidth: 100 }}>
                  Period
                </th>
                {metrics.map(m => (
                  <th key={m.key} style={{ padding: '6px 8px', textAlign: 'right', whiteSpace: 'nowrap', fontSize: '0.75rem' }}>
                    {m.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {periodLabels.map((label, pi) => {
                const d = totals[label] || {};
                const prev = pi > 0 ? (totals[periodLabels[pi - 1]] || {}) : null;

                return (
                  <tr key={label} style={{
                    borderTop: '1px solid #eef2ff',
                    background: pi % 2 === 0 ? '#fff' : '#f8faff',
                    fontWeight: 600,
                  }}>
                    <td style={{
                      padding: '6px 12px',
                      position: 'sticky', left: 0,
                      background: pi % 2 === 0 ? '#fff' : '#f8faff',
                      zIndex: 1, whiteSpace: 'nowrap',
                    }}>
                      {label}
                    </td>
                    {metrics.map(m => {
                      const val = d[m.key] ?? 0;
                      const prevVal = prev ? (prev[m.key] ?? 0) : null;
                      const change = prevVal !== null ? popChange(val, prevVal) : null;
                      const changeColor = prevVal !== null ? popColor(val, prevVal, m.key) : {};

                      return (
                        <td key={m.key} style={{ padding: '6px 8px', textAlign: 'right', whiteSpace: 'nowrap' }}>
                          <div>{val === 0 && ZERO_DASH_KEYS.includes(m.key) ? '-' : m.format(val)}</div>
                          {change && (
                            <div style={{ fontSize: '0.65rem', fontWeight: 400, ...changeColor }}>{change}</div>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function RegionSection({ regionName, data, periodLabels, metrics, fmt }) {
  const { campaigns, totals } = data;
  if (campaigns.length === 0) return null;

  return (
    <div style={{ marginBottom: 40 }}>
      <h2 style={{ margin: '20px 0 12px', borderBottom: '2px solid #ddd', paddingBottom: 8 }}>{regionName}</h2>
      <TotalsCard regionName={regionName} totals={totals} periodLabels={periodLabels} metrics={metrics} />
      {campaigns.map((camp, i) => (
        <CampaignCard key={i} camp={camp} periodLabels={periodLabels} defaultExpanded={false} metrics={metrics} fmt={fmt} />
      ))}
    </div>
  );
}

function monthsAgo(n) {
  const d = new Date();
  d.setMonth(d.getMonth() - n);
  return d.toISOString().slice(0, 10);
}

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

export default function ComparisonTab({ account = 'india' }) {
  const fmt = account === 'us'
    ? (v) => `$${v.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
    : (v) => `₹${v.toLocaleString('en-IN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
  const fmtDec = account === 'us'
    ? (v) => `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    : (v) => `₹${v.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  const metrics = makeMetrics(fmt, fmtDec);

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [rangeMode, setRangeMode] = useState('6m');
  const [customStart, setCustomStart] = useState(monthsAgo(6));
  const [customEnd, setCustomEnd] = useState(todayStr());

  const load = () => {
    setLoading(true);
    setError(null);
    let startDate = null, endDate = null, periods = 12;
    if (rangeMode === '3m') {
      startDate = monthsAgo(3); endDate = todayStr();
    } else if (rangeMode === '6m') {
      startDate = monthsAgo(6); endDate = todayStr();
    } else if (rangeMode === '12m') {
      startDate = monthsAgo(12); endDate = todayStr();
    } else if (rangeMode === 'custom') {
      startDate = customStart; endDate = customEnd;
    }
    fetchComparison(periods, startDate, endDate, account)
      .then(res => setData(res))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, [rangeMode, account]);

  if (loading) return <div className="loading">Loading comparison data...</div>;
  if (error) return <div className="error-msg">Error: {error}</div>;
  if (!data) return <div className="empty-msg">No data available.</div>;

  const { period_labels, regions } = data;

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 12, flexWrap: 'wrap' }}>
        <h2 style={{ margin: 0 }}>Period-on-Period Comparison</h2>
        <div style={{ display: 'flex', gap: 4 }}>
          {['3m', '6m', '12m', 'custom'].map(mode => (
            <button
              key={mode}
              onClick={() => setRangeMode(mode)}
              style={{
                padding: '4px 12px',
                borderRadius: 4,
                border: '1px solid #ccc',
                background: rangeMode === mode ? '#1a73e8' : '#fff',
                color: rangeMode === mode ? '#fff' : '#333',
                cursor: 'pointer',
                fontSize: '0.85rem',
              }}
            >
              {mode === 'custom' ? 'Custom' : mode.toUpperCase()}
            </button>
          ))}
        </div>
        {rangeMode === 'custom' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input
              type="date"
              value={customStart}
              onChange={e => setCustomStart(e.target.value)}
              style={{ padding: '3px 6px', borderRadius: 4, border: '1px solid #ccc', fontSize: '0.85rem' }}
            />
            <span>to</span>
            <input
              type="date"
              value={customEnd}
              onChange={e => setCustomEnd(e.target.value)}
              style={{ padding: '3px 6px', borderRadius: 4, border: '1px solid #ccc', fontSize: '0.85rem' }}
            />
            <button
              onClick={load}
              style={{
                padding: '4px 12px', borderRadius: 4, border: '1px solid #1a73e8',
                background: '#1a73e8', color: '#fff', cursor: 'pointer', fontSize: '0.85rem',
              }}
            >
              Apply
            </button>
          </div>
        )}
        <span style={{ color: '#888', fontSize: '0.8rem' }}>Half-month periods (1-15, 16-end)</span>
      </div>

      <p style={{ color: '#888', fontSize: '0.85rem', marginBottom: 16 }}>
        ENABLED campaigns only. Click a campaign to expand its period-by-period breakdown.
        PoP change shown below each value. Green = improvement, Red = decline.
      </p>

      <RegionSection regionName="US" data={regions.US} periodLabels={period_labels} metrics={metrics} fmt={fmt} />
      <RegionSection regionName="India" data={regions.India} periodLabels={period_labels} metrics={metrics} fmt={fmt} />
    </div>
  );
}
