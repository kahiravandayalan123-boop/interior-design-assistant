import { useState } from "react";
import { downloadImage, mediaUrl } from "../api.js";
import ProductList from "./ProductList.jsx";
import RecommendationList from "./RecommendationList.jsx";
import BeforeAfterSlider from "./BeforeAfterSlider.jsx";
import RecapCard from "./RecapCard.jsx";
import Spinner from "./Spinner.jsx";
import VerdictList, { VerdictSummary } from "./Verdicts.jsx";
import { onImgError } from "../placeholder.js";

const CHECK = {
  passed: ["ok", "Architecture check passed", "Windows, doors and walls match your original photo."],
  corrected: ["ok", "Architecture check passed on the second render", "The first render altered the room, so it was redone and re-checked."],
  mismatch: ["warn", "Architecture differs from your photo", ""],
};

export default function ResultView({ result, originalUrl, onRestart }) {
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState("");
  const [view, setView] = useState("slider"); // "slider" | "side"
  const total = result.estimated_total ?? 0;
  const check = CHECK[result.structure_check?.status];
  const plan = result.planned_furniture || [];

  async function handleDownload() {
    setDownloading(true);
    setDownloadError("");
    try {
      const ext = result.generated_image_url.match(/\.(png|jpe?g)(\?|$)/i)?.[1] || "png";
      await downloadImage(
        mediaUrl(result.generated_image_url),
        `redesign-${result.style.toLowerCase()}.${ext}`
      );
    } catch (e) {
      setDownloadError(e.message || "Couldn't download the image.");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <>
      <div className="card">
        <p className="eyebrow">Your redesign</p>
        <h2>Same room, restyled</h2>
        <p className="card-sub">
          The redesign is painted onto your own photo, so the walls, windows and doors stay put.
        </p>

        {result.image_is_mock && (
          <p className="mock-tag">Sample preview — image generation isn't configured on this server.</p>
        )}

        {originalUrl && (
          <div className="view-toggle" role="group" aria-label="Comparison view">
            <button type="button" aria-pressed={view === "slider"} onClick={() => setView("slider")}>
              Slider
            </button>
            <button type="button" aria-pressed={view === "side"} onClick={() => setView("side")}>
              Side by side
            </button>
          </div>
        )}

        {originalUrl && view === "side" ? (
          <div className="compare">
            <figure>
              <img src={mediaUrl(originalUrl)} alt="Your original room" onError={onImgError} />
              <figcaption>Before</figcaption>
            </figure>
            <figure>
              <img src={mediaUrl(result.generated_image_url)} alt="AI redesign" onError={onImgError} />
              <figcaption>After</figcaption>
            </figure>
          </div>
        ) : (
          <>
            <BeforeAfterSlider
              before={originalUrl ? mediaUrl(originalUrl) : ""}
              after={mediaUrl(result.generated_image_url)}
            />
            {originalUrl && <p className="ba-caption">Drag the handle to compare before and after</p>}
          </>
        )}

        {check && (
          <div className={`check check-${check[0]}`}>
            <span className="check-icon" aria-hidden="true">{check[0] === "ok" ? "✓" : "!"}</span>
            <div>
              <strong>{check[1]}</strong>
              <span>
                {check[2] || `${result.structure_check.issues.join(" ")} Use the image as a furniture and styling guide.`}
              </span>
            </div>
          </div>
        )}

        <div className="actions">
          <button className="primary" type="button" onClick={handleDownload} disabled={downloading}>
            {downloading && <Spinner />}
            {downloading ? "Preparing download…" : "Download image"}
          </button>
          <button className="ghost" type="button" onClick={onRestart}>Start over</button>
        </div>
        {downloadError && <p className="err-inline">{downloadError}</p>}
      </div>

      <div className="card">
        <p className="eyebrow">The plan</p>
        <h2>What to keep and what to change</h2>
        <p className="card-sub">
          Each piece judged against your room's size and layout
          {result.analysis?.size_estimate ? ` (${result.analysis.size_estimate})` : ""}.
        </p>
        <VerdictSummary items={plan} />
        <VerdictList items={plan} />

        <h3>Your choices</h3>
        <RecapCard style={result.style} recap={result.recap} />

        <details className="brief">
          <summary>See the brief sent to the image model</summary>
          <div className="promptbox">{result.image_prompt}</div>
        </details>
      </div>

      <div className="card">
        <p className="eyebrow">Shopping list</p>
        <h2>
          {result.product_matches.length
            ? `${result.product_matches.length} piece${result.product_matches.length > 1 ? "s" : ""} to buy · about ₹${total.toLocaleString("en-IN")}`
            : "Nothing to buy"}
        </h2>
        <p className="card-sub">
          Only the pieces the plan replaces or adds. Links open live searches on real stores; prices are estimates.
        </p>
        {result.product_matches_note && <p className="mock-tag">{result.product_matches_note}</p>}
        <ProductList matches={result.product_matches} />

        {result.recommendations?.length > 0 && (
          <>
            <h3>Optional extras within your remaining budget</h3>
            <RecommendationList recommendations={result.recommendations} />
          </>
        )}
      </div>
    </>
  );
}
