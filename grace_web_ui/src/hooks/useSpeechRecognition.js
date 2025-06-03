import { useEffect, useRef, useState } from "react";

/**
 * Hook: useSpeechRecognition
 * --------------------------
 * Lightweight wrapper around the Web Speech API for voice-to-text functionality.
 */
export default function useSpeechRecognition({ onResult, lang = "en-US" }) {
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef(null);

  useEffect(() => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return; // Browser not supported

    const recog = new SpeechRecognition();
    recog.continuous = false;
    recog.interimResults = false;
    recog.lang = lang;

    recog.onresult = (e) => {
      const text = Array.from(e.results)
        .map((r) => r[0].transcript)
        .join(" ");
      onResult(text);
    };
    recog.onend = () => setListening(false);

    recognitionRef.current = recog;
  }, [lang, onResult]);

  const toggle = () => {
    const recog = recognitionRef.current;
    if (!recog) return;
    if (listening) {
      recog.stop();
      setListening(false);
    } else {
      recog.start();
      setListening(true);
    }
  };

  return { listening, toggle };
}