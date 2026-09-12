import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { IdcardOutlined, FileTextOutlined } from '@ant-design/icons';
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
          <p className="home-subtitle">/ 面试陪练 · 合同管理 /</p>
        </header>

        <div className="home-cards">
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

          <article className="home-card">
            <div className="home-card-icon home-card-icon--contract">
              <FileTextOutlined />
            </div>
            <h2 className="home-card-title">合同管理</h2>
            <p className="home-card-desc">管理客户合同、版本与合同文件，进入合同工作台</p>
            <button
              type="button"
              className="home-card-btn"
              onClick={() => navigate('/contracts')}
            >
              进入工作台 →
            </button>
          </article>
        </div>
      </div>
    </div>
  );
};

export default Home;
