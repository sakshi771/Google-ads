import { useState } from 'react';
import { setPassword } from '../api';

export default function PasswordGate({ onUnlock }) {
  const [value, setValue] = useState('');
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);

  const BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(false);
    try {
      const res = await fetch(`${BASE_URL}/health`, {
        headers: { 'X-App-Password': value },
      });
      if (res.ok) {
        setPassword(value);
        onUnlock();
      } else {
        setError(true);
      }
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'var(--bg)',
    }}>
      <div style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 14,
        padding: '40px 48px',
        width: 360,
        boxShadow: 'var(--shadow-md)',
        textAlign: 'center',
      }}>
        <img
          src="https://upload.wikimedia.org/wikipedia/commons/thumb/c/c7/Google_Ads_logo.svg/1200px-Google_Ads_logo.svg.png"
          alt="Google Ads"
          style={{ width: 140, marginBottom: 28 }}
        />
        <h2 style={{ fontSize: '1.15rem', marginBottom: 6, marginTop: 0 }}>
          Ads Dashboard
        </h2>
        <p style={{ color: 'var(--text-3)', fontSize: '0.875rem', marginBottom: 24 }}>
          Enter the access password to continue
        </p>
        <form onSubmit={handleSubmit}>
          <input
            type="password"
            value={value}
            onChange={e => { setValue(e.target.value); setError(false); }}
            placeholder="Password"
            autoFocus
            style={{
              width: '100%',
              padding: '10px 14px',
              border: `1px solid ${error ? 'var(--red)' : 'var(--border)'}`,
              borderRadius: 8,
              fontSize: '0.95rem',
              marginBottom: 12,
              outline: 'none',
              boxSizing: 'border-box',
            }}
          />
          {error && (
            <p style={{ color: 'var(--red)', fontSize: '0.82rem', marginBottom: 10 }}>
              Incorrect password — try again
            </p>
          )}
          <button
            type="submit"
            disabled={loading || !value}
            style={{
              width: '100%',
              padding: '10px',
              background: 'var(--blue)',
              color: '#fff',
              border: 'none',
              borderRadius: 8,
              fontSize: '0.95rem',
              fontWeight: 600,
              cursor: loading || !value ? 'not-allowed' : 'pointer',
              opacity: loading || !value ? 0.6 : 1,
            }}
          >
            {loading ? 'Checking…' : 'Enter'}
          </button>
        </form>
      </div>
    </div>
  );
}
