import React, { useEffect, useState } from 'react';

const MemoryManager = () => {
  const [memory, setMemory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  // Fetch all memories on component mount
  useEffect(() => {
    fetchMemory();
  }, []);

  // Fetch memory from the backend
  const fetchMemory = async () => {
    setLoading(true);
    setMessage('');
    try {
      const response = await fetch('http://localhost:8000/memory');
      if (!response.ok) {
        throw new Error('Failed to fetch memory');
      }
      const data = await response.json();
      setMemory(data.memories || []);
    } catch (error) {
      console.error('Error fetching memory:', error);
      setMessage('Failed to load memory');
    } finally {
      setLoading(false);
    }
  };

  // Clear all memory
  const clearMemory = async () => {
    setMessage('');
    try {
      const response = await fetch('http://localhost:8000/memory/clear', { method: 'POST' });
      if (!response.ok) {
        throw new Error('Failed to clear memory');
      }
      setMemory([]);
      setMessage('Memory cleared successfully');
    } catch (error) {
      console.error('Error clearing memory:', error);
      setMessage('Error clearing memory');
    }
  };

  return (
    <div className="p-4 bg-white shadow rounded dark:bg-gray-900 dark:text-white">
      <h2 className="text-xl font-bold mb-4">🧠 Memory Manager</h2>

      {loading ? (
        <p>Loading memory...</p>
      ) : memory.length === 0 ? (
        <p className="text-gray-500">No memory found.</p>
      ) : (
        <ul className="mb-4">
          {memory.map((entry, index) => (
            <li
              key={index}
              className="mb-2 p-2 bg-gray-100 rounded dark:bg-gray-800"
            >
              <strong>User:</strong> {entry.sender || 'Unknown'}<br />
              <strong>Grace:</strong> {entry.response || 'No response'}
            </li>
          ))}
        </ul>
      )}

      <button
        className="bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700"
        onClick={clearMemory}
        disabled={loading}
      >
        Clear Memory
      </button>

      {message && <p className="mt-4 text-sm text-blue-600">{message}</p>}
    </div>
  );
};

export default MemoryManager;