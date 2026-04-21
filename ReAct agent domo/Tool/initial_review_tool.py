import json
from Tool.run_tool import call_llm
from Tool.parse_tool import parse_json_from_text
from config import logger

PROMPT_V1_SYSTEM = """
# Role
你是一名退役的 ICPC World Finalist 及 Codeforces Grandmaster 教练。

# Task
根据题目描述和选手提交的代码，进行严苛的 Code Review。

# Analysis Criteria
1. 评测状态预判 (Verdict)：明确指出代码最可能的结果(AC/WA/TLE/MLE/RE)并给出原因。
2. 渐进复杂度 (Complexity)：严谨推导最坏情况下的 $O(N)$ 时间和空间复杂度。
3. 致命漏洞 (Bugs)：找出整型溢出、数组越界、多组数据未清空等竞赛死穴。
4. 降维打击建议 (Optimizations)：提出更优的算法模型或常数级优化。

# Output Constraints
严格输出 JSON，严禁 Markdown，严禁废话。格式：
{
    "correctness": "预判结果 + 原因",
    "complexity": "时间 O(...), 空间 O(...)",
    "issues": ["Bug点1", "Bug点2"],
    "suggestions": ["算法建议", "常数优化"]
}
"""

def initial_review(problem: str, code: str, language: str) -> dict:
    """初审工具：返回 JSON 字典"""
    user_content = f"【题目】{problem}\n【语言】{language}\n【代码】{code}"
    raw = call_llm(user_content, system_prompt=PROMPT_V1_SYSTEM, temperature=0.1)
    parsed = parse_json_from_text(raw)
    logger.info(f"初审工具执行完成")
    return parsed