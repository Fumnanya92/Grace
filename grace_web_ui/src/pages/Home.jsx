import React, { useEffect, useState } from 'react';
import { Link, NavLink } from 'react-router-dom';
import './HomePage.css';

const HomePage = () => {
  const [stats, setStats] = useState({
    totalChats: 0,
    memoryCount: 0,
    recentRequests: [],
  });

  useEffect(() => {
    // Simulated API call — replace with actual backend
    const fetchStats = async () => {
      try {
        const res = await fetch('http://localhost:8000/dev/stats');
        const data = await res.json();
        setStats(data);
      } catch (err) {
        console.error('Failed to fetch stats:', err);
        // fallback demo data
        setStats({
          totalChats: 48,
          memoryCount: 17,
          recentRequests: ['“Who made this dress?”', '“How much for 6 bloom gowns?”', '“I need a size 12 black set”'],
        });
      }
    };

    fetchStats();
  }, []);

  return (
    <div className="home-page">
      <header className="hero-section">
        <h1>✨ Welcome to Grace</h1>
        <p>Your AI-powered business assistant for sales, support, and strategy — all in one place.</p>
        <div className="cta-buttons">
          <NavLink
            to="/chat"
            className={({ isActive }) => (isActive ? 'nav-item active' : 'nav-item')}
          >
            💬 Chat with Grace
          </NavLink>
          <Link to="/catalog" className="btn-secondary">🛍 Browse Catalog</Link>
          <Link to="/devtools" className="btn-tertiary">🛠 Dev Tools</Link>
        </div>
      </header>

      <section className="stats-section">
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
      </section>

      <section className="recent-section">
        <h4>📝 Recent Interactions</h4>
        <ul>
          {stats.recentRequests.map((req, idx) => (
            <li key={idx}>• {req}</li>
          ))}
        </ul>
      </section>

      <section className="quote-section">
        <blockquote>
          “Grace isn’t just smart — she learns with you.”<br />
          <span className="author">— Team Grace</span>
        </blockquote>
      </section>
    </div>
  );
};

export default HomePage;
