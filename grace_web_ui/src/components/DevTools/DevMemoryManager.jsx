import React, { useEffect, useState } from 'react';
import './DevMemoryManager.css'; // Import the CSS file

const DevMemoryManager = () => {
  const [memory, setMemory] = useState({ conversations: [], notes: {} });
  const [loading, setLoading] = useState(false);
  const [newNoteKey, setNewNoteKey] = useState('');
  const [newNoteValue, setNewNoteValue] = useState('');

  // Fetch memory from the backend
  const fetchMemory = async () => {
    setLoading(true);
    try {
      const response = await fetch('http://localhost:8000/admin/get_dev_memory');
      const data = await response.json();
      setMemory(data);
    } catch (error) {
      console.error('Error fetching memory:', error);
    } finally {
      setLoading(false);
    }
  };

  // Add a new note
  const addNote = async () => {
    if (!newNoteKey.trim() || !newNoteValue.trim()) {
      alert('Please fill in both fields.');
      return;
    }
    try {
      const response = await fetch('http://localhost:8000/admin/save_dev_memory', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          key: newNoteKey.trim(),
          value: newNoteValue.trim(),
        }),
      });
      if (response.ok) {
        fetchMemory();
        setNewNoteKey('');
        setNewNoteValue('');
      }
    } catch (error) {
      console.error('Error adding note:', error);
    }
  };

  useEffect(() => {
    fetchMemory();
  }, []);

  return (
    <div className="dev-memory-manager">
      <h2>🧠 Dev Memory Manager</h2>

      {loading ? (
        <p className="loading">Loading memory...</p>
      ) : (
        <div>
          <h3>Conversations</h3>
          <ul>
            {memory.conversations.map((conv, index) => (
              <li key={index}>
                <strong>{conv.timestamp}</strong> [{conv.topic}]: {conv.user_prompt} → {conv.assistant_reply}
              </li>
            ))}
          </ul>

          <h3>Notes</h3>
          <ul>
            {Object.entries(memory.notes).map(([key, values], index) => (
              <li key={index}>
                <strong>{key}:</strong> {values.join(', ')}
              </li>
            ))}
          </ul>

          <div className="mt-4">
            <h4>Add New Note</h4>
            <input
              type="text"
              placeholder="Note Key"
              value={newNoteKey}
              onChange={(e) => setNewNoteKey(e.target.value)}
            />
            <textarea
              placeholder="Note Value"
              value={newNoteValue}
              onChange={(e) => setNewNoteValue(e.target.value)}
            />
            <button onClick={addNote}>Add Note</button>
          </div>
        </div>
      )}
    </div>
  );
};

export default DevMemoryManager;