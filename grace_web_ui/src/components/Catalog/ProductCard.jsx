// File: src/components/Catalog/ProductCard.jsx

import React from "react";
import "./ProductCard.css";

const ProductCard = ({ item }) => {
  // Use image_url if it exists; otherwise fall back to meta.image.src or show a placeholder
  const imgSrc =
    item.image_url ||
    (item.meta && item.meta.image && item.meta.image.src) ||
    "/default-image.jpg"; // Fallback image

  return (
    <div className="product-card">
      <div className="image-wrapper">
        {imgSrc ? (
          <img src={imgSrc} alt={item.name} className="product-image" />
        ) : (
          <div className="image-placeholder">No Image</div>
        )}
      </div>
      <div className="product-details">
        <h3 className="product-name">{item.name}</h3>
        <p className="product-price">₦{item.price}</p>
        <button className="buy-button">Buy Now</button>
      </div>
    </div>
  );
};

export default ProductCard;
