import React, { useState, useEffect, useRef } from "react";
import ChatBubble from "../components/Chat/ChatBubble";
import ChatInput from "../components/Chat/ChatInput";
import useSpeechRecognition from "../hooks/useSpeechRecognition"; // Import the hook
import "../styles/common.css"; // Global CSS variables (colors, fonts, etc.)
import "./ChatPage.css"; // ChatPage‐specific styles

const ChatPage = () => {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState("");
  const { listening, toggle } = useSpeechRecognition({
    onResult: (text) => setQuery(text), // Update the query with the recognized speech
    lang: "en-US",
  });

  /** Scroll to bottom whenever messages change */
  const scrollToBottom = () =>
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  useEffect(scrollToBottom, [messages, isLoading]);

  /** Helper – hit /webhook with FormData the way Twilio would */
  const callWebhook = async (formData) => {
    const res = await fetch("http://localhost:8000/webhook", {
      method: "POST",
      body: formData,
    });
    const mime = res.headers.get("content-type") || "";
    if (mime.includes("application/json")) {
      const json = await res.json();
      return json.reply ?? JSON.stringify(json);
    }
    const text = await res.text();
    const match = text.match(/<Message[^>]*>([\s\S]*?)<\/Message>/i);
    return match ? match[1].trim() : text;
  };

  /** Send a plain text message */
  const sendMessage = async (messageText) => {
    const trimmed = messageText.trim();
    if (!trimmed) return;

    setMessages((prev) => [...prev, { sender: "user", text: trimmed }]);
    setIsLoading(true);

    try {
      const formData = new FormData();
      formData.append("From", "web_client");
      formData.append("Body", trimmed);
      const reply = await callWebhook(formData);

      // Split the reply into lines and add each as a separate bubble
      const lines = reply.split(/\r?\n\r?\n/).flatMap((chunk) => chunk.split(/\r?\n/));
      setMessages((prev) => [
        ...prev,
        ...lines.map((line) => ({ sender: "grace", text: line.trim() })),
      ]);
    } catch (err) {
      console.error("Error sending message:", err);
      setMessages((prev) => [
        ...prev,
        { sender: "grace", text: "❌ Network error." },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  /** Handle image upload */
  const handleImageUpload = async (file, messageText = "") => {
    if (!file) return;

    const trimmedMessage = messageText.trim();
    setMessages((prev) => [
      ...prev,
      { sender: "user", text: trimmedMessage || "[Uploading Image...]" },
    ]);
    setIsLoading(true);

    try {
      // Upload the image to get a public URL
      const uploadFormData = new FormData();
      uploadFormData.append("file", file);
      const uploadResponse = await fetch("http://localhost:8000/upload-image", {
        method: "POST",
        body: uploadFormData,
      });
      const uploadJson = await uploadResponse.json();
      const publicUrl = uploadJson.url;

      // Send the public URL and optional message to the webhook
      const formData = new FormData();
      formData.append("From", "web_client");
      formData.append("MediaUrl0", publicUrl);
      formData.append("MediaContentType0", file.type);
      if (trimmedMessage) {
        formData.append("Body", trimmedMessage);
      }
      const reply = await callWebhook(formData);

      setMessages((prev) => [
        ...prev.slice(0, -1), // Remove the "Uploading Image..." message
        { sender: "user", text: trimmedMessage || publicUrl }, // Show the message or uploaded URL
        { sender: "grace", text: reply },
      ]);
    } catch (err) {
      console.error("Error uploading image:", err);
      setMessages((prev) => [
        ...prev.slice(0, -1),
        { sender: "grace", text: "❌ Failed to upload image." },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  /** Send a query to /dev/chat (Dev Assistant) */
  const handleSend = async () => {
    try {
      const res = await fetch("http://localhost:8000/dev/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      const data = await res.json();
      setResponse(data.result || "No response");
    } catch (error) {
      console.error("Error sending query:", error);
    }
  };

  /** Handle Enter key press */
  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault(); // Prevent adding a new line
      sendMessage(query); // Send the message
      setQuery(""); // Clear the input field
    }
  };

  return (
    <div className="chat-page-container">
      {/* Header */}
      <header className="chat-header">
        <h2 className="chat-title">Grace Chat</h2>
      </header>

      {/* Messages */}
      <main className="chat-messages-area">
        {messages.map((msg, idx) => (
          <div key={idx} className={`bubble-wrapper ${msg.sender}`}>
            <ChatBubble sender={msg.sender} text={msg.text} />
          </div>
        ))}
        {isLoading && (
          <div className="bubble-wrapper grace">
            <ChatBubble sender="grace" text="Grace is typing…" />
          </div>
        )}
        <div ref={messagesEndRef} />
      </main>

      {/* Chat Input (existing component) */}
      <div className="chat-input-wrapper">
        <ChatInput
          onSend={sendMessage} // Pass the sendMessage function from ChatPage
          onImageUpload={(file, message) => handleImageUpload(file, message)} // Pass the handleImageUpload function
        />
      </div>

      {/* Voice + Raw Query Box */}
      <div className="voice-query-wrapper">
        <textarea
          className="voice-query-textarea"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown} // Listen for Enter key
          placeholder="Type your query or use voice input…"
        />
        <div className="voice-buttons">
          <button className="voice-toggle-btn" onClick={toggle}>
            {listening ? "Stop Listening" : "Start Listening"}
          </button>
          <button className="voice-send-btn" onClick={handleSend}>
            Send
          </button>
        </div>
      </div>

      {/* Assistant’s LLM response */}
      {response && <div className="llm-response-box">{response}</div>}
    </div>
  );
};

export default ChatPage;
