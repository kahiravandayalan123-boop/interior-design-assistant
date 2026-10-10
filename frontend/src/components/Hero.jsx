import BeforeAfterSlider from "./BeforeAfterSlider.jsx";

const POINTS = [
  "Keeps your real walls, windows and doors",
  "Tells you what to keep and what to replace",
  "Shopping list sized to your room and budget",
];

// Landing hero: the app title plus a real before/after produced by this app.
export default function Hero() {
  return (
    <header className="hero">
      <div className="hero-copy">
        <h1>
          AI Interior <span>Design</span> Assistant
        </h1>
        <p className="hero-tagline">See your own room, redesigned.</p>
        <p className="hero-sub">
          Upload a photo. Get an honest verdict on the furniture you already
          have, a redesign painted onto your actual room, and a shopping list
          sized to your space and budget.
        </p>
        <ul className="hero-points">
          {POINTS.map((p) => (
            <li key={p}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M5 12.5l4.5 4.5L19 7.5" />
              </svg>
              {p}
            </li>
          ))}
        </ul>
      </div>
      <div className="hero-visual">
        <div className="hero-frame">
          <BeforeAfterSlider
            before="/samples/sunny-living-room.jpg"
            after="/samples/sunny-living-room-after.jpg"
          />
        </div>
        <span className="hero-badge hero-badge-top">Sample result · drag to compare</span>
        <span className="hero-badge hero-badge-bottom">
          <i aria-hidden="true">✓</i> Same windows, same door, new look
        </span>
      </div>
    </header>
  );
}
