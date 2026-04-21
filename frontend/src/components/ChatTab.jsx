import { useState } from 'react';
import { sendChatMessage } from '../api';

const suggestions = [
  'Which campaign is performing best?',
  'Where am I wasting the most money?',
  'What keywords should I pause?',
  'Summarize my account performance',
];

export default function ChatTab({ context, account = 'india' }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [lastModel, setLastModel] = useState(null);

  const send = async (text) => {
    if (!text.trim() || loading) return;

    const userMsg = { role: 'user', content: text.trim() };
    const updated = [...messages, userMsg];
    setMessages(updated);
    setInput('');
    setLoading(true);

    try {
      const res = await sendChatMessage(text.trim(), messages, context, account);
      if (res.model) setLastModel(res.model);
      if (res.error) {
        setMessages([...updated, { role: 'assistant', content: `Error: ${res.error}` }]);
      } else {
        setMessages([...updated, { role: 'assistant', content: res.response }]);
      }
    } catch (e) {
      setMessages([...updated, { role: 'assistant', content: `Error: ${e.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    send(input);
  };

  return (
    <div className="chat-container">
      <p style={{ marginBottom: 16 }}>
        Ask questions about your Google Ads data and get <strong>AI-powered answers</strong>.
        {lastModel && (
          <span style={{ marginLeft: 10, fontSize: '0.78rem', color: '#888', fontStyle: 'italic' }}>
            Last response: {lastModel.includes('8b') ? 'fast model' : 'full model'}
          </span>
        )}
      </p>

      {messages.length === 0 && (
        <>
          <p><strong>Try asking:</strong></p>
          <div className="suggestions">
            {suggestions.map((s, i) => (
              <button key={i} onClick={() => send(s)}>{s}</button>
            ))}
          </div>
        </>
      )}

      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`chat-bubble ${msg.role}`}>
            {msg.content}
          </div>
        ))}
        {loading && (
          <div className="chat-bubble assistant" style={{ fontStyle: 'italic', color: '#888' }}>
            Thinking...
          </div>
        )}
      </div>

      <form className="chat-input-row" onSubmit={handleSubmit}>
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Ask about your ads data..."
          disabled={loading}
        />
        <button type="submit" disabled={loading}>Send</button>
      </form>

      {messages.length > 0 && (
        <button
          className="btn btn-secondary"
          style={{ marginTop: 12 }}
          onClick={() => setMessages([])}
        >
          Clear chat
        </button>
      )}
    </div>
  );
}
