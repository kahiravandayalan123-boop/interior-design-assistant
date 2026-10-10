// First screen: routes the user into one of two flows.
export default function LandingScreen({ onSelect }) {
  return (
    <div className="landing">

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
          <span className="landing-title">Redesign in a new style</span>
          <span className="landing-desc">
            Pick a style and answer four quick questions. We assess what you own, then restyle the room around it.
          </span>
          <span className="landing-go">Start a redesign →</span>
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
          <span className="landing-title">Make a specific change</span>
          <span className="landing-desc">
            Describe what you want in your own words — “make it cosier” or “swap the sofa for a smaller one”.
          </span>
          <span className="landing-go">Describe a change →</span>
        </button>
      </div>
      <ul className="how">
        <li><strong>1</strong>Upload a photo of your room</li>
        <li><strong>2</strong>Get a keep / replace verdict on each piece</li>
        <li><strong>3</strong>See the redesign and shop the changes</li>
      </ul>
    </div>
  );
}
