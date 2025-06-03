import React, { useState } from 'react';
import './PromptPlayground.css';

const PromptPlayground = () => {
  const [prompt, setPrompt] = useState('');
  const [userMessage, setUserMessage] = useState('');
  const [response, setResponse] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!prompt || !userMessage) return;
    setLoading(true);
    try {
      const res = await fetch('http://localhost:8000/dev/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ system_prompt: prompt, message: userMessage }),
      });
      const data = await res.json();
      setResponse(data.response);
    } catch (err) {
      setResponse('Error talking to Grace.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="prompt-playground">
      <h2>🎯 Prompt Playground</h2>
      <textarea
        placeholder="System prompt..."
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
      ></textarea>
      <input
        type="text"
        placeholder="Try a user message..."
        value={userMessage}
        onChange={(e) => setUserMessage(e.target.value)}
      />
      <button onClick={handleSubmit} disabled={loading}>
        {loading ? 'Thinking...' : 'Test'}
      </button>
      <div className="response-box">
        <strong>Response:</strong>
        <p>{response}</p>
      </div>
    </div>
  );
};

export default PromptPlayground;
