import { useCallback, useRef, useState } from "react";
import { onImgError } from "../placeholder.js";

// Draggable before/after comparison. The "after" image sits underneath; the
// "before" image is layered on top and clipped horizontally by the divider.
export default function BeforeAfterSlider({
  before,
  after,
  beforeLabel = "Before",
  afterLabel = "After",
}) {
  const ref = useRef(null);
  const dragging = useRef(false);
  const [pos, setPos] = useState(50); // percent revealed of the "before" image

  const setFromClientX = useCallback((clientX) => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const pct = ((clientX - rect.left) / rect.width) * 100;
    setPos(Math.max(0, Math.min(100, pct)));
  }, []);

  function onPointerDown(e) {
    dragging.current = true;
    e.currentTarget.setPointerCapture?.(e.pointerId);
    setFromClientX(e.clientX);
  }
  function onPointerMove(e) {
    if (dragging.current) setFromClientX(e.clientX);
  }
  function stop(e) {
    dragging.current = false;
    e.currentTarget.releasePointerCapture?.(e.pointerId);
  }
  function onKeyDown(e) {
    if (e.key === "ArrowLeft") setPos((p) => Math.max(0, p - 4));
    else if (e.key === "ArrowRight") setPos((p) => Math.min(100, p + 4));
    else if (e.key === "Home") setPos(0);
    else if (e.key === "End") setPos(100);
    else return;
    e.preventDefault();
  }

  // No original to compare against — just show the redesign.
  if (!before) {
    return (
      <div className="ba">
        <img className="ba-img" src={after} alt={afterLabel} draggable="false" onError={onImgError} />
      </div>
    );
  }

  return (
    <div
      className="ba"
      ref={ref}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={stop}
      onPointerCancel={stop}
    >
      <img className="ba-img" src={after} alt={afterLabel} draggable="false" onError={onImgError} />
      <img
        className="ba-img ba-before"
        src={before}
        alt={beforeLabel}
        draggable="false"
        onError={onImgError}
        style={{ clipPath: `inset(0 ${100 - pos}% 0 0)` }}
      />
      <span className="ba-tag ba-tag-before" style={{ opacity: pos > 12 ? 1 : 0 }}>
        {beforeLabel}
      </span>
      <span className="ba-tag ba-tag-after" style={{ opacity: pos < 88 ? 1 : 0 }}>
        {afterLabel}
      </span>
      <div
        className="ba-divider"
        style={{ left: `${pos}%` }}
        role="slider"
        aria-label="Reveal amount of the redesigned image"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(pos)}
        tabIndex={0}
        onKeyDown={onKeyDown}
      >
        <span className="ba-knob" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 7 4 12l5 5M15 7l5 5-5 5" />
          </svg>
        </span>
      </div>
    </div>
  );
}
