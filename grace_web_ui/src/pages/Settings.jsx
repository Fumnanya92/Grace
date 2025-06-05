import React, { useState, useEffect } from "react";
import "./SettingsPage.css";

const SettingsPage = () => {
  const [theme, setTheme] = useState("system");
  const [language, setLanguage] = useState("en");

  // Apply the selected theme globally
  const applyTheme = (selectedTheme) => {
    const root = document.documentElement;

    if (selectedTheme === "system") {
      // Use system preference
      const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      root.setAttribute("data-theme", prefersDark ? "dark" : "light");
    } else {
      // Apply light or dark theme
      root.setAttribute("data-theme", selectedTheme);
    }
  };

  const handleThemeChange = (e) => {
    const selected = e.target.value;
    setTheme(selected);
    applyTheme(selected); // Apply the theme
  };

  const handleLanguageChange = (e) => {
    const selected = e.target.value;
    setLanguage(selected);
    // Optional: Add i18n language switcher
  };

  const handleReloadPersona = async () => {
    try {
      const response = await fetch("/prompt", { method: "POST" });
      if (response.ok) {
        alert("Grace's persona has been refreshed!");
      } else {
        alert("Failed to reload persona.");
      }
    } catch (error) {
      alert("An error occurred while reloading persona.");
    }
  };

  const handleLogout = () => {
    // Optional: Add logic to clear localStorage/session and redirect
    alert("Logged out!");
  };

  // Apply the theme on initial load
  useEffect(() => {
    console.log("Applying theme:", theme); // Debug log
    applyTheme(theme);
  }, [theme]);

  return (
    <div className="settings-page-container">
      <h2 className="settings-title">Settings</h2>

      <div className="settings-item">
        <label className="settings-label">Theme</label>
        <select
          className="settings-select"
          value={theme}
          onChange={handleThemeChange}
        >
          <option value="system">System Default</option>
          <option value="light">Light Mode</option>
          <option value="dark">Dark Mode</option>
        </select>
      </div>

      <div className="settings-item">
        <label className="settings-label">Language</label>
        <select
          className="settings-select"
          value={language}
          onChange={handleLanguageChange}
        >
          <option value="en">English</option>
          <option value="fr">Français</option>
          <option value="es">Español</option>
          {/* Add more languages here */}
        </select>
      </div>

      <div className="settings-item">
        <button className="settings-btn refresh-btn" onClick={handleReloadPersona}>
          Reload Grace’s Persona
        </button>
      </div>

      <div className="settings-item">
        <button className="settings-btn logout-btn" onClick={handleLogout}>
          Log Out
        </button>
      </div>

      <div className="settings-item">
        <button
          className="settings-btn reset-theme-btn"
          onClick={() => {
            setTheme("system");
            applyTheme("system");
          }}
        >
          Reset to System Default
        </button>
      </div>
    </div>
  );
};

export default SettingsPage;
