# smart-cs-agent 架构设计

## 多Agent客服系统

### 图结构
```
parse_input → dispatcher_agent（路由Agent，LLM意图分类）
                ├→ faq_agent（FAQ子Agent，挂RAG） ← 本期实现
                ├→ return_agent（退货子Agent）    ← 接口占位
                ├→ complaint_agent（投诉子Agent） ← 接口占位
                └→ general_agent（兜底子Agent）   ← 接口占位
                     ↓
                coordinator（统一回复润色）
```

### 状态 State
- messages: 对话历史
- intent: 意图分类结果
- order_id / order_info: 订单数据
- knowledge_results: RAG检索结果
- ticket_id: 工单号
- final_reply: 最终回复

### 工具 Tools
- search_order: Mock JSON 订单查询
- search_logistics: Mock JSON 物流查询
- search_knowledge: TF-IDF RAG 检索 FAQ/政策
- create_ticket: SQLite 工单创建

### 数据存储
- order_mock.json: 模拟外部订单系统
- tickets.db (SQLite): 本系统工单
- data/knowledge/*.md: RAG 知识库

### 技术栈
- FastAPI + LangGraph + DeepSeek
- 纯 Python TF-IDF（零额外依赖）
- SQLite（Python 自带）
