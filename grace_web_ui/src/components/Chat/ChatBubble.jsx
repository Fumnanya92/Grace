import React from "react";
import PropTypes from "prop-types";
import clsx from "clsx";
import "./ChatBubble.css"; // optional custom styling

const ChatBubble = ({ sender, text }) => {
  // Check if the message contains an image URL
  const isImage = text.startsWith("http") && (text.endsWith(".jpg") || text.endsWith(".png") || text.endsWith(".jpeg"));

  return (
    <div
      className={clsx(
        "chat-bubble",
        sender === "user" ? "chat-bubble-user" : "chat-bubble-grace"
      )}
    >
      {isImage ? (
        <img
          src={text}
          alt="Sent content"
          className="max-w-xs rounded-lg shadow-md"
        />
      ) : (
        <p>{text}</p>
      )}
    </div>
  );
};

ChatBubble.propTypes = {
  sender: PropTypes.string.isRequired,
  text: PropTypes.string.isRequired,
};

export default ChatBubble;
