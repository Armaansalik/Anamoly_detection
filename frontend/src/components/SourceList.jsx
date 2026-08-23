export default function SourceList({ sources, selectedId, onSelect }) {
  if (!sources.length) {
    return <div className="empty-note"><span className="icon">&#x1F50D;</span>Waiting for sources...</div>;
  }
  return (
    <div>
      {sources.map((s, idx) => (
        <div
          key={s.id}
          className={`source-item ${s.id === selectedId ? 'selected' : ''}`}
          onClick={() => onSelect(s.id)}
          style={{ animationDelay: `${idx * 0.05}s` }}
        >
          <span className={`h-dot h-${s.status}`} />
          <span className="name">{s.id}</span>
          <span className="score">{Math.round((s.health_score || 0) * 100)}%</span>
        </div>
      ))}
    </div>
  );
}
