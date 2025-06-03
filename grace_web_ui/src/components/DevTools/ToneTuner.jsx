import React, { useEffect, useState } from 'react';
import './ToneTuner.css';

const toneOptions = ['professional', 'warm', 'humorous'];

const ToneTuner = () => {
  const [currentTone, setCurrentTone] = useState('');
  const [status, setStatus] = useState('');

  useEffect(() => {
    fetch('http://localhost:8000/tone')
      .then(res => res.json())
      .then(data => {
        setCurrentTone(data?.tone || '');
      });
  }, []);

  const handleToneChange = async (newTone) => {
    const res = await fetch('http://localhost:8000/tone', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tone: newTone }),
    });

    if (res.ok) {
      setCurrentTone(newTone);
      setStatus(`✅ Tone set to ${newTone}`);
    } else {
      setStatus('❌ Failed to set tone');
    }

    setTimeout(() => setStatus(''), 3000);
  };

  return (
    <div className="tone-tuner">
      <h2>🎙️ Grace Tone Tuner</h2>
      <p>Current tone: <strong>{currentTone || 'loading...'}</strong></p>
      <div className="tone-options">
        {toneOptions.map(tone => (
          <button
            key={tone}
            onClick={() => handleToneChange(tone)}
            className={tone === currentTone ? 'active' : ''}
          >
            {tone.charAt(0).toUpperCase() + tone.slice(1)}
          </button>
        ))}
      </div>
      {status && <p className="status">{status}</p>}
    </div>
  );
};

export default ToneTuner;
