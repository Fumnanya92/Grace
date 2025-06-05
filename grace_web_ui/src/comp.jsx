// File: src/components/DevTools/DevAssistant.jsx

import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import ChatBubble from "../Chat/ChatBubble"; // Reuse your existing ChatBubble component
import useSpeechRecognition from "../../hooks/useSpeechRecognition";
import "../../styles/common.css";
import "./DevAssistant.css";

const DevAssistant = () => {
  const [messages, setMessages] = useState([]); // { sender: "user"|"grace", text: string }
  const [query, setQuery] = useState("");
  const [contextType, setContextType] = useState("none");
  const [promptOverride, setPromptOverride] = useState("");
  const [model, setModel] = useState("gpt-4o");
  const [loading, setLoading] = useState(false);

  const { listening, toggle } = useSpeechRecognition({
    onResult: (text) => setQuery(text),
    lang: "en-US",
  });

  const scrollRef = useRef(null);
  const scrollToBottom = () =>
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  useEffect(scrollToBottom, [messages, loading]);

  const sendQuery = async (e) => {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;

    // Add user message bubble
    setMessages((prev) => [...prev, { sender: "user", text: trimmed }]);
    setLoading(true);

    try {
      const response = await axios.post("http://localhost:8000/dev/chat", {
        query: trimmed,
        context_type: contextType,
        model,
        prompt_override: promptOverride || null,
      });

      const { result: resResult, error } = response.data;
      const replyText = resResult ?? `❌ Error: ${error ?? "Unknown error"}`;

      setMessages((prev) => [...prev, { sender: "grace", text: replyText }]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { sender: "grace", text: `❌ Error: ${err.message}` },
      ]);
    } finally {
      setLoading(false);
      setQuery("");
    }
  };

  return (
    <div className="dev-assistant-container">
      {/* Header */}
      <header className="dev-assistant-header">
        🧠 Grace Dev Assistant
      </header>

      {/* Chat Area */}
      <main className="dev-assistant-chat-area">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`bubble-wrapper ${
              msg.sender === "user" ? "user" : "grace"
            }`}
          >
            <ChatBubble sender={msg.sender} text={msg.text} />
          </div>
        ))}

        {loading && (
          <div className="bubble-wrapper grace">
            <ChatBubble sender="grace" text="Grace is thinking…" />
          </div>
        )}

        <div ref={scrollRef} />
      </main>

      {/* Settings Row */}
      <section className="dev-assistant-settings">
        <label>
          Context:
          <select
            value={contextType}
            onChange={(e) => setContextType(e.target.value)}
            className="dev-assistant-select"
          >
            <option value="none">None</option>
            <option value="catalog">Catalog</option>
            <option value="config">Config</option>
            <option value="tone">Tone</option>
            <option value="chatlog">Chat Log</option>
          </select>
        </label>

        <label>
          Model:
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="dev-assistant-select"
          >
            <option value="gpt-4o">gpt-4o</option>
            <option value="gpt-4">gpt-4</option>
            <option value="gpt-3.5-turbo">gpt-3.5-turbo</option>
          </select>
        </label>

        <label className="prompt-override-label">
          Prompt Override:
          <input
            type="text"
            value={promptOverride}
            onChange={(e) => setPromptOverride(e.target.value)}
            className="dev-assistant-override-input"
            placeholder="Optional custom prompt"
          />
        </label>
      </section>

      {/* Input Area */}
      <form className="dev-assistant-input-area" onSubmit={sendQuery}>
        <textarea
          className="dev-assistant-query-input"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask Grace anything…"
          rows={2}
        />
        <button
          type="button"
          className="dev-assistant-voice-btn"
          onClick={toggle}
        >
          {listening ? "🔴 Stop" : "🎙️ Speak"}
        </button>
        <button
          type="submit"
          className="dev-assistant-send-btn"
          disabled={loading}
        >
          {loading ? "Sending…" : "Send"}
        </button>
      </form>
    </div>
  );
};

export default DevAssistant;
