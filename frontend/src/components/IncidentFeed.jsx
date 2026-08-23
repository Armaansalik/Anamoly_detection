import { useState } from 'react';
import { approveIncident } from '../api';

const TIME = (ts) => {
  try { return new Date(ts).toLocaleTimeString(); } catch { return ''; }
};

export default function IncidentFeed({ incidents, onSelectSource }) {
  const [busy, setBusy] = useState({});

  const approve = async (id, ok) => {
    setBusy((b) => ({ ...b, [id]: true }));
    try { await approveIncident(id, ok); } catch { /* handled by refresh */ }
    finally { setBusy((b) => ({ ...b, [id]: false })); }
  };

  if (!incidents.length) {
    return <div className="empty-note"><span className="icon">&#x1F6E1;</span>No incidents yet - the agent is watching.</div>;
  }

  return (
    <div>
      {incidents.map((inc, idx) => (
        <div
          key={inc.id}
          className={`incident ${idx === 0 ? 'anomaly-alert' : ''}`}
          style={{ animationDelay: `${Math.min(idx * 0.05, 0.5)}s` }}
        >
          <div className="row1">
            <span className={`badge ${inc.severity}`}>{inc.severity}</span>
            <span className={`badge ${inc.status}`}>{inc.status.replace('_', ' ')}</span>
            <span style={{ fontSize: 11, color: '#7a8ba8', marginLeft: 'auto' }}>{TIME(inc.created_at)}</span>
          </div>
          <div className="msg-text">{inc.message}</div>
          <div className="meta">
            source:{' '}
            <a href="#" onClick={(e) => { e.preventDefault(); onSelectSource(inc.source_id); }}>{inc.source_id}</a>
            {' '}&middot; score {inc.anomaly_score}
            {inc.action && <>{' '}&middot; action <b>{inc.action.id}</b> ({inc.action.risk})</>}
          </div>
          {inc.status === 'pending_approval' && inc.action && (
            <div className="actions">
              <button className="btn approve small" disabled={busy[inc.id]} onClick={() => approve(inc.id, true)}>
                Approve
              </button>
              <button className="btn reject small" disabled={busy[inc.id]} onClick={() => approve(inc.id, false)}>
                Reject
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
