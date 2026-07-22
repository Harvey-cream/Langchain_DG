import React from 'react';
import { useLocation } from 'react-router-dom';
import ChatPage, { type Message } from './ChatPage';
import { agentChatApi, interviewChatApi } from '../../services/chatApi';

const WELCOME_AGENT: Message = {
  id: 'welcome',
  content:
    '你好，我是企业知识库AI助手。你可以在侧栏「我的文档」上传材料，我再基于这些文档帮你检索问答、摘要与整理。想先上传一份，还是直接提问？',
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
      featureTitle="企业知识库AI助手"
      welcomeMessage={WELCOME_AGENT}
      chatApi={agentChatApi}
      enableDocuments
    />
  );
};

export default Chat;
