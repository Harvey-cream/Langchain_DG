import React from 'react';
import { useLocation } from 'react-router-dom';
import ChatPage, { type Message } from './ChatPage';
import { agentChatApi, interviewChatApi } from '../../services/chatApi';

const WELCOME_AGENT: Message = {
  id: 'welcome',
  content:
    '你好，我是AI超级智能体。我可以解答各类问题，提供专业建议，请问有什么可以帮助你的吗？',
  isUser: false,
  timestamp: new Date().toLocaleTimeString(),
};

const WELCOME_INTERVIEW: Message = {
  id: 'welcome',
  content:
    '你好，我是AI面试大师，专注编程类面试。我可以和你文字交流编程面试题、解题思路与面试技巧，你想先聊语言基础、计算机基础，还是项目与场景题？',
  isUser: false,
  timestamp: new Date().toLocaleTimeString(),
};

const Chat: React.FC = () => {
  const { pathname } = useLocation();
  const isInterview = pathname === '/interview';

  if (isInterview) {
    return (
      <ChatPage
        featureTitle="AI面试大师"
        welcomeMessage={WELCOME_INTERVIEW}
        chatApi={interviewChatApi}
      />
    );
  }

  return (
    <ChatPage
      featureTitle="AI超级智能体"
      welcomeMessage={WELCOME_AGENT}
      chatApi={agentChatApi}
    />
  );
};

export default Chat;
