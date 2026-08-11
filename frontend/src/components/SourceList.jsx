export default function SourceList({ sources, selectedId, onSelect }) {
  if (!sources.length) {
    return <div className="empty-note">No sources yet — start the simulator or POST events.</div>;
  }
  return (
    <div>
      {sources.map((s) => (
        <div
          key={s.id}
          className={`source-item ${s.id === selectedId ? 'selected' : ''}`}
          onClick={() => onSelect(s.id)}
        >
          <span className={`h-dot h-${s.status}`} />
          <span className="name">{s.id}</span>
          <span className="meta" style={{ fontSize: 11, color: '#94a3b8' }}>
            {Math.round(s.health_score * 100)}%
          </span>
        </div>
      ))}
    </div>
  );
}
