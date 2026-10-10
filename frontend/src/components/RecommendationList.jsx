import { mediaUrl } from "../api.js";
import { onImgError } from "../placeholder.js";
import { ShopLinks } from "./ProductList.jsx";

export default function RecommendationList({ recommendations }) {
  if (!recommendations?.length) return null;
  return (
    <ul className="products">
      {recommendations.map((r) => (
        <li className="product" key={r.product_id}>
          <img src={mediaUrl(r.image)} alt="" onError={onImgError} />
          <div>
            <div className="product-title"><strong>{r.name}</strong></div>
            <div className="meta">{r.category}</div>
            <ShopLinks links={r.shop_links} />
          </div>
          <div className="price">
            ₹{Math.round(r.price).toLocaleString("en-IN")}
            <span>estimate</span>
          </div>
        </li>
      ))}
    </ul>
  );
}
