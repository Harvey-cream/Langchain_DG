import os
from dotenv import load_dotenv
from langchain_community.chat_models import ChatTongyi

# 加载 .env 配置
load_dotenv()

# DashScope API Key（优先读取环境变量）
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "sk-4e708a1839be4179ace4e6a4d72fc638")

# 阿里云千问模型名
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-plus")


def get_qwen_chat_model(temperature: float = 0.7, *, streaming: bool = False) -> ChatTongyi:
    """获取阿里云千问 Chat 模型实例。streaming=True 时走 DashScope 流式接口，便于 on_llm_new_token 回调。"""
    return ChatTongyi(
        model=QWEN_MODEL,
        dashscope_api_key=DASHSCOPE_API_KEY,
        temperature=temperature,
        streaming=streaming,
    )
