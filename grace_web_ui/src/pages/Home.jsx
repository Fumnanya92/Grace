import React, { useEffect, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import "./HomePage.css";

const HomePage = () => {
  const [stats, setStats] = useState({
    totalChats: 0,
    memoryCount: 0,
    recentRequests: [],
  });

  useEffect(() => {
    // Replace with real API call when ready
    const fetchStats = async () => {
      try {
        const res = await fetch("http://localhost:8000/dev/stats");
        const data = await res.json();
        setStats(data);
      } catch (err) {
        console.error("Failed to fetch stats:", err);
        // fallback demo data
        setStats({
          totalChats: 48,
          memoryCount: 17,
          recentRequests: [
            "“Who made this dress?”",
            "“How much for 6 bloom gowns?”",
            "“I need a size 12 black set”",
          ],
        });
      }
    };
    fetchStats();
  }, []);

  return (
    <div className="home-page">
      {/* — Top Navigation Bar — */}
      <nav className="top-nav">
        <div className="nav-logo">✨ Grace</div>
        <div className="nav-links">
          <NavLink
            to="/chat"
            className={({ isActive }) =>
              isActive ? "nav-link active" : "nav-link"
            }
          >
            Chat
          </NavLink>
          <NavLink
            to="/catalog"
            className={({ isActive }) =>
              isActive ? "nav-link active" : "nav-link"
            }
          >
            Catalog
          </NavLink>
          <NavLink
            to="/devtools"
            className={({ isActive }) =>
              isActive ? "nav-link active" : "nav-link"
            }
          >
            Dev Tools
          </NavLink>
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              isActive ? "nav-link active" : "nav-link"
            }
          >
            Settings
          </NavLink>
        </div>
      </nav>

      {/* — Hero Section — */}
      <header className="hero-section">
        <h1 className="hero-title">✨ Welcome to Grace</h1>
        <p className="hero-subtitle">
          Your AI-powered business assistant for sales, support, and strategy — all
          in one place.
        </p>
        <div className="cta-buttons">
          <NavLink
            to="/chat"
            className={({ isActive }) =>
              isActive ? "btn btn-primary active" : "btn btn-primary"
            }
          >
            💬 Chat with Grace
          </NavLink>
          <Link to="/catalog" className="btn btn-secondary">
            🛍 Browse Catalog
          </Link>
          <Link to="/devtools" className="btn btn-tertiary">
            🛠 Dev Tools
          </Link>
        </div>
      </header>

      {/* — Stats & Recent Interactions Side by Side — */}
      <section className="info-section">
        {/* Stats Column */}
        <div className="stats-column fade-in-delay-1">
          <h2 className="section-title">Your Key Metrics</h2>
          <div className="stats-grid">
            <div className="stat-box">
              <h3>{stats.totalChats}</h3>
              <p>Total Conversations</p>
            </div>
            <div className="stat-box">
              <h3>{stats.memoryCount}</h3>
              <p>Memory Entries</p>
            </div>
            <div className="stat-box">
              <h3>{stats.recentRequests.length}</h3>
              <p>Recent Requests</p>
            </div>
          </div>
        </div>

        {/* Recent Column */}
        <div className="recent-column fade-in-delay-2">
          <h2 className="section-title">📝 Recent Interactions</h2>
          <ul className="recent-list">
            {stats.recentRequests.map((req, idx) => (
              <li key={idx}>• {req}</li>
            ))}
          </ul>
        </div>
      </section>

      {/* — Quote Section — */}
      <section className="quote-wrapper fade-in-delay-3">
        <div className="quote-card">
          <blockquote>
            “Grace isn’t just smart — she learns with you.”
          </blockquote>
          <span className="author">— Team Grace</span>
        </div>
      </section>
    </div>
  );
};

export default HomePage;
