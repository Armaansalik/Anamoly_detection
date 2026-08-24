import { useState } from 'react';
import { approveIncident } from '../api';

const TIME = (ts) => {
  try { return new Date(ts).toLocaleTimeString(); } catch { return ''; }
};

export default function IncidentFeed({ incidents, onSelectSource }) {
  const [busy, setBusy] = useState({});
  const [optimistic, setOptimistic] = useState({});

  const approve = async (id, ok) => {
    setBusy((b) => ({ ...b, [id]: true }));
    setOptimistic((p) => ({ ...p, [id]: ok ? 'executed' : 'rejected' }));
    try { await approveIncident(id, ok); } catch { /* refresh will fix */ }
    finally {
      setBusy((b) => ({ ...b, [id]: false }));
      setTimeout(() => setOptimistic((p) => { const n = { ...p }; delete n[id]; return n; }), 2000);
    }
  };

  if (!incidents.length) {
    return <div className="empty-note"><span className="icon">&#x1F6E1;</span>No incidents yet - the agent is watching.</div>;
  }

  return (
    <div>
      {incidents.map((inc, idx) => {
        const displayStatus = optimistic[inc.id] || inc.status;
        return (
          <div
            key={inc.id}
            className={`incident ${idx === 0 ? 'anomaly-alert' : ''}`}
            style={{ animationDelay: `${Math.min(idx * 0.05, 0.5)}s` }}
          >
            <div className="row1">
              <span className={`badge ${inc.severity}`}>{inc.severity}</span>
              <span className={`badge ${displayStatus}`}>{displayStatus.replace('_', ' ')}</span>
              <span style={{ fontSize: 11, color: '#7a8ba8', marginLeft: 'auto' }}>{TIME(inc.created_at)}</span>
            </div>
            <div className="msg-text">{inc.message}</div>
            <div className="meta">
              source:{' '}
              <a href="#" onClick={(e) => { e.preventDefault(); onSelectSource(inc.source_id); }}>{inc.source_id}</a>
              {' '}&middot; score {inc.anomaly_score}
              {inc.action && <>{' '}&middot; action <b>{inc.action.id}</b> ({inc.action.risk})</>}
            </div>
            {displayStatus === 'pending_approval' && inc.action && (
              <div className="actions">
                <button
                  className="btn approve small"
                  disabled={busy[inc.id]}
                  onClick={() => approve(inc.id, true)}
                  style={busy[inc.id] ? { opacity: 0.6, minWidth: 90 } : { minWidth: 90 }}
                >
                  {busy[inc.id] ? <span className="btn-spinner" /> : 'Approve'}
                </button>
                <button
                  className="btn reject small"
                  disabled={busy[inc.id]}
                  onClick={() => approve(inc.id, false)}
                  style={busy[inc.id] ? { opacity: 0.6, minWidth: 80 } : { minWidth: 80 }}
                >
                  {busy[inc.id] ? <span className="btn-spinner" /> : 'Reject'}
                </button>
              </div>
            )}
            {(displayStatus === 'executed' || displayStatus === 'rolled_back') && (
              <div style={{ marginTop: 8, fontSize: 11, color: '#22c55e', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ animation: 'countUp 0.3s ease' }}>&#x2714;</span> Action {displayStatus}
              </div>
            )}
            {displayStatus === 'rejected' && (
              <div style={{ marginTop: 8, fontSize: 11, color: '#ef4444', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ animation: 'countUp 0.3s ease' }}>&#x2718;</span> Action rejected
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
