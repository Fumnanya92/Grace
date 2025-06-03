import React, { useState } from 'react';
import './ChatInput.css';

const ChatInput = ({ onSend, onImageUpload }) => {
  const [input, setInput] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim()) {
      onSend(input);
      setInput('');
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      onImageUpload(file);
    }
  };

  return (
    <form className="chat-input-form" onSubmit={handleSubmit}>
      {/* Attachment */}
      <label className="image-upload-label">
        📎
        <input
          type="file"
          accept="image/*"
          onChange={handleFileChange}
          style={{ display: 'none' }}
        />
      </label>

      {/* Textbox */}
      <input
        type="text"
        placeholder="Type a message..."
        value={input}
        onChange={(e) => setInput(e.target.value)}
        className="chat-input"
      />

      {/* Send Button */}
      <button type="submit" className="send-button" disabled={!input.trim()}>
        ➤
      </button>
    </form>
  );
};

export default ChatInput;
