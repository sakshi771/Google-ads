export default function KPIRow({ metrics }) {
  return (
    <div className="kpi-row">
      {metrics.map((m, i) => (
        <div className="kpi-card" key={i}>
          <div className="kpi-label">{m.label}</div>
          <div className="kpi-value">{m.value}</div>
        </div>
      ))}
    </div>
  );
}
