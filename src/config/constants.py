# Constants for better maintainability
# ==============================================================================
# 缓存相关常量
# ==============================================================================


# 缓存 TTL（秒）
class CacheTTL:
    """缓存过期时间配置（秒）"""

    # 用户缓存 - 用户信息变更较频繁
    USER = 60  # 1分钟

    # Provider/Model 缓存 - 配置变更不频繁
    PROVIDER = 300  # 5分钟
    MODEL = 300  # 5分钟

    # 缓存亲和性 - 对应 provider_api_key.cache_ttl_minutes 默认值
    CACHE_AFFINITY = 300  # 5分钟

    # L1 本地缓存（用于减少 Redis 访问）
    L1_LOCAL = 3  # 3秒

    # 活跃度热力图缓存 - 历史数据变化不频繁
    ACTIVITY_HEATMAP = 300  # 5分钟

    # 并发锁 TTL - 防止死锁
    CONCURRENCY_LOCK = 600  # 10分钟


# 缓存容量限制
class CacheSize:
    """缓存容量配置"""

    # 默认 LRU 缓存大小
    DEFAULT = 1000


# ==============================================================================
# 并发和限流常量
# ==============================================================================


class StreamDefaults:
    """流式处理默认值"""

    # 预读字节上限（避免无换行响应导致内存增长）
    # 64KB 基于：
    # 1. SSE 单条消息通常远小于此值
    # 2. 足够检测 HTML 和 JSON 错误响应
    # 3. 不会占用过多内存
    MAX_PREFETCH_BYTES = 64 * 1024  # 64KB


class ConcurrencyDefaults:
    """并发控制默认值

    算法说明：边界记忆 + 渐进探测
    - 触发 429 时记录边界（last_concurrent_peak），新限制 = 边界 - 1
    - 扩容时不超过边界，除非是探测性扩容（长时间无 429）
    - 这样可以快速收敛到真实限制附近，避免过度保守
    """

    # 自适应并发初始限制（宽松起步，遇到 429 再降低）
    INITIAL_LIMIT = 50

    # 429错误后的冷却时间（分钟）- 在此期间不会增加并发限制
    COOLDOWN_AFTER_429_MINUTES = 5

    # 探测间隔上限（分钟）- 用于长期探测策略
    MAX_PROBE_INTERVAL_MINUTES = 60

    # === 基于滑动窗口的扩容参数 ===
    # 滑动窗口大小（采样点数量）
    UTILIZATION_WINDOW_SIZE = 20

    # 滑动窗口时间范围（秒）- 只保留最近这段时间内的采样
    UTILIZATION_WINDOW_SECONDS = 120  # 2分钟

    # 利用率阈值 - 窗口内平均利用率 >= 此值时考虑扩容
    UTILIZATION_THRESHOLD = 0.7  # 70%

    # 高利用率采样比例 - 窗口内超过阈值的采样点比例 >= 此值时触发扩容
    HIGH_UTILIZATION_RATIO = 0.6  # 60% 的采样点高于阈值

    # 最小采样数 - 窗口内至少需要这么多采样才能做出扩容决策
    MIN_SAMPLES_FOR_DECISION = 5

    # 扩容步长 - 每次扩容增加的并发数
    INCREASE_STEP = 2

    # 最大并发限制上限
    MAX_CONCURRENT_LIMIT = 200

    # 最小并发限制下限
    # 设置为 3 而不是 1，因为预留机制（10%预留给缓存用户）会导致
    # 当 learned_max_concurrent=1 时新用户实际可用槽位为 0，永远无法命中
    # 注意：当 limit < 10 时，预留机制实际不生效（预留槽位 = 0），这是可接受的
    MIN_CONCURRENT_LIMIT = 3

    # === 探测性扩容参数 ===
    # 探测性扩容间隔（分钟）- 长时间无 429 且有流量时尝试扩容
    # 探测性扩容可以突破已知边界，尝试更高的并发
    PROBE_INCREASE_INTERVAL_MINUTES = 30

    # 探测性扩容最小请求数 - 在探测间隔内至少需要这么多请求
    PROBE_INCREASE_MIN_REQUESTS = 10

    # === 缓存用户预留比例 ===
    # 缓存用户槽位预留比例（新用户可用 1 - 此值）
    # 0.1 表示缓存用户预留 10%，新用户可用 90%
    CACHE_RESERVATION_RATIO = 0.1


class CircuitBreakerDefaults:
    """熔断器配置默认值（滑动窗口 + 半开状态模式）

    新的熔断器基于滑动窗口错误率，而不是累计健康度。
    支持半开状态，允许少量请求验证服务是否恢复。
    """

    # === 滑动窗口配置 ===
    # 滑动窗口大小（最近 N 次请求）
    WINDOW_SIZE = 20

    # 滑动窗口时间范围（秒）- 只保留最近这段时间内的请求记录
    WINDOW_SECONDS = 300  # 5分钟

    # 最小请求数 - 窗口内至少需要这么多请求才能做出熔断决策
    MIN_REQUESTS_FOR_DECISION = 5

    # 错误率阈值 - 窗口内错误率超过此值时触发熔断
    ERROR_RATE_THRESHOLD = 0.5  # 50%

    # === 半开状态配置 ===
    # 半开状态持续时间（秒）- 在此期间允许少量请求通过
    HALF_OPEN_DURATION_SECONDS = 30

    # 半开状态成功阈值 - 达到此成功次数则关闭熔断器
    HALF_OPEN_SUCCESS_THRESHOLD = 3

    # 半开状态失败阈值 - 达到此失败次数则重新打开熔断器
    HALF_OPEN_FAILURE_THRESHOLD = 2

    # === 熔断恢复配置 ===
    # 初始探测间隔（秒）- 熔断后多久进入半开状态
    INITIAL_RECOVERY_SECONDS = 30

    # 探测间隔退避倍数
    RECOVERY_BACKOFF_MULTIPLIER = 2

    # 最大探测间隔（秒）
    MAX_RECOVERY_SECONDS = 300  # 5分钟

    # === 旧参数（向后兼容，仍用于展示健康度）===
    # 成功时健康度增量
    SUCCESS_INCREMENT = 0.15

    # 失败时健康度减量
    FAILURE_DECREMENT = 0.03

    # 探测成功后的快速恢复健康度
    PROBE_RECOVERY_SCORE = 0.5


class AdaptiveReservationDefaults:
    """动态预留比例配置默认值

    动态预留机制根据学习置信度和负载自动调整缓存用户预留比例，
    解决固定 30% 预留在学习初期和负载变化时的不适应问题。
    """

    # 探测阶段配置
    PROBE_PHASE_REQUESTS = 100  # 探测阶段请求数阈值
    PROBE_RESERVATION = 0.1  # 探测阶段预留比例（10%）

    # 稳定阶段配置
    STABLE_MIN_RESERVATION = 0.1  # 稳定阶段最小预留（10%）
    STABLE_MAX_RESERVATION = 0.35  # 稳定阶段最大预留（35%）

    # 置信度计算参数
    SUCCESS_COUNT_FOR_FULL_CONFIDENCE = 50  # 连续成功多少次达到满置信
    COOLDOWN_HOURS_FOR_FULL_CONFIDENCE = 24  # 429后多少小时达到满置信

    # 负载阈值
    LOW_LOAD_THRESHOLD = 0.5  # 低负载阈值（50%）
    HIGH_LOAD_THRESHOLD = 0.8  # 高负载阈值（80%）


# ==============================================================================
# 超时和重试常量
# ==============================================================================


class TimeoutDefaults:
    """超时配置默认值（秒）"""

    # HTTP 请求默认超时
    HTTP_REQUEST = 300  # 5分钟

    # 数据库连接池获取超时
    DB_POOL = 30

    # Redis 操作超时
    REDIS_OPERATION = 5


class RetryDefaults:
    """重试配置默认值"""

    # 最大重试次数
    MAX_RETRIES = 3

    # 重试基础延迟（秒）
    BASE_DELAY = 1.0

    # 重试延迟倍数（指数退避）
    DELAY_MULTIPLIER = 2.0


# ==============================================================================
# 消息格式常量
# ==============================================================================

# 角色常量
ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
ROLE_SYSTEM = "system"
ROLE_TOOL = "tool"

# 内容类型常量
CONTENT_TEXT = "text"
CONTENT_IMAGE = "image"
CONTENT_TOOL_USE = "tool_use"
CONTENT_TOOL_RESULT = "tool_result"

# 工具常量
TOOL_FUNCTION = "function"

# 停止原因常量
STOP_END_TURN = "end_turn"
STOP_MAX_TOKENS = "max_tokens"
STOP_TOOL_USE = "tool_use"
STOP_ERROR = "error"

# 事件类型常量
EVENT_MESSAGE_START = "message_start"
EVENT_MESSAGE_STOP = "message_stop"
EVENT_MESSAGE_DELTA = "message_delta"
EVENT_CONTENT_BLOCK_START = "content_block_start"
EVENT_CONTENT_BLOCK_STOP = "content_block_stop"
EVENT_CONTENT_BLOCK_DELTA = "content_block_delta"
EVENT_PING = "ping"

# Delta类型常量
DELTA_TEXT = "text_delta"
DELTA_INPUT_JSON = "input_json_delta"
