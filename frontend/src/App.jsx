import React, { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";

const DEFAULT_API_BASE =
  import.meta.env.VITE_AGENT_API_BASE || "http://localhost:8001";

const markdownComponents = {
  li: ({ children, ...props }) => {
    const unwrapped = React.Children.map(children, (child) => {
      if (React.isValidElement(child) && child.type === "p") {
        return <>{child.props.children}</>;
      }
      return child;
    });
    return <li {...props}>{unwrapped}</li>;
  },
};

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState("");
  const messagesEndRef = useRef(null);

  const typingMessage = {
    role: "assistant",
    typing: true,
    text: "",
  };

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages.length]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isSending) return;

    setError("");
    setIsSending(true);

    const userMessage = { role: "user", text: trimmed };
    setMessages((prev) => [...prev, userMessage, typingMessage]);
    setInput("");

    try {
      const response = await fetch(`${DEFAULT_API_BASE}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message: trimmed }),
      });

      if (!response.ok) {
        const body = await response.text();
        throw new Error(
          `Agent error (${response.status}): ${body || "Unknown error"}`
        );
      }

      const data = await response.json();
      const replyText = data?.response ?? "";

      setMessages((prev) => {
        const next = [...prev];
        // Replace the last typing placeholder with the actual assistant response
        if (next.length > 0 && next[next.length - 1]?.typing) {
          next[next.length - 1] = {
            role: "assistant",
            text: replyText || "[Empty response]",
          };
          return next;
        }
        return [...next, { role: "assistant", text: replyText || "[Empty response]" }];
      });
    } catch (err) {
      console.error(err);
      setError(err.message || "Failed to contact agent.");
      setMessages((prev) => {
        const next = [...prev];
        if (next.length > 0 && next[next.length - 1]?.typing) {
          next.pop();
        }
        return next;
      });
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="app-root">
      <header className="app-header">
        <h1>FDA Agent Chat</h1>
        <p className="subtitle">
          Ask questions about drug labels, adverse events, and Food/Drug recalls.
        </p>
      </header>

      <main className="chat-container">
        <div className="messages">
          {messages.length === 0 && (
            <div className="empty-state">
              Start by asking something like
              <br />
              <span className="example">
                “What are the main warnings for Advil?”
              </span>
            </div>
          )}
          {messages.map((m, idx) => (
            <div
              key={idx}
              className={`message message-${m.role === "user" ? "user" : "agent"}`}
            >
              <div className="message-meta">
                {m.role === "user" ? "You" : "Agent"}
              </div>
              <div className="message-text">
                {m.typing ? (
                  <div className="typing-indicator" aria-label="Agent is typing">
                    <span className="dot dot-1" />
                    <span className="dot dot-2" />
                    <span className="dot dot-3" />
                  </div>
                ) : m.role === "assistant" ? (
                  <ReactMarkdown className="message-content" components={markdownComponents}>
                    {m.text}
                  </ReactMarkdown>
                ) : (
                  m.text
                )}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {error && <div className="error-banner">{error}</div>}

        <form className="input-row" onSubmit={handleSubmit}>
          <input
            type="text"
            placeholder="Type your question and press Enter..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isSending}
          />
          <button type="submit" disabled={isSending || !input.trim()}>
            Send
          </button>
        </form>
      </main>
    </div>
  );
}

export default App;

