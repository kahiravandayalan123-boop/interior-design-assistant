import { mediaUrl } from "../api.js";
import { onImgError } from "../placeholder.js";
import { VerdictBadge } from "./Verdicts.jsx";

const rupees = (n) => `₹${Math.round(n || 0).toLocaleString("en-IN")}`;

// Every piece links to live searches on real retailers. The catalogue price
// is an estimate, so it's labelled as one.
export function ShopLinks({ links }) {
  if (!links?.length) return null;
  return (
    <div className="shop-links">
      <span>Shop similar:</span>
      {links.map((l) => (
        <a key={l.retailer} href={l.url} target="_blank" rel="noopener noreferrer">
          {l.retailer} ↗
        </a>
      ))}
    </div>
  );
}

export default function ProductList({ matches }) {
  if (!matches?.length) {
    return <p className="muted">Nothing to buy — this plan works with what you already have.</p>;
  }
  return (
    <ul className="products">
      {matches.map((m) => (
        <li className="product" key={m.product_id + m.item}>
          <img src={mediaUrl(m.image)} alt="" onError={onImgError} />
          <div>
            <div className="product-title">
              <VerdictBadge action={m.action} />
              <strong>{m.item}</strong>
            </div>
            <div className="meta">Similar to: {m.title}</div>
            <ShopLinks links={m.shop_links} />
          </div>
          <div className="price">
            {rupees(m.price)}
            <span>estimate</span>
          </div>
        </li>
      ))}
    </ul>
  );
}
