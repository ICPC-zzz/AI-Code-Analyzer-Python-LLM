import requests
from config import Config, logger


def call_llm(user_content: str, system_prompt: str = None, temperature: float = 0.1) -> str:
    """调用星火大模型，支持 system prompt（如果提供）"""
    headers = {
        "Authorization": f"Bearer {Config.get_api_key()}",
        "Content-Type": "application/json"
    }
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_content})

    data = {
        "model": "4.0Ultra",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 4096
    }
    try:
        response = requests.post(Config.API_URL, headers=headers, json=data, timeout=(10, 120))
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"LLM API 调用失败: {e}")
        raise