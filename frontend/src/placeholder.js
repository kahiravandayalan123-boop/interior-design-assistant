// Inline SVG data URI shown when an <img> fails to load (broken product photo,
// dropped network request, expired URL). Avoids the browser's broken-image
// icon and an extra network request for a placeholder asset.
export const IMG_FALLBACK =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 150">
      <rect width="200" height="150" fill="#eceae3"/>
      <g stroke="#c7c0af" stroke-width="1.6" fill="none" stroke-linecap="round" stroke-linejoin="round">
        <rect x="24" y="30" width="152" height="90" rx="6"/>
        <circle cx="66" cy="62" r="11"/>
        <path d="M24 104 l40-34 32 26 26-20 54 44"/>
      </g>
    </svg>`
  );

// Swap a broken <img> to the fallback exactly once (avoid an infinite
// error->error loop if the fallback itself somehow fails to render).
export function onImgError(e) {
  e.currentTarget.onerror = null;
  e.currentTarget.src = IMG_FALLBACK;
}
