import { useState, useRef, useEffect } from 'react';
import { chat } from '../api';

export default function ChatPanel({ sourceId }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const logRef = useRef(null);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [messages]);

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    setMessages((prev) => [...prev, { role: 'user', text }]);
    setInput('');
    setBusy(true);
    try {
      const result = await chat(text, sourceId);
      setMessages((prev) => [...prev, { role: 'assistant', text: result.response || 'No answer.', trace: result.trace || [] }]);
    } catch (err) {
      setMessages((prev) => [...prev, { role: 'assistant', text: `Error: ${err.message}` }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="chat-log" ref={logRef}>
        {!messages.length && (
          <div className="empty-note">
            <span className="icon">&#x1F4AC;</span>
            Ask the agent: "why did machine_01 flag an anomaly?"
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <div>{m.text}</div>
            {m.trace && m.trace.length > 0 && (
              <div className="trace">
                {m.trace.map((step, j) => (
                  <div key={j} className="step">{step}</div>
                ))}
              </div>
            )}
          </div>
        ))}
        {busy && <div className="msg assistant" style={{ animation: 'pulse 1s infinite' }}>Thinking...</div>}
      </div>
      <div className="chat-input-row">
        <input
          value={input}
          placeholder="Ask about any incident..."
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
        />
        <button className="btn" onClick={send} disabled={busy || !input.trim()}>Send</button>
      </div>
    </div>
  );
}
