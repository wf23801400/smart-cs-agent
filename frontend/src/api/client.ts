const API_BASE = "/api";

/** 发送消息到后端，自动管理 session_id */
export async function sendMessage(
  message: string
): Promise<{ reply: string; session_id: string }> {
  let sessionId = localStorage.getItem("cs_session_id") || null;

  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
  });

  if (!res.ok) throw new Error(`请求失败: ${res.status}`);

  const data = await res.json();

  // 保存 session_id 到 localStorage
  if (data.session_id) {
    localStorage.setItem("cs_session_id", data.session_id);
  }

  return data;
}

/** 清除会话，重新开始 */
export function clearSession(): void {
  localStorage.removeItem("cs_session_id");
}
