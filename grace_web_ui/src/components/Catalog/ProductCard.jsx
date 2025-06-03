import React from 'react';
import './ProductCard.css'; // Optional: Add custom styles for ProductCard

const ProductCard = ({ item }) => (
  <div className="product-card">
    <img src={item.image_url} alt={item.name} />
    <h3>{item.name}</h3>
    <p className="price">₦{item.price}</p>
    <button className="buy-button">Buy Now</button>
  </div>
);

export default ProductCard;