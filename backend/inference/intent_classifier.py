"""本地意图分类器 —— 用微调后的 Qwen2.5-1.5B 替代 DeepSeek API"""
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

MODEL_PATH = "backend/inference/model"
_labels = ["complaint", "faq", "return", "general"]
_label_ids = {}
_model = None
_tokenizer = None


def _load():
    global _model, _tokenizer, _label_ids
    if _model is not None:
        return
    _tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
    _model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH, torch_dtype=torch.bfloat16, device_map="auto", trust_remote_code=True
    )
    _model.eval()
    _label_ids = {l: _tokenizer.encode(l, add_special_tokens=False)[0] for l in _labels}


def classify(text: str, threshold: float = 0.4):
    """
    返回 (intent, confidence, scores_dict)
    confidence < threshold 时 intent 为 None（建议 fallback DeepSeek）
    """
    _load()

    instruction = (
        "判断以下用户消息的意图类别。\n意图分类标准：\n"
        "- return: 用户明确表示要退货、换货、退款（如\"帮我退掉\"\"我要退货\"\"申请退款\"）\n"
        "- faq: 询问政策、流程、时效、操作方法等知识类问题（如\"退货要几天\"\"能用微信付吗\"）\n"
        "- complaint: 投诉商品质量、服务态度、物流延误，表达不满、抱怨、失望（如\"太慢了\"\"态度好差\"\"等疯了\"）\n"
        "- general: 问候、闲聊、测试、乱码、无法归类的内容（如\"你好\"\"在吗\"\"今天天气怎么样\"）\n"
        "只输出类别名称（faq/return/complaint/general），不要其他内容。"
    )

    messages = [{"role": "user", "content": f"{instruction}\n{text}"}]
    prompt = _tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = _tokenizer(prompt, return_tensors="pt").to(_model.device)

    with torch.no_grad():
        outputs = _model(**inputs)
    logits = outputs.logits[0, -1, :]

    scores = {l: logits[_label_ids[l]].item() for l in _labels}
    # softmax
    max_logit = max(scores.values())
    exp_sum = sum(torch.exp(torch.tensor(v - max_logit)).item() for v in scores.values())
    probs = {l: torch.exp(torch.tensor(scores[l] - max_logit)).item() / exp_sum for l in _labels}

    confidence = max(probs.values())
    predicted = max(probs, key=probs.get) if confidence >= threshold else None

    return predicted, confidence, probs


def warmup():
    """预加载模型（服务启动时调用）"""
    _load()
    classify("你好")
