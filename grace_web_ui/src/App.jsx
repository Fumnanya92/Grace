import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, NavLink } from 'react-router-dom';

import HomePage from './pages/Home';
import ChatPage from './pages/ChatPage';
import CatalogPage from './pages/Catalog';
import SettingsPage from './pages/Settings';
import DevToolsPage from './pages/DevTools';
import DevMemoryManager from './components/DevTools/DevMemoryManager';

import './App.css';

const App = () => {
  // track whether sidebar is visible
  const [sidebarVisible, setSidebarVisible] = useState(true);

  const toggleSidebar = () => {
    setSidebarVisible((prev) => !prev);
  };

  return (
    <Router>
      <div className="app-container">
        {/* Sidebar: add 'collapsed' when sidebarVisible is false */}
        <nav className={`sidebar ${sidebarVisible ? '' : 'collapsed'}`}>
          <h2 className="sidebar-title">Grace</h2>
          <NavLink
            to="/"
            end
            className={({ isActive }) => (isActive ? 'nav-item active' : 'nav-item')}
          >
            Home
          </NavLink>
          <NavLink
            to="/chat"
            className={({ isActive }) => (isActive ? 'nav-item active' : 'nav-item')}
          >
            Chat
          </NavLink>
          <NavLink
            to="/catalog"
            className={({ isActive }) => (isActive ? 'nav-item active' : 'nav-item')}
          >
            Catalog
          </NavLink>
          <NavLink
            to="/settings"
            className={({ isActive }) => (isActive ? 'nav-item active' : 'nav-item')}
          >
            Settings
          </NavLink>
          <NavLink
            to="/devtools"
            className={({ isActive }) => (isActive ? 'nav-item active' : 'nav-item')}
          >
            Dev Tools
          </NavLink>
          <NavLink
            to="/dev-memory-manager"
            className={({ isActive }) => (isActive ? 'nav-item active' : 'nav-item')}
          >
            Dev Memory Manager
          </NavLink>
        </nav>

        <main className="main-content">
          {/* Toggle button—click to retract/expand sidebar */}
          <button
            className="sidebar-toggle"
            onClick={toggleSidebar}
            aria-label="Toggle sidebar"
          >
            {sidebarVisible ? '«' : '»'}
          </button>

          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/catalog" element={<CatalogPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/devtools" element={<DevToolsPage />} />
            <Route path="/dev-memory-manager" element={<DevMemoryManager />} />
            <Route
              path="*"
              element={
                <div className="not-found">
                  <h2>Page Not Found</h2>
                  <p>Looks like you took a wrong turn. 🧭</p>
                </div>
              }
            />
          </Routes>
        </main>
      </div>
    </Router>
  );
};

export default App;
