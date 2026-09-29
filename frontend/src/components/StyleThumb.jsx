// Room vignettes for each design style — self-contained inline SVG, no network
// assets, so the picker always renders (even offline). Each scene uses gradients
// for depth, furniture with realistic proportions and rounded edges, and a few
// props (rug, framed art, plant) so it reads as a curated room, not an icon.
//
// NOTE: all four SVGs live in the DOM at once, so every <linearGradient> /
// <radialGradient> id is namespaced per style (mod- / min- / trad- / scan-).

function Thumb({ label, children }) {
  return (
    <svg
      viewBox="0 0 160 120"
      width="100%"
      height="100%"
      preserveAspectRatio="xMidYMid slice"
      role="img"
      aria-label={label}
    >
      {children}
    </svg>
  );
}

const THUMBS = {
  // ---- Modern: clean warm neutrals + one bold terracotta accent ----------
  Modern: (
    <Thumb label="Modern living room preview: charcoal low sofa, warm neutral walls, terracotta accents">
      <defs>
        <linearGradient id="mod-wall" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ECE7DD" />
          <stop offset="1" stopColor="#DED7C7" />
        </linearGradient>
        <linearGradient id="mod-floor" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#D8C7A9" />
          <stop offset="1" stopColor="#C5B18F" />
        </linearGradient>
        <linearGradient id="mod-sofa" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#4D525B" />
          <stop offset="1" stopColor="#373B42" />
        </linearGradient>
        <linearGradient id="mod-accent" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#CF7A48" />
          <stop offset="1" stopColor="#AE5329" />
        </linearGradient>
      </defs>

      <rect width="160" height="120" fill="url(#mod-wall)" />
      <rect y="82" width="160" height="38" fill="url(#mod-floor)" />
      <rect y="79" width="160" height="4" fill="#D1C8B6" />

      {/* flat-weave geometric rug — sits under the sofa feet */}
      <rect x="20" y="80" width="120" height="13" rx="1" fill="#DACFBA" />
      <path d="M20 84 H140 M20 89 H140" stroke="#CABEA4" strokeWidth="1" strokeOpacity="0.7" />
      <path d="M54 82 l4 4.5 -4 4.5 -4 -4.5 z M80 82 l4 4.5 -4 4.5 -4 -4.5 z M106 82 l4 4.5 -4 4.5 -4 -4.5 z" fill="#C08A5A" fillOpacity="0.5" />

      {/* framed abstract art */}
      <rect x="18" y="10" width="46" height="32" rx="1.5" fill="#2E2E30" />
      <rect x="21" y="13" width="40" height="26" fill="#EFE9DD" />
      <rect x="21" y="13" width="15" height="26" fill="url(#mod-accent)" />
      <circle cx="50" cy="23" r="7" fill="#26333D" />
      <rect x="21" y="35" width="40" height="3" fill="#A99C82" />

      {/* arc floor lamp */}
      <ellipse cx="140" cy="80" rx="8" ry="2.6" fill="#2E2E30" />
      <path d="M140 80 C140 42 150 28 126 28" stroke="#2E2E30" strokeWidth="2.4" fill="none" strokeLinecap="round" />
      <path d="M119 27 q7 -2.5 15 0 l-1.5 10 q-6 2 -12 0 z" fill="#ECE3D2" />
      <ellipse cx="126.5" cy="38" rx="5.5" ry="1.6" fill="#F1D9A8" fillOpacity="0.6" />

      {/* low-profile sofa */}
      <rect x="30" y="44" width="80" height="14" rx="5" fill="#43474E" />
      <rect x="28" y="48" width="10" height="26" rx="4" fill="#3B3F46" />
      <rect x="102" y="48" width="10" height="26" rx="4" fill="#3B3F46" />
      <rect x="30" y="54" width="82" height="20" rx="5" fill="url(#mod-sofa)" />
      <rect x="35" y="55" width="35" height="11" rx="3" fill="#53575F" />
      <rect x="72" y="55" width="35" height="11" rx="3" fill="#53575F" />
      <rect x="93" y="52" width="14" height="14" rx="2.5" fill="url(#mod-accent)" transform="rotate(-6 100 59)" />
      <rect x="37" y="73" width="3.5" height="7" fill="#8C8C8C" />
      <rect x="101" y="73" width="3.5" height="7" fill="#8C8C8C" />

      {/* snake plant */}
      <path d="M17 66 h13 l-2 14 h-9 z" fill="#C6BCA8" />
      <path d="M17 66 h4 l-1.4 14 h-2.6 z" fill="#B4A88F" />
      <path d="M23 66 C21 50 22 40 23 33 C24 40 25 50 23 66 Z" fill="#3F6B4A" />
      <path d="M27 66 C27 52 29 44 32 37 C31 46 30 56 27 66 Z" fill="#4B7B55" />
      <path d="M19 66 C18 54 16 47 13 40 C15 49 16 58 19 66 Z" fill="#356043" />
    </Thumb>
  ),

  // ---- Minimalist: whites / light grays + one muted sage tone -----------
  Minimalist: (
    <Thumb label="Minimalist living room preview: pale low bench, white walls, single sage cushion">
      <defs>
        <linearGradient id="min-wall" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#F8F6F1" />
          <stop offset="1" stopColor="#EDEAE1" />
        </linearGradient>
        <linearGradient id="min-floor" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#E9E3D5" />
          <stop offset="1" stopColor="#D6CEBB" />
        </linearGradient>
        <linearGradient id="min-sofa" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#F1EEE7" />
          <stop offset="1" stopColor="#DAD3C4" />
        </linearGradient>
      </defs>

      <rect width="160" height="120" fill="url(#min-wall)" />
      <rect y="84" width="160" height="36" fill="url(#min-floor)" />
      <rect y="81.5" width="160" height="3" fill="#DAD2C0" />
      <ellipse cx="78" cy="80" rx="52" ry="6" fill="#000000" fillOpacity="0.05" />

      {/* single framed piece */}
      <rect x="62" y="16" width="30" height="22" fill="none" stroke="#C2B9A3" strokeWidth="1.6" />
      <line x1="66" y1="30" x2="88" y2="30" stroke="#B4A992" strokeWidth="1.4" />

      {/* pale rug */}
      <rect x="34" y="70" width="92" height="12" rx="1.5" fill="#EFEBE0" stroke="#E1DACB" strokeWidth="1.2" />

      {/* low platform bench */}
      <rect x="42" y="46" width="72" height="10" rx="3" fill="#E3DDD1" />
      <rect x="42" y="54" width="74" height="14" rx="3.5" fill="url(#min-sofa)" />
      <rect x="42" y="66" width="74" height="2" rx="1" fill="#D3CCBB" />
      <rect x="47" y="55" width="28" height="9" rx="2.5" fill="#DDD6C7" />
      <rect x="90" y="49" width="15" height="11" rx="2.5" fill="#A9B4A0" transform="rotate(-5 97 54)" />
      <rect x="46" y="68" width="2.6" height="6" fill="#B7AC97" />
      <rect x="111" y="68" width="2.6" height="6" fill="#B7AC97" />

      {/* slender vase + single stem */}
      <path d="M123 60 h7 l-1.4 13 h-4.2 z" fill="#DED7C7" />
      <path d="M126.5 60 C126 46 127 40 128 34" stroke="#9BA98F" strokeWidth="1.5" fill="none" strokeLinecap="round" />
      <path d="M126.8 44 C123 42 121 39 121 36 C124 37 126 40 126.8 44 Z" fill="#A7B79B" />
      <path d="M127.4 40 C131 38 133 35 133 32 C130 33 128 36 127.4 40 Z" fill="#A7B79B" />
    </Thumb>
  ),

  // ---- Traditional: warm woods, deep burgundy, gilt frame, ornate rug ----
  Traditional: (
    <Thumb label="Traditional living room preview: burgundy chesterfield, dark wood floor, gilt-framed painting, Persian rug">
      <defs>
        <linearGradient id="trad-wall" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#EADDC4" />
          <stop offset="1" stopColor="#DCCBAD" />
        </linearGradient>
        <linearGradient id="trad-floor" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#7A5231" />
          <stop offset="1" stopColor="#634226" />
        </linearGradient>
        <linearGradient id="trad-sofa" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#7F3131" />
          <stop offset="1" stopColor="#5B1F1F" />
        </linearGradient>
        <linearGradient id="trad-gilt" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#D9B564" />
          <stop offset="0.5" stopColor="#B98F3C" />
          <stop offset="1" stopColor="#8E6B2B" />
        </linearGradient>
        <radialGradient id="trad-glow" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#FBEAB8" stopOpacity="0.7" />
          <stop offset="1" stopColor="#FBEAB8" stopOpacity="0" />
        </radialGradient>
      </defs>

      <rect width="160" height="120" fill="url(#trad-wall)" />
      <rect width="160" height="6" fill="#E2D4B8" />
      <rect y="6" width="160" height="2" fill="#C4AF85" />

      {/* wainscoting */}
      <rect y="46" width="160" height="36" fill="#E1D3B7" />
      <rect y="44" width="160" height="3" fill="#CBB88F" />
      <path d="M40 49 V79 M80 49 V79 M120 49 V79" stroke="#CBB88F" strokeWidth="1.2" />

      {/* dark wood floor */}
      <rect y="82" width="160" height="38" fill="url(#trad-floor)" />
      <path d="M0 92 H160 M0 102 H160" stroke="#4A3018" strokeWidth="1" strokeOpacity="0.5" />

      {/* Persian rug under the sofa: fringed ends, gilt border, medallion */}
      <path d="M12 79 H16 M12 83 H16 M12 87 H16 M12 91 H16 M144 79 H148 M144 83 H148 M144 87 H148 M144 91 H148" stroke="#C9A34E" strokeWidth="1.3" />
      <rect x="16" y="76" width="128" height="19" rx="1.5" fill="#9C433C" />
      <rect x="16" y="76" width="128" height="19" fill="none" stroke="url(#trad-gilt)" strokeWidth="2" />
      <rect x="21" y="79.5" width="118" height="12" fill="none" stroke="#DBB768" strokeWidth="0.9" strokeOpacity="0.5" />
      <ellipse cx="67" cy="85.5" rx="15" ry="5.5" fill="#3B4A38" />
      <ellipse cx="67" cy="85.5" rx="15" ry="5.5" fill="none" stroke="#D9B564" strokeWidth="0.8" />
      <path d="M67 80 l3 3.5 -3 3.5 -3 -3.5 z" fill="#D9B564" />
      <path d="M32 85 l2.5 2.5 -2.5 2.5 -2.5 -2.5 z M102 85 l2.5 2.5 -2.5 2.5 -2.5 -2.5 z" fill="#D9B564" fillOpacity="0.8" />

      {/* gilt-framed landscape */}
      <rect x="52" y="8" width="56" height="34" rx="1" fill="url(#trad-gilt)" />
      <rect x="55.5" y="11.5" width="49" height="27" fill="#8A6D3B" />
      <rect x="58" y="14" width="44" height="22" fill="#CBD3DC" />
      <path d="M58 30 q11 -9 22 -3 q11 6 22 -3 v12 H58 z" fill="#6E7E5C" />
      <circle cx="94" cy="20" r="3.2" fill="#EBDCA9" />
      <circle cx="53" cy="9" r="2.4" fill="#E1C27C" />
      <circle cx="107" cy="9" r="2.4" fill="#E1C27C" />
      <circle cx="53" cy="41" r="2.4" fill="#E1C27C" />
      <circle cx="107" cy="41" r="2.4" fill="#E1C27C" />

      {/* rolled-arm chesterfield */}
      <rect x="36" y="40" width="62" height="18" rx="7" fill="#6E2828" />
      <circle cx="38" cy="56" r="8" fill="#742B2B" />
      <circle cx="96" cy="56" r="8" fill="#742B2B" />
      <rect x="34" y="52" width="66" height="20" rx="6" fill="url(#trad-sofa)" />
      <rect x="41" y="55" width="26" height="10" rx="3" fill="#8A3A3A" />
      <rect x="68" y="55" width="26" height="10" rx="3" fill="#8A3A3A" />
      <path d="M46 46 l4 4 -4 4 -4 -4 z M60 46 l4 4 -4 4 -4 -4 z M74 46 l4 4 -4 4 -4 -4 z M88 46 l4 4 -4 4 -4 -4 z" fill="#5A1E1E" fillOpacity="0.7" />
      <path d="M40 72 q-1 4 1 6 h4 q2 -2 1 -6 z M92 72 q-1 4 1 6 h4 q2 -2 1 -6 z" fill="#4A3018" />

      {/* brass floor lamp with warm glow */}
      <circle cx="134" cy="24" r="18" fill="url(#trad-glow)" />
      <ellipse cx="134" cy="78" rx="7" ry="2.4" fill="#A6812F" />
      <rect x="132.6" y="30" width="2.8" height="48" fill="#A6812F" />
      <path d="M124 30 h20 l-4 -11 h-12 z" fill="#C1963B" />

      {/* potted fern */}
      <path d="M14 62 q9 -5 18 0 l-2.5 16 h-13 z" fill="#8A6D3B" />
      <ellipse cx="23" cy="62" rx="9" ry="2.6" fill="#9C7C45" />
      <path d="M23 62 C13 55 10 45 13 35 M23 62 C18 51 16 42 18 33 M23 62 C23 49 23 41 23 33 M23 62 C28 51 30 43 29 34 M23 62 C33 54 37 47 36 39" stroke="#46683B" strokeWidth="1.5" fill="none" strokeLinecap="round" />
    </Thumb>
  ),

  // ---- Scandinavian: light wood, soft pastels, cozy knit textiles -------
  Scandinavian: (
    <Thumb label="Scandinavian living room preview: cream rounded sofa, light wood, blush and blue cushions, knit throw">
      <defs>
        <linearGradient id="scan-wall" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#FBFAF6" />
          <stop offset="1" stopColor="#F0EEE6" />
        </linearGradient>
        <linearGradient id="scan-floor" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ECD6B4" />
          <stop offset="1" stopColor="#DEC49A" />
        </linearGradient>
        <linearGradient id="scan-sofa" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#EFEBE2" />
          <stop offset="1" stopColor="#E0DACC" />
        </linearGradient>
        <linearGradient id="scan-window" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#EAF2F4" />
          <stop offset="1" stopColor="#D9E7EA" />
        </linearGradient>
      </defs>

      <rect width="160" height="120" fill="url(#scan-wall)" />

      {/* window */}
      <rect x="96" y="10" width="52" height="46" rx="2" fill="url(#scan-window)" stroke="#D9D1C1" strokeWidth="2.4" />
      <path d="M122 10 V56 M96 33 H148" stroke="#D9D1C1" strokeWidth="1.8" />
      <rect x="94" y="56" width="56" height="3" fill="#E4DCCB" />

      {/* light wood floor */}
      <rect y="84" width="160" height="36" fill="url(#scan-floor)" />
      <path d="M0 94 H160 M0 104 H160 M0 114 H160" stroke="#D3B888" strokeWidth="1" strokeOpacity="0.5" />

      {/* soft light pooling from the window */}
      <path d="M100 84 H140 L152 108 H108 z" fill="#FCF5E5" fillOpacity="0.55" />

      {/* thin oak-framed line-art poster */}
      <rect x="16" y="14" width="32" height="26" fill="#FCFBF7" stroke="#C9A876" strokeWidth="2.2" />
      <path d="M23 34 C23 21 41 21 41 34" stroke="#B7AA90" strokeWidth="1.5" fill="none" />

      {/* round high-pile rug */}
      <ellipse cx="66" cy="94" rx="54" ry="12" fill="#F3EEE2" />
      <ellipse cx="66" cy="94" rx="45" ry="9" fill="none" stroke="#E7DECD" strokeWidth="1.2" />

      {/* light-wood coffee table */}
      <ellipse cx="60" cy="80" rx="21" ry="5" fill="#E6CBA0" stroke="#CDAF7E" strokeWidth="1.4" />
      <path d="M44 82 l-3 9 M76 82 l3 9" stroke="#CDAF7E" strokeWidth="2.2" strokeLinecap="round" />

      {/* rounded cream sofa */}
      <rect x="24" y="44" width="66" height="12" rx="6" fill="#E6E0D4" />
      <rect x="22" y="48" width="11" height="24" rx="6" fill="#E2DBCD" />
      <rect x="82" y="48" width="11" height="24" rx="6" fill="#E2DBCD" />
      <rect x="26" y="52" width="62" height="18" rx="8" fill="url(#scan-sofa)" />
      <rect x="30" y="53" width="56" height="9" rx="4.5" fill="#EDE8DD" />
      <rect x="34" y="47" width="13" height="13" rx="3" fill="#E7C3BE" transform="rotate(-7 40 53)" />
      <rect x="68" y="47" width="13" height="13" rx="3" fill="#A9C4CE" transform="rotate(6 74 53)" />
      <rect x="35" y="70" width="2.6" height="6" fill="#CBAD7C" />
      <rect x="78" y="70" width="2.6" height="6" fill="#CBAD7C" />

      {/* chunky knit throw over the left arm */}
      <path d="M22 50 q-5 9 1 20 q9 3 14 -2 q-7 -7 -4 -18 z" fill="#D9A75B" />
      <path d="M20 56 q6 2 14 0 M20 62 q6 2 13 -1 M21 68 q6 2 12 -1" stroke="#C4923F" strokeWidth="0.9" fill="none" />

      {/* leggy plant in a woven basket */}
      <path d="M95 74 h15 l-2.5 13 h-10 z" fill="#C9A876" />
      <path d="M95.6 78 H109.4 M96.4 83 H108.6" stroke="#B0904F" strokeWidth="1" />
      <path d="M103 74 C93 68 90 56 99 49 C107 55 108 67 103 74 Z" fill="#89A778" />
      <path d="M104 74 C112 66 114 57 107 51 C104 59 103 67 104 74 Z" fill="#7C9A6C" />
      <path d="M103 63 C103 54 103 48 103 42" stroke="#7C9A6C" strokeWidth="1.4" fill="none" />
    </Thumb>
  ),
};

export default function StyleThumb({ style }) {
  return <span className="style-thumb">{THUMBS[style] ?? THUMBS.Modern}</span>;
}
