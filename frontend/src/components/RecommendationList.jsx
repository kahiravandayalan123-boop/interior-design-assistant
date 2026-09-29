import { mediaUrl } from "../api.js";
import { onImgError } from "../placeholder.js";

export default function RecommendationList({ recommendations }) {
  if (!recommendations?.length) return null;
  return (
    <ul className="products">
      {recommendations.map((r) => (
        <li className="product" key={r.product_id}>
          <img src={mediaUrl(r.image)} alt={r.name} loading="lazy" onError={onImgError} />
          <div>
            <div><strong>{r.name}</strong></div>
            <div className="meta">{r.description}</div>
            <a href={r.url} target="_blank" rel="noreferrer">View product →</a>
          </div>
          <div className="price">
            {r.currency === "INR" ? "₹" : r.currency === "USD" ? "$" : ""}
            {r.price.toLocaleString("en-IN")}
          </div>
        </li>
      ))}
    </ul>
  );
}
