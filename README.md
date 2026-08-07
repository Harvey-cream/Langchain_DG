

# LangChain DG

基于 LangChain 构建的企业级 AI 对话应用平台，提供智能 Agent 和面试助手功能，支持流式输出、知识库检索、RAG 向量化和 PDF 文档导出。

## 🌟 核心特性

### 智能对话系统
- **多 Agent 架构**：基于 LangGraph 的状态流图实现，支持知识问答、文档总结、面试助手等多种 Agent
- **上下文记忆**：长期记忆与短期会话记忆结合，支持对话历史压缩与摘要
- **流式响应**：Server-Sent Events (SSE) 实现实时token流输出

### 知识库检索 (RAG)
- **混合检索**：语义向量检索 + 重排序 (Rerank) 双重优化
- **多格式支持**：Markdown、PDF、TXT 文档向量化存储
- **动态更新**：支持用户文档上传与实时索引构建

### 面试助手
- **智能追问**：根据回答内容动态调整面试问题
- **多维度评估**：自动生成面试评估报告
- **PDF 导出**：面试记录导出为标准化文档

### 企业级特性
- **安全认证**：JWT 令牌 + SM2 国密算法双重加密
- **高可用部署**：Docker 容器化 + Nginx 反向代理
- **性能监控**：内置延迟基准测试工具

## 🛠 技术架构

| 层级 | 技术选型 | 说明 |
|------|----------|------|
| **后端框架** | FastAPI 0.115+ | 异步高性能 Python Web 框架 |
| **LLM 框架** | LangChain 0.3+ | 大语言模型应用开发框架 |
| **图计算** | LangGraph | Agent 状态机与工作流编排 |
| **数据库** | PostgreSQL + Redis | 主数据存储与缓存层 |
| **向量库** | PgVector + Chroma | 混合向量检索引擎 |
| **前端框架** | React 18 + TypeScript | 函数式组件开发 |
| **UI 组件** | Ant Design 5.x | 企业级 UI 组件库 |
| **构建工具** | Vite 6.x | 极速前端构建工具 |
| **文档模型** | DashScope (阿里云) | 通义千问 Embedding 模型 |

## 🚀 快速部署

### 环境准备

```bash
# 系统要求
Python >= 3.12
Node.js >= 18
Docker & Docker Compose >= 2.20
PostgreSQL >= 15 (若不使用 Docker)
Redis >= 7 (若不使用 Docker)
```

### 1. 环境变量配置

```bash
# 复制环境变量模板
cp backend_langchain/.env.example backend_langchain/.env

# 根据部署环境选择配置
# 开发环境
cp backend_langchain/env/settings_debug.example.yaml backend_langchain/env/settings_debug.yaml

# 生产环境
cp backend_langchain/env/settings_pro.example.yaml backend_langchain/env/settings_pro.yaml
```

### 2. Docker 部署 (推荐)

```bash
# 启动所有服务
docker compose up -d

# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f backend
```

服务将在以下端口启动：
- **API 服务**: http://localhost:8000
- **前端界面**: http://localhost:5173 (开发) / http://localhost (生产)

### 3. 本地开发启动

```bash
# 后端服务
cd backend_langchain
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 前端服务 (新终端)
cd frontend_langchain
npm install
npm run dev
```

## 📁 项目结构

```
LangChain_DG/
├── backend_langchain/              # FastAPI 后端服务
│   ├── app/                        # 应用核心模块
│   │   ├── main.py                # 应用入口与生命周期管理
│   │   ├── routers/               # API 路由层
│   │   │   ├── api.py             # 智能 Agent 对话接口
│   │   │   ├── interview.py       # 面试助手接口
│   │   │   ├── user.py            # 用户认证接口
│   │   │   └── documents.py       # 文档管理接口
│   │   ├── models.py              # SQLAlchemy 数据模型
│   │   ├── deps.py                # 依赖注入配置
│   │   ├── auth/                  # 认证模块
│   │   │   ├── jwt_token.py       # JWT 令牌处理
│   │   │   └── sm2.py             # SM2 国密加密
│   │   ├── services/              # 业务服务层
│   │   │   ├── document_pipeline/# 文档处理管道
│   │   │   ├── oss_client.py      # 对象存储服务
│   │   │   └── extend.py          # 扩展功能
│   │   └── db.py                  # 数据库连接管理
│   ├── agent/                     # Agent 核心模块
│   │   ├── graph_factory.py       # Agent 图工厂
│   │   ├── runtime/               # 运行时配置
│   │   │   ├── runtime_knowledge.py
│   │   │   └── runtime_interview.py
│   │   ├── memory/                # 记忆管理
│   │   │   ├── long_term_store.py # 长期记忆存储
│   │   │   └── memory_trim.py     # 记忆裁剪策略
│   │   ├── rag/                   # RAG 检索模块
│   │   │   ├── rag.py             # 检索主逻辑
│   │   │   ├── rerank.py          # 重排序
│   │   │   └── skill_router.py    # 技能路由
│   │   ├── tools/                 # 工具函数
│   │   └── mcp/                   # MCP 工具集成
│   ├── Scripts/                   # 运维脚本
│   │   ├── build_rag_knowledge.py # 知识库构建
│   │   ├── benchmark_*.py         # 性能基准测试
│   │   └── preview_*.py           # 文档预览工具
│   ├── config/                    # 配置模块
│   └── env/                       # 环境配置
│
├── frontend_langchain/            # React 前端应用
│   ├── src/
│   │   ├── page/                  # 页面组件
│   │   │   ├── Home.tsx           # 首页
│   │   │   ├── Langchain/         # 对话模块
│   │   │   │   ├── Chat.tsx       # 聊天主界面
│   │   │   │   ├── ChatPage.tsx   # 聊天页面容器
│   │   │   │   └── ChatSidebar.tsx# 侧边栏
│   │   │   └── Langchain_login/   # 认证模块
│   │   ├── services/              # API 服务
│   │   │   ├── api.ts             # 基础 API
│   │   │   ├── chatApi.ts         # 对话 API
│   │   │   └── chatStream.ts      # 流式响应处理
│   │   ├── utils/                 # 工具函数
│   │   └── types/                 # 类型定义
│   └── package.json
│
├── nginx/                         # Nginx 配置
│   ├── nginx.conf                 # 主配置
│   └── certs/                     # SSL 证书
│
├── docker-compose.yml             # Docker 编排配置
├── Dockerfile                     # 后端镜像构建
└── README.md                      # 项目文档
```

## 📖 API 文档

### 认证接口

```typescript
// POST /api/user/register/ - 用户注册
interface RegisterBody {
  username: string;
  password: string;
  refer_code?: string;
}

// POST /api/user/login/ - 用户登录
interface LoginBody {
  username: string;
  password: string;
}

// GET /api/user/info/ - 获取用户信息
// PUT /api/user/info/update/ - 更新用户信息
```

### 智能对话接口

```typescript
// GET /api/agent/chat/ - 获取对话列表或消息
interface ChatQuery {
  conversation_id?: number;
  session_id?: number;
}

// POST /api/agent/chat/stream/ - 流式对话
interface StreamBody {
  message: string;
  conversation_id?: number;
  enable_web_search?: boolean;
  attachments?: ChatAttachment[];
}

// PATCH /api/agent/conversation/ - 更新对话
// DELETE /api/agent/conversation/ - 删除对话
```

### 面试助手接口

```typescript
// GET /api/interview/chat/ - 获取面试列表
// POST /api/interview/chat/stream/ - 流式面试对话
interface InterviewStreamBody {
  message: string;
  conversation_id?: number;
  resume_pdf_export?: boolean;
}
```

### 文档管理接口

```typescript
// POST /api/agent/documents/upload-init - 初始化上传
// POST /api/agent/documents/{id}/confirm - 确认上传完成
// GET /api/agent/documents - 文档列表
// DELETE /api/agent/documents/{id} - 删除文档
```

## 📚 知识库管理

### 内置知识库构建

```bash
# 方式一：容器内构建
docker compose exec backend python -m Scripts.build_rag_knowledge

# 方式二：本地构建
cd backend_langchain
python -m Scripts.build_rag_knowledge

# 指定领域构建
python -m Scripts.build_rag_knowledge --agent-domains "vibe_coding" --do-interview
```

### 用户文档上传

1. 前端选择文件 (Markdown/PDF/TXT)
2. 调用 `/api/agent/documents/upload-init` 获取上传签名
3. 上传文件至对象存储
4. 调用 `/api/agent/documents/{id}/confirm` 确认并触发索引

### 知识库格式要求

```
knowledge/
├── docs1/
│   └── vibe_coding/          # 领域名称
│       ├── README.md
│       ├── 01_入门指南.md
│       └── 02_进阶技巧.pdf
```

## ⚙️ 配置说明

### 核心配置项

```yaml
# backend_langchain/env/settings_pro.yaml

# 大语言模型配置
llm_config:
  api_key: ${DASHSCOPE_API_KEY}
  model_name: qwen-turbo
  temperature: 0.45

# 向量模型配置
dashscope_config:
  embedding_model: text-embedding-v3
  dimensions: 1024
  rerank_model: rerank-later

# RAG 配置
rag_config:
  chunk_size: 1000
  chunk_overlap: 150
  top_k: 5
  rerank_top_k: 3

# Redis 配置
redis_url: redis://:password@localhost:6379/0

# 对象存储配置
oss_config:
  endpoint: oss-cn-hangzhou.aliyuncs.com
  bucket: your-bucket-name
```

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `DASHSCOPE_API_KEY` | 阿里云 DashScope API Key | - |
| `DATABASE_URL` | PostgreSQL 连接字符串 | - |
| `REDIS_URL` | Redis 连接字符串 | - |
| `OSS_ACCESS_KEY_ID` | OSS Access Key | - |
| `OSS_ACCESS_KEY_SECRET` | OSS Secret Key | - |
| `JWT_SECRET_KEY` | JWT 签名密钥 | - |
| `SM2_PRIVATE_KEY` | SM2 私钥文件路径 | - |

## 🧪 测试与调试

### 性能基准测试

```bash
# 基准测试单个场景
python -m Scripts.benchmark_agent_latency

# 基准测试文档清理
python -m Scripts.benchmark_document_cleanup
```

### 文档预览

```bash
# 预览文档切分效果
python -m Scripts.preview_clean_chunk --format md --sample 10
```

### 诊断工具

```bash
# 诊断用户 RAG 配置
python -m Scripts.diagnose_user_rag --user-id 1
```

## 🔧 开发指南

### 添加新工具

1. 在 `backend_langchain/agent/tools/` 创建工具文件
2. 继承 `BaseTool` 或使用 `@tool` 装饰器
3. 注册到 Agent 工具列表

```python
from langchain_core.tools import tool

@tool("custom_search")
async def custom_search(query: str) -> str:
    """自定义搜索工具"""
    # 实现逻辑
    return result
```

### 添加新 Agent

1. 在 `backend_langchain/agent/graphs/agents/` 创建子目录
2. 实现 `build_<agent>_graph()` 函数
3. 在 `graph_factory.py` 注册

### 代码规范

- Python: PEP 8 + Black 格式化
- TypeScript: ESLint + Prettier
- Git Commit: Conventional Commits 规范

## 🚢 部署架构

```
┌─────────────────────────────────────────────────────────┐
│                      Nginx (SSL)                         │
│                    (负载均衡/静态资源)                    │
└─────────────────────┬───────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        ▼                           ▼
┌───────────────┐           ┌───────────────┐
│  Frontend     │           │   Backend     │
│   (React)     │◄─────────►│   (FastAPI)   │
│   :5173       │   REST    │   :8000       │
└───────────────┘           └───────┬───────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
┌───────────────┐           ┌───────────────┐           ┌───────────────┐
│   PostgreSQL  │           │    Redis      │           │   DashScope   │
│   :5432       │           │   :6379       │           │   (LLM API)   │
│   (主数据)     │           │   (缓存/会话)  │           │               │
└───────────────┘           └───────────────┘           └───────────────┘
```

## 📄 许可证

本项目基于 **MIT License** 开源，更多信息请查看 [LICENSE](LICENSE) 文件。

## 🤝 贡献指南

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交改动 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

**技术支持**: 如有问题，请通过 Issue 反馈或联系 maintainer@gitee.com

**更新日期**: 2024年