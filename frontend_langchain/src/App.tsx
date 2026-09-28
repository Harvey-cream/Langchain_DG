import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Home from './app/HomePage';
import Login from './common/auth/Login';
import Register from './common/auth/Register';
import ContractRoutes from './products/contract/routes';
import InterviewChatPage from './products/interview/InterviewPage';

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
