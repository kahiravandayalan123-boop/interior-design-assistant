import { useState } from "react";
import { downloadImage, mediaUrl } from "../api.js";
import ProductList from "./ProductList.jsx";
import RecommendationList from "./RecommendationList.jsx";
import BeforeAfterSlider from "./BeforeAfterSlider.jsx";
import RecapCard from "./RecapCard.jsx";
import Spinner from "./Spinner.jsx";
import { onImgError } from "../placeholder.js";

export default function ResultView({ result, originalUrl, onRestart }) {
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState("");
  const [view, setView] = useState("side"); // "side" | "slider"
  const total =
    result.estimated_total ??
    result.product_matches.reduce((s, m) => s + (m.price || 0), 0);

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
    <div className="card">
      <h2>Your redesign</h2>
      <p className="card-sub">Your original room next to the AI redesign.</p>

      {result.image_is_mock && (
        <p className="mock-tag">
          Sample preview — add a real <code>OPENAI_API_KEY</code> to backend/.env and
          regenerate for an actual AI-rendered room.
        </p>
      )}

      {originalUrl && (
        <div className="view-toggle" role="group" aria-label="Comparison view">
          <button type="button" aria-pressed={view === "side"} onClick={() => setView("side")}>
            Side by side
          </button>
          <button type="button" aria-pressed={view === "slider"} onClick={() => setView("slider")}>
            Slider
          </button>
        </div>
      )}

      {originalUrl && view === "side" ? (
        <div className="compare">
          <figure>
            <span className="img-label">Before</span>
            <img src={mediaUrl(originalUrl)} alt="Your original room" onError={onImgError} />
          </figure>
          <figure>
            <span className="img-label">After</span>
            <img src={mediaUrl(result.generated_image_url)} alt="AI redesign" onError={onImgError} />
          </figure>
        </div>
      ) : (
        <>
          <BeforeAfterSlider
            before={originalUrl ? mediaUrl(originalUrl) : ""}
            after={mediaUrl(result.generated_image_url)}
          />
          {originalUrl && <p className="ba-caption">Drag · or focus the handle and use ← →</p>}
        </>
      )}

      <div className="actions">
        <button className="primary" type="button" onClick={handleDownload} disabled={downloading}>
          {downloading && <Spinner />}
          {downloading ? "Preparing download…" : "Download image"}
        </button>
      </div>
      {downloadError && <p className="err-inline">{downloadError}</p>}

      <h3>Your choices</h3>
      <RecapCard style={result.style} recap={result.recap} />

      <h3>Image prompt</h3>
      <div className="promptbox">{result.image_prompt}</div>

      <h3>
        Shopping list ({result.product_matches.length} items · ~₹
        {total.toLocaleString("en-IN")})
      </h3>
      {result.product_matches_note && (
        <p className="mock-tag">{result.product_matches_note}</p>
      )}
      <ProductList matches={result.product_matches} />

      {result.recommendations?.length > 0 && (
        <>
          <h3>
            Recommended for you ({result.recommendations.length} items · ~₹
            {(result.recommendations_total ?? 0).toLocaleString("en-IN")})
          </h3>
          <p className="card-sub">
            More pieces from our catalogue, matched to your redesign by similarity.
          </p>
          {result.recommendations_note && (
            <p className="mock-tag">{result.recommendations_note}</p>
          )}
          <RecommendationList recommendations={result.recommendations} />
        </>
      )}

      <div className="actions">
        <button className="ghost" onClick={onRestart}>Start over</button>
      </div>
    </div>
  );
}
