import requests
import json
import os
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional
import uvicorn

# ================= 1. 系统配置与日志系统 =================
# 配置日志：确保生产环境下也能清晰追踪请求链路
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("CodeAnalyzer")


class Config:
    """
    配置管理类：解决环境变量加载时序问题。
    只有在真正发起 API 请求时才会读取环境变量，确保容器或 IDE 注入的环境变量生效。
    """

    @staticmethod
    def get_api_key():
        key = os.getenv("SPARK_API_PASSWORD")
        if not key:
            logger.error("环境变量 SPARK_API_PASSWORD 未检测到！")
            raise RuntimeError("Missing API Key: Please set SPARK_API_PASSWORD environment variable.")
        return key

    API_URL = "https://spark-api-open.xf-yun.com/v1/chat/completions"


# ================= 2. 数据模型 =================
class CodeRequest(BaseModel):
    problem: str
    code: str
    language: str


class UnifiedResponse(BaseModel):
    """统一 API 返回格式"""
    status: str
    data: Optional[Any] = None
    message: Optional[str] = None


# ================= 3. 核心工具函数 =================
def chat(question: str, temperature: float = 0.1):
    """底层 API 调用逻辑（含延迟配置加载）"""
    headers = {
        "Authorization": f"Bearer {Config.get_api_key()}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "4.0Ultra",
        "messages": [{"role": "user", "content": question}],
        "temperature": temperature,
        "max_tokens": 4096
    }
    try:
        response = requests.post(Config.API_URL, headers=headers, json=data, timeout=(10, 120))
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"星火大模型 API 调用失败: {str(e)}")
        raise e


def parse_result(raw_response: str):
    """强鲁棒性 JSON 解析逻辑"""
    try:
        # 针对大模型可能带有的 Markdown 标签进行预清洗
        clean_res = raw_response.strip()
        start_idx = clean_res.find('{')
        end_idx = clean_res.rfind('}')

        if start_idx != -1 and end_idx != -1:
            json_str = clean_res[start_idx:end_idx + 1]
            return json.loads(json_str)
        raise ValueError("模型返回内容中未包含有效的 JSON 结构")
    except Exception as e:
        logger.error(f"解析大模型输出失败。原始输出片段: {raw_response[:200]}")
        raise e


# ================= 4. FastAPI 核心接口 =================
app = FastAPI(title="ACM Code Analyzer Pro", version="2.0.0")


@app.post("/analyze", response_model=UnifiedResponse)
def analyze(req: CodeRequest):
    # 记录请求元数据，提升系统可观测性
    logger.info(f"--- 接收分析请求 | 语言: {req.language} | 题目长度: {len(req.problem)} chars ---")

    try:
        # --- 阶段 1: ICPC 专家初审 ---
        logger.info("阶段 1: 正在生成初次分析报告...")
        prompt_v1 = f"""
        # Role
        你是一名退役的 ICPC World Finalist 及 Codeforces Grandmaster 教练。

        # Task
        根据题目描述和选手提交的代码，进行严苛的 Code Review。

        # Analysis Criteria
        1. 评测状态预判 (Verdict)：明确指出代码最可能的结果(AC/WA/TLE/MLE/RE)并给出原因。
        2. 渐进复杂度 (Complexity)：严谨推导最坏情况下的 $O(N)$ 时间和空间复杂度。
        3. 致命漏洞 (Bugs)：找出整型溢出、数组越界、多组数据未清空等竞赛死穴。
        4. 降维打击建议 (Optimizations)：提出更优的算法模型或常数级优化。

        # Input Data
        【题目】{req.problem}
        【语言】{req.language}
        【代码】{req.code}

        # Output Constraints
        严格输出 JSON，严禁 Markdown，严禁废话。格式：
        {{
            "correctness": "预判结果 + 原因",
            "complexity": "时间 O(...), 空间 O(...)",
            "issues": ["Bug点1", "Bug点2"],
            "suggestions": ["算法建议", "常数优化"]
        }}
        """
        raw_v1 = chat(prompt_v1, temperature=0.1)
        data_v1 = parse_result(raw_v1)

        # --- 阶段 2: 主裁判 Self-Reflection (自检) ---
        logger.info("阶段 2: 启动 Chief Judge 二次校验...")
        prompt_v2 = f"""
        # Role
        你是竞赛 Chief Judge。你需要复核教练的分析报告，确保没有幻觉。

        # Input Data
        【原题目】：{req.problem}
        【选手代码】：{req.code}
        【教练初步报告】：{json.dumps(data_v1, ensure_ascii=False)}

        # Task
        1. 教练指出的复杂度是否准确？
        2. 教练指出的 Bug 是否真实存在？
        3. 优化建议是否符合本题数据范围？

        # Output Constraints
        修正报告中的错误，直接输出修正后的最终 JSON。格式必须一致。
        """
        raw_v2 = chat(prompt_v2, temperature=0.01)  # 自检使用更低温度保证稳定性
        final_data = parse_result(raw_v2)

        logger.info("分析请求处理成功。")
        return {
            "status": "success",
            "data": final_data,
            "message": None
        }

    except Exception as e:
        logger.error(f"分析请求处理失败: {str(e)}")
        # 统一错误返回格式
        return {
            "status": "error",
            "data": None,
            "message": f"服务器内部错误: {str(e)}"
        }


# ================= 5. 启动入口 =================
if __name__ == "__main__":
    # 提醒：请确保在 PyCharm 的 Run Configuration 或系统环境变量中设置了 SPARK_API_PASSWORD
    uvicorn.run(app, host="127.0.0.1", port=8000)