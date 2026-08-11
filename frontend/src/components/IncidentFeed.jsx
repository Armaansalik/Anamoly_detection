import { useState } from 'react';
import { approveIncident } from '../api';

export default function IncidentFeed({ incidents, onSelectSource }) {
  const [busy, setBusy] = useState({});

  const approve = async (id, ok) => {
    setBusy((b) => ({ ...b, [id]: true }));
    try {
      await approveIncident(id, ok);
    } catch {
      /* backend refresh will reflect truth */
    } finally {
      setBusy((b) => ({ ...b, [id]: false }));
    }
  };

  if (!incidents.length) {
    return <div className="empty-note">No incidents yet — the agent is watching.</div>;
  }

  return (
    <div>
      {incidents.map((inc) => (
        <div key={inc.id} className="incident">
          <div className="row1">
            <span className={`badge ${inc.severity}`}>{inc.severity}</span>
            <span className={`badge ${inc.status}`}>{inc.status}</span>
            <span style={{ fontSize: 11, color: '#94a3b8', marginLeft: 'auto' }}>
              {new Date(inc.created_at).toLocaleTimeString()}
            </span>
          </div>
          <div className="msg">{inc.message}</div>
          <div className="meta">
            source: <a href="#" onClick={(e) => { e.preventDefault(); onSelectSource(inc.source_id); }}>{inc.source_id}</a>
            {' '}· score {inc.anomaly_score}
            {inc.action && (
              <>
                {' '}· action <b>{inc.action.id}</b> ({inc.action.risk})
              </>
            )}
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
