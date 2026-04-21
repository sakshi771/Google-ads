import { useState, useEffect, useMemo } from 'react';
import { fetchCampaigns, getPassword } from './api';
import Sidebar from './components/Sidebar';
import CampaignTab from './components/CampaignTab';
import KeywordTab from './components/KeywordTab';
import SearchTermTab from './components/SearchTermTab';
import ChatTab from './components/ChatTab';
import KeywordIdeasTab from './components/KeywordIdeasTab';
import ComparisonTab from './components/ComparisonTab';
import PasswordGate from './components/PasswordGate';

function formatDate(d) {
  return d.toISOString().slice(0, 10);
}

const defaultEnd = new Date();
const defaultStart = new Date();
defaultStart.setDate(defaultEnd.getDate() - 30);

const defaultFilters = {
  dateMode: 'preset',
  preset: 30,
  startDate: formatDate(defaultStart),
  endDate: formatDate(defaultEnd),
  status: null,
  region: 'All',
  selectedCampaigns: [],
  account: 'india',
};

const tabs = [
  { label: 'Campaign Performance', key: 'campaigns' },
  { label: 'Keyword Breakdown', key: 'keywords' },
  { label: 'Search Term Breakdown', key: 'search-terms' },
  { label: 'Keyword Ideas', key: 'keyword-ideas' },
  { label: 'MoM Comparison', key: 'comparison' },
  { label: 'Ask AI', key: 'chat' },
];

// Main dashboard — only rendered after password is verified
function Dashboard() {
  const [filters, setFilters] = useState(defaultFilters);
  const [activeTab, setActiveTab] = useState(0);
  const [campaignNames, setCampaignNames] = useState([]);
  const [campaignData, setCampaignData] = useState([]);

  useEffect(() => {
    fetchCampaigns({
      startDate: filters.startDate,
      endDate: filters.endDate,
      status: filters.status,
      region: filters.region,
      account: filters.account,
    })
      .then(res => {
        const camps = res.campaigns || [];
        setCampaignData(camps);
        const names = camps.map(c => c.Campaign).sort();
        setCampaignNames(names);
        setFilters(prev => ({ ...prev, selectedCampaigns: names }));
      })
      .catch(() => {});
  }, [filters.startDate, filters.endDate, filters.status, filters.region, filters.account]);

  const filtersKey = useMemo(() => JSON.stringify({
    startDate: filters.startDate,
    endDate: filters.endDate,
    status: filters.status,
    region: filters.region,
    selectedCampaigns: filters.selectedCampaigns,
    account: filters.account,
  }), [filters.startDate, filters.endDate, filters.status, filters.region, filters.selectedCampaigns, filters.account]);

  const chatContext = useMemo(() => {
    if (campaignData.length === 0) return '';
    const sym = filters.account === 'us' ? '$' : '₹';
    const lines = [
      `Account: ${filters.account === 'us' ? 'US (USD)' : 'India (INR)'}`,
      `Date range: ${filters.startDate} to ${filters.endDate}`,
      `Region filter: ${filters.region}`,
      '',
      `--- CAMPAIGN DATA (${campaignData.length} campaigns) ---`,
    ];
    for (const c of campaignData) {
      lines.push(
        `Campaign: ${c.Campaign} | Status: ${c.Status} | Spend: ${sym}${c.Cost.toFixed(2)} | ` +
        `Clicks: ${c.Clicks} | Impressions: ${c.Impressions} | CTR: ${(c.CTR * 100).toFixed(2)}% | ` +
        `CPC: ${sym}${c['Avg CPC'].toFixed(2)} | Conversions: ${c.Conversions.toFixed(0)} | CPA: ${sym}${c.CPA.toFixed(2)} | ` +
        `MQLs: ${c.MQLs || 0} | SALs: ${c.SALs || 0} | SQLs: ${c.SQLs || 0}`
      );
    }
    const totalSpend = campaignData.reduce((s, c) => s + c.Cost, 0);
    const totalClicks = campaignData.reduce((s, c) => s + c.Clicks, 0);
    const totalImpressions = campaignData.reduce((s, c) => s + c.Impressions, 0);
    const totalConversions = campaignData.reduce((s, c) => s + c.Conversions, 0);
    const totalMQLs = campaignData.reduce((s, c) => s + (c.MQLs || 0), 0);
    const totalSALs = campaignData.reduce((s, c) => s + (c.SALs || 0), 0);
    const totalSQLs = campaignData.reduce((s, c) => s + (c.SQLs || 0), 0);
    lines.push('');
    lines.push(`TOTALS: Spend=${sym}${totalSpend.toFixed(2)}, Clicks=${totalClicks}, Impressions=${totalImpressions}, Conversions=${totalConversions.toFixed(0)}, MQLs=${totalMQLs}, SALs=${totalSALs}, SQLs=${totalSQLs}`);
    return lines.join('\n');
  }, [campaignData, filters.startDate, filters.endDate, filters.region, filters.account]);

  const childFilters = useMemo(() => ({
    startDate: filters.startDate,
    endDate: filters.endDate,
    status: filters.status,
    region: filters.region,
    selectedCampaigns: filters.selectedCampaigns,
    account: filters.account,
  }), [filtersKey]);

  return (
    <div className="app-layout">
      <Sidebar filters={filters} onFilterChange={setFilters} campaignNames={campaignNames} />
      <div className="main-content">
        <h1>Google Ads Dashboard {filters.account === 'us' ? '— US Account' : ''}</h1>
        <div className="tab-bar">
          {tabs.map((tab, i) => (
            <button
              key={tab.key}
              className={activeTab === i ? 'active' : ''}
              onClick={() => setActiveTab(i)}
            >
              {tab.label}
            </button>
          ))}
        </div>
        {activeTab === 0 && <CampaignTab filters={childFilters} />}
        {activeTab === 1 && <KeywordTab filters={childFilters} />}
        {activeTab === 2 && <SearchTermTab filters={childFilters} />}
        {activeTab === 3 && <KeywordIdeasTab filters={childFilters} />}
        {activeTab === 4 && <ComparisonTab account={filters.account} />}
        {activeTab === 5 && <ChatTab context={chatContext} account={filters.account} />}
      </div>
    </div>
  );
}

export default function App() {
  const [unlocked, setUnlocked] = useState(() => !!getPassword());
  return unlocked ? <Dashboard /> : <PasswordGate onUnlock={() => setUnlocked(true)} />;
}
