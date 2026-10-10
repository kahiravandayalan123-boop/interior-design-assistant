// Optional room size. A photo can't be measured, so letting the user say
// "this is a 100 sq ft room" is what keeps the recommendations realistic.
const SIZES = [
  { value: "", label: "Not sure", sub: "estimate from the photo" },
  { value: "small", label: "Small", sub: "about 100 sq ft" },
  { value: "medium", label: "Medium", sub: "150–200 sq ft" },
  { value: "large", label: "Large", sub: "250 sq ft or more" },
];

export default function RoomSizePicker({ value, onChange, disabled }) {
  return (
    <div className="seg" role="group" aria-label="Room size">
      {SIZES.map((s) => (
        <button
          key={s.value || "auto"}
          type="button"
          className="seg-btn"
          aria-pressed={value === s.value}
          disabled={disabled}
          onClick={() => onChange(s.value)}
        >
          <strong>{s.label}</strong>
          <span>{s.sub}</span>
        </button>
      ))}
    </div>
  );
}
