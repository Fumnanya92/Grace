import React, { useState } from "react";
import "./DevToolsPage.css";
import PromptPlayground from "../components/DevTools/PromptPlayground";
import MemoryManager from "../components/DevTools/MemoryManager";
import SpeechLibraryEditor from "../components/DevTools/SpeechLibraryEditor";
import PromptTuner from "../components/DevTools/PromptTuner";
import IntentTrainer from "../components/DevTools/IntentTrainer";
import DevAssistant from "../components/DevTools/DevAssistant";

const DevToolsPage = () => {
  const tabs = [
    { id: "prompt", label: "🧪 Prompt Playground" },
    { id: "memory", label: "🧠 Memory Viewer" },
    { id: "speech", label: "🗣️ Speech Library" },
    { id: "tuner", label: "🧠 Prompt Tuner" },
    { id: "intent", label: "🏷️ Intent Trainer" },
    { id: "config", label: "⚙️ System Config" },
    { id: "devAssistant", label: "🤖 Dev Assistant" },
  ];

  const [activeTab, setActiveTab] = useState("prompt");

  return (
    <div className="devtools-page">
      <h2 className="devtools-title">Grace Developer Tools</h2>

      {/* Tab Bar */}
      <div className="devtools-tab-bar">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={`devtools-tab-button ${
              activeTab === tab.id ? "active" : ""
            }`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="devtools-tab-content">
        {activeTab === "prompt" && (
          <div className="tool-card">
            <h3>🧪 Prompt Playground</h3>
            <p>Test new system prompts and simulate chats to observe behavior.</p>
            <PromptPlayground />
          </div>
        )}

        {activeTab === "memory" && (
          <div className="tool-card">
            <h3>🧠 Memory Viewer</h3>
            <p>See stored memories, delete or inspect how Grace remembers.</p>
            <MemoryManager />
          </div>
        )}

        {activeTab === "speech" && (
          <div className="tool-card">
            <h3>🗣️ Speech Library</h3>
            <p>Edit fallback phrases and custom response triggers.</p>
            <SpeechLibraryEditor />
          </div>
        )}

        {activeTab === "tuner" && (
          <div className="tool-card">
            <h3>🧠 Prompt Tuner</h3>
            <p>View and update Grace’s system prompt live.</p>
            <PromptTuner />
          </div>
        )}

        {activeTab === "intent" && (
          <div className="tool-card">
            <h3>🏷️ Intent Trainer</h3>
            <p>Add new phrases and responses to Grace’s training data.</p>
            <IntentTrainer />
          </div>
        )}

        {activeTab === "config" && (
          <div className="tool-card">
            <h3>⚙️ System Config Loader</h3>
            <p>Reload tone, catalog, and config for Grace.</p>
            <button className="reload-button" onClick={() => window.location.reload()}>
              Reload
            </button>
          </div>
        )}

        {activeTab === "devAssistant" && (
          <div className="tool-card">
            <h3>🤖 Dev Assistant</h3>
            <p>
              Ask Grace’s dev assistant questions about the system, catalog, or
              configuration.
            </p>
            <DevAssistant />
          </div>
        )}
      </div>
    </div>
  );
};

export default DevToolsPage;
