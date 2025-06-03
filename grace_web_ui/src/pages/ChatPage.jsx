import React, { useState, useEffect, useRef } from "react";
import ChatBubble from "../components/Chat/ChatBubble";
import ChatInput from "../components/Chat/ChatInput";
import "./ChatPage.css";
import useSpeechRecognition from "../hooks/useSpeechRecognition"; // Import the hook
import "./../styles/common.css"; // Import common styles

/**
 * ChatPage – Grace web‑client that talks to `/webhook` just like Twilio does.
 * ------------------------------------------------------------
 * • Sends text & image messages using FormData (mimics Twilio).
 * • Adds required `From` field so FastAPI doesn't return 422.
 * • Parses XML replies (Twilio <Response>) or JSON fallback.
 * • Auto‑scrolls, nice Tailwind styling, attachment icon, disabled send‑btn, etc.
 */
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
  const scrollToBottom = () => messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
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
      setMessages((prev) => [...prev, { sender: "grace", text: reply }]);
    } catch (err) {
      console.error("Error sending message:", err);
      setMessages((prev) => [...prev, { sender: "grace", text: "❌ Network error." }]);
    } finally {
      setIsLoading(false);
    }
  };

  /** Handle image upload */
  const handleImageUpload = async (file) => {
    if (!file) return;

    setMessages((prev) => [...prev, { sender: "user", text: "[Uploading Image...]" }]);
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

      // Send the public URL to the webhook
      const formData = new FormData();
      formData.append("From", "web_client");
      formData.append("MediaUrl0", publicUrl);
      formData.append("MediaContentType0", file.type);
      const reply = await callWebhook(formData);

      setMessages((prev) => [
        ...prev.slice(0, -1), // Remove the "Uploading Image..." message
        { sender: "user", text: publicUrl }, // Pass the image URL
        { sender: "grace", text: reply },
      ]);
    } catch (err) {
      console.error("Error uploading image:", err);
      setMessages((prev) => [
        ...prev.slice(0, -1), // Remove the "Uploading Image..." message
        { sender: "grace", text: "❌ Failed to upload image." },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

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

  return (
    <div className="chat-container">
      {/* Header */}
      <header className="chat-header">
        <h2>Grace Chat</h2>
      </header>

      {/* Messages */}
      <main className="chat-messages">
        {messages.map((msg, idx) => (
          <ChatBubble key={idx} sender={msg.sender} text={msg.text} />
        ))}
        {isLoading && <ChatBubble sender="grace" text="Grace is typing…" />}
        <div ref={messagesEndRef} />
      </main>

      {/* Chat Input */}
      <ChatInput onSend={sendMessage} onImageUpload={handleImageUpload} />
      <div>
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Type your query or use voice input..."
        />
        <button onClick={toggle}>
          {listening ? "Stop Listening" : "Start Listening"}
        </button>
        <button onClick={handleSend}>Send</button>
        {response && <p className="response">{response}</p>}
      </div>
    </div>
  );
};

export default ChatPage;
