// src/components/Chat/ChatBubble.jsx
import React from "react";
import PropTypes from "prop-types";
import clsx from "clsx";
import "./ChatBubble.css";

/**
 * ChatBubble will:
 *  - Split the incoming `text` on newline (\n) to preserve line breaks.
 *  - Within each line, look for any substring that “looks like” an image URL:
 *      e.g.  https://cdn.shopify.com/.../something_200x200.jpg
 *    and render that substring as <img> instead of plain text.
 */
const ChatBubble = ({ sender, text }) => {
  const URL_REGEX = /(https?:\/\/\S+\.(?:jpg|jpeg|png|gif))/gi;

  // Split text into lines and handle URLs
  const lines = text.split(/\r?\n/);

  return (
    <div
      className={clsx(
        "chat-bubble",
        sender === "user" ? "chat-bubble-user" : "chat-bubble-grace"
      )}
    >
      {lines.map((line, idx) => {
        const parts = line.split(URL_REGEX);

        return (
          <div key={idx} className="chat-bubble-line">
            {parts.map((chunk, i) => {
              if (chunk.match(URL_REGEX)) {
                return (
                  <img
                    key={i}
                    src={chunk}
                    alt="matched item"
                    className="chat-image-inline"
                  />
                );
              } else {
                return (
                  <span key={i} className="chat-text-chunk">
                    {chunk}
                  </span>
                );
              }
            })}
          </div>
        );
      })}
    </div>
  );
};

ChatBubble.propTypes = {
  sender: PropTypes.oneOf(["user", "grace"]).isRequired,
  text: PropTypes.string.isRequired,
};

export default ChatBubble;
