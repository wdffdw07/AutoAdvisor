"""
配置管理模块 - 集中管理所有系统配置
支持从环境变量或提供默认值
"""
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


class Config:
    """系统配置类 - 单例模式"""
    
    # ==================== 服务器配置 ====================
    # WebSocket 服务端口
    SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8000"))
    
    # 日志级别
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "info")
    
    # ==================== LLM 配置 ====================
    # OpenAI API 配置（或兼容的 API）
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    
    # 模型配置
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "500"))
    
    # ==================== UI 配置 ====================
    # UI 拓扑地图文件路径
    SCHEMA_PATH: Path = Path(__file__).parent / "schema.json"
    
    # ==================== 用户配置 ====================
    # 默认用户目标（可被客户端动态覆盖）
    DEFAULT_USER_GOAL: str = os.getenv("DEFAULT_USER_GOAL", "加一个老电视特效")
    
    # ==================== 开发模式配置 ====================
    # 是否启用降级模式（LLM 失败时使用硬编码响应）
    ENABLE_FALLBACK: bool = os.getenv("ENABLE_FALLBACK", "true").lower() == "true"
    
    # 是否启用详细日志
    VERBOSE_LOGGING: bool = os.getenv("VERBOSE_LOGGING", "true").lower() == "true"
    
    # ==================== 性能配置 ====================
    # 最大并发 WebSocket 连接数
    MAX_CONNECTIONS: int = int(os.getenv("MAX_CONNECTIONS", "10"))
    
    # 截图数据大小限制（字节）
    MAX_IMAGE_SIZE: int = int(os.getenv("MAX_IMAGE_SIZE", str(10 * 1024 * 1024)))  # 10MB
    
    @classmethod
    def validate(cls) -> bool:
        """
        验证配置是否完整
        
        Returns:
            bool: 配置是否有效
        """
        issues = []
        
        # 检查必需的配置
        if not cls.OPENAI_API_KEY:
            issues.append("⚠️  OPENAI_API_KEY 未设置")
        
        if not cls.SCHEMA_PATH.exists():
            issues.append(f"⚠️  UI 拓扑地图文件不存在: {cls.SCHEMA_PATH}")
        
        # 打印配置状态
        if issues:
            print("\n" + "=" * 60)
            print("⚠️  配置警告：")
            for issue in issues:
                print(f"   {issue}")
            print("=" * 60 + "\n")
            return False
        
        return True
    
    @classmethod
    def print_config(cls):
        """打印当前配置（隐藏敏感信息）"""
        print("\n" + "=" * 60)
        print("📋 当前系统配置")
        print("=" * 60)
        print(f"🌐 服务器地址: {cls.SERVER_HOST}:{cls.SERVER_PORT}")
        print(f"🔗 WebSocket 端点: ws://{cls.SERVER_HOST}:{cls.SERVER_PORT}/ws")
        print(f"🤖 LLM 模型: {cls.LLM_MODEL}")
        print(f"🔑 API Key: {'✅ 已设置' if cls.OPENAI_API_KEY else '❌ 未设置'}")
        print(f"🌍 API Base URL: {cls.OPENAI_BASE_URL}")
        print(f"🎯 默认用户目标: {cls.DEFAULT_USER_GOAL}")
        print(f"📊 最大连接数: {cls.MAX_CONNECTIONS}")
        print(f"🔄 降级模式: {'启用' if cls.ENABLE_FALLBACK else '禁用'}")
        print(f"📝 详细日志: {'启用' if cls.VERBOSE_LOGGING else '禁用'}")
        print(f"📁 Schema 路径: {cls.SCHEMA_PATH}")
        print("=" * 60 + "\n")


# 全局配置实例
config = Config()


# 启动时验证配置
if __name__ == "__main__":
    print("🔍 配置验证:")
    config.print_config()
    
    if config.validate():
        print("✅ 配置验证通过")
    else:
        print("⚠️  配置存在问题，某些功能可能无法正常工作")
