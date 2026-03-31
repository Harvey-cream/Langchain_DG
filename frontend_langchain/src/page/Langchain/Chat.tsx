import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './Chat.css';

interface Message {
  id: string;
  content: string;
  isUser: boolean;
  timestamp: string;
}

const Chat: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      content: '你好，我是AI超级智能体。我可以解答各类问题，提供专业建议，请问有什么可以帮助你的吗？',
      isUser: false,
      timestamp: new Date().toLocaleTimeString(),
    },
  ]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    // 检查是否已登录
    const token = localStorage.getItem('token');
    if (!token) {
      navigate('/login');
    }
  }, [navigate]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async () => {
    if (!inputMessage.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      content: inputMessage,
      isUser: true,
      timestamp: new Date().toLocaleTimeString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    // 模拟AI回复
    setTimeout(() => {
      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: `你好！你刚刚说："${inputMessage}"。这是一个模拟回复，实际应用中会调用真实的AI API。`,
        isUser: false,
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages(prev => [...prev, aiMessage]);
      setIsLoading(false);
    }, 1000);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="chat-container">
      <div className="chat-header">
        <button className="back-button" onClick={() => navigate('/')}>
          ← 返回
        </button>
        <h1>AI超级智能体</h1>
      </div>

      <div className="chat-messages">
        {messages.map(message => (
          <div key={message.id} className={`message ${message.isUser ? 'user-message' : 'ai-message'}`}>
            <div className="message-content">
              {message.content}
            </div>
            <div className="message-time">{message.timestamp}</div>
          </div>
        ))}
        {isLoading && (
          <div className="message ai-message">
            <div className="message-content">
              <div className="loading-indicator">
                <span className="loading-dot"></span>
                <span className="loading-dot"></span>
                <span className="loading-dot"></span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        <input
          type="text"
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="请输入消息..."
          className="chat-input"
        />
        <button onClick={handleSendMessage} className="send-button">
          发送
        </button>
      </div>

      <div className="chat-footer">
        <div className="footer-left">鱼皮AI超级智能体应用平台</div>
        <div className="footer-center">友情链接</div>
        <div className="footer-right">联系我们</div>
      </div>
    </div>
  );
};

export default Chat;