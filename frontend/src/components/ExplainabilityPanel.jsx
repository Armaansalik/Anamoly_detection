import { useEffect, useState } from 'react';
import { explainSource } from '../api';

export default function ExplainabilityPanel({ sourceId }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(null);
    if (!sourceId) return;
    setLoading(true);
    explainSource(sourceId)
      .then((result) => { if (!cancelled) setData(result); })
      .catch((err) => { if (!cancelled) setError(err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [sourceId]);

  if (!sourceId) {
    return <div className="empty-note"><span className="icon">&#x1F50D;</span>Select a source to see why its readings were flagged.</div>;
  }
  if (loading) {
    return (
      <div>
        <div className="skeleton" style={{ height: 40, marginBottom: 12 }} />
        <div className="skeleton" style={{ height: 28, marginBottom: 8 }} />
        <div className="skeleton" style={{ height: 28, marginBottom: 8 }} />
        <div className="skeleton" style={{ height: 28 }} />
      </div>
    );
  }
  if (error) return <div className="empty-note">Explainability unavailable: {error}</div>;
  if (!data) return null;

  return (
    <div>
      <div className="explain-summary">{data.summary}</div>
      {data.contributions.map((c, idx) => {
        const width = Math.min(100, Math.abs(c.contribution) * 100);
        const color = c.contribution >= 0 ? '#ef4444' : '#22d3ee';
        return (
          <div key={c.metric} className="contrib-bar" style={{ animationDelay: `${idx * 0.08}s` }}>
            <span className="label">{c.metric}</span>
            <span className="track">
              <span className="fill" style={{ width: `${width}%`, background: color }} />
            </span>
            <span className="val">
              {c.value} {c.unit} &middot; {c.contribution > 0 ? '+' : ''}{c.contribution}
            </span>
          </div>
        );
      })}
    </div>
  );
}
