"""
core/config.py
职责：仅从 .env 文件读取配置，对外暴露 settings 单例。
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 智谱 AI API Key（必填，在 .env 中配置）
    zhipu_api_key: str

    # 模型名称，默认使用 glm-4v-flash
    model_name: str = "glm-4v-flash"

    # WebSocket 服务监听端口
    server_port: int = 8000

    # 单次推理最大 token 数
    max_tokens: int = 512

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


# 全局单例，其他模块 from core.config import settings 直接使用
settings = Settings()
