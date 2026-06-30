

# LangChain DG

基于 Langchain + Django + React 的 AI 对话应用，支持通用 AI 助手和面试助手两种模式。

## 功能特性

### 🤖 AI 助手 (Langchain_Agent)
- **AI 编程问答**：使用 RAG 技术提供专业的编程问题解答
- **OpenClaw 支持**：集成 OpenClaw 工具
- **Vibe Coding**：支持 Vibing Coding 相关知识检索
- **面试学习**：提供面试相关知识问答
- **网络搜索**：可选的网络搜索功能

### 🎯 面试助手 (Langchain_Agent1)
- **AI/LLM 面试**：AI 和大模型相关面试问题
- **Java 面试**：Java 技术栈面试题
- **Vue 面试**：Vue.js 技术栈面试题
- **对话记忆**：支持多轮对话上下文记忆

### 📄 其他功能
- **流式输出**：支持实时流式响应
- **PDF 导出**：支持将对话内容导出为 PDF
- **RAG 检索**：基于 Chroma 向量数据库的文档检索
- **MCP 支持**：Model Context Protocol 多服务器支持
- **技能路由**：智能选择合适的技能上下文

## 技术栈

### 后端
- Python 3.10
- Django 5.0
- Langchain
- Chroma (向量数据库)
- SSE (Server-Sent Events)

### 前端
- React 18
- TypeScript
- Vite
- Ant Design

## 快速开始

### 环境要求
- Python 3.10+
- Node.js 18+
- Redis

### 后端安装

```bash
cd backend_langchain

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 复制环境配置
cp .env.example .env

# 运行数据库迁移
python manage.py migrate

# 启动服务
python manage.py runserver
```

### 前端安装

```bash
cd frontend_langchain

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

### Docker 部署

```bash
# 构建并运行
docker-compose up -d
```

## API 端点

### 用户接口
- `POST /api/user/register/` - 用户注册
- `POST /api/user/login/` - 用户登录
- `GET /api/user/info/` - 获取用户信息

### AI 聊天接口
- `POST /api/agent/chat/` - 发送聊天消息
- `GET /api/agent/chat/stream/` - 流式聊天
- `POST /api/agent/conversation/` - 管理会话

### 面试助手接口
- `POST /api/interview/chat/` - 面试聊天
- `GET /api/interview/chat/stream/` - 流式面试聊天

## 配置说明

主要配置项在 `backend_langchain/env/settings_pro.yaml` 或 `settings_debug.yaml`：

```yaml
llm:
  model: qwen-turbo
  temperature: 0.45

redis:
  host: localhost
  port: 6379

database:
  name: langchain_db
```

## 项目结构

```
backend_langchain/
├── Langchain_Agent/       # 通用 AI 助手
├── Langchain_Agent1/      # 面试助手
├── Langchain_rag/         # RAG 工具
├── Langchain_tool/         # 工具集
├── MCP/                  # MCP 多服务器
├── User/                 # 用户模块
├── common/               # 公共模块
├── common_web/           # Web 公共模块
├── config/               # 配置模块
├── env/                  # 环境配置
└── human_in_the_loop/    # 人机协作

frontend_langchain/
├── src/
│   ├── page/            # 页面组件
│   ├── services/        # API 服务
│   └── utils/           # 工具函数
```

## 开发指南

### 添加新的 RAG 知识库

在 `Scripts/build_knowledge.py` 中配置 PDF 文件路径和向量数据库参数，然后运行：

```bash
python Scripts/build_knowledge.py
```

### 添加新工具

在对应的 Agent 目录下的 `tools.py` 中使用 `@tool` 装饰器添加新工具。

## 许可证

本项目未包含 LICENSE 文件。

## 贡献指南

欢迎提交 Issue 和 Pull Request！