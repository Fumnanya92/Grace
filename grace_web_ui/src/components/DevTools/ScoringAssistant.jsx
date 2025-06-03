import React, { useState } from 'react';
import './ScoringAssistant.css';

const ScoringAssistant = () => {
  const [userPhrase, setUserPhrase] = useState('');
  const [graceResponse, setGraceResponse] = useState('');
  const [rating, setRating] = useState('');
  const [comment, setComment] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async () => {
    if (!userPhrase || !graceResponse || !rating) {
      alert('Please fill in all required fields.');
      return;
    }

    const payload = {
      phrase: userPhrase,
      response: graceResponse,
      rating,
      comment,
    };

    try {
      const res = await fetch('http://localhost:8000/score-feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        setSubmitted(true);
        setUserPhrase('');
        setGraceResponse('');
        setRating('');
        setComment('');
      } else {
        alert('Failed to submit feedback.');
      }
    } catch (err) {
      console.error('Error submitting score:', err);
    }
  };

  return (
    <div className="scoring-assistant">
      <h2>📝 Scoring Assistant</h2>
      {submitted && <p className="success-msg">✅ Feedback submitted!</p>}
      <input
        type="text"
        placeholder="User phrase"
        value={userPhrase}
        onChange={(e) => setUserPhrase(e.target.value)}
      />
      <textarea
        placeholder="Grace's response"
        value={graceResponse}
        onChange={(e) => setGraceResponse(e.target.value)}
      />
      <select value={rating} onChange={(e) => setRating(e.target.value)}>
        <option value="">Rate this response</option>
        <option value="excellent">👍 Excellent</option>
        <option value="average">😐 Average</option>
        <option value="poor">👎 Poor</option>
      </select>
      <textarea
        placeholder="Optional comment"
        value={comment}
        onChange={(e) => setComment(e.target.value)}
      />
      <button onClick={handleSubmit}>Submit Feedback</button>
    </div>
  );
};

export default ScoringAssistant;
