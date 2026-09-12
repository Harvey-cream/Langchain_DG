import React from 'react';
import ChatPage, { type Message } from '../../page/Langchain/ChatPage';
import { interviewChatApi } from '../../features/chat/api/chatApi';

const WELCOME_INTERVIEW: Message = {
  id: 'welcome',
  content:
    '你好，我是AI面试大师，专注编程类面试。我可以和你文字交流编程面试题、解题思路与面试技巧，你想先聊语言基础、计算机基础，还是项目与场景题？',
  isUser: false,
  timestamp: new Date().toLocaleTimeString(),
};

const InterviewChatPage: React.FC = () => (
  <ChatPage
    featureTitle="AI面试大师"
    welcomeMessage={WELCOME_INTERVIEW}
    chatApi={interviewChatApi}
  />
);

export default InterviewChatPage;
