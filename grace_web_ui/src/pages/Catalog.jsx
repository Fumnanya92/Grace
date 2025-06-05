import React, { useEffect, useState } from "react";
import "./CatalogPage.css";
import ProductCard from "../components/Catalog/ProductCard";

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
      const res = await fetch("http://localhost:8000/shopify/catalog", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });

      if (!res.ok) {
        throw new Error(`Error: ${res.status}`);
      }

      const data = await res.json();
      setProducts(data.products || []);
    } catch (error) {
      console.error("Error fetching catalog:", error);
      setError("Failed to fetch products. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  /** Handle form submission for search */
  const handleSearch = (e) => {
    e.preventDefault();
    if (!query.trim()) {
      setError("Please enter a valid search query.");
      return;
    }
    fetchCatalog(query);
  };

  /** Fetch all products on initial load */
  useEffect(() => {
    fetchCatalog();
  }, []);

  return (
    <div className="catalog-page-container">
      <h2 className="catalog-title">Grace Product Catalog</h2>

      {/* Search Bar */}
      <form onSubmit={handleSearch} className="catalog-search-bar">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search for products (e.g., 'red dresses')"
          className="catalog-search-input"
          aria-label="Search for products"
        />
        <button
          type="submit"
          className="catalog-search-button"
          disabled={!query.trim()}
          aria-label="Search"
        >
          Search
        </button>
      </form>

      {/* Error Message */}
      {error && <p className="catalog-error-message">{error}</p>}

      {/* Product Grid */}
      {loading ? (
        <p className="catalog-loading">Loading catalog...</p>
      ) : products.length === 0 ? (
        <p className="catalog-no-results">No products found.</p>
      ) : (
        <div className="catalog-product-grid">
          {products.map((item, index) => (
            <ProductCard key={index} item={item} />
          ))}
        </div>
      )}
    </div>
  );
};

export default CatalogPage;
