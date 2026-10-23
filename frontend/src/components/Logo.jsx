// Brand mark: a rounded house glyph with a sparkle (the "AI" cue) plus the
// two-line wordmark, matching the intro video / outreach assets. Colors come
// from the site's own --accent / --clay variables so it stays in sync with
// the rest of the theme if those ever change.
export default function Logo({ size = 48, tagline = false, className = "" }) {
  return (
    <span className={`brand-logo ${className}`}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 140 140"
        aria-hidden="true"
        className="brand-logo-mark"
      >
        <rect x="4" y="4" width="132" height="132" rx="30" style={{ fill: "var(--accent)" }} />
        <path
          d="M38 78 L70 50 L102 78 V98 C102 101 99.5 103.5 96.5 103.5 H43.5 C40.5 103.5 38 101 38 98 Z"
          fill="none"
          stroke="#fff"
          strokeWidth="5.5"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        <rect x="60" y="80" width="20" height="23" rx="2" fill="none" stroke="#fff" strokeWidth="4.5" />
        <path
          d="M100 38 L103.2 46.8 L112 50 L103.2 53.2 L100 62 L96.8 53.2 L88 50 L96.8 46.8 Z"
          style={{ fill: "var(--clay)" }}
        />
        <circle cx="116" cy="64" r="3.2" style={{ fill: "var(--clay)" }} />
      </svg>
      <span className="brand-wordmark">
        <span className="brand-wordmark-line brand-wordmark-ink">AI Interior</span>
        <span className="brand-wordmark-line brand-wordmark-clay">Design Assistant</span>
        {tagline && <span className="brand-wordmark-tagline">See your room, redesigned.</span>}
      </span>
    </span>
  );
}
