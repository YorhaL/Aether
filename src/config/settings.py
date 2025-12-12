"""
服务器配置
从环境变量或 .env 文件加载配置
"""

import os
from pathlib import Path

# 尝试加载 .env 文件
try:
    from dotenv import load_dotenv

    env_file = Path(".env")
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    # 如果没有安装 python-dotenv，仍然可以从环境变量读取
    pass


class Config:
    def __init__(self) -> None:
        # 服务器配置
        self.host = os.getenv("HOST", "0.0.0.0")
        self.port = int(os.getenv("PORT", "8084"))
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.worker_processes = int(
            os.getenv("WEB_CONCURRENCY", os.getenv("GUNICORN_WORKERS", "4"))
        )

        # PostgreSQL 连接池计算相关配置
        # PG_MAX_CONNECTIONS: PostgreSQL 的 max_connections 设置（默认 100）
        # PG_RESERVED_CONNECTIONS: 为其他应用/管理工具预留的连接数（默认 10）
        self.pg_max_connections = int(os.getenv("PG_MAX_CONNECTIONS", "100"))
        self.pg_reserved_connections = int(os.getenv("PG_RESERVED_CONNECTIONS", "10"))

        # 数据库配置 - 延迟验证，支持测试环境覆盖
        self._database_url = os.getenv("DATABASE_URL")

        # JWT配置
        self.jwt_secret_key = os.getenv("JWT_SECRET_KEY", None)
        self.jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        self.jwt_expiration_hours = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

        # 加密密钥配置（独立于JWT密钥，用于敏感数据加密）
        self.encryption_key = os.getenv("ENCRYPTION_KEY", None)

        # 环境配置 - 智能检测
        # Docker 部署默认为生产环境，本地开发默认为开发环境
        is_docker = (
            os.path.exists("/.dockerenv")
            or os.environ.get("DOCKER_CONTAINER", "false").lower() == "true"
        )
        default_env = "production" if is_docker else "development"
        self.environment = os.getenv("ENVIRONMENT", default_env)

        # Redis 依赖策略（生产默认必需，开发默认可选，可通过 REDIS_REQUIRED 覆盖）
        redis_required_env = os.getenv("REDIS_REQUIRED")
        if redis_required_env is None:
            self.require_redis = self.environment not in {"development", "test", "testing"}
        else:
            self.require_redis = redis_required_env.lower() == "true"

        # CORS配置 - 使用环境变量配置允许的源
        # 格式: 逗号分隔的域名列表,如 "http://localhost:3000,https://example.com"
        cors_origins = os.getenv("CORS_ORIGINS", "")
        if cors_origins:
            self.cors_origins = [
                origin.strip() for origin in cors_origins.split(",") if origin.strip()
            ]
        else:
            # 默认: 开发环境允许本地前端,生产环境不允许任何跨域
            if self.environment == "development":
                self.cors_origins = [
                    "http://localhost:3000",
                    "http://localhost:5173",  # Vite 默认端口
                    "http://127.0.0.1:3000",
                    "http://127.0.0.1:5173",
                ]
            else:
                # 生产环境默认不允许跨域,必须显式配置
                self.cors_origins = []

        # CORS是否允许凭证(Cookie/Authorization header)
        # 注意: allow_credentials=True 时不能使用 allow_origins=["*"]
        self.cors_allow_credentials = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"

        # 管理员账户配置（用于初始化）
        self.admin_email = os.getenv("ADMIN_EMAIL", "admin@localhost")
        self.admin_username = os.getenv("ADMIN_USERNAME", "admin")

        # 管理员密码 - 必须在环境变量中设置
        admin_password_env = os.getenv("ADMIN_PASSWORD")
        if admin_password_env:
            self.admin_password = admin_password_env
        else:
            # 未设置密码，启动时会报错
            self.admin_password = ""
            self._missing_admin_password = True

        # API Key 配置
        self.api_key_prefix = os.getenv("API_KEY_PREFIX", "sk")

        # LLM API 速率限制配置（每分钟请求数）
        self.llm_api_rate_limit = int(os.getenv("LLM_API_RATE_LIMIT", "100"))
        self.public_api_rate_limit = int(os.getenv("PUBLIC_API_RATE_LIMIT", "60"))

        # 异常处理配置
        # 设置为 True 时，ProxyException 会传播到路由层以便记录 provider_request_headers
        # 设置为 False 时，使用全局异常处理器统一处理
        self.propagate_provider_exceptions = os.getenv(
            "PROPAGATE_PROVIDER_EXCEPTIONS", "true"
        ).lower() == "true"

        # 数据库连接池配置 - 智能自动调整
        # 系统会根据 Worker 数量和 PostgreSQL 限制自动计算安全值
        self.db_pool_size = int(os.getenv("DB_POOL_SIZE") or self._auto_pool_size())
        self.db_max_overflow = int(os.getenv("DB_MAX_OVERFLOW") or self._auto_max_overflow())
        self.db_pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "60"))
        self.db_pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "3600"))
        self.db_pool_warn_threshold = int(os.getenv("DB_POOL_WARN_THRESHOLD", "70"))

        # 并发控制配置
        # CONCURRENCY_SLOT_TTL: 并发槽位 TTL（秒），防止死锁
        # CACHE_RESERVATION_RATIO: 缓存用户预留比例（默认 30%）
        self.concurrency_slot_ttl = int(os.getenv("CONCURRENCY_SLOT_TTL", "600"))
        self.cache_reservation_ratio = float(os.getenv("CACHE_RESERVATION_RATIO", "0.3"))

        # HTTP 请求超时配置（秒）
        self.http_connect_timeout = float(os.getenv("HTTP_CONNECT_TIMEOUT", "10.0"))
        self.http_write_timeout = float(os.getenv("HTTP_WRITE_TIMEOUT", "60.0"))
        self.http_pool_timeout = float(os.getenv("HTTP_POOL_TIMEOUT", "10.0"))

        # 流式处理配置
        # STREAM_PREFETCH_LINES: 预读行数，用于检测嵌套错误
        # STREAM_STATS_DELAY: 统计记录延迟（秒），等待流完全关闭
        self.stream_prefetch_lines = int(os.getenv("STREAM_PREFETCH_LINES", "5"))
        self.stream_stats_delay = float(os.getenv("STREAM_STATS_DELAY", "0.1"))

        # 验证连接池配置
        self._validate_pool_config()

    def _auto_pool_size(self) -> int:
        """
        智能计算连接池大小 - 根据 Worker 数量和 PostgreSQL 限制计算

        公式: (pg_max_connections - reserved) / workers / 2
        除以 2 是因为还要预留 max_overflow 的空间
        """
        available_connections = self.pg_max_connections - self.pg_reserved_connections
        # 每个 Worker 可用的连接数（pool_size + max_overflow）
        per_worker_total = available_connections // max(self.worker_processes, 1)
        # pool_size 取总数的一半，另一半留给 overflow
        pool_size = max(per_worker_total // 2, 5)  # 最小 5 个连接
        return min(pool_size, 30)  # 最大 30 个连接

    def _auto_max_overflow(self) -> int:
        """智能计算最大溢出连接数 - 与 pool_size 相同"""
        return self.db_pool_size

    def _validate_pool_config(self) -> None:
        """验证连接池配置是否安全"""
        total_per_worker = self.db_pool_size + self.db_max_overflow
        total_all_workers = total_per_worker * self.worker_processes
        safe_limit = self.pg_max_connections - self.pg_reserved_connections

        if total_all_workers > safe_limit:
            # 记录警告（不抛出异常，避免阻止启动）
            self._pool_config_warning = (
                f"[WARN] 数据库连接池配置可能超过 PostgreSQL 限制: "
                f"{self.worker_processes} workers x {total_per_worker} connections = "
                f"{total_all_workers} > {safe_limit} (pg_max_connections - reserved). "
                f"建议调整 DB_POOL_SIZE 或 PG_MAX_CONNECTIONS 环境变量。"
            )
        else:
            self._pool_config_warning = None

    @property
    def database_url(self) -> str:
        """
        数据库 URL（延迟验证）

        在测试环境中可以通过依赖注入覆盖，而不会在导入时崩溃
        """
        if not self._database_url:
            raise ValueError(
                "DATABASE_URL environment variable is required. "
                "Example: postgresql://username:password@localhost:5432/dbname"
            )
        return self._database_url

    @database_url.setter
    def database_url(self, value: str):
        """允许在测试中设置数据库 URL"""
        self._database_url = value

    def log_startup_warnings(self) -> None:
        """
        记录启动时的安全警告
        这个方法应该在 logger 初始化后调用
        """
        from src.core.logger import logger

        # 连接池配置警告
        if hasattr(self, "_pool_config_warning") and self._pool_config_warning:
            logger.warning(self._pool_config_warning)

        # 管理员密码检查（必须在环境变量中设置）
        if hasattr(self, "_missing_admin_password") and self._missing_admin_password:
            logger.error("必须设置 ADMIN_PASSWORD 环境变量！")
            raise ValueError("ADMIN_PASSWORD environment variable must be set!")

        # JWT 密钥警告
        if not self.jwt_secret_key:
            if self.environment == "production":
                logger.error(
                    "生产环境未设置 JWT_SECRET_KEY! 这是严重的安全漏洞。"
                    "使用 'python generate_keys.py' 生成安全密钥。"
                )
            else:
                logger.warning("JWT_SECRET_KEY 未设置，将使用默认密钥（仅限开发环境）")

        # 加密密钥警告
        if not self.encryption_key and self.environment != "production":
            logger.warning(
                "ENCRYPTION_KEY 未设置，使用开发环境默认密钥。生产环境必须设置。"
            )

        # CORS 配置警告（生产环境）
        if self.environment == "production" and not self.cors_origins:
            logger.warning("生产环境 CORS 未配置，前端将无法访问 API。请设置 CORS_ORIGINS。")

    def validate_security_config(self) -> list[str]:
        """
        验证安全配置，返回错误列表
        生产环境会阻止启动，开发环境仅警告

        Returns:
            错误消息列表（空列表表示验证通过）
        """
        errors: list[str] = []

        if self.environment == "production":
            # 生产环境必须设置 JWT 密钥
            if not self.jwt_secret_key:
                errors.append(
                    "JWT_SECRET_KEY must be set in production. "
                    "Use 'python generate_keys.py' to generate a secure key."
                )
            elif len(self.jwt_secret_key) < 32:
                errors.append("JWT_SECRET_KEY must be at least 32 characters in production.")

            # 生产环境必须设置加密密钥
            if not self.encryption_key:
                errors.append(
                    "ENCRYPTION_KEY must be set in production. "
                    "Use 'python generate_keys.py' to generate a secure key."
                )

        return errors

    def __repr__(self):
        """配置信息字符串表示"""
        return f"""
Configuration:
  Server: {self.host}:{self.port}
  Log Level: {self.log_level}
  Environment: {self.environment}
"""


# 创建全局配置实例
config = Config()

# 在调试模式下记录配置（延迟到日志系统初始化后）
# 这个配置信息会在应用启动时通过日志系统输出
