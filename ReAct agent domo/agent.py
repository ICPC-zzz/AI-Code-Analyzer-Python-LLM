from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, Any
import uvicorn
import logging
from brain import ReActBrain

logger = logging.getLogger("ReActAgent")
app = FastAPI(title="ReAct Code Analyzer", version="3.0.0")

agent = ReActBrain()

class CodeRequest(BaseModel):
    problem: str
    code: str
    language: str

class UnifiedResponse(BaseModel):
    status: str
    data: Optional[Any] = None
    message: Optional[str] = None

@app.post("/analyze", response_model=UnifiedResponse)
def analyze_endpoint(req: CodeRequest):
    logger.info(f"收到请求: language={req.language}, problem_len={len(req.problem)}")
    try:
        result = agent.analyze_code(req.problem, req.code, req.language)
        return UnifiedResponse(status="success", data=result, message=None)
    except Exception as e:
        logger.error(f"分析失败: {e}", exc_info=True)
        return UnifiedResponse(status="error", data=None, message=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)