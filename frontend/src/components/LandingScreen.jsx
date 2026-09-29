// First screen: routes the user into one of two flows.
export default function LandingScreen({ onSelect }) {
  return (
    <div className="card landing">
      <h2>What would you like to do?</h2>
      <p className="card-sub">Pick how you'd like to start.</p>

      <div className="landing-options">
        <button
          type="button"
          className="landing-card"
          onClick={() => onSelect("new")}
        >
          <span className="landing-icon" aria-hidden="true">
            <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="4" width="18" height="16" rx="2" />
              <path d="M12 9v6M9 12h6" />
            </svg>
          </span>
          <span className="landing-title">New Room Design</span>
          <span className="landing-desc">
            Empty or raw room? Pick a style, answer a few questions, and design it from scratch.
          </span>
        </button>

        <button
          type="button"
          className="landing-card"
          onClick={() => onSelect("modify")}
        >
          <span className="landing-icon" aria-hidden="true">
            <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 20h9" />
              <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
            </svg>
          </span>
          <span className="landing-title">Modify Existing Room</span>
          <span className="landing-desc">
            Already furnished? Tell us what to change — general or specific — and we'll redesign it.
          </span>
        </button>
      </div>
    </div>
  );
}
