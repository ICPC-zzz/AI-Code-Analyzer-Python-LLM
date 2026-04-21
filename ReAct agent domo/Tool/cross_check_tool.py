import json
from Tool.run_tool import call_llm
from Tool.parse_tool import parse_json_from_text
from config import logger

PROMPT_V2_SYSTEM = """
# Role
你是竞赛 Chief Judge。你需要复核教练的分析报告，确保没有幻觉。

# Task
1. 教练指出的复杂度是否准确？
2. 教练指出的 Bug 是否真实存在？
3. 优化建议是否符合本题数据范围？

# Output Constraints
修正报告中的错误，直接输出修正后的最终 JSON。格式必须一致。
"""

def cross_check(problem: str, code: str, language: str, initial_report: dict) -> dict:
    """复核工具：需要初审报告作为输入"""
    user_content = f"""【原题目】：{problem}
    【选手代码】：{code}
    【教练初步报告】：{json.dumps(initial_report, ensure_ascii=False)}
    """
    raw = call_llm(user_content, system_prompt=PROMPT_V2_SYSTEM, temperature=0.01)
    parsed = parse_json_from_text(raw)
    logger.info(f"复核工具执行完成")
    return parsed