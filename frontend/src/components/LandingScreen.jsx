const Arrow = () => (
  <span className="landing-arrow" aria-hidden="true">
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  </span>
);

const STEPS = [
  {
    title: "Upload a photo",
    text: "Any normal photo of the room. Tell us its size if you know it.",
    icon: <path d="M4 8a2 2 0 0 1 2-2h2l1.5-2h5L16 6h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2zM12 16a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z" />,
  },
  {
    title: "Get the verdict",
    text: "Every piece you own is marked keep, replace or remove, with a reason.",
    icon: <path d="M9 6h11M9 12h11M9 18h11M4 6l1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2" />,
  },
  {
    title: "See it redesigned",
    text: "The new look is painted onto your own photo, then checked against it.",
    icon: <path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8zM18.5 15l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z" />,
  },
  {
    title: "Shop the changes",
    text: "Only what the plan buys, within budget, with links to real stores.",
    icon: <path d="M6 8h12l-1 12H7zM9 8V6a3 3 0 0 1 6 0v2" />,
  },
];

// First screen: routes the user into one of two flows.
export default function LandingScreen({ onSelect }) {
  return (
    <div className="landing">
      <h2 className="landing-heading">What would you like to do?</h2>
      <p className="landing-sub">Pick how you'd like to start.</p>

      <div className="landing-options">
        <button type="button" className="landing-card landing-card-new" onClick={() => onSelect("new")}>
          <span className="landing-icon" aria-hidden="true">
            <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="4" width="18" height="16" rx="2" />
              <path d="M12 9v6M9 12h6" />
            </svg>
          </span>
          <span className="landing-title">New Room Design</span>
          <span className="landing-desc">
            Empty or raw room? Pick a style, answer a few questions, and design it from scratch.
          </span>
          <Arrow />
        </button>

        <button type="button" className="landing-card landing-card-modify" onClick={() => onSelect("modify")}>
          <span className="landing-icon" aria-hidden="true">
            <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 20h9" />
              <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
            </svg>
          </span>
          <span className="landing-title">Modify Existing Room</span>
          <span className="landing-desc">
            Already furnished? Tell us what to change — general or specific — and we'll redesign it.
          </span>
          <Arrow />
        </button>
      </div>

      <section className="how">
        <h2 className="how-heading">How it works</h2>
        <ol className="how-steps">
          {STEPS.map((s, i) => (
            <li key={s.title}>
              <span className="how-icon" aria-hidden="true">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                  {s.icon}
                </svg>
              </span>
              <span className="how-num">Step {i + 1}</span>
              <strong>{s.title}</strong>
              <p>{s.text}</p>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
