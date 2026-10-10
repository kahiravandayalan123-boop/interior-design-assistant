import { useEffect, useRef, useState } from "react";
import StylePicker from "./StylePicker.jsx";
import Spinner from "./Spinner.jsx";
import Alert from "./Alert.jsx";
import SampleRooms from "./SampleRooms.jsx";
import RoomSizePicker from "./RoomSizePicker.jsx";

export default function UploadStep({ onSubmit, busy }) {
  const [style, setStyle] = useState("Modern");
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [error, setError] = useState("");
  const [roomSize, setRoomSize] = useState("");
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef(null);

  // Release the object URL when it changes or the component unmounts.
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
    onSubmit({ style, file, roomSize });
  }

  return (
    <form className="card" onSubmit={submit}>
      <p className="eyebrow">New Room Design</p>
      <h2>Upload a room photo</h2>
      <p className="card-sub">We'll assess the furniture you already have, the layout and the light — then tell you what to keep and what to change.</p>

      <span className="field" id="room-label">Room photo</span>
      <div
        className={`file-drop${dragActive ? " drag-active" : ""}${previewUrl ? " has-file" : ""}`}
        role="button"
        tabIndex={busy ? -1 : 0}
        aria-labelledby="room-label"
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
          id="room"
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

      <h3>Room size</h3>
      <RoomSizePicker value={roomSize} onChange={setRoomSize} disabled={busy} />

      <h3>Target style</h3>
      <StylePicker value={style} onChange={setStyle} disabled={busy} />

      {error && <Alert tone="notice" onDismiss={() => setError("")}>{error}</Alert>}

      <div className="actions">
        <button className="primary" type="submit" disabled={busy}>
          {busy && <Spinner />}
          {busy ? "Analyzing room…" : "Analyze room"}
        </button>
      </div>
    </form>
  );
}
