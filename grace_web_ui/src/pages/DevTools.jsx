import React from 'react';
import './DevToolsPage.css';
import PromptPlayground from '../components/DevTools/PromptPlayground'; // Import the PromptPlayground component
import MemoryManager from '../components/DevTools/MemoryManager'; // Import the MemoryManager component
import SpeechLibraryEditor from '../components/DevTools/SpeechLibraryEditor'; // Import the SpeechLibraryEditor component
import PromptTuner from '../components/DevTools/PromptTuner'; // Import the PromptTuner component
import IntentTrainer from '../components/DevTools/IntentTrainer'; // Import the IntentTrainer component
import DevAssistant from '../components/DevTools/DevAssistant'; // Import the DevAssistant component

const DevToolsPage = () => {
  return (
    <div className="devtools-page">
      <h2>Grace Developer Tools</h2>

      <div className="tool-card">
        <h3>🧪 Prompt Playground</h3>
        <p>Test new system prompts and simulate chats to observe behavior.</p>
        <PromptPlayground />
      </div>

      <div className="tool-card">
        <h3>🧠 Memory Viewer</h3>
        <p>See stored memories, delete or inspect how Grace remembers.</p>
        <MemoryManager />
      </div>

      <div className="tool-card">
        <h3>🗣️ Speech Library</h3>
        <p>Edit fallback phrases and custom response triggers.</p>
        <SpeechLibraryEditor />
      </div>

      <div className="tool-card">
        <h3>🧠 Prompt Tuner</h3>
        <p>View and update Grace’s system prompt live.</p>
        <PromptTuner />
      </div>

      <div className="tool-card">
        <h3>🏷️ Intent Trainer</h3>
        <p>Add new phrases and responses to Grace’s training data.</p>
        <IntentTrainer />
      </div>

      <div className="tool-card">
        <h3>⚙️ System Config Loader</h3>
        <p>Reload tone, catalog, and config for Grace.</p>
        <button>Reload</button>
      </div>

      <div className="tool-card">
        <h3>🤖 Dev Assistant</h3>
        <p>Ask Grace’s dev assistant questions about the system, catalog, or configuration.</p>
        <DevAssistant />
      </div>
    </div>
  );
};

export default DevToolsPage;
