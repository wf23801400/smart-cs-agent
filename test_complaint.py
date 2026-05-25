import sys
sys.path.insert(0, "/mnt/c/Ccode/smart-cs-agent")
for mod in list(sys.modules):
    if "backend" in mod:
        del sys.modules[mod]

# 测试 complaint_graph 独立运行
from backend.graph.agents.complaint_agent import complaint_graph

state = {
    "messages": [{"role": "user", "content": "收到的耳机盒子都压扁了，里面耳机划痕一堆，你们发的是不是二手货？"}],
    "intent": "complaint",
    "order_info": {"order_id": "ORD-001", "product": "无线蓝牙耳机 Pro", "price": 299.0},
    "knowledge_results": [],
    "ticket_id": "",
    "final_reply": "",
}
result = complaint_graph.invoke(state)
print(f"severity: {result['order_info'].get('complaint_severity', '')}")
print(f"ticket_id: {result.get('ticket_id', '')}")
print(f"reply: {result.get('final_reply', '')}")
