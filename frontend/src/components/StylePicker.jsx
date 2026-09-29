import StyleThumb from "./StyleThumb.jsx";

const STYLES = ["Modern", "Minimalist", "Traditional", "Scandinavian"];

export default function StylePicker({ value, onChange, disabled }) {
  return (
    <div className="styles">
      {STYLES.map((s) => (
        <button
          key={s}
          type="button"
          className="style-btn"
          aria-pressed={value === s}
          disabled={disabled}
          onClick={() => onChange(s)}
        >
          <StyleThumb style={s} />
          <span className="style-name">{s}</span>
        </button>
      ))}
    </div>
  );
}
