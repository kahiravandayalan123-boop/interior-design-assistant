import { mediaUrl } from "../api.js";
import VerdictList, { VerdictSummary } from "./Verdicts.jsx";

const SIZE_LABEL = { small: "Small room", medium: "Medium room", large: "Large room" };

export default function AnalysisCard({ originalUrl, style, analysis }) {
  const s = analysis.structure || {};
  const fixed = [
    ...(s.windows || []).map((w) => ["Window", w]),
    ...(s.doors || []).map((d) => ["Door", d]),
    ...(s.stairs ? [["Stairs", s.stairs]] : []),
    ...(s.other_fixed || []).map((o) => ["Fixed", o]),
  ];
  return (
    <div className="card">
      <p className="eyebrow">Step 1 · Assessment</p>
      <h2>Here's our read of your room</h2>
      <p className="card-sub">{analysis.summary}</p>

      <div className="grid-2">
        <div>
          <div className="preview">
            {originalUrl && <img src={mediaUrl(originalUrl)} alt="Your room" />}
          </div>
          <div className="facts">
            <span className="fact">
              <strong>{SIZE_LABEL[analysis.size_class] || "Room"}</strong>
              {analysis.size_estimate}
              {analysis.size_from_user ? " · as you told us" : " · estimated from the photo"}
            </span>
            <span className="fact"><strong>Target style</strong>{style}</span>
          </div>
          {fixed.length > 0 && (
            <>
              <h3>Architecture we'll preserve</h3>
              <ul className="fixed-list">
                {fixed.map(([kind, text], i) => (
                  <li key={i}><span>{kind}</span>{text}</li>
                ))}
              </ul>
            </>
          )}
        </div>
        <div>
          <h3 className="h3-first">Your existing furniture</h3>
          <VerdictSummary items={analysis.existing_furniture} />
          <VerdictList items={analysis.existing_furniture} />
          {analysis.layout_notes && (
            <>
              <h3>Layout</h3>
              <p className="muted">{analysis.layout_notes}</p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
