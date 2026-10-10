// Keep / replace / remove / add verdicts on furniture, with the reason.
const LABEL = { keep: "Keep", replace: "Replace", remove: "Remove", add: "Add" };
const ORDER = ["keep", "replace", "remove", "add"];

export function VerdictBadge({ action }) {
  if (!LABEL[action]) return null;
  return <span className={`verdict verdict-${action}`}>{LABEL[action]}</span>;
}

export function VerdictSummary({ items }) {
  const counts = ORDER.map((a) => [a, items.filter((i) => i.action === a).length]).filter(([, n]) => n > 0);
  if (!counts.length) return null;
  return (
    <div className="verdict-summary">
      {counts.map(([a, n]) => (
        <span key={a} className={`verdict-count verdict-${a}`}>
          <strong>{n}</strong> {LABEL[a].toLowerCase()}
        </span>
      ))}
    </div>
  );
}

export default function VerdictList({ items }) {
  if (!items?.length) return <p className="muted">No furniture was detected in this photo.</p>;
  const sorted = [...items].sort((a, b) => ORDER.indexOf(a.action) - ORDER.indexOf(b.action));
  return (
    <ul className="verdicts">
      {sorted.map((f, i) => (
        <li key={i} className="verdict-row">
          <VerdictBadge action={f.action} />
          <div>
            <div className="verdict-name">
              {f.name}
              {f.size && <span className="verdict-size">{f.size}</span>}
            </div>
            {f.reason && <div className="verdict-reason">{f.reason}</div>}
          </div>
        </li>
      ))}
    </ul>
  );
}
