import { useEffect, useState } from 'react';
import { explainSource } from '../api';

export default function ExplainabilityPanel({ sourceId }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(null);
    if (!sourceId) return;
    explainSource(sourceId)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [sourceId]);

  if (!sourceId) {
    return <div className="empty-note">Select a source to see why its readings were flagged.</div>;
  }
  if (error) return <div className="empty-note">Explainability unavailable: {error}</div>;
  if (!data) return <div className="empty-note">Loading…</div>;

  return (
    <div>
      <div className="explain-summary">{data.summary}</div>
      {data.contributions.map((c) => {
        const width = Math.min(100, Math.abs(c.contribution) * 100);
        const color = c.contribution >= 0 ? '#ef4444' : '#22d3ee';
        return (
          <div key={c.metric} className="contrib-bar">
            <span className="label">{c.metric}</span>
            <span className="track">
              <span
                className="fill"
                style={{ width: `${width}%`, background: color, display: 'block' }}
              />
            </span>
            <span className="val">
              {c.value} {c.unit} · {c.contribution > 0 ? '+' : ''}
              {c.contribution}
            </span>
          </div>
        );
      })}
    </div>
  );
}
