import React, { useState } from 'react';
import './IntentTrainer.css';

const IntentTrainer = () => {
  const [phrase, setPhrase] = useState('');
  const [response, setResponse] = useState('');
  const [status, setStatus] = useState('');

  const submitTrainingPair = async () => {
    if (!phrase.trim() || !response.trim()) {
      setStatus('⚠️ Phrase and response are required.');
      return;
    }

    try {
      const res = await fetch('http://localhost:8000/speech-library/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phrase, response }),
      });

      if (res.ok) {
        setStatus('✅ Training data added!');
        setPhrase('');
        setResponse('');
      } else {
        setStatus('❌ Failed to add training data.');
      }
    } catch (err) {
      console.error(err);
      setStatus('❌ Server error.');
    }
  };

  return (
    <div className="intent-trainer">
      <h2>🏷️ Intent Trainer</h2>
      <input
        type="text"
        placeholder="User phrase..."
        value={phrase}
        onChange={(e) => setPhrase(e.target.value)}
      />
      <textarea
        rows={4}
        placeholder="Grace's response..."
        value={response}
        onChange={(e) => setResponse(e.target.value)}
      />
      <button onClick={submitTrainingPair}>➕ Add to Speech Library</button>
      {status && <p className="status">{status}</p>}
    </div>
  );
};

export default IntentTrainer;
