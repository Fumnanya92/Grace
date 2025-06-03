import React, { useEffect, useState } from 'react';
import './PromptTuner.css';

const PromptTuner = () => {
  const [prompt, setPrompt] = useState('');
  const [status, setStatus] = useState('');

  const fetchPrompt = async () => {
    try {
      const response = await fetch('http://localhost:8000/prompt');
      const data = await response.json();
      console.log(data.prompt);
    } catch (error) {
      console.error('Error fetching prompt:', error);
    }
  };

  const updatePrompt = async () => {
    try {
      await fetch('http://localhost:8000/prompt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt }),
      });
      setStatus('✅ Prompt updated successfully!');
    } catch (err) {
      console.error('Failed to update prompt:', err);
      setStatus('❌ Failed to update');
    }
  };

  useEffect(() => {
    fetchPrompt();
  }, []);

  return (
    <div className="prompt-tuner">
      <h2>🧠 Prompt Tuner</h2>
      <textarea
        rows={16}
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
      />
      <button onClick={updatePrompt}>💾 Save and Reload</button>
      {status && <p className="status">{status}</p>}
    </div>
  );
};

export default PromptTuner;
