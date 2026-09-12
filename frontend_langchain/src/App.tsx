import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Login from './page/Langchain_login/Login';
import Register from './page/Langchain_login/Register';
import Home from './page/Home';
import InterviewChatPage from './pages/interview/InterviewChatPage';
import ContractRoutes from './app/routes/ContractRoutes';

const App: React.FC = () => {
  return (
    <Router>
      <div className="app">
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/home" element={<Home />} />
          <Route path="/interview" element={<InterviewChatPage />} />
          <Route path="/contracts/*" element={<ContractRoutes />} />
          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </div>
    </Router>
  );
};

export default App;