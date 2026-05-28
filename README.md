# 🤖 智能客服系统 (Smart CS Agent)

多 Agent 协作的智能客服系统，基于 **LangGraph + DeepSeek + Qwen2.5-1.5B 微调 + MySQL + Qdrant + Mem0**，已做好生产部署准备。

## 🎯 系统架构

```
                          ┌──────────────────────────────────────┐
                          │           用户 (浏览器/API)            │
                          └─────────────────┬────────────────────┘
                                            │ POST /chat
                                            ▼
                          ┌──────────────────────────────────────┐
                          │        FastAPI 入口 (main.py)         │
                          │  ① 认证中间件 → X-API-Key 校验        │
                          │  ② 限流中间件 → Redis 滑动窗口        │
                          └─────────────────┬────────────────────┘
                                            │
                                            ▼
                          ┌──────────────────────────────────────┐
                          │         parse_input_node              │
                          │  提取上下文消息 + 订单号正则匹配        │
                          │  查询 Mem0 用户画像（跨会话记忆）       │
                          └─────────────────┬────────────────────┘
                                            │
                                            ▼
                          ┌──────────────────────────────────────┐
                          │       dispatcher_agent_node           │
                          │                                      │
                          │  ┌─────────────────────────────┐     │
                          │  │ 本地模型 (Qwen2.5-1.5B 微调) │     │
                          │  │   47-54ms GPU 推理           │     │
                          │  │   Logits 分类 + Softmax      │     │
                          │  └──────────────┬──────────────┘     │
                          │                 │ conf ≥ 0.4?         │
                          │            YES  │          NO         │
                          │                 ▼           ▼         │
                          │            本地结果    DeepSeek API    │
                          │                        fallback       │
                          └─────────────────┬────────────────────┘
                                            │ intent
                                            ▼
                          ┌──────────────────────────────────────┐
                          │          check_cache_node             │
                          │   同意图+相似问题 → 命中则跳过 Agent    │
                          │   未命中 → 继续路由                    │
                          └─────────────────┬────────────────────┘
                                            │
                          ┌─────────────────┼─────────────────────┐
                          ▼                 ▼                     ▼
              ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐
              │  faq_agent   │  │ return_agent │  │ complaint_agent   │
              │              │  │              │  │                  │
              │ RAG 知识检索  │  │ 订单查询     │  │ 等级评估(1-3)     │
              │ Qdrant+BGE   │  │ 退货政策匹配  │  │ 上下文感知        │
              │ 闲聊兜底     │  │ 创建工单     │  │ 创建工单          │
              └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘
                     │                 │                    │
                     │    ┌────────────┘                    │
                     │    │  general_agent ─────────────────┘
                     │    │  (问候/闲聊/转人工)
                     │    │
                     └────┼─────────────────────────────────┘
                          ▼
              ┌──────────────────────────────────────┐
              │          coordinator_node             │
              │  汇总子Agent回复                      │
              │  注入工单号 (TKT-xxx)                 │
              │  追加到对话历史                       │
              └─────────────────┬────────────────────┘
                                │
                                ▼
              ┌──────────────────────────────────────┐
              │           save_cache_node             │
              │  FAQ/general 类回复缓存到 SQLite       │
              │  后续同问题命中跳过 Agent              │
              └─────────────────┬────────────────────┘
                                │
                                ▼
              ┌──────────────────────────────────────┐
              │           返回用户 (JSON/SSE)         │
              └──────────────────────────────────────┘
```

### 意图分类混合策略

```
用户消息
   │
   ▼
┌─────────────┐    conf ≥ 0.4    ┌──────────┐
│ 本地微调模型  │ ──────────────→ │ 本地结果  │  ~50ms, 0 API 成本
│ Qwen2.5-1.5B │                 └──────────┘
└──────┬──────┘
       │ conf < 0.4（模型不确定）
       ▼
┌─────────────┐                  ┌──────────┐
│ DeepSeek API │ ──────────────→ │ API 结果  │  兜底保证准确率
│ (fallback)   │                 └──────────┘
└─────────────┘
```

**关于本地模型微调**：详见 [`docs/intent-finetune-guide.md`](docs/intent-finetune-guide.md)，包含完整的 LoRA 微调过程、数据构建、训练配置、踩坑记录。

## 🔧 功能矩阵

| 层级 | 功能 | 说明 |
|------|------|------|
| 🔴 核心 | 多 Agent 意图路由 | FAQ / 退货 / 投诉 / 闲聊 4 路分发 |
| 🔴 核心 | 本地意图分类 | Qwen2.5-1.5B LoRA 微调，47-54ms，低置信度 fallback DeepSeek |
| 🔴 核心 | RAG 知识检索 | Qdrant + BGE Embedding，26 条 FAQ 覆盖 6 类场景 |
| 🔴 核心 | 跨会话用户记忆 | Mem0 自动提取 + 更新用户画像 |
| 🔴 生产 | MySQL 持久化 | 会话/消息/订单/物流/工单/反馈 全入库 |
| 🔴 生产 | 连接池 | DBUtils 5-20 连接池，ping 保活 |
| 🔴 生产 | Redis 限流 | 原子滑动窗口，重启不丢，Redis 挂了自动降级 |
| 🔴 生产 | 结构化日志 | loguru JSON 格式 → Loki/Grafana 可检索 |
| 🔴 生产 | 异常边界 | 全图 13 处 try/except，任何节点挂了不炸 500 |
| 🔴 生产 | 同义问题缓存 | API 层拦截，避免重复调用 LLM |
| 🔴 生产 | 人工兜底 | 连续不满自动升级工单 |
| 🔴 生产 | 反馈闭环 | 点赞/踩 + 好评率统计 |
| 🔴 生产 | 对话截断 | 10 轮自动摘要防爆 token |
| 🟡 运营 | 意图分布看板 | 各类意图占比 + 趋势 |
| 🟡 运营 | 成本追踪 | 按 Agent 统计 token 费用 |
| 🟡 运营 | 知识库管理 | CRUD 端点 + 自动重建索引 |

## 📦 技术栈

| 技术 | 用途 |
|------|------|
| **LangGraph** | 多 Agent 图编排，子图嵌套 |
| **DeepSeek** | LLM（6 个实例不同 temperature）+ 意图 fallback |
| **Qwen2.5-1.5B (微调)** | 本地意图分类，LoRA + logits，87.3% 验证准确率 |
| **LLaMA-Factory** | LoRA 微调框架 |
| **FastAPI** | HTTP 后端，API Key 认证中间件 |
| **MySQL 8.0** | 核心业务数据（订单/工单/会话/消息） |
| **Redis 7** | 限流计数器 |
| **Qdrant** | 向量检索（本地文件模式） |
| **硅基流动 BGE** | Embedding（1024 维） |
| **Mem0** | 跨会话用户记忆 |
| **LangSmith** | 全链路 tracing（云端 SaaS，无需本地部署） |
| **loguru** | 结构化日志（JSON → Loki） |
| **DBUtils** | MySQL 连接池 |
| **pydantic-settings** | 多环境配置（对标 Spring Boot profiles） |
| **Docker Compose** | 容器编排，崩溃自动重启 |
| **React + Vite** | 前端（端口 5173） |

## 🚀 快速启动

> **前提**：MySQL + Redis 在 Docker 中已运行。

### 开发环境（Windows）

```powershell
# 终端 1 —— 后端 (端口 8000)
cd C:\Ccode\smart-cs-agent
C:\python\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# 终端 2 —— 前端 (端口 5173)
cd C:\Ccode\smart-cs-agent\frontend
npm run dev
```

> `.env` 已在 `main.py` 启动时自动加载（项目根 + `C:\code\.env`），无需手动设置环境变量。

### 服务地址

| 服务 | 地址 |
|------|------|
| 后端 Swagger | `http://localhost:8000/docs` |
| 健康检查 | `http://localhost:8000/health` |
| 前端页面 | `http://localhost:5173` |

### Docker 依赖确认

```powershell
# 确保 MySQL 和 Redis 运行中
docker ps --filter "name=mysql" --filter "name=smart-cs-redis"
```

### 测试请求

```powershell
curl -X POST http://localhost:8000/chat `
  -H "X-API-Key: cs-agent-prod-key-2024" `
  -H "Content-Type: application/json" `
  -d '{"message":"退货需要几天到账？","user_id":"zhangsan"}'
```

返回示例：
```json
{
  "reply": "亲，退货一般需要 3-5 个工作日到账。需要我帮您提交退货申请吗？",
  "session_id": "a1b2c3d4",
  "reply_index": 1
}
```

### 方式二：Docker Compose — 生产部署

```bash
# 1. 配置密钥
cp .env.prod .env.prod.bak
# 编辑 .env.prod，填入 DEEPSEEK_API_KEY / SILICONFLOW_API_KEY / API_KEY

# 2. 一键启动
bash deploy.sh start

# 3. 验证
curl http://114.55.101.73:8000/health

# 常用操作
bash deploy.sh status   # 运行状态
bash deploy.sh logs     # 查看日志
bash deploy.sh restart  # 重启
```

## 📡 API 端点

| 端点 | 方法 | 认证 | 功能 |
|------|------|------|------|
| `/health` | GET | 公开 | 健康检查 |
| `/docs` | GET | 公开 | Swagger 文档 |
| `/chat` | POST | API Key | 客服对话（同步） |
| `/chat/stream` | POST | API Key | 客服对话（SSE 流式） |
| `/sessions/{id}` | GET | API Key | 会话历史 |
| `/feedback` | POST | API Key | 提交反馈 |
| `/feedback/stats` | GET | API Key | 反馈统计 |
| `/stats/intents` | GET | API Key | 意图分布 |
| `/stats/intents/trend` | GET | API Key | 意图趋势 |
| `/cost/summary` | GET | API Key | 成本汇总 |
| `/cost/trend` | GET | API Key | 成本趋势 |
| `/knowledge` | GET/POST | API Key | 知识库列表/新增 |
| `/knowledge/{id}` | PUT/DELETE | API Key | 编辑/删除知识 |
| `/knowledge/reindex` | POST | API Key | 重建索引 |

所有认证端点需携带 Header：**`X-API-Key: cs-agent-prod-key-2024`**

## 📁 项目结构

```
smart-cs-agent/
├── backend/
│   ├── main.py                   # FastAPI 入口 + .env 自动加载 + 模型预热
│   ├── logger.py                 # loguru 集中日志配置
│   ├── config/                   # 多环境配置
│   │   ├── __init__.py           # 统一出口：settings + LLM 实例
│   │   └── settings.py           # pydantic BaseSettings
│   ├── middleware/
│   │   ├── auth.py               # API Key 认证（X-API-Key）
│   │   └── rate_limit.py        # Redis 滑动窗口限流
│   ├── db/
│   │   └── mysql.py              # MySQL 连接池（DBUtils）
│   ├── inference/                # 🆕 本地意图分类
│   │   ├── intent_classifier.py  # 模型加载 + logits 分类
│   │   └── model/ → 微调模型     # Windows Junction 链接
│   ├── graph/
│   │   ├── main_graph.py         # 主图编排（dispatcher + cache + router）
│   │   ├── state.py              # AgentState 类型定义
│   │   └── agents/               # 4 个子 Agent
│   │       ├── faq_agent.py      # FAQ + RAG 检索 + 闲聊
│   │       ├── return_agent.py   # 退货（查订单 + 查政策 + 建工单）
│   │       ├── complaint_agent.py # 投诉（等级评估 + 建工单）
│   │       └── general_agent.py   # 问候/闲聊/转人工
│   ├── tools/
│   │   ├── vector_store.py       # Qdrant 向量存储（嵌入模式）
│   │   ├── search_knowledge.py   # RAG 检索器
│   │   ├── search_order.py       # MySQL 订单查询
│   │   ├── create_ticket.py      # MySQL 工单创建
│   │   ├── feedback_store.py     # MySQL 反馈存储
│   │   ├── response_cache.py     # 同义问题缓存（SQLite）
│   │   ├── intent_stats.py       # 意图统计（SQLite）
│   │   ├── cost_tracker.py       # LLM 费用追踪（SQLite）
│   │   ├── llm_utils.py          # LLM 安全包装 + 重试 + 兜底
│   │   └── knowledge_manager.py  # 知识库 CRUD
│   ├── memory/
│   │   ├── session_store.py      # MySQL 会话/消息管理
│   │   └── mem0_store.py         # Mem0 用户画像
│   └── data/                     # 持久化数据
│       ├── knowledge/            # RAG 知识文档
│       ├── qdrant_db/            # Qdrant 向量索引
│       └── mem0_qdrant/          # Mem0 记忆索引
├── frontend/                     # React + Vite
│   ├── src/
│   │   ├── App.jsx               # 主界面
│   │   ├── api.js                # API 客户端（含 X-API-Key）
│   │   └── main.jsx              # 入口
│   └── vite.config.js
├── docs/
│   ├── intent-finetune-guide.md  # 🆕 意图分类模型微调全记录
│   ├── mysql_schema.sql          # MySQL 建表脚本
│   └── mysql_mock_data.sql       # 测试数据
├── model/                        # 本地微调模型（Junction → C:\code\python\models\qwen2.5-1.5b-intent-merged）
├── docker-compose.yml            # 生产容器编排
├── Dockerfile                    # 后端镜像
├── promtail-config.yml           # 日志采集配置
├── .env                          # 环境变量（不提交 Git）
└── logs/                         # 结构化日志（自动生成）
    ├── app.json.log              # INFO+ 全量日志
    └── error.json.log            # ERROR 独立日志
```

## 🔍 日志查询

日志以 JSON 格式写入 `logs/app.json.log`，每条记录包含：

```json
{
  "time": "2026-05-25T19:49:33.134+08:00",
  "level": "INFO",
  "message": "意图分类结果: return",
  "component": "dispatcher_agent",
  "intent": "return",
  "session_id": "1a6fefa4",
  "file": "main_graph.py:119"
}
```

本地查询：
```bash
# 按级别过滤
jq 'select(.record.level.name=="ERROR")' logs/app.json.log

# 按组件过滤
jq 'select(.record.extra.component=="return_agent")' logs/app.json.log

# 按 session 追踪
jq 'select(.record.extra.session_id=="1a6fefa4")' logs/app.json.log
```

Docker 部署后，Loki + Grafana 支持同等查询语法：`{component="return_agent"} |= "失败"`

## 🛡️ 生产就绪清单

- [x] MySQL 连接池（DBUtils, 5-20 连接, ping 保活）
- [x] Redis 限流（滑动窗口, 原子操作, Redis 不可用自动降级）
- [x] 本地意图分类（Qwen2.5-1.5B 微调, 47-54ms, 低置信度 DeepSeek fallback）
- [x] 结构化日志（loguru JSON, 按 session/component/intent 可检索）
- [x] 全图异常边界（13 处 try/except, 主入口兜底防止 500）
- [x] Docker Compose（backend + frontend + mysql + redis, restart=unless-stopped）
- [x] 编码统一（PYTHONIOENCODING=utf-8, MySQL utf8mb4）
- [x] API Key 认证 + 健康检查
- [x] Loki + Grafana 日志面板（`{container_name=~"smart-cs.*"}` 查询）
- [x] 同义问题缓存 + 反馈闭环
- [x] LangSmith 全链路追踪
- [ ] HTTPS / API 版本号
- [ ] 意图评估体系 / 测试用例
- [ ] 审计日志
