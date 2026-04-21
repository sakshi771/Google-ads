import { useMemo } from 'react';

const presets = [
  { label: 'Last 7 Days', days: 7 },
  { label: 'Last 14 Days', days: 14 },
  { label: 'Last 30 Days', days: 30 },
  { label: 'Last 60 Days', days: 60 },
  { label: 'Last 90 Days', days: 90 },
];

function formatDate(d) {
  return d.toISOString().slice(0, 10);
}

function toDisplayDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

export default function Sidebar({ filters, onFilterChange, campaignNames }) {
  const { startDate, endDate, status, region, selectedCampaigns, dateMode, preset, account } = filters;

  const update = (patch) => onFilterChange({ ...filters, ...patch });

  const handleAccountSwitch = (newAccount) => {
    update({ account: newAccount, selectedCampaigns: [], region: 'All' });
  };

  const handlePresetChange = (e) => {
    const days = parseInt(e.target.value);
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - days);
    update({
      preset: days,
      dateMode: 'preset',
      startDate: formatDate(start),
      endDate: formatDate(end),
    });
  };

  const allSelected = campaignNames.length > 0 &&
    selectedCampaigns.length === campaignNames.length;

  const toggleSelectAll = () => {
    update({ selectedCampaigns: allSelected ? [] : [...campaignNames] });
  };

  const toggleCampaign = (name) => {
    const next = selectedCampaigns.includes(name)
      ? selectedCampaigns.filter(c => c !== name)
      : [...selectedCampaigns, name];
    update({ selectedCampaigns: next });
  };

  return (
    <div className="sidebar">
      <img
        className="logo"
        src="https://upload.wikimedia.org/wikipedia/commons/thumb/c/c7/Google_Ads_logo.svg/1200px-Google_Ads_logo.svg.png"
        alt="Google Ads"
      />

      <div className="account-toggle">
        <button
          className={account === 'india' ? 'active' : ''}
          onClick={() => handleAccountSwitch('india')}
        >
          India (INR)
        </button>
        <button
          className={account === 'us' ? 'active' : ''}
          onClick={() => handleAccountSwitch('us')}
        >
          US (USD)
        </button>
      </div>

      <hr />

      <h3>Date Range</h3>
      <div className="radio-group">
        <label>
          <input type="radio" checked={filters.dateMode === 'preset'}
            onChange={() => update({ dateMode: 'preset' })} /> Preset
        </label>
        <label>
          <input type="radio" checked={filters.dateMode === 'custom'}
            onChange={() => update({ dateMode: 'custom' })} /> Custom
        </label>
      </div>

      {filters.dateMode === 'preset' ? (
        <select value={preset} onChange={handlePresetChange}>
          {presets.map(p => (
            <option key={p.days} value={p.days}>{p.label}</option>
          ))}
        </select>
      ) : (
        <>
          <input type="date" value={startDate}
            onChange={e => update({ startDate: e.target.value })} />
          <input type="date" value={endDate}
            onChange={e => update({ endDate: e.target.value })} />
        </>
      )}
      <div className="date-caption">
        {toDisplayDate(startDate)} — {toDisplayDate(endDate)}
      </div>

      <hr />

      <h3>Campaign Status</h3>
      <label>
        <input type="checkbox"
          checked={status === null || status === 'ENABLED' || status === undefined}
          onChange={() => {
            if (status === 'PAUSED') update({ status: null });
            else if (status === null || status === undefined) update({ status: 'PAUSED' });
            else update({ status: null });
          }}
        /> ENABLED
      </label>
      <label>
        <input type="checkbox"
          checked={status === null || status === 'PAUSED' || status === undefined}
          onChange={() => {
            if (status === 'ENABLED') update({ status: null });
            else if (status === null || status === undefined) update({ status: 'ENABLED' });
            else update({ status: null });
          }}
        /> PAUSED
      </label>

      {account !== 'us' && (
        <>
          <hr />
          <h3>Region</h3>
          <div className="radio-group">
            {['All', 'US', 'India'].map(r => (
              <label key={r}>
                <input type="radio" checked={region === r}
                  onChange={() => update({ region: r })} /> {r}
              </label>
            ))}
          </div>
        </>
      )}

      <hr />

      <h3>Campaigns</h3>
      <label style={{ fontWeight: 600, marginBottom: 4 }}>
        <input type="checkbox" checked={allSelected} onChange={toggleSelectAll} />
        Select All
      </label>
      <div className="campaign-list">
        {campaignNames.map(name => (
          <label key={name}>
            <input type="checkbox"
              checked={selectedCampaigns.includes(name)}
              onChange={() => toggleCampaign(name)}
            /> {name}
          </label>
        ))}
        {campaignNames.length === 0 && (
          <div style={{ color: '#888', fontSize: '0.85rem' }}>Loading...</div>
        )}
      </div>

      <hr />
      <div className="date-caption">Dashboard powered by React + FastAPI</div>
    </div>
  );
}
