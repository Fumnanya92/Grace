import React, { useState } from 'react';
import './SettingsPage.css';

const SettingsPage = () => {
  const [theme, setTheme] = useState('system');
  const [language, setLanguage] = useState('en');

  const handleThemeChange = (e) => {
    const selected = e.target.value;
    setTheme(selected);
    // Optional: Add logic to update theme globally
  };

  const handleLanguageChange = (e) => {
    const selected = e.target.value;
    setLanguage(selected);
    // Optional: Add i18n language switcher
  };

  const handleReloadPersona = async () => {
    try {
      const response = await fetch('/prompt', { method: 'POST' });
      if (response.ok) {
        alert("Grace's persona has been refreshed!");
      } else {
        alert('Failed to reload persona.');
      }
    } catch (error) {
      alert('An error occurred while reloading persona.');
    }
  };

  const handleLogout = () => {
    // Optional: Add logic to clear localStorage/session and redirect
    alert('Logged out!');
  };

  return (
    <div className="settings-container">
      <h2>Settings</h2>

      <div className="setting-item">
        <label>Theme:</label>
        <select value={theme} onChange={handleThemeChange}>
          <option value="system">System Default</option>
          <option value="light">Light Mode</option>
          <option value="dark">Dark Mode</option>
        </select>
      </div>

      <div className="setting-item">
        <label>Language:</label>
        <select value={language} onChange={handleLanguageChange}>
          <option value="en">English</option>
          <option value="fr">Français</option>
          <option value="es">Español</option>
          {/* Add more languages here */}
        </select>
      </div>

      <div className="setting-item">
        <button className="refresh-btn" onClick={handleReloadPersona}>
          Reload Grace's Persona
        </button>
      </div>

      <div className="setting-item">
        <button className="logout-btn" onClick={handleLogout}>
          Log Out
        </button>
      </div>
    </div>
  );
};

export default SettingsPage;
