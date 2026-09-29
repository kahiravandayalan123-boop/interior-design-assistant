import { mediaUrl } from "../api.js";

export default function AnalysisCard({ originalUrl, style, analysis }) {
  return (
    <div className="card">
      <h2>What we detected</h2>
      <p className="card-sub">
        Your photo · target style: <strong>{style}</strong>
      </p>
      <div className="grid-2">
        <div className="preview">
          <span className="img-label">Your room</span>
          {originalUrl && <img src={mediaUrl(originalUrl)} alt="Original room" />}
        </div>
        <div>
          <p className="analysis-summary">{analysis.summary}</p>
          <h3>Existing furniture</h3>
          <ul className="analysis">
            {analysis.existing_furniture.map((f, i) => (
              <li key={i}>
                {f.name}{" "}
                <span className="muted">
                  ({f.category}{f.color ? `, ${f.color}` : ""})
                </span>
              </li>
            ))}
          </ul>
          {analysis.layout_notes && (
            <>
              <h3>Layout</h3>
              <p className="muted">{analysis.layout_notes}</p>
            </>
          )}
          {analysis.lighting && (
            <>
              <h3>Lighting</h3>
              <p className="muted">{analysis.lighting}</p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
