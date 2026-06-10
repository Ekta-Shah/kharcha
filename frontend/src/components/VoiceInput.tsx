import { useEffect, useRef, useState } from "react";

interface Props {
  onResult: (text: string) => void;
  disabled?: boolean;
}

type SR = {
  lang: string;
  interimResults: boolean;
  onresult: ((e: { results: { 0: { transcript: string } }[] }) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
};

declare global {
  interface Window {
    SpeechRecognition: { new(): SR };
    webkitSpeechRecognition: { new(): SR };
  }
}

export default function VoiceInput({ onResult, disabled }: Props) {
  const [listening, setListening] = useState(false);
  const [text, setText] = useState("");
  const recRef = useRef<SR | null>(null);
  const SR = typeof window !== "undefined"
    ? (window.SpeechRecognition || window.webkitSpeechRecognition)
    : null;

  useEffect(() => () => recRef.current?.abort(), []);

  function startListening() {
    if (!SR) return;
    const rec = new SR();
    rec.lang = "en-IN";
    rec.interimResults = false;
    rec.onresult = (e: { results: { 0: { transcript: string } }[] }) => {
      const t = e.results[0][0].transcript;
      setText(t);
      onResult(t);
    };
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    recRef.current = rec;
    rec.start();
    setListening(true);
  }

  function stopListening() {
    recRef.current?.stop();
    setListening(false);
  }

  return (
    <div className="flex gap-2 items-start">
      <textarea
        className="flex-1 border border-ink/20 rounded px-3 py-2 text-sm bg-white resize-none focus:outline-none focus:border-ink"
        rows={2}
        placeholder='e.g. "zomato 320, auto 80, sabzi ke liye 150 yesterday"'
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            if (text.trim()) onResult(text.trim());
          }
        }}
        disabled={disabled}
      />
      {SR && (
        <button
          onClick={listening ? stopListening : startListening}
          disabled={disabled}
          className={`px-3 py-2 rounded border text-sm font-medium transition-colors ${
            listening
              ? "bg-ledgerRed text-white border-ledgerRed animate-pulse"
              : "border-ink/30 hover:border-ink"
          }`}
          title={listening ? "Stop recording" : "Speak"}
        >
          {listening ? "■ Stop" : "🎙 Speak"}
        </button>
      )}
    </div>
  );
}
