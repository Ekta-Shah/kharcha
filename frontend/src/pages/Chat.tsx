import { useEffect, useRef, useState } from "react";
import { api } from "../api";

type Message = { role: "user" | "assistant"; content: string };

const SUGGESTIONS = [
  "How much did I spend this month?",
  "What's my biggest expense category?",
  "Am I spending more than last month?",
  "Show my recurring payments",
  "Which day did I spend the most?",
];

function UserBubble({ content }: { content: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[75%] bg-ink text-paper rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm">
        {content}
      </div>
    </div>
  );
}

function AssistantBubble({ content }: { content: string }) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[75%] bg-paper border border-ink/10 rounded-2xl rounded-tl-sm px-4 py-2.5 text-sm text-ink/90 leading-relaxed whitespace-pre-wrap font-mono">
        {content}
      </div>
    </div>
  );
}

function TypingDots() {
  return (
    <div className="flex justify-start">
      <div className="bg-paper border border-ink/10 rounded-2xl rounded-tl-sm px-4 py-3 flex gap-1">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="w-1.5 h-1.5 rounded-full bg-ink/40 animate-bounce"
            style={{ animationDelay: `${i * 0.15}s` }}
          />
        ))}
      </div>
    </div>
  );
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function send(question: string) {
    if (!question.trim() || loading) return;
    setErr(null);
    const userMsg: Message = { role: "user", content: question.trim() };
    const nextMessages = [...messages, userMsg];
    setMessages(nextMessages);
    setInput("");
    setLoading(true);

    try {
      const res = await api.chat(
        question.trim(),
        messages.map((m) => ({ role: m.role, content: m.content }))
      );
      setMessages([...nextMessages, { role: "assistant", content: res.answer }]);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  }

  return (
    <div className="flex flex-col gap-4" style={{ height: "calc(100vh - 180px)" }}>
      {/* Message area */}
      <div className="flex-1 overflow-y-auto space-y-3 pr-1">
        {messages.length === 0 && (
          <div className="text-center py-12 space-y-6">
            <p className="text-ink/40 text-sm">Ask anything about your expenses</p>
            <div className="flex flex-wrap gap-2 justify-center">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="px-3 py-1.5 text-sm border border-ink/20 rounded-full text-ink/70 hover:border-ink/50 hover:text-ink transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) =>
          m.role === "user" ? (
            <UserBubble key={i} content={m.content} />
          ) : (
            <AssistantBubble key={i} content={m.content} />
          )
        )}

        {loading && <TypingDots />}

        {err && (
          <div className="text-red-600 text-sm text-center">{err}</div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className="flex gap-2 items-end border-t border-ink/10 pt-4">
        <textarea
          rows={1}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder='Ask about your expenses… (Enter to send, Shift+Enter for newline)'
          className="flex-1 resize-none border border-ink/20 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-ink/50 bg-paper text-ink placeholder:text-ink/30"
          style={{ maxHeight: 120 }}
          disabled={loading}
        />
        <button
          onClick={() => send(input)}
          disabled={!input.trim() || loading}
          className="px-4 py-3 bg-ink text-paper text-sm font-medium rounded-xl disabled:opacity-40 hover:bg-ink/80 transition-colors"
        >
          Send
        </button>
      </div>
    </div>
  );
}
