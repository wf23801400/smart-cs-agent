# 🤖 智能客服系统 (Smart CS Agent)

多 Agent 协作的智能客服系统，基于 LangGraph + DeepSeek + Qdrant + Mem0。

## 架构

```
用户 → /chat → parse_input → dispatcher → [faq/return/complaint/general] → coordinator → 回复
                      ↑                        ↑
                 Mem0 用户记忆            Qdrant 知识检索
                                        LangSmith 全链路追踪
```

## 功能

| 层级 | 功能 | 说明 |
|------|------|------|
| 🔴 核心 | 多 Agent 意图路由 | FAQ/退货/投诉/闲聊 4 路分发 |
| 🔴 核心 | RAG 知识检索 | Qdrant + BGE Embedding 语义搜索 |
| 🔴 核心 | 跨会话用户记忆 | Mem0 自动提取用户画像 |
| 🔴 生产 | 同义问题缓存 | API 层拦截，24 倍加速 |
| 🔴 生产 | 人工兜底 | 连续不满自动升级工单 |
| 🔴 生产 | 反馈闭环 | 点赞/踩 + 好评率统计 |
| 🔴 生产 | 对话截断 | 10 轮自动摘要防爆 token |
| 🟡 运营 | 意图分布看板 | 各类意图占比 + 趋势 |
| 🟡 运营 | 成本追踪 | 按 Agent 统计 token 费用 |
| 🟡 运营 | 知识库管理 | CRUD 端点 + 自动重建索引 |

## 技术栈

| 技术 | 用途 |
|------|------|
| LangGraph | 多 Agent 图编排 |
| DeepSeek | LLM（6 个实例不同 temperature） |
| Qdrant | 向量检索 |
| 硅基流动 BGE | Embedding（1024维） |
| Mem0 | 跨会话用户记忆 |
| LangSmith | 全链路 tracing |
| FastAPI | HTTP 后端 |
| SQLite | 会话/反馈/缓存/统计 |
| React + Vite | 前端 |

## 快速启动

### 1. 环境准备

```powershell
# 克隆
git clone https://github.com/wf23801400/smart-cs-agent.git
cd smart-cs-agent

# 安装依赖
pip install -r requirements.txt

# 前端依赖（可选）
cd frontend && npm install && cd ..
```

### 2. 配置环境变量

创建 `C:\code\.env`（或项目根目录 `.env`）：

```env
DEEPSEEK_API_KEY=sk-your-key
SILICONFLOW_API_KEY=sk-your-key
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_your-key
LANGCHAIN_PROJECT=smart-cs-agent
```

### 3. 启动

```powershell
# 加载环境变量
Get-Content C:\code\.env | ForEach-Object {
    if ($_ -match '^([^#].+?)=(.+)$') {
        [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
    }
}

# 启动后端
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# 启动前端（另一个终端）
cd frontend && npm run dev
```

### 4. 访问

- 后端 Swagger：`http://localhost:8000/docs`
- 前端：`http://localhost:5173`
- LangSmith：`https://smith.langchain.com` → 项目 `smart-cs-agent`

## API 端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/chat` | POST | 客服对话 |
| `/sessions/{id}` | GET | 会话历史 |
| `/feedback` | POST | 提交反馈 |
| `/feedback/stats` | GET | 反馈统计 |
| `/stats/intents` | GET | 意图分布 |
| `/stats/intents/trend` | GET | 意图趋势 |
| `/cost/summary` | GET | 成本汇总 |
| `/cost/trend` | GET | 成本趋势 |
| `/knowledge` | GET/POST | 知识库列表/新增 |
| `/knowledge/{id}` | PUT/DELETE | 编辑/删除知识 |
| `/knowledge/reindex` | POST | 重建索引 |

## 项目结构

```
smart-cs-agent/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # LLM 配置 + LangSmith
│   ├── graph/
│   │   ├── main_graph.py    # 主 Graph 编排
│   │   ├── state.py         # AgentState 定义
│   │   └── agents/          # 4 个子 Agent
│   ├── tools/
│   │   ├── vector_store.py  # Qdrant + Embedding
│   │   ├── search_knowledge.py  # RAG 检索
│   │   ├── cost_tracker.py  # 成本追踪 callback
│   │   ├── response_cache.py    # 缓存
│   │   ├── feedback_store.py    # 反馈存储
│   │   ├── intent_stats.py      # 意图统计
│   │   ├── knowledge_manager.py # 知识库 CRUD
│   │   └── llm_utils.py     # LLM 安全包装
│   ├── memory/
│   │   ├── session_store.py # 会话记忆 SQLite
│   │   └── mem0_store.py    # Mem0 用户画像
│   └── data/
│       └── knowledge/faq.md # 知识库文档
├── frontend/                # React + Vite
├── docs/tech-stack.md       # 技术点详解
└── requirements.txt
```
