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

export default function App() {
  const [sources, setSources] = useState([]);
  const [incidents, setIncidents] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [liveData, setLiveData] = useState({});
  const [drift, setDrift] = useState(null);
  const driftTimer = useRef(null);

  const refresh = useCallback(async () => {
    try {
      const [src, inc] = await Promise.all([getSources(), getIncidents(100)]);
      setSources(src.sources || []);
      setIncidents(inc.incidents || []);
    } catch {
      /* backend not up yet */
    }
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
        const next = { ...prev, [ev.source_id]: { ...src, [ev.metric_name]: [...series, { i: series.length, value: ev.value }].slice(-MAX_POINTS) } };
        return next;
      });
    } else if (msg.type === 'alert') {
      setIncidents((prev) => [msg.incident, ...prev.filter((i) => i.id !== msg.incident.id)].slice(0, 100));
      refresh();
    } else if (msg.type === 'action' && msg.incident_id) {
      setIncidents((prev) =>
        prev.map((i) =>
          i.id === msg.incident_id
            ? { ...i, status: (msg.action && msg.action.status) || i.status, action: { ...(i.action || {}), ...(msg.action || {}) } }
            : i
        )
      );
    } else if (msg.type === 'drift') {
      setDrift(`Drift detected on ${msg.source_id} (${msg.metric}): ${msg.recommendation}`);
      clearTimeout(driftTimer.current);
      driftTimer.current = setTimeout(() => setDrift(null), 15000);
    }
  }, [refresh]);

  const connected = useWebSocket(handleMessage);

  const selectedSource = useMemo(
    () => sources.find((s) => s.id === selectedId) || sources[0] || null,
    [sources, selectedId]
  );

  const chartData = selectedId ? liveData[selectedId] || {} : {};

  return (
    <div className="app">
      <div className="header">
        <h1>SentinelAgent</h1>
        <span className="subtitle">Autonomous anomaly detection &amp; self-healing agent</span>
        <div className="spacer" />
        <span className={`status-dot ${connected ? 'on' : 'off'}`} title={connected ? 'live' : 'offline'} />
      </div>
      {drift && <div className="drift-banner">{drift}</div>}
      <div className="main">
        <div className="col" style={{ gridColumn: 1 }}>
          <div className="panel flex-1">
            <h2>Sources</h2>
            <SourceList sources={sources} selectedId={selectedId} onSelect={setSelectedId} />
          </div>
        </div>
        <div className="col" style={{ gridColumn: 2 }}>
          <div className="panel" style={{ flex: 1.2, minHeight: 0 }}>
            <h2>Live Telemetry — {selectedSource ? selectedSource.id : 'select a source'}</h2>
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
