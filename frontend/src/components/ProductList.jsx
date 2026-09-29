import { mediaUrl } from "../api.js";
import { onImgError } from "../placeholder.js";

export default function ProductList({ matches }) {
  if (!matches?.length) return <p className="muted">No catalogue matches found.</p>;
  return (
    <ul className="products">
      {matches.map((m) => (
        <li className="product" key={m.product_id + m.item}>
          <img src={mediaUrl(m.image)} alt={m.title} loading="lazy" onError={onImgError} />
          <div>
            <div><strong>{m.title}</strong></div>
            <div className="meta">
              for “{m.item}” · {m.brand} · {m.retailer}
              {m.style_tags?.length ? ` · ${m.style_tags.join("/")}` : ""}
            </div>
            <a href={m.url} target="_blank" rel="noreferrer">View product →</a>
          </div>
          <div className="price">
            {m.currency === "INR" ? "₹" : m.currency === "USD" ? "$" : ""}
            {m.price.toLocaleString("en-IN")}
          </div>
        </li>
      ))}
    </ul>
  );
}
