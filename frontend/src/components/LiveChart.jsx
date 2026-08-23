import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

const COLORS = ['#22d3ee', '#a78bfa', '#34d399', '#fbbf24', '#f472b6', '#60a5fa'];

export default function LiveChart({ data }) {
  const metrics = Object.keys(data || {});
  if (!metrics.length) {
    return (
      <div className="chart-empty">
        <div className="spinner" />
        Waiting for live telemetry...
      </div>
    );
  }
  return (
    <div>
      {metrics.map((metric, idx) => {
        const series = data[metric] || [];
        return (
          <div key={metric} className="chart-box" style={{ animationDelay: `${idx * 0.1}s` }}>
            <div className="chart-title">{metric}</div>
            <ResponsiveContainer width="100%" height={110}>
              <LineChart data={series} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
                <CartesianGrid stroke="#2a3a5c" strokeDasharray="3 3" />
                <XAxis dataKey="i" tick={{ fill: '#7a8ba8', fontSize: 10 }} />
                <YAxis tick={{ fill: '#7a8ba8', fontSize: 10 }} domain={['auto', 'auto']} />
                <Tooltip
                  contentStyle={{ background: '#141c30', border: '1px solid #2a3a5c', borderRadius: 8, color: '#e8edf5' }}
                  labelStyle={{ color: '#7a8ba8' }}
                />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke={COLORS[idx % COLORS.length]}
                  dot={false}
                  strokeWidth={2}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        );
      })}
    </div>
  );
}
