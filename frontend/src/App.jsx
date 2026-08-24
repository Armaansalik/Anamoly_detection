import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { getIncidents, getSources } from './api';
import { useWebSocket } from './hooks/useWebSocket';
import SourceList from './components/SourceList';
import LiveChart from './components/LiveChart';
import DigitalTwin from './components/DigitalTwin';
import ChatPanel from './components/ChatPanel';
import IncidentFeed from './components/IncidentFeed';
import ExplainabilityPanel from './components/ExplainabilityPanel';

const MAX_POINTS = 200;
let toastId = 0;

export default function App() {
  const [sources, setSources] = useState([]);
  const [incidents, setIncidents] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [liveData, setLiveData] = useState({});
  const [drift, setDrift] = useState(null);
  const [toasts, setToasts] = useState([]);
  const driftTimer = useRef(null);

  const addToast = useCallback((type, badge, message) => {
    const id = ++toastId;
    setToasts((prev) => [...prev, { id, type, badge, message }].slice(-4));
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 6000);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const [src, inc] = await Promise.all([getSources(), getIncidents(100)]);
      setSources(src.sources || []);
      setIncidents(inc.incidents || []);
    } catch { /* backend not up */ }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 10000);
    return () => clearInterval(t);
  }, [refresh]);

  const handleMessage = useCallback((msg) => {
    if (msg.type === 'event' && msg.event) {
      const ev = msg.event;
      setLiveData((prev) => {
        const src = prev[ev.source_id] || {};
        const series = src[ev.metric_name] || [];
        return { ...prev, [ev.source_id]: { ...src, [ev.metric_name]: [...series, { i: series.length, value: ev.value }].slice(-MAX_POINTS) } };
      });
    } else if (msg.type === 'alert') {
      setIncidents((prev) => [msg.incident, ...prev.filter((i) => i.id !== msg.incident.id)].slice(0, 100));
      const inc = msg.incident;
      addToast('anomaly', inc.severity, `${inc.source_id}: ${inc.message.slice(0, 80)}`);
      refresh();
    } else if (msg.type === 'action' && msg.incident_id) {
      setIncidents((prev) =>
        prev.map((i) => i.id === msg.incident_id ? { ...i, status: msg.action?.status || i.status, action: { ...(i.action || {}), ...msg.action } } : i)
      );
      addToast('action', msg.action?.status || 'executed', `${msg.action?.id || 'action'} on ${msg.source_id}`);
    } else if (msg.type === 'drift') {
      setDrift(`Drift detected on ${msg.source_id} (${msg.metric}): ${msg.recommendation}`);
      addToast('warning', 'drift', `${msg.source_id} - ${msg.metric} distribution changed`);
      clearTimeout(driftTimer.current);
      driftTimer.current = setTimeout(() => setDrift(null), 15000);
    }
  }, [refresh, addToast]);

  const connected = useWebSocket(handleMessage);

  const selectedSource = useMemo(
    () => sources.find((s) => s.id === selectedId) || sources[0] || null,
    [sources, selectedId]
  );

  const chartData = selectedId ? liveData[selectedId] || {} : {};

  const stats = useMemo(() => {
    const total = incidents.length;
    const pending = incidents.filter((i) => i.status === 'pending_approval').length;
    const resolved = incidents.filter((i) => i.status === 'executed' || i.status === 'rolled_back').length;
    const open = incidents.filter((i) => i.status === 'open').length;
    const avgHealth = sources.length ? sources.reduce((s, src) => s + (src.health_score || 0), 0) / sources.length : 1;
    return { total, pending, resolved, open, avgHealth, sourceCount: sources.length };
  }, [incidents, sources]);

  return (
    <div className="app">
      <div className="header">
        <span className="logo-icon" title="SentinelAgent">&#x1F6E1;</span>
        <h1>SentinelAgent</h1>
        <span className="subtitle">Autonomous anomaly detection &amp; self-healing agent</span>
        <div className="spacer" />
        <span className={`status-dot ${connected ? 'on' : 'off'}`} title={connected ? 'live' : 'offline'} />
      </div>

      <div className="stats-bar">
        <div className="stat-card" style={{ animationDelay: '0s' }}>
          <div className="icon blue">&#x1F4CA;</div>
          <div className="info"><div className="value">{stats.sourceCount}</div><div className="label">Sources</div></div>
        </div>
        <div className="stat-card" style={{ animationDelay: '0.05s' }}>
          <div className="icon yellow">&#x26A0;</div>
          <div className="info"><div className="value">{stats.total}</div><div className="label">Total Incidents</div></div>
        </div>
        <div className="stat-card" style={{ animationDelay: '0.1s' }}>
          <div className="icon red">&#x1F534;</div>
          <div className="info"><div className="value">{stats.pending}</div><div className="label">Pending Approval</div></div>
        </div>
        <div className="stat-card" style={{ animationDelay: '0.15s' }}>
          <div className="icon green">&#x2705;</div>
          <div className="info"><div className="value">{stats.resolved}</div><div className="label">Resolved</div></div>
        </div>
        <div className="stat-card" style={{ animationDelay: '0.2s' }}>
          <div className="icon blue">&#x1F7E2;</div>
          <div className="info"><div className="value">{Math.round(stats.avgHealth * 100)}%</div><div className="label">Avg Health</div></div>
        </div>
      </div>

      {drift && <div className="drift-banner"><span className="icon">&#x26A0;</span>{drift}</div>}

      <div className="toast-container">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.type}`} onClick={() => setToasts((prev) => prev.filter((x) => x.id !== t.id))}>
            <span className="badge">{t.badge}</span>
            <span>{t.message}</span>
          </div>
        ))}
      </div>

      <div className="main">
        <div className="col" style={{ gridColumn: 1 }}>
          <div className="panel flex-1">
            <h2>Sources</h2>
            <SourceList sources={sources} selectedId={selectedId} onSelect={setSelectedId} />
          </div>
        </div>
        <div className="col" style={{ gridColumn: 2 }}>
          <div className="panel" style={{ flex: 1.2, minHeight: 0 }}>
            <h2>Live Telemetry &mdash; {selectedSource ? selectedSource.id : 'select a source'}</h2>
            <LiveChart data={chartData} />
          </div>
          <div className="panel" style={{ flex: 1, minHeight: 0 }}>
            <h2>Digital Twin</h2>
            <DigitalTwin sources={sources} selectedId={selectedSource ? selectedSource.id : null} />
          </div>
          <div className="panel" style={{ flex: 1.2, minHeight: 0 }}>
            <h2>Explainability</h2>
            <ExplainabilityPanel sourceId={selectedSource ? selectedSource.id : null} />
          </div>
        </div>
        <div className="col" style={{ gridColumn: 3 }}>
          <div className="panel" style={{ flex: 1, minHeight: 0 }}>
            <h2>Conversational Copilot</h2>
            <ChatPanel sourceId={selectedSource ? selectedSource.id : null} />
          </div>
          <div className="panel" style={{ flex: 1.4, minHeight: 0 }}>
            <h2>Incidents &amp; Actions</h2>
            <IncidentFeed incidents={incidents} onSelectSource={setSelectedId} />
          </div>
        </div>
      </div>
    </div>
  );
}
