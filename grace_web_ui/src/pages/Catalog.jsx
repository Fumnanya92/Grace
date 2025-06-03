import React, { useEffect, useState } from 'react';
import './CatalogPage.css';
import ProductCard from '../components/Catalog/ProductCard';

const CatalogPage = () => {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState(""); // State for the search query
  const [error, setError] = useState(null);

  /** Fetch products based on the query */
  const fetchCatalog = async (searchQuery = "") => {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch('http://localhost:8000/shopify/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: searchQuery }),
      });

      if (!res.ok) {
        throw new Error(`Error: ${res.status}`);
      }

      const data = await res.json();
      setProducts(data.products || []);
    } catch (error) {
      console.error('Error fetching catalog:', error);
      setError("Failed to fetch products. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  /** Handle form submission for search */
  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim()) {
      setError("Please enter a valid search query.");
      return;
    }
    setLoading(true);
    setError(null);

    try {
      const res = await fetch("http://localhost:8000/shopify/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });

      if (!res.ok) {
        throw new Error(`Error: ${res.status}`);
      }

      const data = await res.json();
      setProducts(data.products || []);
    } catch (err) {
      console.error("Error fetching product details:", err);
      setError("Failed to fetch product details. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  /** Fetch all products on initial load */
  useEffect(() => {
    fetchCatalog();
  }, []);

  return (
    <div className="catalog-container">
      <h2>Grace Product Catalog</h2>

      {/* Search Bar */}
      <form onSubmit={handleSearch} className="search-bar">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search for products (e.g., 'red dresses')"
          className="search-input"
        />
        <button type="submit" className="search-button">
          Search
        </button>
      </form>

      {/* Error Message */}
      {error && <p className="error-message">{error}</p>}

      {/* Product Grid */}
      {loading ? (
        <p>Loading catalog...</p>
      ) : products.length === 0 ? (
        <p>No products found.</p>
      ) : (
        <div className="product-grid">
          {products.map((item, index) => (
            <ProductCard key={index} item={item} />
          ))}
        </div>
      )}
    </div>
  );
};

export default CatalogPage;
