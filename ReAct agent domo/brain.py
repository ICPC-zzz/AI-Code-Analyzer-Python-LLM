import json
import logging
import os
import re
from datetime import datetime
from typing import Dict, Any
from Tool import call_llm, parse_json_from_text, initial_review, cross_check

logger = logging.getLogger("ReActAgent")


class ReActBrain:
    def __init__(self):
        self.memory = []
        self.max_steps = 5
        self.memory_file = "memory/memory.md"
        self._ensure_memory_file()

        # 注册可用工具
        self.tools = {
            "initial_review": initial_review,
            "cross_check": cross_check,
        }

    def _ensure_memory_file(self):
        os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)
        if not os.path.exists(self.memory_file):
            with open(self.memory_file, "w", encoding="utf-8") as f:
                f.write("# ReAct Agent Memory Log\n\n")

    def _append_message(self, role: str, content: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.memory.append({"role": role, "content": content, "timestamp": timestamp})
        with open(self.memory_file, "a", encoding="utf-8") as f:
            f.write(f"\n## {timestamp} - {role}\n{content}\n---\n")

    def _build_thought_prompt(self, problem: str, code: str, language: str) -> str:
        """构建严格格式的 ReAct 提示词，强制模型输出标准格式"""
        has_initial = any("初审结果" in msg["content"] for msg in self.memory if msg["role"] == "tool_output")

        if not has_initial:
            hint = "你还没有进行初审。请先调用 initial_review 工具。"
        else:
            hint = "你已经完成了初审，现在应该调用 cross_check 工具进行复核，然后输出 FinalAnswer。"

        # 强制输出格式
        prompt = f"""你是一个 ReAct Agent，需要分析选手的代码并给出最终报告。

可用工具：
- initial_review: 输入格式为 JSON: {{"problem": "...", "code": "...", "language": "..."}}，返回 JSON 分析报告。
- cross_check: 输入格式为 JSON: {{"problem": "...", "code": "...", "language": "...", "initial_report": 初审报告对象}}，返回最终 JSON 报告。
- FinalAnswer: 直接输出最终结果的 JSON 字符串。

当前任务：
题目：{problem}
语言：{language}
代码：{code}

{hint}

**你必须严格按以下格式输出，不要有任何多余解释，不要加 Markdown 代码块，每行以关键词开头：**
Thought: <你的思考>
Action: <工具名>
Action Input: <JSON字符串>

示例（第一次调用）：
Thought: 我需要先进行初审。
Action: initial_review
Action Input: {{"problem": "{problem}", "code": "{code}", "language": "{language}"}}

示例（获得初审结果后）：
Thought: 现在可以复核初审报告。
Action: cross_check
Action Input: {{"problem": "{problem}", "code": "{code}", "language": "{language}", "initial_report": 初审结果对象}}

示例（得到最终答案后）：
Thought: 我已经得到了最终报告。
Action: FinalAnswer
Action Input: {{"correctness": "...", "complexity": "...", "issues": [...], "suggestions": [...]}}

请立即输出："""
        return prompt

    def _parse_action(self, llm_output: str):
        """强健的解析函数：提取 Action 和 Action Input，确保返回可用的字典"""
        action = None
        action_input = {}

        # 先尝试按行解析
        lines = llm_output.strip().split('\n')
        for line in lines:
            line_lower = line.lower().strip()
            if line_lower.startswith("action:"):
                action = line.split(":", 1)[1].strip()
            elif line_lower.startswith("action input:"):
                input_str = line.split(":", 1)[1].strip()
                # 使用统一的 JSON 解析工具
                try:
                    action_input = parse_json_from_text(input_str)
                except Exception:
                    # 如果解析失败，尝试用正则提取 JSON
                    json_match = re.search(r'\{.*\}', input_str, re.DOTALL)
                    if json_match:
                        try:
                            action_input = json.loads(json_match.group())
                        except:
                            action_input = {}
                    else:
                        action_input = {}

        # 默认动作处理
        if action is None:
            # 检查是否已经完成初审
            has_initial = any("初审结果" in msg["content"] for msg in self.memory if msg["role"] == "tool_output")
            if has_initial:
                action = "cross_check"
            else:
                action = "initial_review"
            logger.warning(f"未解析到 Action，默认使用: {action}")

        # 确保 action_input 是字典
        if not isinstance(action_input, dict):
            action_input = {}
        return action, action_input

    def analyze_code(self, problem: str, code: str, language: str) -> Dict[str, Any]:
        """ReAct 循环，每一步都强制解析并执行"""
        self.memory = []
        self._append_message("user", f"题目：{problem}\n语言：{language}\n代码：{code}")

        step = 0
        final_result = None

        while True:
            step += 1
            if step > self.max_steps:
                logger.error(f"超过最大步数 {self.max_steps}，当前记忆：{self.memory}")
                final_result = {"error": f"超过最大步数 {self.max_steps}"}
                break

            logger.info(f"=== ReAct Step {step} ===")

            # 1. 思考
            thought_prompt = self._build_thought_prompt(problem, code, language)
            llm_output = call_llm(thought_prompt, temperature=0.2)
            self._append_message("assistant_thought", llm_output)
            logger.debug(f"LLM 原始输出:\n{llm_output}")

            # 2. 解析动作
            action, action_input = self._parse_action(llm_output)
            logger.info(f"解析结果 -> Action: {action}, Input: {action_input}")

            # 3. 执行动作
            if action == "FinalAnswer":
                final_result = action_input
                break

            elif action in self.tools:
                tool_func = self.tools[action]
                try:
                    if action == "initial_review":
                        # 从 action_input 或默认值中获取参数
                        prob = action_input.get("problem", problem)
                        cd = action_input.get("code", code)
                        lang = action_input.get("language", language)
                        result = tool_func(problem=prob, code=cd, language=lang)
                        self._append_message("tool_output", f"初审结果: {json.dumps(result, ensure_ascii=False)}")
                        # 初审完成后，下一轮应该调用 cross_check

                    elif action == "cross_check":
                        # 获取 initial_report
                        init_report = action_input.get("initial_report")
                        if not init_report:
                            # 从记忆中提取最近的初审结果
                            for msg in reversed(self.memory):
                                if msg["role"] == "tool_output" and "初审结果" in msg["content"]:
                                    try:
                                        init_report = parse_json_from_text(msg["content"])
                                        break
                                    except:
                                        continue
                        if not init_report:
                            raise ValueError("未找到初审报告，无法进行复核")
                        result = tool_func(
                            problem=action_input.get("problem", problem),
                            code=action_input.get("code", code),
                            language=action_input.get("language", language),
                            initial_report=init_report
                        )
                        self._append_message("tool_output", f"复核结果: {json.dumps(result, ensure_ascii=False)}")
                        final_result = result
                        break  # 复核完成，直接结束

                    else:
                        # 其他预留工具
                        result = tool_func(**action_input) if isinstance(action_input, dict) else tool_func(
                            action_input)
                        self._append_message("tool_output", f"{action} 结果: {json.dumps(result, ensure_ascii=False)}")

                except Exception as e:
                    error_msg = f"工具 {action} 执行失败: {str(e)}"
                    self._append_message("observation", error_msg)
                    logger.error(error_msg)
                    # 继续循环，让模型重新思考
            else:
                self._append_message("observation", f"未知动作: {action}，可用: {list(self.tools.keys())} + FinalAnswer")

        # 确保最终结果是字典
        if isinstance(final_result, str):
            try:
                final_result = parse_json_from_text(final_result)
            except:
                final_result = {"raw_output": final_result}
        return final_result