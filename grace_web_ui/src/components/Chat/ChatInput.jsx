import React, { useState } from "react";
import "./ChatInput.css";

const ChatInput = ({ onSend, onImageUpload }) => {
  const [input, setInput] = useState("");
  const [file, setFile] = useState(null);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() || file) {
      if (file) {
        onImageUpload(file, input); // Send both the file and the message
        setFile(null); // Clear the file after sending
      } else {
        onSend(input); // Send only the message
      }
      setInput(""); // Clear the input field
    }
  };

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      setFile(selectedFile); // Store the selected file
    }
  };

  const handleRemoveFile = () => {
    setFile(null); // Remove the selected file
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
          style={{ display: "none" }}
        />
      </label>

      {/* File Preview */}
      {file && (
        <div className="file-preview">
          <span>{file.name}</span>
          <button
            type="button"
            className="remove-file-button"
            onClick={handleRemoveFile}
          >
            ✖
          </button>
        </div>
      )}

      {/* Textbox */}
      <input
        type="text"
        placeholder={file ? "Add a message to your image..." : "Type a message..."}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        className="chat-input"
      />

      {/* Send Button */}
      <button
        type="submit"
        className="send-button"
        disabled={!input.trim() && !file} // Disable if no input or file
      >
        ➤
      </button>
    </form>
  );
};

export default ChatInput;
