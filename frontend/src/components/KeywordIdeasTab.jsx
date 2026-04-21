import { useState, useEffect } from 'react';
import { fetchKeywordIdeas, fetchCompetitorKeywords, fetchAuctionInsights } from '../api';
import InsightBox from './InsightBox';

const fmt = (v) => `₹${v.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const fmtUsd = (v) => `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const num = (v) => typeof v === 'number' ? v.toLocaleString() : v;
const pct = (v) => typeof v === 'number' ? `${(v * 100).toFixed(1)}%` : v;

function SortableTable({ data, columns, highlightOpportunities }) {
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

  const isHighOpp = (row) => highlightOpportunities &&
    row['Avg Monthly Searches'] >= 1000 &&
    !row['In Account'];

  return (
    <div className="data-table-wrapper">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map(col => (
              <th key={col.key} onClick={() => handleSort(col.key)} style={{ cursor: 'pointer' }}>
                {col.label} {sortCol === col.key ? (sortAsc ? '↑' : '↓') : ''}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => (
            <tr key={i} style={{
              ...(row['In Account'] || row['In Campaign'] ? { opacity: 0.5 } : {}),
              ...(isHighOpp(row) ? { background: '#e6f4ea' } : {}),
            }}>
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

const campaignColumns = [
  { key: 'Keyword', label: 'Keyword' },
  { key: 'Avg Monthly Searches', label: 'Avg Monthly Searches', format: num },
  { key: 'Competition', label: 'Competition' },
  { key: 'Low CPC', label: 'Low CPC', format: fmt },
  { key: 'High CPC', label: 'High CPC', format: fmt },
  { key: 'In Campaign', label: 'In Campaign', format: v => v ? 'Yes' : '' },
  { key: 'In Account', label: 'In Account', format: v => v ? 'Yes' : '' },
];

// SEMrush competitor columns
const competitorColumns = [
  { key: 'Keyword', label: 'Keyword' },
  { key: 'Position', label: 'Ad Position', format: num },
  { key: 'Avg Monthly Searches', label: 'Search Volume', format: num },
  { key: 'CPC', label: 'CPC (USD)', format: fmtUsd },
  { key: 'Traffic %', label: 'Traffic %', format: v => `${v.toFixed(2)}%` },
  { key: 'Traffic Cost', label: 'Traffic Cost', format: fmtUsd },
  { key: 'Competition', label: 'Density', format: v => typeof v === 'number' ? v.toFixed(2) : v },
  { key: 'In Account', label: 'In Account', format: v => v ? 'Yes' : '' },
];

// Auction insights columns
const auctionColumns = [
  { key: 'Domain', label: 'Competitor' },
  { key: 'Impression Share', label: 'Imp. Share', format: pct },
  { key: 'Overlap Rate', label: 'Overlap Rate', format: pct },
  { key: 'Position Above Rate', label: 'Position Above', format: pct },
  { key: 'Top Impression %', label: 'Top Imp. %', format: pct },
  { key: 'Outranking Share', label: 'Outranking Share', format: pct },
  { key: 'Campaigns Overlapping', label: 'Campaigns', format: num },
];

function CampaignIdeaCard({ campaign }) {
  const [expanded, setExpanded] = useState(false);
  const newIdeas = campaign.ideas.filter(i => !i['In Campaign']);
  const highOpp = newIdeas.filter(i => i['Avg Monthly Searches'] >= 1000 && i['Competition'] !== 'HIGH' && !i['In Account']);

  return (
    <div style={{
      border: '1px solid #e0e0e0',
      borderRadius: 8,
      marginBottom: 12,
      background: '#fff',
    }}>
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          padding: '14px 18px',
          cursor: 'pointer',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: expanded ? '1px solid #e0e0e0' : 'none',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: '1.1rem', fontWeight: 600 }}>{expanded ? '▼' : '▶'}</span>
          <span style={{ fontWeight: 600 }}>{campaign.campaign}</span>
        </div>
        <div style={{ display: 'flex', gap: 12, fontSize: '0.85rem' }}>
          {highOpp.length > 0 && (
            <span style={{ background: '#e6f4ea', color: '#137333', padding: '2px 10px', borderRadius: 12 }}>
              {highOpp.length} high-opp
            </span>
          )}
          <span style={{ background: '#e8f0fe', color: '#1a73e8', padding: '2px 10px', borderRadius: 12 }}>
            {newIdeas.length} new ideas
          </span>
          <span style={{ color: '#888' }}>
            {campaign.ideas.length} total
          </span>
        </div>
      </div>

      {expanded && (
        <div style={{ padding: '12px 18px' }}>
          {campaign.error && !campaign.ideas.length ? (
            <div style={{ color: '#d93025', fontSize: '0.9rem' }}>{campaign.error}</div>
          ) : (
            <>
              <div style={{ marginBottom: 12 }}>
                <span style={{ fontSize: '0.85rem', color: '#555', marginRight: 8 }}>Seed keywords:</span>
                {campaign.seed_keywords.map((s, i) => (
                  <span key={i} style={{
                    background: '#e8f0fe', color: '#1a73e8', padding: '3px 10px',
                    borderRadius: 12, fontSize: '0.8rem', marginRight: 4, display: 'inline-block', marginBottom: 4,
                  }}>{s}</span>
                ))}
              </div>
              <SortableTable data={campaign.ideas} columns={campaignColumns} highlightOpportunities />
            </>
          )}
        </div>
      )}
    </div>
  );
}

function AuctionInsightsSection({ filters }) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [loaded, setLoaded] = useState(false);

  const load = () => {
    setLoading(true);
    setError(null);
    fetchAuctionInsights(filters)
      .then(res => {
        if (res.error) setError(res.error);
        else setData(res.competitors || []);
        setLoaded(true);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  return (
    <div style={{
      marginTop: 24,
      padding: '16px 20px',
      border: '1px solid #e0e0e0',
      borderRadius: 8,
      background: '#fff',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <div>
          <h3 style={{ margin: 0 }}>Auction Insights</h3>
          <p style={{ color: '#888', fontSize: '0.85rem', margin: '4px 0 0' }}>
            See which competitors overlap with your campaigns on Google Ads (free, from your account data).
          </p>
        </div>
        {!loaded && (
          <button onClick={load} disabled={loading} style={{
            padding: '8px 20px', borderRadius: 6, border: 'none',
            background: '#1a73e8', color: '#fff', cursor: 'pointer', fontSize: '0.9rem',
            opacity: loading ? 0.6 : 1,
          }}>
            {loading ? 'Loading...' : 'Load Auction Insights'}
          </button>
        )}
      </div>

      {error && <div className="error-msg" style={{ marginTop: 8 }}>Error: {error}</div>}

      {loaded && !error && data.length === 0 && (
        <p style={{ color: '#888', fontSize: '0.9rem', marginTop: 8 }}>No auction insight data found for the selected filters.</p>
      )}

      {data.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <SortableTable data={data} columns={auctionColumns} />
        </div>
      )}
    </div>
  );
}

function CompetitorSection({ region, filters }) {
  const [knownCompetitors, setKnownCompetitors] = useState([
    { name: 'ElevenLabs', domain: 'elevenlabs.io' },
    { name: 'Cartesia', domain: 'cartesia.ai' },
    { name: 'Poly.ai', domain: 'poly.ai' },
  ]);
  const [customDomain, setCustomDomain] = useState('');
  const [ideas, setIdeas] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeDomain, setActiveDomain] = useState(null);
  const [showInAccount, setShowInAccount] = useState(false);

  const analyze = async (domain) => {
    setLoading(true);
    setError(null);
    setActiveDomain(domain);
    try {
      const res = await fetchCompetitorKeywords(domain, region);
      if (res.error) {
        setError(res.error);
        setIdeas([]);
      } else {
        setIdeas(res.ideas || []);
        if (res.known_competitors) setKnownCompetitors(res.known_competitors);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCustomSubmit = (e) => {
    e.preventDefault();
    if (customDomain.trim()) analyze(customDomain.trim());
  };

  const displayed = showInAccount ? ideas : ideas.filter(i => !i['In Account']);
  const notInAccount = ideas.filter(i => !i['In Account']).length;

  return (
    <div style={{ marginTop: 32 }}>
      <h2 style={{ marginBottom: 4 }}>Competitor Keyword Spy</h2>
      <p style={{ color: '#888', fontSize: '0.85rem', marginBottom: 16 }}>
        See actual paid keywords competitors are bidding on (powered by SEMrush).
        Select a known competitor or enter any domain.
      </p>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12, alignItems: 'center' }}>
        {knownCompetitors.map((c, i) => (
          <button
            key={i}
            onClick={() => analyze(c.domain)}
            style={{
              padding: '6px 16px',
              borderRadius: 20,
              border: activeDomain === c.domain ? '2px solid #1a73e8' : '1px solid #d0d0d0',
              background: activeDomain === c.domain ? '#e8f0fe' : '#fff',
              color: activeDomain === c.domain ? '#1a73e8' : '#333',
              cursor: 'pointer',
              fontWeight: activeDomain === c.domain ? 600 : 400,
              fontSize: '0.9rem',
            }}
          >
            {c.name}
          </button>
        ))}

        <form onSubmit={handleCustomSubmit} style={{ display: 'flex', gap: 6 }}>
          <input
            type="text"
            value={customDomain}
            onChange={e => setCustomDomain(e.target.value)}
            placeholder="competitor-domain.com"
            style={{
              padding: '6px 12px', borderRadius: 6, border: '1px solid #d0d0d0',
              fontSize: '0.9rem', width: 200,
            }}
          />
          <button type="submit" style={{
            padding: '6px 16px', borderRadius: 6, border: 'none',
            background: '#1a73e8', color: '#fff', cursor: 'pointer', fontSize: '0.9rem',
          }}>
            Analyze
          </button>
        </form>
      </div>

      {loading && <div className="loading">Fetching competitor paid keywords...</div>}

      {error && (
        <InsightBox type="insight">
          <strong>{error}</strong>
          {error.includes('SEMRUSH_API_KEY') && (
            <p style={{ margin: '8px 0 0', fontSize: '0.85rem' }}>
              Find your API key at <strong>semrush.com &gt; Subscription Info &gt; API units</strong>.
              API access requires a Guru or Business plan.
            </p>
          )}
          {error.includes('Nothing found') && (
            <p style={{ margin: '8px 0 0', fontSize: '0.85rem' }}>
              This domain may not be running paid search ads, or SEMrush hasn't indexed them yet.
            </p>
          )}
        </InsightBox>
      )}

      {!loading && !error && ideas.length > 0 && (
        <>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 8 }}>
            <h3 style={{ margin: 0 }}>
              {activeDomain} — {ideas.length} paid keywords ({notInAccount} not in your account)
            </h3>
            <label style={{ fontSize: '0.85rem', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={showInAccount}
                onChange={e => setShowInAccount(e.target.checked)}
                style={{ marginRight: 4 }}
              />
              Show keywords already in account
            </label>
          </div>
          <SortableTable data={displayed} columns={competitorColumns} highlightOpportunities />
        </>
      )}

      {/* Auction Insights — free, from Google Ads */}
      <AuctionInsightsSection filters={filters} />
    </div>
  );
}

export default function KeywordIdeasTab({ filters }) {
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [accessError, setAccessError] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setAccessError(false);
    fetchKeywordIdeas(filters)
      .then(res => {
        if (res.access_error) {
          setAccessError(true);
          setError(res.error);
          setCampaigns(res.campaigns || []);
        } else if (res.error) {
          setError(res.error);
        } else {
          setCampaigns(res.campaigns || []);
        }
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [filters]);

  if (loading) return <div className="loading">Generating campaign keyword ideas...</div>;

  if (accessError) {
    return (
      <div>
        <h2>Keyword Intelligence</h2>
        <InsightBox type="insight">
          <strong>Basic API Access Required</strong>
          <p style={{ margin: '8px 0 0' }}>
            The Keyword Planner API needs Basic or Standard developer token access.
            Apply at <strong>Google Ads &gt; Tools &amp; Settings &gt; API Center</strong>.
          </p>
        </InsightBox>
        {campaigns.length > 0 && (
          <>
            <h3 style={{ marginTop: 16 }}>Campaign Seed Keywords</h3>
            <p style={{ color: '#888', fontSize: '0.85rem' }}>
              These will be used to generate per-campaign suggestions once access is granted:
            </p>
            {campaigns.map((c, i) => (
              <div key={i} style={{ margin: '8px 0' }}>
                <strong>{c.campaign}</strong>:{' '}
                {(c.seed_keywords || []).map((s, j) => (
                  <span key={j} style={{
                    background: '#e8f0fe', color: '#1a73e8', padding: '3px 10px',
                    borderRadius: 12, fontSize: '0.8rem', marginRight: 4,
                  }}>{s}</span>
                ))}
              </div>
            ))}
          </>
        )}
        <CompetitorSection region={filters.region} filters={filters} />
      </div>
    );
  }

  if (error) return <div className="error-msg">Error: {error}</div>;

  const totalNewIdeas = campaigns.reduce((sum, c) => sum + c.ideas.filter(i => !i['In Campaign']).length, 0);

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>Keyword Intelligence</h2>
        <span style={{ fontSize: '0.9rem', color: '#555' }}>
          {campaigns.length} campaigns, {totalNewIdeas} new keyword ideas
        </span>
      </div>

      {campaigns.length === 0 ? (
        <div className="empty-msg">No campaigns found for the selected filters.</div>
      ) : (
        <>
          <h3 style={{ marginBottom: 8 }}>Campaign Keyword Suggestions</h3>
          <p style={{ color: '#888', fontSize: '0.85rem', marginBottom: 12 }}>
            Each campaign shows tailored keyword suggestions based on its top spending keywords.
            Green rows indicate high-opportunity keywords (high volume, not in account).
          </p>
          {campaigns.map((c, i) => (
            <CampaignIdeaCard key={i} campaign={c} />
          ))}
        </>
      )}

      <CompetitorSection region={filters.region} filters={filters} />
    </div>
  );
}
