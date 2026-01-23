"""
模型权限工具

allowed_models 格式: ["claude-sonnet-4", "gpt-4o"]
使用 None/null 表示不限制（允许所有模型）

支持模型映射匹配：
- GlobalModel.config.model_mappings 定义映射模式
- 映射模式支持正则表达式语法
- 例如：claude-haiku-.* 可匹配 claude-haiku-4.5, claude-haiku-last
- 使用 regex 库的原生超时保护（100ms）防止 ReDoS
"""

import re
from functools import lru_cache
from typing import List, Optional, Tuple

import regex

from src.core.logger import logger

# 映射规则限制
MAX_MAPPINGS_PER_MODEL = 50
MAX_MAPPING_LENGTH = 200
MAX_MODEL_NAME_LENGTH = 200  # 与 MAX_MAPPING_LENGTH 保持一致
REGEX_MATCH_TIMEOUT_MS = 100  # 正则匹配超时（毫秒）

# 类型别名
AllowedModels = Optional[List[str]]


def normalize_allowed_models(allowed_models: AllowedModels) -> Optional[set[str]]:
    """
    将 allowed_models 规范化为模型名称集合

    Args:
        allowed_models: 允许的模型配置（列表）

    Returns:
        - None: 不限制（允许所有模型）
        - set[str]: 允许的模型名称集合（可能为空集，表示拒绝所有）
    """
    if allowed_models is None:
        return None

    return set(allowed_models)


def check_model_allowed(
    model_name: str,
    allowed_models: AllowedModels,
) -> bool:
    """
    检查模型是否被允许

    Args:
        model_name: 请求的模型名称
        allowed_models: 允许的模型配置

    Returns:
        True: 允许使用该模型
        False: 不允许使用该模型
    """
    allowed_set = normalize_allowed_models(allowed_models)

    if allowed_set is None:
        # 不限制
        return True

    if len(allowed_set) == 0:
        # 空集合 = 拒绝所有
        return False

    # 检查请求的模型名是否在白名单中
    return model_name in allowed_set


def merge_allowed_models(
    allowed_models_1: AllowedModels,
    allowed_models_2: AllowedModels,
) -> AllowedModels:
    """
    合并两个 allowed_models 配置，取交集

    规则：
    - 如果任一为 None，返回另一个
    - 如果都有值，取交集

    Args:
        allowed_models_1: 第一个配置
        allowed_models_2: 第二个配置

    Returns:
        合并后的配置
    """
    if allowed_models_1 is None:
        return allowed_models_2
    if allowed_models_2 is None:
        return allowed_models_1

    intersection = set(allowed_models_1) & set(allowed_models_2)
    return sorted(intersection) if intersection else []


def get_allowed_models_preview(
    allowed_models: AllowedModels,
    max_items: int = 3,
) -> str:
    """
    获取 allowed_models 的预览字符串（用于日志和错误消息）

    Args:
        allowed_models: 允许的模型配置
        max_items: 最多显示的模型数

    Returns:
        预览字符串，如 "gpt-4o, claude-sonnet-4, ..."
    """
    if allowed_models is None:
        return "(不限制)"

    if not allowed_models:
        return "(无)"

    sorted_models = sorted(allowed_models)
    preview = ", ".join(sorted_models[:max_items])
    if len(sorted_models) > max_items:
        preview += f", ...共{len(sorted_models)}个"

    return preview


def parse_allowed_models_to_list(allowed_models: AllowedModels) -> List[str]:
    """
    解析 allowed_models 为列表

    Args:
        allowed_models: 允许的模型配置

    Returns:
        模型名称列表（可能为空）
    """
    if allowed_models is None:
        return []

    return list(allowed_models)


def validate_mapping_pattern(pattern: str) -> Tuple[bool, Optional[str]]:
    """
    验证映射模式是否安全

    Args:
        pattern: 待验证的正则模式

    Returns:
        (is_valid, error_message)
    """
    if not pattern or not pattern.strip():
        return False, "映射规则不能为空"

    if len(pattern) > MAX_MAPPING_LENGTH:
        return False, f"映射规则过长 (最大 {MAX_MAPPING_LENGTH} 字符)"

    # 尝试编译验证语法
    try:
        re.compile(f"^{pattern}$", re.IGNORECASE)
    except re.error as e:
        return False, f"正则表达式语法错误: {e}"

    return True, None


def validate_model_mappings(mappings: Optional[List[str]]) -> Tuple[bool, Optional[str]]:
    """
    验证映射列表是否合法

    Args:
        mappings: 映射列表

    Returns:
        (is_valid, error_message)
    """
    if not mappings:
        return True, None

    if len(mappings) > MAX_MAPPINGS_PER_MODEL:
        return False, f"映射规则数量超限 (最大 {MAX_MAPPINGS_PER_MODEL} 条)"

    for i, mapping in enumerate(mappings):
        is_valid, error = validate_mapping_pattern(mapping)
        if not is_valid:
            return False, f"第 {i + 1} 条规则无效: {error}"

    return True, None


def validate_and_extract_model_mappings(
    config: Optional[dict],
) -> Tuple[bool, Optional[str], Optional[List[str]]]:
    """
    从 config 中验证并提取 model_mappings

    用于 GlobalModel 创建/更新时的统一验证

    Args:
        config: GlobalModel 的 config 字典

    Returns:
        (is_valid, error_message, mappings):
        - is_valid: 验证是否通过
        - error_message: 错误信息（验证失败时）
        - mappings: 提取的映射列表（验证成功时）
    """
    if not config or "model_mappings" not in config:
        return True, None, None

    mappings = config.get("model_mappings")

    # 允许显式设置为 None（表示清除映射）
    if mappings is None:
        return True, None, None

    # 类型验证：必须是列表
    if not isinstance(mappings, list):
        return False, "model_mappings 必须是数组类型", None

    # 元素类型验证：必须是字符串
    if not all(isinstance(m, str) for m in mappings):
        return False, "model_mappings 数组元素必须是字符串", None

    # 业务规则验证
    is_valid, error = validate_model_mappings(mappings)
    if not is_valid:
        return False, error, None

    return True, None, mappings


@lru_cache(maxsize=2000)
def _compile_pattern_cached(pattern: str) -> Optional[regex.Pattern]:
    """
    编译正则模式（带 LRU 缓存）

    Args:
        pattern: 正则模式字符串

    Returns:
        编译后的正则对象，如果无效则返回 None
    """
    try:
        return regex.compile(f"^{pattern}$", regex.IGNORECASE)
    except regex.error as e:
        logger.debug(f"正则编译失败: pattern={pattern}, error={e}")
        return None


def clear_regex_cache() -> None:
    """
    清空正则缓存

    在 GlobalModel 映射更新时调用此函数以确保缓存一致性
    """
    _compile_pattern_cached.cache_clear()
    logger.debug("[RegexCache] 缓存已清空")


def _match_with_timeout(
    compiled_regex: regex.Pattern, text: str, timeout_ms: int = REGEX_MATCH_TIMEOUT_MS
) -> Optional[bool]:
    """
    带超时的正则匹配（使用 regex 库的原生超时支持）

    相比 ThreadPoolExecutor 方案的优势：
    - C 层面中断匹配，不会留下僵尸线程
    - 更低的性能开销
    - 更精确的超时控制

    Args:
        compiled_regex: 编译后的 regex.Pattern 对象
        text: 待匹配的文本
        timeout_ms: 超时时间（毫秒）

    Returns:
        True: 匹配成功
        False: 匹配失败
        None: 超时或异常
    """
    try:
        # regex 库的 timeout 参数单位是秒
        result = compiled_regex.match(text, timeout=timeout_ms / 1000.0)
        return result is not None
    except TimeoutError:
        logger.warning(
            f"正则匹配超时 ({timeout_ms}ms): pattern={compiled_regex.pattern[:50]}..., text={text[:50]}..."
        )
        return None
    except Exception as e:
        logger.warning(f"正则匹配异常: {e}")
        return None


def match_model_with_pattern(pattern: str, model_name: str) -> bool:
    """
    检查模型名是否匹配映射模式（支持正则表达式）

    安全特性：
    - 长度限制检查
    - 正则编译缓存
    - 正则匹配超时保护（100ms，使用 regex 库原生超时）

    Args:
        pattern: 映射模式，支持正则表达式语法
        model_name: 被检查的模型名（来自 Key 的 allowed_models）

    Returns:
        True 如果匹配

    示例:
        match_model_with_pattern("claude-haiku-.*", "claude-haiku-4.5") -> True
        match_model_with_pattern("gpt-4o", "gpt-4o") -> True
        match_model_with_pattern("gpt-4o", "gpt-4") -> False
    """
    # 快速路径：精确匹配
    if pattern.lower() == model_name.lower():
        return True

    # 长度检查
    if len(pattern) > MAX_MAPPING_LENGTH or len(model_name) > MAX_MODEL_NAME_LENGTH:
        return False

    # 使用缓存的编译结果
    compiled = _compile_pattern_cached(pattern)
    if compiled is None:
        return False

    # 使用带超时的匹配（regex 库原生支持）
    result = _match_with_timeout(compiled, model_name)
    return result is True


def check_model_allowed_with_mappings(
    model_name: str,
    allowed_models: AllowedModels,
    model_mappings: Optional[List[str]] = None,
    candidate_models: Optional[set[str]] = None,
) -> tuple[bool, Optional[str]]:
    """
    检查模型是否被允许（支持映射通配符匹配）

    匹配优先级：
    1. 精确匹配 model_name（用户请求的模型名，即 GlobalModel.name）
    2. 精确匹配 candidate_models ∩ allowed_models（Provider 支持且 Key 允许的模型名）
    3. 遍历 model_mappings 正则，检查 allowed_models 中是否有匹配项

    映射匹配顺序说明：
    - 按 allowed_models 集合的迭代顺序遍历（通常为字母顺序，因为内部使用 set）
    - 对于每个 allowed_model，按 model_mappings 数组顺序依次尝试匹配
    - 返回第一个成功匹配的 allowed_model
    - 如需确定性行为，请确保 model_mappings 中的规则从最具体到最通用排序

    Args:
        model_name: 请求的模型名称（GlobalModel.name）
        allowed_models: 允许的模型配置（来自 Provider Key）
        model_mappings: GlobalModel 的映射列表（来自 config.model_mappings），支持正则表达式
        candidate_models: 可选的候选模型集合（Provider 的 provider_model_names），
                         仅用于步骤 2 的精确匹配，不影响步骤 3 的正则匹配

    Returns:
        (is_allowed, matched_model_name):
        - is_allowed: 是否允许使用该模型
        - matched_model_name: 匹配到的模型名（用于实际请求时的模型名替换）
          - model_name 精确匹配时为 None（无需替换）
          - candidate_models 或 model_mappings 匹配时返回匹配到的模型名
    """
    # 先尝试精确匹配 model_name
    if check_model_allowed(model_name, allowed_models):
        return True, None

    # 获取 allowed_models 的集合
    allowed_set = normalize_allowed_models(allowed_models)

    if allowed_set is None:
        # 不限制，已在 check_model_allowed 中返回 True
        return True, None

    if len(allowed_set) == 0:
        # 空集合 = 拒绝所有
        return False, None

    # 检查 candidate_models 与 allowed_models 的交集
    # candidate_models = Provider 实际支持的模型名（provider_model_name + provider_model_mappings）
    # 如果有交集，说明 Key 的 allowed_models 中有 Provider 支持的模型名，可以直接使用
    if candidate_models:
        intersection = allowed_set & candidate_models
        if intersection:
            # 返回第一个匹配的模型名（排序确保确定性），用于实际请求时替换 model_name
            return True, sorted(intersection)[0]

    # 如果精确匹配失败且有映射配置，尝试映射匹配
    if not model_mappings:
        return False, None

    # 正则映射匹配：直接在 allowed_models 上进行匹配
    # GlobalModel.config.model_mappings 定义了"可以用哪些 Provider 模型名来提供服务"
    # 如果 Key 的 allowed_models 中有能被正则匹配的模型名，说明这个 Key 可以用于请求
    #
    # 注意：不再用 candidate_models 限制搜索空间
    # 原因：用户可能只配置了 GlobalModel 的正则映射规则，而没有在 Provider Model 的
    # provider_model_mappings 中添加对应的模型名。正则映射的语义是"将请求重定向到匹配的模型名"，
    # 所以应该直接检查 Key 的 allowed_models 是否包含能被正则匹配的模型名。
    #
    # 遍历 allowed_set，检查是否有模型名能匹配 model_mappings 中的任一正则
    # 排序确保确定性行为
    for allowed_model in sorted(allowed_set):
        for mapping_pattern in model_mappings:
            if match_model_with_pattern(mapping_pattern, allowed_model):
                return True, allowed_model

    return False, None
