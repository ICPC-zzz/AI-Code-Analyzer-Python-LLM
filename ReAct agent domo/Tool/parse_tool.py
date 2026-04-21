import json
import logging

logger = logging.getLogger("ReActAgent")


def parse_json_from_text(raw_response: str) -> dict:
    """
    从 LLM 返回的文本中提取 JSON 对象。
    支持去除 Markdown 代码块标记。
    """
    try:
        clean = raw_response.strip()
        # 去除可能的 ```json ... ``` 包裹
        if clean.startswith("```json"):
            clean = clean[7:]
        if clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()

        # 找到第一个 { 和最后一个 }
        start = clean.find('{')
        end = clean.rfind('}')
        if start != -1 and end != -1:
            json_str = clean[start:end + 1]
            return json.loads(json_str)
        raise ValueError("No JSON object found")
    except Exception as e:
        logger.error(f"JSON 解析失败: {e}\n原始文本前200字符: {raw_response[:200]}")
        raise