// Horizontal "Step X of N" progress indicator across the top of the flow.
// "Preferences" only applies to the New Room Design path — the Modify
// Existing Room path skips straight from Upload to Generate.
export const STEPS = ["Start", "Upload", "Preferences", "Generate", "Results"];

export default function Stepper({ current }) {
  return (
    <>
      <div className="stepper" aria-hidden="true">
        {STEPS.map((label, i) => {
          const state = i < current ? "done" : i === current ? "active" : "upcoming";
          return (
            <div className={`stepper-item ${state}`} key={label}>
              <span className="stepper-dot">{i < current ? "✓" : i + 1}</span>
              <span className="stepper-label">{label}</span>
            </div>
          );
        })}
      </div>
      <p className="step-count">
        Step {Math.min(current + 1, STEPS.length)} of {STEPS.length}
        {" · "}
        {STEPS[current]}
      </p>
    </>
  );
}
