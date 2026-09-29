import { useState } from "react";
import { loadSample } from "../api.js";

// Bundled demo photos (frontend/public/samples) — a fallback in case a live
// upload from disk misbehaves during a presentation.
export const SAMPLES = [
  { src: "/samples/living-room-tv.jpg", name: "living-room-tv.jpg", label: "Living room with TV" },
  { src: "/samples/sunny-living-room.jpg", name: "sunny-living-room.jpg", label: "Sunny living room" },
];

export default function SampleRooms({ onPick, disabled }) {
  const [loading, setLoading] = useState("");
  const [error, setError] = useState("");

  async function pick(sample) {
    setLoading(sample.src);
    setError("");
    try {
      onPick(await loadSample(sample.src, sample.name));
    } catch (e) {
      setError(e.message || "Couldn't load the sample photo.");
    } finally {
      setLoading("");
    }
  }

  return (
    <div className="samples">
      <span className="samples-label">No photo handy? Try a sample:</span>
      {SAMPLES.map((s) => (
        <button
          key={s.src}
          type="button"
          className="sample-btn"
          onClick={() => pick(s)}
          disabled={disabled || !!loading}
        >
          <img src={s.src} alt="" />
          <span>{loading === s.src ? "Loading…" : s.label}</span>
        </button>
      ))}
      {error && <p className="err-inline">{error}</p>}
    </div>
  );
}
