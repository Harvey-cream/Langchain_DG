import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { RobotOutlined, IdcardOutlined } from '@ant-design/icons';
import './Home.css';

const Home: React.FC = () => {
  const navigate = useNavigate();

  useEffect(() => {
    if (!localStorage.getItem('token')) {
      navigate('/login', { replace: true });
      return;
    }
    const html = document.documentElement;
    const body = document.body;
    const prevHtml = html.style.overflow;
    const prevBody = body.style.overflow;
    html.style.overflow = 'hidden';
    body.style.overflow = 'hidden';
    return () => {
      html.style.overflow = prevHtml;
      body.style.overflow = prevBody;
    };
  }, [navigate]);

  return (
    <div className="home-page">
      <div className="home-landing">
        <div className="home-grid-bg" aria-hidden />
        <header className="home-header">
          <h1 className="home-title">小龙 AI</h1>
          <p className="home-subtitle">/ 企业知识库 · 面试陪练 /</p>
        </header>

        <div className="home-cards">
          <article className="home-card">
            <div className="home-card-icon home-card-icon--agent">
              <RobotOutlined />
            </div>
            <h2 className="home-card-title">企业知识库AI助手</h2>
            <p className="home-card-desc">上传文档，基于你的资料做检索问答与摘要</p>
            <button
              type="button"
              className="home-card-btn"
              onClick={() => navigate('/chat')}
            >
              立即体验 →
            </button>
          </article>

          <article className="home-card">
            <div className="home-card-icon home-card-icon--interview">
              <IdcardOutlined />
            </div>
            <h2 className="home-card-title">AI面试大师</h2>
            <p className="home-card-desc">
              编程方向面试题、答题思路与面试技巧，夯实八股与表达
            </p>
            <button
              type="button"
              className="home-card-btn"
              onClick={() => navigate('/interview')}
            >
              立即体验 →
            </button>
          </article>
        </div>
      </div>
    </div>
  );
};

export default Home;
