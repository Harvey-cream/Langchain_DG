

# LangChain AI 助手后端服务

基于 Django + LangChain 构建的 AI 助手后端服务，提供对话式 AI 编程助手和面试助手功能。

## 项目简介

本项目是一个生产级的 AI 对话系统，采用前后端分离架构：

- **后端**：Django + LangChain + Chroma 向量数据库
- **前端**：React + TypeScript + Ant Design
- **部署**：Docker + Nginx

### 核心功能

1. **AI 编程助手** - 基于 RAG 的智能编程问答
   - AI 编程知识库检索
   - Openclaw 知识检索
   - Vibecoding 知识检索
   - 面试学习资料检索

2. **AI 面试助手** - 专业技术面试辅导
   - AI/LLM 面试知识
   - Java 面试题库
   - Vue 面试题库

3. **用户系统**
   - 用户注册/登录
   - JWT 认证
   - SM2 国密加密
   - 对话历史管理

## 技术栈

### 后端
- Python 3.10
- Django 4.x
- LangChain
- Chroma (向量数据库)
- Qwen (通义千问大模型)
- Redis
- SQLite (checkpointer)

### 前端
- React 18
- TypeScript
- Ant Design
- Vite

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- Docker & Docker Compose (可选)

### 后端配置

1. 创建虚拟环境：
```bash
cd backend_langchain
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 配置环境变量：
```bash
cp .env.example .env
# 编辑 .env 文件，配置必要的环境变量
```

4. 运行数据库迁移：
```bash
python manage.py migrate
```

5. 启动开发服务器：
```bash
python manage.py runserver 0.0.0.0:8000
```

### 前端配置

1. 安装依赖：
```bash
cd frontend_langchain
npm install
```

2. 启动开发服务器：
```bash
npm run dev
```

### Docker 部署

```bash
docker-compose up -d
```

## 项目结构

```
├── backend_langchain/          # Django 后端
│   ├── Langchain_Agent/        # AI 编程助手模块
│   ├── Langchain_Agent1/       # AI 面试助手模块
│   ├── User/                   # 用户模块
│   ├── common/                 # 通用组件
│   │   ├── agent.py           # Agent 核心逻辑
│   │   ├── embedding.py       # 向量嵌入
│   │   └── skill_router.py    # 技能路由
│   ├── config/                 # 配置模块
│   ├── env/                    # 环境配置
│   └── Scripts/                # 知识库构建脚本
├── frontend_langchain/         # React 前端
│   └── src/
│       ├── page/               # 页面组件
│       ├── services/           # API 服务
│       └── utils/              # 工具函数
└── nginx/                      # Nginx 配置
```

## API 接口

### 用户接口
- `POST /api/user/register/` - 用户注册
- `POST /api/user/login/` - 用户登录
- `GET /api/user/info/` - 获取用户信息
- `PUT /api/user/info/` - 更新用户信息

### 对话接口
- `POST /api/chat/` - 发送消息（非流式）
- `GET /api/chat/stream/` - 流式对话
- `GET /api/conversations/` - 获取会话列表
- `POST /api/conversations/` - 创建会话
- `DELETE /api/conversations/<id>/` - 删除会话

### 面试接口
- `POST /api/interview/chat/` - 面试对话
- `GET /api/interview/stream/` - 流式面试对话

## 构建知识库

### 从 PDF 构建
```bash
python Scripts/build_knowledge.py
```

### 从 Markdown 构建
```bash
python Scripts/build_md_knowledge.py
```

## 环境变量说明

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `DATABASE_URL` | 数据库连接串 | SQLite 本地文件 |
| `REDIS_URL` | Redis 连接串 | 本地 Redis |
| `LLM_API_KEY` | 大模型 API Key | - |
| `LLM_BASE_URL` | 大模型 API 地址 | - |
| `EMBEDDING_MODEL` | 向量模型名称 | - |

## 许可证

MIT License