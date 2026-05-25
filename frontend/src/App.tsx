import { useState, useRef, useEffect } from "react";
import { sendMessage, clearSession } from "./api/client";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  // 自动滚动到底部
  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || loading) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setLoading(true);

    try {
      const data = await sendMessage(text);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.reply },
      ]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "抱歉，系统出了点问题，请稍后重试。" },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleNewSession = () => {
    clearSession();
    setMessages([]);
  };

  return (
    <div className="chat-container">
      {/* 头部 */}
      <header className="chat-header">
        <h1>💬 智能客服</h1>
        <button onClick={handleNewSession} className="btn-new">
          新会话
        </button>
      </header>

      {/* 消息列表 */}
      <div className="chat-messages" ref={listRef}>
        {messages.length === 0 && (
          <div className="welcome">
            <div className="welcome-icon">🤖</div>
            <h2>你好！我是智能客服</h2>
            <p>可以问我退换货、物流、售后等问题，也可以直接告诉我订单号帮你处理～</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            <div className="message-avatar">{msg.role === "user" ? "👤" : "🤖"}</div>
            <div className="message-bubble">
              {msg.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="message assistant">
            <div className="message-avatar">🤖</div>
            <div className="message-bubble typing">
              <span></span><span></span><span></span>
            </div>
          </div>
        )}
      </div>

      {/* 输入区 */}
      <footer className="chat-input">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入消息，Enter 发送..."
          disabled={loading}
          rows={1}
        />
        <button onClick={handleSend} disabled={loading || !input.trim()}>
          ➤
        </button>
      </footer>
    </div>
  );
}
