import { useEffect, useState } from "react";

// Small inline spinner (inherits currentColor) or a larger standalone one.
export default function Spinner({ lg = false }) {
  return <span className={lg ? "spinner lg" : "spinner"} role="status" aria-label="Loading" />;
}

// Full loading panel used while a step is working in the background.
export function LoadingPanel({ title, sub }) {
  return (
    <div className="loading-panel">
      <Spinner lg />
      <p className="loading-title">{title}</p>
      {sub && <p className="loading-sub">{sub}</p>}
    </div>
  );
}

// Loading panel for the long multi-part requests. The backend does all the
// steps in one request, so step progress is estimated from elapsed time
// (`at` = seconds when a step typically starts); the live seconds counter is
// what keeps it from ever looking frozen. The last step stays "in progress"
// until the response actually arrives.
export function ProgressPanel({ title, sub, steps }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const started = Date.now();
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(id);
  }, []);

  const current = steps.reduce((idx, s, i) => (elapsed >= s.at ? i : idx), 0);

  return (
    <div className="loading-panel" aria-live="polite">
      <Spinner lg />
      <p className="loading-title">{title}</p>
      {sub && <p className="loading-sub">{sub}</p>}
      <ol className="progress-steps">
        {steps.map((s, i) => (
          <li key={s.label} className={i < current ? "done" : i === current ? "active" : ""}>
            <span className="progress-mark" aria-hidden="true">
              {i < current ? "✓" : i === current ? <Spinner /> : ""}
            </span>
            {s.label}
          </li>
        ))}
      </ol>
      <p className="loading-elapsed">{elapsed}s elapsed</p>
    </div>
  );
}
