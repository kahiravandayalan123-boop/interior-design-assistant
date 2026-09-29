// Styled inline alert. tone: "error" (something failed) or "notice" (needs attention).
export default function Alert({ tone = "error", title, children, onDismiss }) {
  const isError = tone === "error";
  return (
    <div className={`alert ${isError ? "alert-error" : "alert-notice"}`} role="alert">
      <span className="alert-icon" aria-hidden="true">{isError ? "⚠" : "ℹ"}</span>
      <div className="alert-body">
        {title && <div className="alert-title">{title}</div>}
        <div>{children}</div>
      </div>
      {onDismiss && (
        <button type="button" className="alert-dismiss" aria-label="Dismiss" onClick={onDismiss}>
          ×
        </button>
      )}
    </div>
  );
}
