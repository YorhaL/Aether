"""
数据库模型定义
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import Optional

import bcrypt
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from ..config import config
from ..core.enums import ProviderBillingType, UserRole

Base = declarative_base()


class User(Base):
    """用户模型"""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(
        Enum(
            UserRole,
            name="userrole",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=UserRole.USER,
        nullable=False,
    )

    # 访问限制（NULL 表示不限制，允许访问所有资源）
    allowed_providers = Column(JSON, nullable=True)  # 允许使用的提供商 ID 列表
    allowed_endpoints = Column(JSON, nullable=True)  # 允许使用的端点 ID 列表
    allowed_models = Column(JSON, nullable=True)  # 允许使用的模型名称列表

    # Key 能力配置
    model_capability_settings = Column(JSON, nullable=True)  # 用户针对特定模型的能力配置
    # 示例: {"claude-sonnet-4-20250514": {"cache_1h": true}}

    # 配额管理
    quota_usd = Column(Float, nullable=True)  # 美元配额(NULL 表示无限制)
    used_usd = Column(Float, default=0.0)  # 当前周期已使用美元
    total_usd = Column(Float, default=0.0)  # 累积消费总额

    # 状态
    is_active = Column(Boolean, default=True, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)

    # 时间戳
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # 关系 - CASCADE delete: 让数据库处理级联删除
    api_keys = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")
    preferences = relationship(
        "UserPreference", back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    quotas = relationship(
        "UserQuota", back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    announcement_reads = relationship(
        "AnnouncementRead",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # 关系 - SET NULL: 保留历史记录，让数据库处理 SET NULL
    usage_records = relationship("Usage", back_populates="user", passive_deletes=True)
    authored_announcements = relationship(
        "Announcement",
        back_populates="author",
        foreign_keys="Announcement.author_id",
        passive_deletes=True,
    )
    audit_logs = relationship("AuditLog", back_populates="user", passive_deletes=True)

    def set_password(self, password: str):
        """设置密码"""
        self.password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode(
            "utf-8"
        )

    def verify_password(self, password: str) -> bool:
        """验证密码"""
        if not self.password_hash:
            return False
        return bcrypt.checkpw(password.encode("utf-8"), self.password_hash.encode("utf-8"))


class ApiKey(Base):
    """API密钥模型"""

    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    key_hash = Column(String(64), unique=True, index=True, nullable=False)  # API密钥的SHA256哈希
    key_encrypted = Column(Text, nullable=True)  # 加密后的完整密钥，用于查看
    name = Column(String(100), nullable=True)  # 密钥名称，便于用户管理

    # 使用统计
    total_requests = Column(Integer, default=0)
    total_cost_usd = Column(Float, default=0.0)

    # 余额管理（仅用于独立余额 Key）
    balance_used_usd = Column(Float, default=0.0)  # 已使用余额（USD），用于统计
    current_balance_usd = Column(Float, nullable=True)  # 当前余额（USD），NULL 表示无限制
    is_standalone = Column(
        Boolean, default=False, nullable=False
    )  # 是否为独立余额 Key（给非注册用户使用）

    # 访问限制（NULL 表示不限制，允许访问所有资源）
    allowed_providers = Column(JSON, nullable=True)  # 允许使用的提供商 ID 列表
    allowed_endpoints = Column(JSON, nullable=True)  # 允许使用的端点 ID 列表
    allowed_api_formats = Column(JSON, nullable=True)  # 允许使用的 API 格式列表
    allowed_models = Column(JSON, nullable=True)  # 允许使用的模型名称列表
    rate_limit = Column(Integer, default=100)  # 每分钟请求限制
    concurrent_limit = Column(Integer, default=5, nullable=True)  # 并发请求限制

    # Key 能力配置
    force_capabilities = Column(JSON, nullable=True)  # 强制开启的能力
    # 示例: {"cache_1h": true} - 强制所有支持的模型都用 1h 缓存

    # 状态
    is_active = Column(Boolean, default=True, nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)  # 过期时间
    auto_delete_on_expiry = Column(Boolean, default=False, nullable=False)  # 过期后是否自动删除

    # 时间戳
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # 关系
    user = relationship("User", back_populates="api_keys")
    usage_records = relationship("Usage", back_populates="api_key")
    provider_mappings = relationship(
        "ApiKeyProviderMapping", back_populates="api_key", cascade="all, delete-orphan"
    )

    @staticmethod
    def generate_key() -> str:
        """生成API密钥（使用加密安全的随机数生成器）"""
        import string

        # 只使用字母和数字，避免特殊字符
        alphabet = string.ascii_letters + string.digits
        random_part = "".join(secrets.choice(alphabet) for _ in range(32))
        return f"{config.api_key_prefix}-{random_part}"

    @staticmethod
    def hash_key(api_key: str) -> str:
        """对API密钥进行哈希"""
        return hashlib.sha256(api_key.encode()).hexdigest()

    def set_key(self, api_key: str) -> None:
        """
        设置API密钥(用于测试和数据初始化)

        Args:
            api_key: 明文API密钥

        注意: 此方法会设置 key_hash 和 key_encrypted
        """
        from src.core.crypto import crypto_service

        # 设置哈希(用于验证)
        self.key_hash = self.hash_key(api_key)

        # 设置加密的完整密钥(用于显示和管理)
        self.key_encrypted = crypto_service.encrypt(api_key)

    def verify_key(self, api_key: str) -> bool:
        """
        验证API密钥是否匹配(用于测试)

        Args:
            api_key: 明文API密钥

        Returns:
            bool: 密钥是否匹配
        """
        return self.key_hash == self.hash_key(api_key)

    def get_display_key(self) -> str:
        """获取用于显示的脱敏密钥（前缀...后4位）"""
        from src.core.crypto import crypto_service

        if self.key_encrypted:
            try:
                # 使用静默模式，避免在显示场景打印错误日志
                full_key = crypto_service.decrypt(self.key_encrypted, silent=True)
                # 格式：sk-SpJ3y...sdf4
                prefix = full_key[:10] if len(full_key) >= 10 else full_key[: len(full_key) // 2]
                suffix = full_key[-4:] if len(full_key) >= 4 else ""
                return f"{prefix}...{suffix}"
            except Exception:
                pass
        # 降级：无法解密时返回占位符
        return "sk-****"


class Usage(Base):
    """使用记录模型"""

    __tablename__ = "usage"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    api_key_id = Column(String(36), ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True)

    # 请求信息
    request_id = Column(String(100), unique=True, index=True, nullable=False)
    provider = Column(String(100), nullable=False)
    model = Column(String(100), nullable=False)
    target_model = Column(String(100), nullable=True, comment="映射后的目标模型名（若无映射则为空）")

    # Provider 侧追踪信息（记录最终成功的 Provider/Endpoint/Key）
    provider_id = Column(String(36), ForeignKey("providers.id", ondelete="SET NULL"), nullable=True)
    provider_endpoint_id = Column(
        String(36), ForeignKey("provider_endpoints.id", ondelete="SET NULL"), nullable=True
    )
    provider_api_key_id = Column(
        String(36), ForeignKey("provider_api_keys.id", ondelete="SET NULL"), nullable=True
    )

    # Token统计
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)

    # 缓存相关 tokens (for Claude models)
    cache_creation_input_tokens = Column(Integer, default=0)
    cache_read_input_tokens = Column(Integer, default=0)

    # 成本计算
    input_cost_usd = Column(Float, default=0.0)
    output_cost_usd = Column(Float, default=0.0)
    cache_cost_usd = Column(Float, default=0.0)  # 总缓存成本（兼容旧数据）
    cache_creation_cost_usd = Column(Float, default=0.0)  # 缓存创建成本
    cache_read_cost_usd = Column(Float, default=0.0)  # 缓存读取成本
    request_cost_usd = Column(Float, default=0.0)  # 按次计费成本
    total_cost_usd = Column(Float, default=0.0)

    # 真实成本计算（表面成本 × 倍率）
    actual_input_cost_usd = Column(Float, default=0.0)  # 真实输入成本
    actual_output_cost_usd = Column(Float, default=0.0)  # 真实输出成本
    actual_cache_creation_cost_usd = Column(Float, default=0.0)  # 真实缓存创建成本
    actual_cache_read_cost_usd = Column(Float, default=0.0)  # 真实缓存读取成本
    actual_request_cost_usd = Column(Float, default=0.0)  # 真实按次计费成本
    actual_total_cost_usd = Column(Float, default=0.0)  # 真实总成本
    rate_multiplier = Column(Float, default=1.0)  # 使用的倍率（来自 ProviderAPIKey）

    # 历史价格记录（每1M tokens的美元价格，记录请求时的实际价格）
    input_price_per_1m = Column(Float, nullable=True)  # 输入单价
    output_price_per_1m = Column(Float, nullable=True)  # 输出单价
    cache_creation_price_per_1m = Column(Float, nullable=True)  # 缓存创建单价
    cache_read_price_per_1m = Column(Float, nullable=True)  # 缓存读取单价
    price_per_request = Column(Float, nullable=True)  # 按次计费单价（历史记录）

    # 请求详情
    request_type = Column(String(50))  # chat, completion, embedding等
    api_format = Column(String(50), nullable=True)  # API 格式: CLAUDE, OPENAI 等
    is_stream = Column(Boolean, default=False)  # 是否为流式请求
    status_code = Column(Integer)
    error_message = Column(Text, nullable=True)
    response_time_ms = Column(Integer)  # 响应时间（毫秒）

    # 请求状态追踪
    # pending: 请求开始处理中
    # streaming: 流式响应进行中
    # completed: 请求成功完成
    # failed: 请求失败
    status = Column(String(20), default="completed", nullable=False, index=True)

    # 完整请求和响应记录
    request_headers = Column(JSON, nullable=True)  # 客户端请求头
    request_body = Column(JSON, nullable=True)  # 请求体（7天内未压缩）
    provider_request_headers = Column(JSON, nullable=True)  # 向提供商发送的请求头
    response_headers = Column(JSON, nullable=True)  # 响应头
    response_body = Column(JSON, nullable=True)  # 响应体（7天内未压缩）

    # 压缩存储字段（7天后自动压缩到这里）
    request_body_compressed = Column(LargeBinary, nullable=True)  # gzip压缩的请求体
    response_body_compressed = Column(LargeBinary, nullable=True)  # gzip压缩的响应体

    # 元数据
    request_metadata = Column(JSON, nullable=True)  # 存储额外信息

    # 时间戳
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # 关系
    user = relationship("User", back_populates="usage_records")
    api_key = relationship("ApiKey", back_populates="usage_records")
    provider_obj = relationship("Provider")  # 使用 provider_obj 避免与 provider 字段名冲突
    provider_endpoint = relationship("ProviderEndpoint")
    provider_api_key = relationship("ProviderAPIKey")

    def get_request_body(self):
        """获取请求体（自动解压）"""
        if self.request_body is not None:
            return self.request_body
        if self.request_body_compressed is not None:
            from src.utils.compression import decompress_json

            return decompress_json(self.request_body_compressed)
        return None

    def get_response_body(self):
        """获取响应体（自动解压）"""
        if self.response_body is not None:
            return self.response_body
        if self.response_body_compressed is not None:
            from src.utils.compression import decompress_json

            return decompress_json(self.response_body_compressed)
        return None


class UserQuota(Base):
    """用户配额历史记录"""

    __tablename__ = "user_quotas"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # 配额类型
    quota_type = Column(String(50), nullable=False)  # monthly, daily, custom

    # 配额值
    quota_usd = Column(Float, nullable=False)

    # 时间范围
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)

    # 使用情况
    used_usd = Column(Float, default=0.0)

    # 状态
    is_active = Column(Boolean, default=True)

    # 时间戳
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # 关系
    user = relationship("User", back_populates="quotas")


class SystemConfig(Base):
    """系统配置表"""

    __tablename__ = "system_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(JSON, nullable=False)
    description = Column(Text, nullable=True)

    # 时间戳
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class Provider(Base):
    """提供商配置表"""

    __tablename__ = "providers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)  # 提供商唯一标识
    display_name = Column(String(100), nullable=False)  # 显示名称
    description = Column(Text, nullable=True)  # 提供商描述
    website = Column(String(500), nullable=True)  # 主站网站

    # 计费类型配置
    billing_type = Column(
        Enum(
            ProviderBillingType,
            name="providerbillingtype",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=ProviderBillingType.PAY_AS_YOU_GO,
        nullable=False,
    )

    # 月卡配置
    monthly_quota_usd = Column(Float, nullable=True)  # 月卡总额度
    monthly_used_usd = Column(Float, default=0.0)  # 本月已用额度
    quota_reset_day = Column(Integer, default=30)  # 额度重置周期(天数)，例如：7=每周，30=每月
    quota_last_reset_at = Column(DateTime(timezone=True), nullable=True)  # 上次额度重置时间
    quota_expires_at = Column(DateTime(timezone=True), nullable=True)  # 月卡过期时间

    # RPM限制：NULL=无限制，0=禁止请求
    rpm_limit = Column(Integer, nullable=True)  # 每分钟请求数限制（NULL=无限制，0=禁止请求）
    rpm_used = Column(Integer, default=0)  # 当前分钟已用请求数
    rpm_reset_at = Column(DateTime(timezone=True), nullable=True)  # RPM重置时间

    # 提供商优先级 (数字越小越优先，用于提供商优先模式下的 Provider 排序)
    # 0-10: 急需消耗(如即将过期的月卡)
    # 11-50: 优先消耗(月卡)
    # 51-100: 正常消费(按量付费)
    # 101+: 备用(高成本或限制严格的)
    provider_priority = Column(Integer, default=100)

    # 状态
    is_active = Column(Boolean, default=True, nullable=False)

    # 限制
    rate_limit = Column(Integer, nullable=True)  # 每分钟请求限制
    concurrent_limit = Column(Integer, nullable=True)  # 并发请求限制

    # 配置
    config = Column(JSON, nullable=True)  # 额外配置（如Azure deployment name等）

    # 时间戳
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # 关系
    models = relationship("Model", back_populates="provider", cascade="all, delete-orphan")
    endpoints = relationship(
        "ProviderEndpoint", back_populates="provider", cascade="all, delete-orphan"
    )
    api_key_mappings = relationship(
        "ApiKeyProviderMapping", back_populates="provider", cascade="all, delete-orphan"
    )
    usage_tracking = relationship(
        "ProviderUsageTracking", back_populates="provider", cascade="all, delete-orphan"
    )


class ProviderEndpoint(Base):
    """提供商端点 - 一个提供商可以有多个 API 格式端点"""

    __tablename__ = "provider_endpoints"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    provider_id = Column(String(36), ForeignKey("providers.id", ondelete="CASCADE"), nullable=False)

    # API 格式和配置
    api_format = Column(String(50), nullable=False)  # 存储 APIFormat 枚举值的字符串
    base_url = Column(String(500), nullable=False)

    # 请求配置
    headers = Column(JSON, nullable=True)  # 额外请求头
    timeout = Column(Integer, default=300)  # 超时（秒）
    max_retries = Column(Integer, default=3)  # 最大重试次数

    # 限制
    max_concurrent = Column(
        Integer, nullable=True, default=None
    )  # 该端点的最大并发数（NULL=不限制）
    rate_limit = Column(Integer, nullable=True)  # 每分钟请求限制

    # 状态
    is_active = Column(Boolean, default=True, nullable=False)

    # 路径配置
    custom_path = Column(
        String(200), nullable=True
    )  # 自定义请求路径，为空则使用 API 格式的默认路径

    # 额外配置
    config = Column(JSON, nullable=True)  # 端点特定配置（不推荐使用，优先使用专用字段）

    # 时间戳
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # 关系
    provider = relationship("Provider", back_populates="endpoints")
    api_keys = relationship(
        "ProviderAPIKey", back_populates="endpoint", cascade="all, delete-orphan"
    )

    # 唯一约束和索引在表定义后
    __table_args__ = (
        UniqueConstraint("provider_id", "api_format", name="uq_provider_api_format"),
        Index("idx_endpoint_format_active", "api_format", "is_active"),
    )


class GlobalModel(Base):
    """全局统一模型定义 - 包含价格和能力配置

    设计原则:
    - 定义模型的基本信息和价格配置（价格为必填项）
    - Provider 级别的 Model 可以覆盖这些默认值
    - 如果 Model 的价格/能力字段为空，则使用 GlobalModel 的值
    """

    __tablename__ = "global_models"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)  # 统一模型名（唯一）
    display_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # 模型元数据
    icon_url = Column(String(500), nullable=True)
    official_url = Column(String(500), nullable=True)  # 官方文档链接

    # 按次计费配置（每次请求的固定费用，美元）- 可选，与按 token 计费叠加
    default_price_per_request = Column(Float, nullable=True, default=None)  # 每次请求固定费用

    # 统一阶梯计费配置（JSON格式）- 必填
    # 固定价格也用单阶梯表示: {"tiers": [{"up_to": null, "input_price_per_1m": X, ...}]}
    # 结构示例:
    # {
    #     "tiers": [
    #         {
    #             "up_to": 128000,  # 阶梯上限（tokens），null 表示无上限
    #             "input_price_per_1m": 2.50,
    #             "output_price_per_1m": 10.00,
    #             "cache_creation_price_per_1m": 3.75,  # 可选
    #             "cache_read_price_per_1m": 0.30,      # 可选
    #             "cache_ttl_pricing": [                 # 可选：按缓存时长分价格
    #                 {"ttl_minutes": 5, "cache_read_price_per_1m": 0.30},
    #                 {"ttl_minutes": 60, "cache_read_price_per_1m": 0.50}
    #             ]
    #         },
    #         {"up_to": null, "input_price_per_1m": 1.25, ...}
    #     ]
    # }
    default_tiered_pricing = Column(JSON, nullable=False)

    # 默认能力配置 - Provider 可覆盖
    default_supports_vision = Column(Boolean, default=False, nullable=True)
    default_supports_function_calling = Column(Boolean, default=False, nullable=True)
    default_supports_streaming = Column(Boolean, default=True, nullable=True)
    default_supports_extended_thinking = Column(Boolean, default=False, nullable=True)
    default_supports_image_generation = Column(Boolean, default=False, nullable=True)

    # Key 能力配置 - 模型支持的能力列表（如 ["cache_1h", "context_1m"]）
    # Key 只能启用模型支持的能力
    supported_capabilities = Column(JSON, nullable=True, default=list)

    # 状态
    is_active = Column(Boolean, default=True, nullable=False)

    # 统计计数器（优化性能，避免实时查询）
    usage_count = Column(Integer, default=0, nullable=False, index=True)

    # 时间戳
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # 关系
    models = relationship("Model", back_populates="global_model")


class Model(Base):
    """Provider 模型配置表 - Provider 如何使用某个 GlobalModel

    设计原则 (方案 A):
    - 每个 Model 必须关联一个 GlobalModel (global_model_id 不可为空)
    - Model 表示 Provider 对某个 GlobalModel 的具体实现
    - provider_model_name 是 Provider 侧的实际模型名称 (可能与 GlobalModel.name 不同)
    - 价格和能力配置可为空，为空时使用 GlobalModel 的默认值
    """

    __tablename__ = "models"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    provider_id = Column(String(36), ForeignKey("providers.id"), nullable=False)
    global_model_id = Column(String(36), ForeignKey("global_models.id"), nullable=False, index=True)

    # Provider 映射配置
    provider_model_name = Column(String(200), nullable=False)  # Provider 侧的主模型名称
    # 模型名称别名列表（带优先级），用于同一模型在 Provider 侧有多个名称变体的场景
    # 格式: [{"name": "Claude-Sonnet-4.5", "priority": 1}, {"name": "Claude-Sonnet-4-5", "priority": 2}]
    # 为空时只使用 provider_model_name
    provider_model_aliases = Column(JSON, nullable=True, default=None)

    # 按次计费配置（每次请求的固定费用，美元）- 可为空，为空时使用 GlobalModel 的默认值
    price_per_request = Column(Float, nullable=True)  # 每次请求固定费用

    # 阶梯计费配置（JSON格式）- 可为空，为空时使用 GlobalModel 的默认值
    tiered_pricing = Column(JSON, nullable=True, default=None)

    # Provider 能力配置 - 可为空，为空时使用 GlobalModel 的默认值
    supports_vision = Column(Boolean, nullable=True)
    supports_function_calling = Column(Boolean, nullable=True)
    supports_streaming = Column(Boolean, nullable=True)
    supports_extended_thinking = Column(Boolean, nullable=True)
    supports_image_generation = Column(Boolean, nullable=True)

    # 状态
    is_active = Column(Boolean, default=True, nullable=False)
    is_available = Column(Boolean, default=True)  # 是否当前可用

    # 扩展配置
    config = Column(JSON, nullable=True)

    # 时间戳
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # 关系
    provider = relationship("Provider", back_populates="models")
    global_model = relationship("GlobalModel", back_populates="models")

    # 唯一约束：同一个提供商下的 provider_model_name 不能重复
    __table_args__ = (
        UniqueConstraint("provider_id", "provider_model_name", name="uq_provider_model"),
    )

    # 辅助方法：获取有效的阶梯计费配置
    def get_effective_tiered_pricing(self) -> dict | None:
        """获取有效的阶梯计费配置"""
        if self.tiered_pricing is not None:
            return self.tiered_pricing
        if self.global_model:
            return self.global_model.default_tiered_pricing
        return None

    def _get_first_tier(self) -> dict | None:
        """获取第一个阶梯（用于获取默认价格）"""
        tiered = self.get_effective_tiered_pricing()
        if tiered and tiered.get("tiers"):
            return tiered["tiers"][0]
        return None

    def get_effective_input_price(self) -> float:
        """获取有效的输入价格（从第一个阶梯）"""
        tier = self._get_first_tier()
        if tier:
            return tier.get("input_price_per_1m", 0.0)
        return 0.0

    def get_effective_output_price(self) -> float:
        """获取有效的输出价格（从第一个阶梯）"""
        tier = self._get_first_tier()
        if tier:
            return tier.get("output_price_per_1m", 0.0)
        return 0.0

    def get_effective_cache_creation_price(self) -> float | None:
        """获取有效的缓存创建价格（从第一个阶梯）"""
        tier = self._get_first_tier()
        if tier:
            return tier.get("cache_creation_price_per_1m")
        return None

    def get_effective_cache_read_price(self) -> float | None:
        """获取有效的缓存读取价格（从第一个阶梯）"""
        tier = self._get_first_tier()
        if tier:
            return tier.get("cache_read_price_per_1m")
        return None

    def get_effective_1h_cache_creation_price(self) -> float | None:
        """获取有效的 1h 缓存创建价格（从第一个阶梯）"""
        tier = self._get_first_tier()
        if tier:
            cache_ttl_pricing = tier.get("cache_ttl_pricing") or []
            for ttl_entry in cache_ttl_pricing:
                if ttl_entry.get("ttl_minutes") == 60:
                    return ttl_entry.get("cache_creation_price_per_1m")
        return None

    def get_effective_price_per_request(self) -> float | None:
        """获取有效的按次计费价格"""
        if self.price_per_request is not None:
            return self.price_per_request
        if self.global_model:
            return self.global_model.default_price_per_request
        return None

    def _get_effective_capability(self, attr_name: str, default: bool = False) -> bool:
        """获取有效的能力配置（通用辅助方法）"""
        local_value = getattr(self, attr_name, None)
        if local_value is not None:
            return local_value
        if self.global_model:
            global_value = getattr(self.global_model, f"default_{attr_name}", None)
            if global_value is not None:
                return global_value
        return default

    def get_effective_supports_vision(self) -> bool:
        return self._get_effective_capability("supports_vision", False)

    def get_effective_supports_function_calling(self) -> bool:
        return self._get_effective_capability("supports_function_calling", False)

    def get_effective_supports_streaming(self) -> bool:
        return self._get_effective_capability("supports_streaming", True)

    def get_effective_supports_extended_thinking(self) -> bool:
        return self._get_effective_capability("supports_extended_thinking", False)

    def get_effective_supports_image_generation(self) -> bool:
        return self._get_effective_capability("supports_image_generation", False)

    def select_provider_model_name(self, affinity_key: Optional[str] = None) -> str:
        """按优先级选择要使用的 Provider 模型名称

        如果配置了 provider_model_aliases，按优先级选择（数字越小越优先）；
        相同优先级的别名通过哈希分散实现负载均衡（与 Key 调度策略一致）；
        否则返回 provider_model_name。

        Args:
            affinity_key: 用于哈希分散的亲和键（如用户 API Key 哈希），确保同一用户稳定选择同一别名
        """
        import hashlib

        if not self.provider_model_aliases:
            return self.provider_model_name

        raw_aliases = self.provider_model_aliases
        if not isinstance(raw_aliases, list) or len(raw_aliases) == 0:
            return self.provider_model_name

        aliases: list[dict] = []
        for raw in raw_aliases:
            if not isinstance(raw, dict):
                continue
            name = raw.get("name")
            if not isinstance(name, str) or not name.strip():
                continue

            raw_priority = raw.get("priority", 1)
            try:
                priority = int(raw_priority)
            except Exception:
                priority = 1
            if priority < 1:
                priority = 1

            aliases.append({"name": name.strip(), "priority": priority})

        if not aliases:
            return self.provider_model_name

        # 按优先级排序（数字越小越优先）
        sorted_aliases = sorted(aliases, key=lambda x: x["priority"])

        # 获取最高优先级（最小数字）
        highest_priority = sorted_aliases[0]["priority"]

        # 获取所有最高优先级的别名
        top_priority_aliases = [
            alias for alias in sorted_aliases
            if alias["priority"] == highest_priority
        ]

        # 如果有多个相同优先级的别名，通过哈希分散选择
        if len(top_priority_aliases) > 1 and affinity_key:
            # 为每个别名计算哈希得分，选择得分最小的
            def hash_score(alias: dict) -> int:
                combined = f"{affinity_key}:{alias['name']}"
                return int(hashlib.md5(combined.encode()).hexdigest(), 16)

            selected = min(top_priority_aliases, key=hash_score)
        elif len(top_priority_aliases) > 1:
            # 没有 affinity_key 时，使用确定性选择（按名称排序后取第一个）
            # 避免随机选择导致同一请求重试时选择不同的模型名称
            selected = min(top_priority_aliases, key=lambda x: x["name"])
        else:
            selected = top_priority_aliases[0]

        return selected["name"]

    def get_all_provider_model_names(self) -> list[str]:
        """获取所有可用的 Provider 模型名称（主名称 + 别名）"""
        names = [self.provider_model_name]
        if self.provider_model_aliases:
            for alias in self.provider_model_aliases:
                if isinstance(alias, dict) and alias.get("name"):
                    names.append(alias["name"])
        return names


class ProviderAPIKey(Base):
    """Provider API密钥表 - 归属于特定 ProviderEndpoint"""

    __tablename__ = "provider_api_keys"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)

    # 外键关系
    endpoint_id = Column(
        String(36), ForeignKey("provider_endpoints.id", ondelete="CASCADE"), nullable=False
    )

    # API密钥信息
    api_key = Column(String(500), nullable=False)  # API密钥（加密存储）
    name = Column(String(100), nullable=False)  # 密钥名称（必填，用于识别）
    note = Column(String(500), nullable=True)  # 备注说明（可选）

    # 成本计算
    rate_multiplier = Column(
        Float, default=1.0, nullable=False
    )  # 成本倍率（真实成本 = 表面成本 × 倍率）

    # 优先级配置 (数字越小越优先)
    internal_priority = Column(
        Integer, default=50
    )  # Endpoint 内部优先级（用于提供商优先模式，同 Endpoint 内 Keys 的排序，同优先级参与负载均衡）
    global_priority = Column(
        Integer, nullable=True
    )  # 全局 Key 优先级（用于全局 Key 优先模式，跨 Provider 的 Key 排序，NULL=未配置使用默认排序）

    # 并发限制配置
    # max_concurrent 决定并发控制模式：
    #   - NULL: 自适应模式，系统自动学习并调整（使用 learned_max_concurrent）
    #   - 数字: 固定限制模式，使用用户指定的值
    max_concurrent = Column(Integer, nullable=True, default=None)
    rate_limit = Column(Integer, nullable=True)  # 速率限制（每分钟请求数）
    daily_limit = Column(Integer, nullable=True)  # 每日请求限制
    monthly_limit = Column(Integer, nullable=True)  # 每月请求限制

    # 模型权限控制
    allowed_models = Column(JSON, nullable=True)  # 允许使用的模型列表（null = 支持所有模型）

    # Key 能力标签
    capabilities = Column(JSON, nullable=True)  # Key 拥有的能力
    # 示例: {"cache_1h": true, "context_1m": true}

    # 自适应并发调整（仅当 max_concurrent = NULL 时生效）
    learned_max_concurrent = Column(
        Integer, nullable=True
    )  # 学习到的并发限制（自适应模式下的有效值）
    concurrent_429_count = Column(Integer, default=0, nullable=False)  # 因并发导致的429次数
    rpm_429_count = Column(Integer, default=0, nullable=False)  # 因RPM导致的429次数
    last_429_at = Column(DateTime(timezone=True), nullable=True)  # 最后429时间
    last_429_type = Column(String(50), nullable=True)  # 最后429类型: concurrent/rpm/unknown
    last_concurrent_peak = Column(Integer, nullable=True)  # 触发429时的并发数
    adjustment_history = Column(JSON, nullable=True)  # 并发调整历史
    # 基于滑动窗口的利用率追踪
    utilization_samples = Column(
        JSON, nullable=True
    )  # 利用率采样窗口 [{"ts": timestamp, "util": 0.8}, ...]
    last_probe_increase_at = Column(
        DateTime(timezone=True), nullable=True
    )  # 上次探测性扩容时间

    # 健康度追踪（基于滑动窗口）
    health_score = Column(Float, default=1.0)  # 0.0-1.0（保留用于展示，实际熔断基于滑动窗口）
    consecutive_failures = Column(Integer, default=0)
    last_failure_at = Column(DateTime(timezone=True), nullable=True)  # 最后失败时间
    # 滑动窗口：记录最近 N 次请求的结果 [{"ts": timestamp, "ok": true/false}, ...]
    request_results_window = Column(JSON, nullable=True)

    # 缓存与熔断配置
    cache_ttl_minutes = Column(
        Integer, default=5, nullable=False
    )  # 缓存TTL(分钟)，0表示不支持缓存，默认5分钟
    max_probe_interval_minutes = Column(
        Integer, default=32, nullable=False
    )  # 最大探测间隔(分钟)，默认32分钟（硬上限）

    # 熔断器字段（滑动窗口 + 半开状态模式）
    circuit_breaker_open = Column(Boolean, default=False, nullable=False)  # 熔断器是否打开
    circuit_breaker_open_at = Column(DateTime(timezone=True), nullable=True)  # 熔断器打开时间
    next_probe_at = Column(DateTime(timezone=True), nullable=True)  # 下次探测时间
    # 半开状态：允许少量请求通过验证服务是否恢复
    half_open_until = Column(DateTime(timezone=True), nullable=True)  # 半开状态结束时间
    half_open_successes = Column(Integer, default=0)  # 半开状态下的成功次数
    half_open_failures = Column(Integer, default=0)  # 半开状态下的失败次数

    # 使用统计
    request_count = Column(Integer, default=0)  # 请求次数
    success_count = Column(Integer, default=0)  # 成功次数
    error_count = Column(Integer, default=0)  # 错误次数
    total_response_time_ms = Column(Integer, default=0)  # 总响应时间（用于计算平均值）
    last_used_at = Column(DateTime(timezone=True), nullable=True)  # 最后使用时间
    last_error_at = Column(DateTime(timezone=True), nullable=True)  # 最后错误时间
    last_error_msg = Column(Text, nullable=True)  # 最后错误信息

    # 状态
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)  # 过期时间

    # 时间戳
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # 关系
    endpoint = relationship("ProviderEndpoint", back_populates="api_keys")


class UserPreference(Base):
    """用户偏好设置表"""

    __tablename__ = "user_preferences"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    # 个人信息
    avatar_url = Column(String(500), nullable=True)  # 头像URL
    bio = Column(Text, nullable=True)  # 个人简介

    # 偏好设置
    default_provider_id = Column(String(36), ForeignKey("providers.id"), nullable=True)
    theme = Column(String(20), default="light")  # light/dark/auto
    language = Column(String(10), default="zh-CN")
    timezone = Column(String(50), default="Asia/Shanghai")

    # 通知设置
    email_notifications = Column(Boolean, default=True)
    usage_alerts = Column(Boolean, default=True)
    announcement_notifications = Column(Boolean, default=True)

    # 时间戳
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # 关系
    user = relationship("User", back_populates="preferences")
    default_provider = relationship("Provider")


class Announcement(Base):
    """公告表"""

    __tablename__ = "announcements"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)  # 支持 Markdown
    type = Column(String(20), default="info")  # info, warning, maintenance, important
    priority = Column(Integer, default=0)  # 优先级,数字越大越重要

    # 发布信息
    author_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    is_pinned = Column(Boolean, default=False)  # 置顶

    # 时间范围
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)

    # 时间戳
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # 关系
    author = relationship("User", back_populates="authored_announcements")
    reads = relationship(
        "AnnouncementRead", back_populates="announcement", cascade="all, delete-orphan"
    )


class AnnouncementRead(Base):
    """公告已读记录表"""

    __tablename__ = "announcement_reads"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    announcement_id = Column(String(36), ForeignKey("announcements.id"), nullable=False)
    read_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # 唯一约束
    __table_args__ = (UniqueConstraint("user_id", "announcement_id", name="uq_user_announcement"),)

    # 关系
    user = relationship("User", back_populates="announcement_reads")
    announcement = relationship("Announcement", back_populates="reads")


class AuditEventType(PyEnum):
    """审计事件类型"""

    # 认证相关
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    API_KEY_CREATED = "api_key_created"
    API_KEY_DELETED = "api_key_deleted"
    API_KEY_USED = "api_key_used"

    # 请求相关
    REQUEST_SUCCESS = "request_success"
    REQUEST_FAILED = "request_failed"
    REQUEST_RATE_LIMITED = "request_rate_limited"
    REQUEST_QUOTA_EXCEEDED = "request_quota_exceeded"

    # 管理操作
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    PROVIDER_ADDED = "provider_added"
    PROVIDER_UPDATED = "provider_updated"
    PROVIDER_REMOVED = "provider_removed"

    # 安全事件
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    DATA_EXPORT = "data_export"
    CONFIG_CHANGED = "config_changed"


class AuditLog(Base):
    """审计日志模型"""

    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    event_type = Column(String(50), nullable=False, index=True)
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    api_key_id = Column(String(36), nullable=True)

    # 事件详情
    description = Column(Text, nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    request_id = Column(String(100), nullable=True, index=True)

    # 相关数据
    event_metadata = Column(JSON, nullable=True)

    # 响应信息
    status_code = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    # 时间戳
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # 关系
    user = relationship("User", back_populates="audit_logs")


class RequestCandidate(Base):
    """请求候选记录 - 追踪所有候选（包括未使用的）"""

    __tablename__ = "request_candidates"

    # 主键
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 关联字段
    request_id = Column(String(100), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    api_key_id = Column(String(36), ForeignKey("api_keys.id", ondelete="CASCADE"), nullable=True)

    # 候选信息
    candidate_index = Column(Integer, nullable=False)  # 候选序号（从0开始）
    retry_index = Column(Integer, nullable=False, default=0)  # 重试序号（从0开始）
    provider_id = Column(String(36), ForeignKey("providers.id", ondelete="CASCADE"), nullable=True)
    endpoint_id = Column(
        String(36), ForeignKey("provider_endpoints.id", ondelete="CASCADE"), nullable=True
    )
    key_id = Column(
        String(36), ForeignKey("provider_api_keys.id", ondelete="CASCADE"), nullable=True
    )

    # 状态信息
    status = Column(String(20), nullable=False)  # 'pending', 'success', 'failed', 'skipped'
    skip_reason = Column(Text, nullable=True)  # 跳过/失败原因
    is_cached = Column(Boolean, default=False)  # 是否为缓存亲和性候选

    # 执行结果信息（当 status = success/failed 时）
    status_code = Column(Integer, nullable=True)  # HTTP 状态码
    error_type = Column(String(50), nullable=True)  # 错误类型
    error_message = Column(Text, nullable=True)  # 错误消息
    latency_ms = Column(Integer, nullable=True)  # 延迟（毫秒）
    concurrent_requests = Column(Integer, nullable=True)  # 并发请求数

    # 元数据
    extra_data = Column(JSON, nullable=True)
    required_capabilities = Column(JSON, nullable=True)  # 请求实际需要的能力标签

    # 时间戳
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    started_at = Column(DateTime(timezone=True), nullable=True)  # 开始执行时间
    finished_at = Column(DateTime(timezone=True), nullable=True)  # 完成时间

    # 唯一约束和索引
    __table_args__ = (
        UniqueConstraint(
            "request_id", "candidate_index", "retry_index", name="uq_request_candidate_with_retry"
        ),
        Index("idx_request_candidates_request_id", "request_id"),
        Index("idx_request_candidates_status", "status"),
        Index("idx_request_candidates_provider_id", "provider_id"),
    )

    # 关系
    user = relationship("User")
    api_key = relationship("ApiKey")
    provider = relationship("Provider")
    endpoint = relationship("ProviderEndpoint")
    key = relationship("ProviderAPIKey")


# ==================== 统计数据模型 ====================


class StatsDaily(Base):
    """每日统计快照 - 用于快速查询历史数据"""

    __tablename__ = "stats_daily"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 统计日期 (UTC)
    date = Column(DateTime(timezone=True), nullable=False, unique=True, index=True)

    # 请求统计
    total_requests = Column(Integer, default=0, nullable=False)
    success_requests = Column(Integer, default=0, nullable=False)
    error_requests = Column(Integer, default=0, nullable=False)

    # Token 统计
    input_tokens = Column(BigInteger, default=0, nullable=False)
    output_tokens = Column(BigInteger, default=0, nullable=False)
    cache_creation_tokens = Column(BigInteger, default=0, nullable=False)
    cache_read_tokens = Column(BigInteger, default=0, nullable=False)

    # 成本统计 (USD)
    total_cost = Column(Float, default=0.0, nullable=False)
    actual_total_cost = Column(Float, default=0.0, nullable=False)  # 倍率后成本
    input_cost = Column(Float, default=0.0, nullable=False)
    output_cost = Column(Float, default=0.0, nullable=False)
    cache_creation_cost = Column(Float, default=0.0, nullable=False)
    cache_read_cost = Column(Float, default=0.0, nullable=False)

    # 性能统计
    avg_response_time_ms = Column(Float, default=0.0, nullable=False)
    fallback_count = Column(Integer, default=0, nullable=False)  # Provider 切换次数

    # 使用维度统计
    unique_models = Column(Integer, default=0, server_default="0", nullable=False)
    unique_providers = Column(Integer, default=0, server_default="0", nullable=False)

    # 时间戳
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class StatsSummary(Base):
    """全局统计汇总 - 单行记录，存储截止到昨天的累计数据"""

    __tablename__ = "stats_summary"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 统计截止日期 (不含当天)
    cutoff_date = Column(DateTime(timezone=True), nullable=False)

    # 累计请求统计
    all_time_requests = Column(Integer, default=0, nullable=False)
    all_time_success_requests = Column(Integer, default=0, nullable=False)
    all_time_error_requests = Column(Integer, default=0, nullable=False)

    # 累计 Token 统计
    all_time_input_tokens = Column(BigInteger, default=0, nullable=False)
    all_time_output_tokens = Column(BigInteger, default=0, nullable=False)
    all_time_cache_creation_tokens = Column(BigInteger, default=0, nullable=False)
    all_time_cache_read_tokens = Column(BigInteger, default=0, nullable=False)

    # 累计成本统计 (USD)
    all_time_cost = Column(Float, default=0.0, nullable=False)
    all_time_actual_cost = Column(Float, default=0.0, nullable=False)

    # 累计用户/API Key 统计 (快照)
    total_users = Column(Integer, default=0, nullable=False)
    active_users = Column(Integer, default=0, nullable=False)
    total_api_keys = Column(Integer, default=0, nullable=False)
    active_api_keys = Column(Integer, default=0, nullable=False)

    # 时间戳
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class StatsUserDaily(Base):
    """用户每日统计快照 - 用于用户仪表盘"""

    __tablename__ = "stats_user_daily"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 用户关联
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # 统计日期 (UTC)
    date = Column(DateTime(timezone=True), nullable=False, index=True)

    # 请求统计
    total_requests = Column(Integer, default=0, nullable=False)
    success_requests = Column(Integer, default=0, nullable=False)
    error_requests = Column(Integer, default=0, nullable=False)

    # Token 统计
    input_tokens = Column(BigInteger, default=0, nullable=False)
    output_tokens = Column(BigInteger, default=0, nullable=False)
    cache_creation_tokens = Column(BigInteger, default=0, nullable=False)
    cache_read_tokens = Column(BigInteger, default=0, nullable=False)

    # 成本统计 (USD)
    total_cost = Column(Float, default=0.0, nullable=False)

    # 时间戳
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # 唯一约束：每个用户每天只有一条记录
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_stats_user_daily"),
        Index("idx_stats_user_daily_user_date", "user_id", "date"),
    )

    # 关系
    user = relationship("User")


# 导入扩展的数据库模型
from .database_extensions import ApiKeyProviderMapping, ProviderUsageTracking
