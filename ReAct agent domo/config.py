import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ReActAgent")


class Config:
    API_URL = "https://spark-api-open.xf-yun.com/v1/chat/completions"

    @staticmethod
    def get_api_key():
        key = os.getenv("SPARK_API_PASSWORD")
        if not key:
            logger.error("环境变量 SPARK_API_PASSWORD 未设置")
            raise RuntimeError("Missing API Key: Please set SPARK_API_PASSWORD environment variable.")
        return key