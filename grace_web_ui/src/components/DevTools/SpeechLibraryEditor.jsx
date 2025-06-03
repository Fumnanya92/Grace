import React, { useEffect, useState } from 'react';
import './SpeechLibraryEditor.css';

const SpeechLibraryEditor = () => {
  const [entries, setEntries] = useState([]);
  const [newPhrase, setNewPhrase] = useState('');
  const [newResponse, setNewResponse] = useState('');
  const [loading, setLoading] = useState(false);

  // Fetch the speech library from the backend
  const fetchLibrary = async () => {
    setLoading(true);
    try {
      const response = await fetch('http://localhost:8000/admin/get_speech_library');
      const data = await response.json();
      setEntries(data.training_data || []);
    } catch (error) {
      console.error('Failed to fetch speech library:', error);
    } finally {
      setLoading(false);
    }
  };

  // Add a new entry to the speech library
  const handleAdd = async () => {
    if (!newPhrase.trim() || !newResponse.trim()) {
      alert('Please fill in both fields.');
      return;
    }

    const newEntry = { phrase: newPhrase.trim(), response: newResponse.trim() };

    try {
      await fetch('http://localhost:8000/admin/save_speech_library', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newEntry),
      });
      setNewPhrase('');
      setNewResponse('');
      fetchLibrary();
    } catch (error) {
      console.error('Failed to add new entry:', error);
    }
  };

  // Delete an entry from the speech library
  const handleDelete = async (index) => {
    const phraseToDelete = entries[index]?.phrase;

    if (!phraseToDelete) return;

    try {
      await fetch('http://localhost:8000/admin/save_speech_library', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phrase: phraseToDelete, delete: true }),
      });
      fetchLibrary();
    } catch (error) {
      console.error('Failed to delete entry:', error);
    }
  };

  // Fetch the speech library on component mount
  useEffect(() => {
    fetchLibrary();
  }, []);

  return (
    <div className="speech-editor">
      <h2>🗣️ Speech Library Editor</h2>

      {loading ? (
        <p>Loading speech entries...</p>
      ) : entries.length === 0 ? (
        <p>No entries found in the speech library.</p>
      ) : (
        <ul className="speech-list">
          {entries.map((entry, index) => (
            <li key={index} className="speech-list-item">
              <strong>“{entry.phrase}”</strong> → {entry.response}
              <button
                className="delete-button"
                onClick={() => handleDelete(index)}
              >
                🗑
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="add-entry">
        <h4>Add New Entry</h4>
        <input
          type="text"
          placeholder="Trigger phrase"
          value={newPhrase}
          onChange={(e) => setNewPhrase(e.target.value)}
          className="input-field"
        />
        <textarea
          placeholder="Response text"
          value={newResponse}
          onChange={(e) => setNewResponse(e.target.value)}
          className="textarea-field"
        />
        <button onClick={handleAdd} className="add-button">
          ➕ Add
        </button>
      </div>
    </div>
  );
};

export default SpeechLibraryEditor;
