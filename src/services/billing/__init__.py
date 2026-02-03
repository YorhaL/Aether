"""
计费模块

提供配置驱动的计费计算，支持不同厂商的差异化计费模式：
- Claude: input + output + cache_creation + cache_read
- OpenAI: input + output + cache_read (无缓存创建费用)
- 豆包: input + output + cache_read + cache_storage (缓存按时计费)
- 按次计费: per_request

使用方式:
    from src.services.billing import BillingCalculator, UsageMapper, StandardizedUsage

    # 1. 将原始 usage 映射为标准格式
    usage = UsageMapper.map(raw_usage, api_format="openai:chat")

    # 2. 使用计费计算器计算费用
    calculator = BillingCalculator(template="openai")
    result = calculator.calculate(usage, prices)

    # 3. 获取费用明细
    print(result.total_cost)
    print(result.costs)  # {"input": 0.01, "output": 0.02, ...}
"""

from src.services.billing.calculator import BillingCalculator, calculate_request_cost
from src.services.billing.models import (
    BillingDimension,
    BillingUnit,
    CostBreakdown,
    StandardizedUsage,
)
from src.services.billing.schema import BillingSnapshot, CostResult
from src.services.billing.service import BillingService
from src.services.billing.shadow import ShadowBillingService
from src.services.billing.templates import BILLING_TEMPLATE_REGISTRY, BillingTemplates
from src.services.billing.usage_mapper import UsageMapper, map_usage, map_usage_from_response

__all__ = [
    # 数据模型
    "BillingDimension",
    "BillingUnit",
    "CostBreakdown",
    "StandardizedUsage",
    # 模板
    "BillingTemplates",
    "BILLING_TEMPLATE_REGISTRY",
    # 计算器
    "BillingCalculator",
    "calculate_request_cost",
    # 统一入口（Phase2）
    "BillingService",
    "BillingSnapshot",
    "CostResult",
    "ShadowBillingService",
    # 映射器
    "UsageMapper",
    "map_usage",
    "map_usage_from_response",
]
