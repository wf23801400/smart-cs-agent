import React, { useState, useRef, useEffect } from 'react'
import { sendMessage } from './api'

export default function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sessionId, setSessionId] = useState(null)
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    const text = input.trim()
    if (!text || loading) return

    // 添加用户消息到界面
    const userMsg = { role: 'user', content: text }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const data = await sendMessage(text, sessionId)

      // 首次对话自动记录 session_id
      if (!sessionId) {
        setSessionId(data.session_id)
      }

      // 添加助手回复
      setMessages(prev => [...prev, { role: 'assistant', content: data.reply }])
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '抱歉，系统暂时无法响应 😅 请检查后端是否已启动，或稍后重试。'
      }])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleNewSession = () => {
    setMessages([])
    setSessionId(null)
  }

  return (
    <div className="app">
      {/* 顶栏 */}
      <header className="header">
        <h1>🤖 智能客服系统</h1>
        <div className="header-right">
          {sessionId && <span className="session-badge">会话: {sessionId}</span>}
          <button className="btn-new" onClick={handleNewSession}>新会话</button>
        </div>
      </header>

      {/* 消息区 */}
      <div className="chat-area">
        {messages.length === 0 && (
          <div className="welcome">
            <p>👋 你好！我是智能客服助手，有什么可以帮你的？</p>
            <div className="quick-actions">
              <button onClick={() => setInput('我要退货')}>我要退货</button>
              <button onClick={() => setInput('退货要几天到账？')}>退货政策</button>
              <button onClick={() => setInput('你们客服态度太差了！')}>我要投诉</button>
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`msg-row ${msg.role}`}>
            <div className="msg-avatar">{msg.role === 'user' ? '👤' : '🤖'}</div>
            <div className="msg-bubble">
              <div className="msg-text">{msg.content}</div>
            </div>
          </div>
        ))}

        {loading && (
          <div className="msg-row assistant">
            <div className="msg-avatar">🤖</div>
            <div className="msg-bubble typing">
              <span></span><span></span><span></span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* 输入区 */}
      <div className="input-area">
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入你的问题...（Enter 发送，Shift+Enter 换行）"
          rows={2}
          disabled={loading}
        />
        <button
          className="btn-send"
          onClick={handleSend}
          disabled={loading || !input.trim()}
        >
          {loading ? '发送中...' : '发送'}
        </button>
      </div>
    </div>
  )
}
