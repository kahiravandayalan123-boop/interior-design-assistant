import { useEffect, useRef, useState } from "react";
import Spinner from "./Spinner.jsx";
import Alert from "./Alert.jsx";
import SampleRooms from "./SampleRooms.jsx";

const BUDGETS = ["₹10,000", "₹20,000", "₹30,000"];

// One-click example instructions for the demo — one general, one specific.
const EXAMPLE_INSTRUCTIONS = [
  "Make it feel warmer and cosier — softer lighting, more plants and textured textiles",
  "Replace the sofa with a deep green velvet one and add a reading lamp beside it",
];

// "Modify Existing Room" flow: one form — photo, free-text instruction,
// budget — then straight to the redesign (no separate Q&A step).
export default function ModifyStep({ onSubmit, onBack, busy }) {
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [instruction, setInstruction] = useState("");
  const [budget, setBudget] = useState("");
  const [error, setError] = useState("");
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    return () => { if (previewUrl) URL.revokeObjectURL(previewUrl); };
  }, [previewUrl]);

  function acceptFile(f) {
    if (!f) return;
    if (!f.type.startsWith("image/")) {
      setError("That file isn't an image. Choose a JPEG, PNG, or WebP photo.");
      return;
    }
    setError("");
    setFile(f);
    setPreviewUrl((old) => {
      if (old) URL.revokeObjectURL(old);
      return URL.createObjectURL(f);
    });
  }

  function pickFile(e) {
    acceptFile(e.target.files?.[0] || null);
  }

  function openBrowse() {
    if (!busy) inputRef.current?.click();
  }

  function onDragOver(e) {
    e.preventDefault();
    if (!busy) setDragActive(true);
  }
  function onDragLeave(e) {
    e.preventDefault();
    setDragActive(false);
  }
  function onDrop(e) {
    e.preventDefault();
    setDragActive(false);
    if (busy) return;
    acceptFile(e.dataTransfer.files?.[0] || null);
  }

  function submit(e) {
    e.preventDefault();
    setError("");
    if (!file) return setError("Choose a room photo first.");
    if (!instruction.trim()) return setError("Describe the change you'd like — general or specific.");
    if (!budget) return setError("Pick a budget for this refresh.");
    onSubmit({ file, instruction: instruction.trim(), budget });
  }

  return (
    <form className="card" onSubmit={submit}>
      <h2>Modify your room</h2>
      <p className="card-sub">
        Upload a photo of your furnished room and tell us what to change —
        as general as “make it more appealing” or as specific as “move the
        table near the window to be near the bed instead.”
      </p>

      <span className="field" id="modify-room-label">Room photo</span>
      <div
        className={`file-drop${dragActive ? " drag-active" : ""}${previewUrl ? " has-file" : ""}`}
        role="button"
        tabIndex={busy ? -1 : 0}
        aria-labelledby="modify-room-label"
        onClick={openBrowse}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openBrowse(); }
        }}
        onDragOver={onDragOver}
        onDragEnter={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
      >
        <input
          ref={inputRef}
          id="modify-room"
          type="file"
          accept="image/png,image/jpeg,image/webp"
          onChange={pickFile}
          disabled={busy}
          hidden
        />
        {previewUrl ? (
          <div className="file-preview">
            <img src={previewUrl} alt="Selected room" />
            <div className="file-preview-meta">
              <strong>{file?.name}</strong>
              <span className="muted">Click or drop another image to replace</span>
            </div>
          </div>
        ) : (
          <div className="file-drop-cta">
            <span className="file-drop-icon" aria-hidden="true">
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 16V4M6 10l6-6 6 6" />
                <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
              </svg>
            </span>
            <p className="file-drop-title">Drag &amp; drop a room photo</p>
            <p className="file-hint">or click to browse · JPEG, PNG, WebP · up to 10&nbsp;MB</p>
          </div>
        )}
      </div>
      <SampleRooms onPick={acceptFile} disabled={busy} />

      <h3>What should change?</h3>
      <textarea
        className="instruction-input"
        value={instruction}
        disabled={busy}
        onChange={(e) => setInstruction(e.target.value)}
        placeholder='e.g. "make it appealing" or "move the table near the window to be near the bed instead"'
        rows={4}
        maxLength={600}
      />
      <div className="opts examples">
        <span className="samples-label">Examples:</span>
        {EXAMPLE_INSTRUCTIONS.map((ex) => (
          <button key={ex} type="button" className="chip chip-sm" disabled={busy} onClick={() => setInstruction(ex)}>
            {ex}
          </button>
        ))}
      </div>

      <h3>Budget for this refresh</h3>
      <div className="opts">
        {BUDGETS.map((b) => (
          <button
            key={b}
            type="button"
            className="chip"
            aria-pressed={budget === b}
            disabled={busy}
            onClick={() => setBudget((cur) => (cur === b ? "" : b))}
          >
            {b}
          </button>
        ))}
      </div>

      {error && <Alert tone="notice" onDismiss={() => setError("")}>{error}</Alert>}

      <div className="actions">
        <button className="primary" type="submit" disabled={busy}>
          {busy && <Spinner />}
          {busy ? "Working…" : "Generate redesign"}
        </button>
        <button className="ghost" type="button" onClick={onBack} disabled={busy}>
          Back
        </button>
      </div>
    </form>
  );
}
