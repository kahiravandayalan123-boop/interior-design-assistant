// Small recap of the choices that produced this redesign: target style plus
// every follow-up question the user answered (budget, priorities, etc).
export default function RecapCard({ style, recap }) {
  return (
    <div className="recap">
      <div className="recap-row recap-style">
        <span className="recap-label">Style</span>
        <span className="recap-value recap-style-pill">{style}</span>
      </div>
      {recap.map((r) => (
        <div className="recap-row" key={r.id}>
          <span className="recap-label">{recapLabel(r)}</span>
          <span className="recap-value">{r.answer}</span>
        </div>
      ))}
    </div>
  );
}

// Prefer a short label for well-known question kinds; fall back to the full
// question text for anything custom the AI asked.
function recapLabel(r) {
  const known = {
    budget: "Budget",
    seating: "Seating",
    space: "Space priority",
    storage: "Storage",
    lighting: "Lighting",
    colors: "Colours",
    priorities: "Priorities",
    instruction: "Requested change",
  };
  return known[r.kind] || r.question;
}
