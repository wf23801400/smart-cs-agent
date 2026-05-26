# 🤖 智能客服系统 (Smart CS Agent)

多 Agent 协作的智能客服系统，基于 **LangGraph + DeepSeek + MySQL + Qdrant + Mem0**，已做好生产部署准备。

## 🎯 核心设计

```
用户 → /chat → [认证] → [限流] → parse_input → dispatcher → router
                                                    ↓
                                   ┌─────────────────┼─────────────────┐
                                   ↓                 ↓                  ↓
                              faq_agent         return_agent      complaint_agent
                           (RAG + 闲聊)       (查订单+工单)       (等级评估+工单)
                                   ↓                 ↓                  ↓
                                   └─────────────────┼─────────────────┘
                                                     ↓
                                               coordinator → 回复
```

## 🔧 功能矩阵

| 层级 | 功能 | 说明 |
|------|------|------|
| 🔴 核心 | 多 Agent 意图路由 | FAQ / 退货 / 投诉 / 闲聊 4 路分发 |
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
| **DeepSeek** | LLM（6 个实例不同 temperature） |
| **FastAPI** | HTTP 后端，API Key 认证中间件 |
| **MySQL 8.0** | 核心业务数据（订单/工单/会话/消息） |
| **Redis 7** | 限流计数器 |
| **Qdrant** | 向量检索（本地文件模式） |
| **硅基流动 BGE** | Embedding（1024 维） |
| **Mem0** | 跨会话用户记忆 |
| **LangSmith** | 全链路 tracing |
| **loguru** | 结构化日志（JSON → Loki） |
| **DBUtils** | MySQL 连接池 |
| **pydantic-settings** | 多环境配置（对标 Spring Boot profiles） |
| **Docker Compose** | 容器编排，崩溃自动重启 |

## 🚀 快速启动

### 方式一：Docker Compose — 生产部署（推荐）

```bash
# 1. 配置密钥（只需填 3 个）
cp .env.prod .env.prod.bak
# 编辑 .env.prod，填入：
#   DEEPSEEK_API_KEY=sk-xxx
#   SILICONFLOW_API_KEY=sk-xxx
#   API_KEY=your-secret-key

# 2. 一键启动
bash deploy.sh start

# 3. 验证
curl http://localhost:8000/health
# → {"status":"ok","env":"prod"}
```

**包含什么：** CS Agent + MySQL 8.0 + Redis 7，三容器自动组网。

| 服务 | 端口 | 说明 |
|------|------|------|
| CS Agent | `8000` | FastAPI + Gunicorn (4 workers) |
| MySQL | `3306` | 会话/订单/反馈数据 |
| Redis | `6379` | IP 限流计数器 |

更多操作：
```bash
bash deploy.sh status   # 查看运行状态
bash deploy.sh logs     # 查看日志
bash deploy.sh restart  # 重启
```

### 方式二：本地开发

```powershell
# 前提：MySQL + Redis 已启动（Docker 或本地）

# 安装依赖
pip install -r requirements.txt

# 启动后端（自动读取 .env.dev）
.\start_backend.ps1

# 或手动指定环境
$env:APP_ENV="test"
C:\python\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8002
```

### 多环境配置

对标 Spring Boot `application-{profile}.yml`：

| 环境 | 命令 | 端口 | 热重载 | 认证 Key |
|------|------|------|--------|----------|
| dev | `.\start_backend.ps1` | 8001 | ✅ | `cs-agent-dev-key-2024` |
| test | `$env:APP_ENV="test"` | 8002 | ❌ | `cs-agent-test-key-2024` |
| prod | `$env:APP_ENV="prod"` | 8000 | ❌ | 运维注入 |

所有配置集中在 `backend/config/settings.py`，通过 `APP_ENV` 选择 `.env.{env}` 文件。
模块中使用 `from backend.config import settings` 获取配置项（如 `settings.MYSQL_HOST`）。

### 测试

```powershell
# 同步对话
curl -X POST http://localhost:8001/chat `
  -H "X-API-Key: cs-agent-dev-key-2024" `
  -H "Content-Type: application/json" `
  -d '{"message":"退货需要几天到账？","user_id":"zhangsan"}'

# 流式对话（SSE）
curl -N -X POST http://localhost:8001/chat/stream `
  -H "X-API-Key: cs-agent-dev-key-2024" `
  -H "Content-Type: application/json" `
  -d '{"message":"退货需要几天到账？","user_id":"zhangsan"}'
```

返回示例：
```json
{
  "reply": "亲，看到您说耳机有问题想退货...工单号 TKT-20260525-001",
  "session_id": "a1b2c3d4",
  "reply_index": 1
}
```

## 📡 API 端点

| 端点 | 方法 | 认证 | 功能 |
|------|------|------|------|
| `/health` | GET | 公开 | 健康检查 |
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

所有认证端点需携带 Header：`X-API-Key: <环境对应 Key>`（dev=`cs-agent-dev-key-2024`）

## 📁 项目结构

```
smart-cs-agent/
├── Dockerfile                   # 后端镜像
├── docker-compose.yml           # 容器编排（backend + redis + loki + promtail）
├── promtail-config.yml          # 日志采集配置
├── .env.dev                     # 开发环境配置
├── .env.test                    # 测试环境配置
├── .env.prod                    # 生产环境配置（密钥由运维注入）
├── requirements.txt
├── backend/
│   ├── logger.py                # loguru 集中日志配置
│   ├── main.py                  # FastAPI 入口 + 异常兜底
│   ├── config/                  # 多环境配置（对标 Spring Boot profiles）
│   │   ├── __init__.py           # 统一出口：settings + LLM 实例
│   │   └── settings.py           # pydantic BaseSettings 集中配置
│   ├── middleware/
│   │   ├── auth.py              # API Key 认证
│   │   └── rate_limit.py        # Redis 滑动窗口限流
│   ├── db/
│   │   └── mysql.py             # MySQL 连接池（DBUtils）
│   ├── graph/
│   │   ├── main_graph.py        # 主图编排 + 异常边界
│   │   ├── state.py             # AgentState 类型定义
│   │   └── agents/              # 4 个子 Agent
│   │       ├── faq_agent.py     # FAQ + 闲聊
│   │       ├── return_agent.py  # 退货（查订单+查政策+建工单）
│   │       └── complaint_agent.py # 投诉（等级评估+建工单）
│   ├── tools/
│   │   ├── vector_store.py      # Qdrant 向量存储
│   │   ├── search_knowledge.py  # RAG 检索器
│   │   ├── search_order.py      # MySQL 订单查询
│   │   ├── create_ticket.py     # MySQL 工单创建
│   │   ├── feedback_store.py    # MySQL 反馈存储
│   │   ├── response_cache.py    # 同义问题缓存（SQLite）
│   │   ├── intent_stats.py      # 意图统计（SQLite）
│   │   ├── cost_tracker.py      # LLM 费用追踪（SQLite）
│   │   └── llm_utils.py         # LLM 安全包装 + 重试
│   ├── memory/
│   │   ├── session_store.py     # MySQL 会话/消息
│   │   └── mem0_store.py        # Mem0 用户画像
│   └── data/                    # 持久化数据（Docker 卷挂载）
│       ├── knowledge/           # RAG 知识文档
│       ├── qdrant_db/           # 向量索引
│       └── mem0_qdrant/         # Mem0 记忆索引
├── docs/
│   ├── mysql_schema.sql         # MySQL 建表脚本
│   └── mysql_mock_data.sql      # 测试数据
├── frontend/                    # React + Vite（可选）
└── logs/                        # 结构化日志（自动生成）
    ├── app.json.log             # INFO+ 全量日志
    └── error.json.log           # ERROR 独立日志
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
- [x] 结构化日志（loguru JSON, 按 session/component/intent 可检索）
- [x] 全图异常边界（13 处 try/except, 主入口兜底防止 500）
- [x] Docker Compose（backend + redis + loki + promtail, restart=unless-stopped）
- [x] 编码统一（PYTHONIOENCODING=utf-8, MySQL utf8mb4）
- [x] API Key 认证 + 健康检查
- [x] Loki + Grafana 日志面板（`{container_name=~"smart-cs.*"}` 查询）
- [ ] HTTPS / API 版本号
- [ ] 意图评估体系 / 测试用例
- [ ] 审计日志
