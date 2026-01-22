"""
Provider Query API 端点
用于查询提供商的模型列表等信息
"""

from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from src.config.constants import TimeoutDefaults
from src.core.crypto import crypto_service
from src.core.api_format import get_extra_headers_from_endpoint
from src.core.logger import logger
from src.database.database import get_db
from src.models.database import Provider, ProviderEndpoint, User
from src.services.model.upstream_fetcher import (
    _get_adapter_for_format,
    build_all_format_configs,
    fetch_models_from_endpoints,
)
from src.utils.auth_utils import get_current_user
from src.utils.ssl_utils import get_ssl_context


router = APIRouter(prefix="/api/admin/provider-query", tags=["Provider Query"])


# ============ Request/Response Models ============


class ModelsQueryRequest(BaseModel):
    """模型列表查询请求"""

    provider_id: str
    api_key_id: Optional[str] = None
    force_refresh: bool = False  # 强制刷新，跳过缓存


class TestModelRequest(BaseModel):
    """模型测试请求"""

    provider_id: str
    model_name: str
    api_key_id: Optional[str] = None
    endpoint_id: Optional[str] = None  # 指定使用的端点ID
    stream: bool = False
    message: Optional[str] = "你好"
    api_format: Optional[str] = None  # 指定使用的API格式，如果不指定则使用端点的默认格式


# ============ API Endpoints ============


@router.post("/models")
async def query_available_models(
    request: ModelsQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    查询提供商可用模型

    优先从缓存获取（缓存由定时任务刷新），缓存未命中时实时调用上游 API。
    从所有 API 格式尝试获取模型，然后聚合去重。

    Args:
        request: 查询请求

    Returns:
        所有端点的模型列表（合并）
    """
    from src.services.model.fetch_scheduler import (
        get_upstream_models_from_cache,
        set_upstream_models_to_cache,
    )

    # 获取提供商基本信息
    provider = (
        db.query(Provider)
        .options(
            joinedload(Provider.endpoints),
            joinedload(Provider.api_keys),
        )
        .filter(Provider.id == request.provider_id)
        .first()
    )

    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    # 如果指定了 api_key_id 且不是强制刷新，优先从缓存获取
    if request.api_key_id and not request.force_refresh:
        cached_models = await get_upstream_models_from_cache(
            request.provider_id, request.api_key_id
        )
        if cached_models is not None:
            return {
                "success": True,
                "data": {"models": cached_models, "error": None, "from_cache": True},
                "provider": {
                    "id": provider.id,
                    "name": provider.name,
                },
            }

    # 缓存未命中或强制刷新，实时获取

    # 构建 api_format -> endpoint 映射
    format_to_endpoint: dict[str, ProviderEndpoint] = {}
    for endpoint in provider.endpoints:
        if endpoint.is_active:
            format_to_endpoint[endpoint.api_format] = endpoint

    if not format_to_endpoint:
        raise HTTPException(status_code=400, detail="No active endpoints found for this provider")

    # 获取 API Key
    if request.api_key_id:
        # 指定了特定的 API Key
        api_key = next(
            (key for key in provider.api_keys if key.id == request.api_key_id),
            None
        )
        if not api_key:
            raise HTTPException(status_code=404, detail="API Key not found")
    else:
        # 使用第一个可用的 Key
        api_key = next(
            (key for key in provider.api_keys if key.is_active),
            None
        )
        if not api_key:
            raise HTTPException(status_code=400, detail="No active API Key found for this provider")

    try:
        api_key_value = crypto_service.decrypt(api_key.api_key)
    except Exception as e:
        logger.error(f"Failed to decrypt API key: {e}")
        raise HTTPException(status_code=500, detail="Failed to decrypt API key")

    # 使用公共函数构建所有格式的端点配置并获取模型
    endpoint_configs = build_all_format_configs(api_key_value, format_to_endpoint)  # type: ignore[arg-type]
    all_models, errors, has_success = await fetch_models_from_endpoints(endpoint_configs)

    # 按 model id + api_format 去重（保留第一个）
    seen_keys: set[str] = set()
    unique_models: list = []
    for model in all_models:
        model_id = model.get("id")
        api_format = model.get("api_format", "")
        unique_key = f"{model_id}:{api_format}"
        if model_id and unique_key not in seen_keys:
            seen_keys.add(unique_key)
            unique_models.append(model)

    error = "; ".join(errors) if errors else None
    if not unique_models and not error:
        error = "No models returned from any endpoint"

    # 如果指定了 api_key_id 且获取成功，写入缓存
    if request.api_key_id and unique_models:
        await set_upstream_models_to_cache(
            request.provider_id, request.api_key_id, unique_models
        )

    return {
        "success": len(unique_models) > 0,
        "data": {"models": unique_models, "error": error, "from_cache": False},
        "provider": {
            "id": provider.id,
            "name": provider.name,
        },
    }


@router.post("/test-model")
async def test_model(
    request: TestModelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    测试模型连接性

    向指定提供商的指定模型发送测试请求，验证模型是否可用
    """
    # 获取提供商及其端点和 Keys
    provider = (
        db.query(Provider)
        .options(
            joinedload(Provider.endpoints),
            joinedload(Provider.api_keys),
        )
        .filter(Provider.id == request.provider_id)
        .first()
    )

    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    # 构建 api_format -> endpoint 映射 和 id -> endpoint 映射
    format_to_endpoint: dict[str, ProviderEndpoint] = {}
    id_to_endpoint: dict[str, ProviderEndpoint] = {}
    for ep in provider.endpoints:
        if ep.is_active:
            format_to_endpoint[ep.api_format] = ep
            id_to_endpoint[ep.id] = ep

    # 找到合适的端点和 API Key
    endpoint = None
    api_key = None

    # 优先级: api_format > endpoint_id > api_key_id > 自动选择
    # 如果指定了 api_format，优先使用该格式对应的 endpoint
    if request.api_format:
        endpoint = format_to_endpoint.get(request.api_format)
        if not endpoint:
            raise HTTPException(
                status_code=404,
                detail=f"No active endpoint found for API format: {request.api_format}"
            )

        if request.api_key_id:
            # 使用指定的 Key，但需要校验是否支持该格式
            api_key = next(
                (key for key in provider.api_keys if key.id == request.api_key_id and key.is_active),
                None
            )
            if api_key and request.api_format not in (api_key.api_formats or []):
                raise HTTPException(
                    status_code=400,
                    detail=f"API Key does not support format: {request.api_format}"
                )
        else:
            # 找支持该格式的第一个可用 Key
            for key in provider.api_keys:
                if not key.is_active:
                    continue
                if request.api_format in (key.api_formats or []):
                    api_key = key
                    break
    elif request.endpoint_id:
        # 使用指定的端点
        endpoint = id_to_endpoint.get(request.endpoint_id)
        if not endpoint:
            raise HTTPException(status_code=404, detail="Endpoint not found or not active")

        if request.api_key_id:
            # 同时指定了 Key，需要校验是否支持该端点格式
            api_key = next(
                (key for key in provider.api_keys if key.id == request.api_key_id and key.is_active),
                None
            )
            if api_key and endpoint.api_format not in (api_key.api_formats or []):
                raise HTTPException(
                    status_code=400,
                    detail=f"API Key does not support endpoint format: {endpoint.api_format}"
                )
        else:
            # 找支持该端点格式的第一个可用 Key
            for key in provider.api_keys:
                if not key.is_active:
                    continue
                if endpoint.api_format in (key.api_formats or []):
                    api_key = key
                    break
    elif request.api_key_id:
        # 使用指定的 API Key
        api_key = next(
            (key for key in provider.api_keys if key.id == request.api_key_id and key.is_active),
            None
        )
        if api_key:
            # 找到该 Key 支持的第一个活跃 Endpoint
            for fmt in (api_key.api_formats or []):
                if fmt in format_to_endpoint:
                    endpoint = format_to_endpoint[fmt]
                    break
    else:
        # 使用第一个可用的端点和密钥
        for ep in provider.endpoints:
            if not ep.is_active:
                continue
            # 找支持该格式的第一个可用 Key
            for key in provider.api_keys:
                if not key.is_active:
                    continue
                if ep.api_format in (key.api_formats or []):
                    endpoint = ep
                    api_key = key
                    break
            if endpoint:
                break

    if not endpoint or not api_key:
        raise HTTPException(status_code=404, detail="No active endpoint or API key found")

    try:
        api_key_value = crypto_service.decrypt(api_key.api_key)
    except Exception as e:
        logger.error(f"[test-model] Failed to decrypt API key: {e}")
        raise HTTPException(status_code=500, detail="Failed to decrypt API key")

    # 构建请求配置
    endpoint_config = {
        "api_key": api_key_value,
        "api_key_id": api_key.id,  # 添加API Key ID用于用量记录
        "base_url": endpoint.base_url,
        "api_format": endpoint.api_format,
        "extra_headers": get_extra_headers_from_endpoint(endpoint),
        "timeout": TimeoutDefaults.HTTP_REQUEST,
    }

    try:
        # 获取对应的 Adapter 类
        adapter_class = _get_adapter_for_format(endpoint.api_format)
        if not adapter_class:
            return {
                "success": False,
                "error": f"Unknown API format: {endpoint.api_format}",
                "provider": {
                    "id": provider.id,
                    "name": provider.name,
                },
                "model": request.model_name,
            }

        logger.debug(f"[test-model] 使用 Adapter: {adapter_class.__name__}")
        logger.debug(f"[test-model] 端点 API Format: {endpoint.api_format}")

        # 准备测试请求数据
        check_request = {
            "model": request.model_name,
            "messages": [
                {"role": "user", "content": request.message or "Hello! This is a test message."}
            ],
            "max_tokens": 30,
            "temperature": 0.7,
        }

        # 发送测试请求
        async with httpx.AsyncClient(timeout=endpoint_config["timeout"], verify=get_ssl_context()) as client:
            # 非流式测试
            logger.debug(f"[test-model] 开始非流式测试...")

            response = await adapter_class.check_endpoint(
                client,
                endpoint_config["base_url"],
                endpoint_config["api_key"],
                check_request,
                endpoint_config.get("extra_headers"),
                # 用量计算参数（现在强制记录）
                db=db,
                user=current_user,
                provider_name=provider.name,
                provider_id=provider.id,
                api_key_id=endpoint_config.get("api_key_id"),
                model_name=request.model_name,
            )

            # 记录提供商返回信息
            logger.debug(f"[test-model] 非流式测试结果:")
            logger.debug(f"[test-model] Status Code: {response.get('status_code')}")
            logger.debug(f"[test-model] Response Headers: {response.get('headers', {})}")
            response_data = response.get('response', {})
            response_body = response_data.get('response_body', {})
            logger.debug(f"[test-model] Response Data: {response_data}")
            logger.debug(f"[test-model] Response Body: {response_body}")
            # 尝试解析 response_body (通常是 JSON 字符串)
            parsed_body = response_body
            import json
            if isinstance(response_body, str):
                try:
                    parsed_body = json.loads(response_body)
                except json.JSONDecodeError:
                    pass

            if isinstance(parsed_body, dict) and 'error' in parsed_body:
                error_obj = parsed_body['error']
                # 兼容 error 可能是字典或字符串的情况
                if isinstance(error_obj, dict):
                    logger.debug(f"[test-model] Error Message: {error_obj.get('message')}")
                    raise HTTPException(status_code=500, detail=error_obj.get('message'))
                else:
                    logger.debug(f"[test-model] Error: {error_obj}")
                    raise HTTPException(status_code=500, detail=error_obj)
            elif 'error' in response:
                logger.debug(f"[test-model] Error: {response['error']}")
                raise HTTPException(status_code=500, detail=response['error'])
            else:
                # 如果有选择或消息，记录内容预览
                if isinstance(response_data, dict):
                    if 'choices' in response_data and response_data['choices']:
                        choice = response_data['choices'][0]
                        if 'message' in choice:
                            content = choice['message'].get('content', '')
                            logger.debug(f"[test-model] Content Preview: {content[:200]}...")
                    elif 'content' in response_data and response_data['content']:
                        content = str(response_data['content'])
                        logger.debug(f"[test-model] Content Preview: {content[:200]}...")

            # 检查测试是否成功（基于HTTP状态码）
            status_code = response.get('status_code', 0)
            is_success = status_code == 200 and 'error' not in response

            return {
                "success": is_success,
                "data": {
                    "stream": False,
                    "response": response,
                },
                "provider": {
                    "id": provider.id,
                    "name": provider.name,
                },
                "model": request.model_name,
                "endpoint": {
                    "id": endpoint.id,
                    "api_format": endpoint.api_format,
                    "base_url": endpoint.base_url,
                },
            }

    except Exception as e:
        logger.error(f"[test-model] Error testing model {request.model_name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "provider": {
                "id": provider.id,
                "name": provider.name,
            },
            "model": request.model_name,
            "endpoint": {
                "id": endpoint.id,
                "api_format": endpoint.api_format,
                "base_url": endpoint.base_url,
            } if endpoint else None,
        }
