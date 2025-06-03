// File: src/components/DevTools/DevAssistant.jsx

import React, { useState } from 'react';
import axios from 'axios';
import './DevAssistant.css'; // Import the CSS file
import useSpeechRecognition from '../../hooks/useSpeechRecognition'; // Import the hook
import "../../styles/common.css"; // Corrected import path for common styles

const DevAssistant = () => {
  const [query, setQuery] = useState('');
  const [contextType, setContextType] = useState('none');
  const [promptOverride, setPromptOverride] = useState('');
  const [model, setModel] = useState('gpt-4o');
  const [result, setResult] = useState('');
  const [loading, setLoading] = useState(false);
  const { listening, toggle } = useSpeechRecognition({
    onResult: (text) => setQuery(text), // Update the query with the recognized speech
    lang: 'en-US',
  });

  // Handles the form submission
  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setResult('');

    try {
      const response = await axios.post('http://localhost:8000/dev/chat', {
        query,
        context_type: contextType,
        model,
        prompt_override: promptOverride || null,
      });

      const { result: responseResult, error } = response.data;

      if (responseResult) {
        setResult(responseResult);
      } else if (error) {
        setResult(`❌ Error: ${error}`);
      }
    } catch (error) {
      setResult(`❌ Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Renders the form field
  const renderFormField = (label, value, onChange, options = null, isTextarea = false) => {
    return (
      <div className="form-field">
        <label className="block text-sm font-medium">{label}</label>
        {isTextarea ? (
          <textarea
            rows={isTextarea === 'small' ? 2 : 3}
            value={value}
            onChange={onChange}
            className="dev-assistant-textarea"
            placeholder={label}
          />
        ) : (
          <select value={value} onChange={onChange} className="dev-assistant-select">
            {options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        )}
      </div>
    );
  };

  return (
    <div className="dev-assistant-container">
      <h2 className="dev-assistant-header">🧠 Grace Dev Assistant</h2>
      <form onSubmit={handleSubmit} className="dev-assistant-form">
        {renderFormField(
          'What do you want to ask the dev assistant?',
          query,
          (e) => setQuery(e.target.value),
          null,
          true
        )}
        <div className="flex flex-wrap gap-4">
          {renderFormField(
            'Context Type',
            contextType,
            (e) => setContextType(e.target.value),
            [
              { value: 'none', label: 'None' },
              { value: 'catalog', label: 'Catalog' },
              { value: 'config', label: 'Config' },
              { value: 'tone', label: 'Tone' },
              { value: 'chatlog', label: 'Chat Log' },
            ]
          )}
          {renderFormField(
            'Model',
            model,
            (e) => setModel(e.target.value),
            [
              { value: 'gpt-4o', label: 'gpt-4o' },
              { value: 'gpt-4', label: 'gpt-4' },
              { value: 'gpt-3.5-turbo', label: 'gpt-3.5-turbo' },
            ]
          )}
        </div>
        {renderFormField(
          'Prompt Override (optional)',
          promptOverride,
          (e) => setPromptOverride(e.target.value),
          null,
          'small'
        )}
        <button
          type="submit"
          disabled={loading}
          className="dev-assistant-button"
        >
          {loading ? 'Thinking...' : 'Ask Grace Dev Assistant'}
        </button>
      </form>
      <button onClick={toggle} className="dev-assistant-voice-button">
        {listening ? 'Stop Listening' : 'Start Listening'}
      </button>
      {result && (
        <div className="dev-assistant-response">
          <strong>Response:</strong>
          <p>{result}</p>
        </div>
      )}
    </div>
  );
};

export default DevAssistant;