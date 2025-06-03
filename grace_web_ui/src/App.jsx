// src/App.jsx
import React from 'react';
import { BrowserRouter as Router, Routes, Route, NavLink } from 'react-router-dom';
import HomePage from './pages/Home';
import ChatPage from './pages/ChatPage';
import CatalogPage from './pages/Catalog';
import SettingsPage from './pages/Settings';
import DevToolsPage from './pages/DevTools'; // Import the DevToolsPage component
import DevMemoryManager from './components/DevTools/DevMemoryManager'; // Import the DevMemoryManager component
import './App.css';

const App = () => {
  return (
    <Router>
      <div className="app-container">
        <nav className="sidebar">
          <h2 className="sidebar-title">Grace</h2>
          <NavLink to="/" end className="nav-item" activeClassName="active">Home</NavLink>
          <NavLink to="/chat" className="nav-item" activeClassName="active">Chat</NavLink>
          <NavLink to="/catalog" className="nav-item" activeClassName="active">Catalog</NavLink>
          <NavLink to="/settings" className="nav-item" activeClassName="active">Settings</NavLink>
          <NavLink to="/devtools" className="nav-item" activeClassName="active">Dev Tools</NavLink>
          <NavLink to="/dev-memory-manager" className="nav-item" activeClassName="active">Dev Memory Manager</NavLink> {/* Added Dev Memory Manager */}
        </nav>

        <main className="main-content">
          <h1>Hello, Grace!</h1>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/catalog" element={<CatalogPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/devtools" element={<DevToolsPage />} />
            <Route path="/dev-memory-manager" element={<DevMemoryManager />} /> {/* Added Route for DevMemoryManager */}
          </Routes>
        </main>
      </div>
    </Router>
  );
};

export default App;
