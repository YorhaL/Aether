"""
OpenAI CLI / Responses Normalizer (OPENAI_CLI)

目标：
- 将 OpenAI Responses API（/v1/responses）映射到 InternalRequest / InternalResponse
- 支持流式事件：response.output_text.delta / response.completed 等

说明：
- 这里实现的是“最佳努力”的最小可用映射，重点覆盖文本与 usage。
- 未识别的字段会进入 extra/raw，未知内容块保留在 internal，但默认输出阶段会丢弃。
"""

import json
import time
from typing import Any

from src.core.api_format.conversion.field_mappings import (
    ERROR_TYPE_MAPPINGS,
    RETRYABLE_ERROR_TYPES,
)
from src.core.api_format.conversion.internal import (
    ContentBlock,
    ContentType,
    ErrorType,
    FormatCapabilities,
    InstructionSegment,
    InternalError,
    InternalMessage,
    InternalRequest,
    InternalResponse,
    Role,
    StopReason,
    TextBlock,
    ToolChoice,
    ToolChoiceType,
    ToolDefinition,
    ToolResultBlock,
    ToolUseBlock,
    UnknownBlock,
    UsageInfo,
)
from src.core.api_format.conversion.normalizer import FormatNormalizer
from src.core.api_format.conversion.stream_events import (
    ContentBlockStartEvent,
    ContentBlockStopEvent,
    ContentDeltaEvent,
    ErrorEvent,
    InternalStreamEvent,
    MessageStartEvent,
    MessageStopEvent,
    ToolCallDeltaEvent,
    UnknownStreamEvent,
)
from src.core.api_format.conversion.stream_state import StreamState


class OpenAICliNormalizer(FormatNormalizer):
    FORMAT_ID = "openai:cli"
    capabilities = FormatCapabilities(
        supports_stream=True,
        supports_error_conversion=True,
        supports_tools=True,
        supports_images=True,
    )

    _ERROR_TYPE_TO_OPENAI: dict[ErrorType, str] = {
        ErrorType.INVALID_REQUEST: "invalid_request_error",
        ErrorType.AUTHENTICATION: "invalid_api_key",
        ErrorType.PERMISSION_DENIED: "invalid_request_error",
        ErrorType.NOT_FOUND: "not_found",
        ErrorType.RATE_LIMIT: "rate_limit_exceeded",
        ErrorType.OVERLOADED: "server_error",
        ErrorType.SERVER_ERROR: "server_error",
        ErrorType.CONTENT_FILTERED: "content_policy_violation",
        ErrorType.CONTEXT_LENGTH_EXCEEDED: "context_length_exceeded",
        ErrorType.UNKNOWN: "server_error",
    }

    # =========================
    # Requests
    # =========================

    def request_to_internal(self, request: dict[str, Any]) -> InternalRequest:
        model = str(request.get("model") or "")

        instructions_text = request.get("instructions")
        instructions: list[InstructionSegment] = []
        system_text: str | None = None
        if isinstance(instructions_text, str) and instructions_text.strip():
            system_text = instructions_text
            instructions.append(InstructionSegment(role=Role.SYSTEM, text=instructions_text))

        messages = self._input_to_internal_messages(request.get("input"))

        tools = self._tools_to_internal(request.get("tools"))
        tool_choice = self._tool_choice_to_internal(request.get("tool_choice"))

        max_tokens = self._optional_int(request.get("max_output_tokens", request.get("max_tokens")))

        internal = InternalRequest(
            model=model,
            messages=messages,
            instructions=instructions,
            system=system_text,
            max_tokens=max_tokens,
            temperature=self._optional_float(request.get("temperature")),
            top_p=self._optional_float(request.get("top_p")),
            stop_sequences=self._coerce_str_list(request.get("stop")),
            stream=bool(request.get("stream") or False),
            tools=tools,
            tool_choice=tool_choice,
            extra={"openai_cli": self._extract_extra(request, {"input"})},
        )

        return internal

    def request_from_internal(self, internal: InternalRequest) -> dict[str, Any]:
        result: dict[str, Any] = {
            "model": internal.model,
            "input": self._internal_messages_to_input(internal.messages),
        }

        instructions_text = self._join_instructions(internal)
        if instructions_text:
            result["instructions"] = instructions_text

        if internal.max_tokens is not None:
            # Responses API 使用 max_output_tokens；兼容层仍可能接受 max_tokens
            result["max_output_tokens"] = internal.max_tokens
        if internal.temperature is not None:
            result["temperature"] = internal.temperature
        if internal.top_p is not None:
            result["top_p"] = internal.top_p
        if internal.stop_sequences:
            result["stop"] = list(internal.stop_sequences)
        if internal.stream:
            result["stream"] = True

        if internal.tools:
            result["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters or {},
                        **(t.extra.get("openai_function") or {}),
                    },
                    **(t.extra.get("openai_tool") or {}),
                }
                for t in internal.tools
            ]

        if internal.tool_choice:
            result["tool_choice"] = self._tool_choice_to_openai(internal.tool_choice)

        return result

    # =========================
    # Responses
    # =========================

    def response_to_internal(self, response: dict[str, Any]) -> InternalResponse:
        payload = self._unwrap_response_object(response)

        rid = str(payload.get("id") or "")
        model = str(payload.get("model") or "")

        blocks, extra = self._extract_output_text_blocks(payload)
        usage = self._usage_to_internal(payload.get("usage"))

        stop_reason = StopReason.UNKNOWN
        status = payload.get("status")
        if isinstance(status, str) and status == "completed":
            stop_reason = StopReason.END_TURN

        return InternalResponse(
            id=rid,
            model=model,
            content=blocks,
            stop_reason=stop_reason,
            usage=usage,
            extra=extra,
        )

    def response_from_internal(
        self,
        internal: InternalResponse,
        *,
        requested_model: str | None = None,
    ) -> dict[str, Any]:
        text = self._collapse_internal_text(internal.content)

        output_message = {
            "type": "message",
            "id": f"msg_{internal.id or 'stream'}",
            "role": "assistant",
            "content": [{"type": "output_text", "text": text}],
        }

        usage = internal.usage or UsageInfo()
        usage_obj: dict[str, Any] = {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": usage.total_tokens or (usage.input_tokens + usage.output_tokens),
        }

        # 优先使用用户请求的原始模型名，回退到上游返回的模型名
        model_name = requested_model if requested_model else (internal.model or "")

        return {
            "id": internal.id or "resp",
            "object": "response",
            "created": int(time.time()),
            "model": model_name,
            "status": "completed",
            "output": [output_message],
            "usage": usage_obj,
        }

    # =========================
    # Stream conversion
    # =========================

    def stream_chunk_to_internal(
        self,
        chunk: dict[str, Any],
        state: StreamState,
    ) -> list[InternalStreamEvent]:
        ss = state.substate(self.FORMAT_ID)
        events: list[InternalStreamEvent] = []

        # 统一错误结构（最佳努力）
        if isinstance(chunk, dict) and "error" in chunk:
            try:
                events.append(ErrorEvent(error=self.error_to_internal(chunk)))
            except Exception:
                pass
            return events

        etype = str(chunk.get("type") or "")

        # 尽量在首次事件补齐 message_start
        if not ss.get("message_started"):
            resp_obj = chunk.get("response")
            resp_obj = resp_obj if isinstance(resp_obj, dict) else {}
            msg_id = str(resp_obj.get("id") or chunk.get("id") or state.message_id or "")
            # 保留初始化时设置的 model（客户端请求的模型），仅在空时用上游值
            model = state.model or str(resp_obj.get("model") or chunk.get("model") or "")
            if msg_id or model or etype:
                state.message_id = msg_id
                if not state.model:
                    state.model = model
                ss["message_started"] = True
                ss.setdefault("text_block_started", False)
                ss.setdefault("text_block_stopped", False)
                events.append(MessageStartEvent(message_id=msg_id, model=model))

        # response.created：响应创建事件，message_start 已在上面处理
        if etype == "response.created":
            return events

        # 文本增量：response.output_text.delta
        if etype in ("response.output_text.delta", "response.outtext.delta"):
            delta = chunk.get("delta")
            delta_text = ""
            if isinstance(delta, str):
                delta_text = delta
            elif isinstance(delta, dict) and isinstance(delta.get("text"), str):
                delta_text = str(delta.get("text") or "")

            if delta_text:
                if not ss.get("text_block_started"):
                    ss["text_block_started"] = True
                    events.append(
                        ContentBlockStartEvent(block_index=0, block_type=ContentType.TEXT)
                    )
                events.append(ContentDeltaEvent(block_index=0, text_delta=delta_text))
            return events

        # 文本完成：response.output_text.done（可选）
        if etype == "response.output_text.done":
            if ss.get("text_block_started") and not ss.get("text_block_stopped"):
                ss["text_block_stopped"] = True
                events.append(ContentBlockStopEvent(block_index=0))
            return events

        # 完成：response.completed（包含 usage）
        if etype == "response.completed":
            resp_obj = chunk.get("response")
            resp_obj = resp_obj if isinstance(resp_obj, dict) else {}
            usage = self._usage_to_internal(resp_obj.get("usage") or chunk.get("usage"))

            if ss.get("text_block_started") and not ss.get("text_block_stopped"):
                ss["text_block_stopped"] = True
                events.append(ContentBlockStopEvent(block_index=0))

            events.append(MessageStopEvent(stop_reason=StopReason.END_TURN, usage=usage))
            return events

        # 失败：response.failed（最佳努力）
        if etype == "response.failed":
            try:
                events.append(ErrorEvent(error=self.error_to_internal(chunk)))
            except Exception:
                pass
            return events

        # response.in_progress：状态更新，不产生内容事件
        if etype == "response.in_progress":
            # 更新 state 中的元数据（如果有）
            # 注意：model 保持初始值（客户端请求的模型），不被上游覆盖
            resp_obj = chunk.get("response")
            if isinstance(resp_obj, dict):
                if resp_obj.get("id"):
                    state.message_id = str(resp_obj.get("id"))
                # 仅在 model 为空时才用上游值
                if not state.model and resp_obj.get("model"):
                    state.model = str(resp_obj.get("model"))
            return []

        # response.output_item.added：新输出项添加（如 message、function_call 等）
        if etype == "response.output_item.added":
            item = chunk.get("item")
            if isinstance(item, dict):
                item_type = item.get("type")
                # function_call 输出项
                if item_type == "function_call":
                    if not ss.get("tool_block_started"):
                        ss["tool_block_started"] = True
                        ss["current_tool_id"] = item.get("call_id") or item.get("id") or ""
                        ss["current_tool_name"] = item.get("name") or ""
                        events.append(
                            ContentBlockStartEvent(
                                block_index=ss.get("block_index", 0),
                                block_type=ContentType.TOOL_USE,
                                extra={
                                    "tool_id": ss["current_tool_id"],
                                    "tool_name": ss["current_tool_name"],
                                },
                            )
                        )
                        ss["block_index"] = ss.get("block_index", 0) + 1
                # message 输出项
                elif item_type == "message":
                    # 通常在 response.created 时已处理，这里可以忽略或更新状态
                    pass
            return events

        # response.output_item.done：输出项完成
        if etype == "response.output_item.done":
            item = chunk.get("item")
            if isinstance(item, dict):
                item_type = item.get("type")
                if item_type == "function_call" and ss.get("tool_block_started"):
                    ss["tool_block_started"] = False
                    events.append(ContentBlockStopEvent(block_index=ss.get("block_index", 1) - 1))
            return events

        # response.function_call_arguments.delta：工具调用参数增量
        if etype == "response.function_call_arguments.delta":
            delta = chunk.get("delta") or ""
            if delta:
                events.append(
                    ToolCallDeltaEvent(
                        block_index=ss.get("block_index", 1) - 1,
                        tool_id=ss.get("current_tool_id", ""),
                        input_delta=delta,
                    )
                )
            return events

        # response.function_call_arguments.done：工具调用参数完成
        if etype == "response.function_call_arguments.done":
            # 参数已完整，不产生额外事件
            return []

        # response.content_part.added / response.content_part.done：内容部分事件
        if etype in ("response.content_part.added", "response.content_part.done"):
            # 通常伴随 output_text 事件，这里可以忽略
            return []

        # response.reasoning_summary_text.delta：推理摘要增量
        if etype == "response.reasoning_summary_text.delta":
            # 保留为 UnknownStreamEvent，让下游决定是否使用
            return [UnknownStreamEvent(raw_type=etype, payload=chunk)]

        # response.reasoning_summary_text.done：推理摘要完成
        if etype == "response.reasoning_summary_text.done":
            return [UnknownStreamEvent(raw_type=etype, payload=chunk)]

        if etype:
            return [UnknownStreamEvent(raw_type=etype, payload=chunk)]
        return [UnknownStreamEvent(raw_type="unknown", payload=chunk)]

    def stream_event_from_internal(
        self,
        event: InternalStreamEvent,
        state: StreamState,
    ) -> list[dict[str, Any]]:
        ss = state.substate(self.FORMAT_ID)
        out: list[dict[str, Any]] = []

        def event_block(payload: dict[str, Any]) -> dict[str, Any]:
            # OpenAI Responses SSE 的 payload 通常自带 type 字段；这里强制保证
            return payload

        if isinstance(event, MessageStartEvent):
            state.message_id = event.message_id or state.message_id or "resp_stream"
            # 保留初始化时设置的 model（客户端请求的模型），仅在空时用事件值
            if not state.model:
                state.model = event.model or ""
            ss.setdefault("collected_text", "")
            out.append(
                event_block(
                    {
                        "type": "response.created",
                        "response": {
                            "id": state.message_id,
                            "object": "response",
                            "created": int(time.time()),
                            "model": state.model,
                            "status": "in_progress",
                            "output": [],
                        },
                    }
                )
            )
            return out

        if isinstance(event, ContentDeltaEvent):
            if event.text_delta:
                ss["collected_text"] = str(ss.get("collected_text") or "") + event.text_delta
                out.append(
                    event_block(
                        {
                            "type": "response.output_text.delta",
                            "delta": event.text_delta,
                        }
                    )
                )
            return out

        if isinstance(event, MessageStopEvent):
            final_text = str(ss.get("collected_text") or "")
            response_obj = self.response_from_internal(
                InternalResponse(
                    id=state.message_id or "resp",
                    model=state.model or "",
                    content=[TextBlock(text=final_text)] if final_text else [],
                    stop_reason=event.stop_reason or StopReason.END_TURN,
                    usage=event.usage or UsageInfo(),
                )
            )
            out.append(event_block({"type": "response.completed", "response": response_obj}))
            return out

        if isinstance(event, ErrorEvent):
            err_payload = self.error_from_internal(event.error)
            err_payload["type"] = "response.failed"
            out.append(event_block(err_payload))
            return out

        # 其他事件：Responses SSE 无直接对应，跳过
        return out

    # =========================
    # Error conversion
    # =========================

    def is_error_response(self, response: dict[str, Any]) -> bool:
        return isinstance(response, dict) and "error" in response

    def error_to_internal(self, error_response: dict[str, Any]) -> InternalError:
        err = error_response.get("error") if isinstance(error_response, dict) else None
        err = err if isinstance(err, dict) else {}

        raw_type = err.get("type")
        mapped = ERROR_TYPE_MAPPINGS.get("OPENAI", {}).get(str(raw_type), ErrorType.UNKNOWN.value)
        internal_type = self._error_type_from_value(mapped)
        retryable = internal_type.value in RETRYABLE_ERROR_TYPES

        return InternalError(
            type=internal_type,
            message=str(err.get("message") or ""),
            code=err.get("code") if err.get("code") is None else str(err.get("code")),
            param=err.get("param") if err.get("param") is None else str(err.get("param")),
            retryable=retryable,
            extra={"openai_cli": {"error": err}, "raw": {"type": raw_type}},
        )

    def error_from_internal(self, internal: InternalError) -> dict[str, Any]:
        type_str = self._ERROR_TYPE_TO_OPENAI.get(internal.type, "server_error")
        payload: dict[str, Any] = {"type": type_str, "message": internal.message}
        if internal.code is not None:
            payload["code"] = internal.code
        if internal.param is not None:
            payload["param"] = internal.param
        return {"error": payload}

    # =========================
    # Helpers
    # =========================

    def _unwrap_response_object(self, response: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(response, dict):
            return {}
        resp_inner = response.get("response")
        if isinstance(resp_inner, dict) and isinstance(response.get("type"), str):
            # 例如：{"type": "response.completed", "response": {...}}
            return resp_inner
        return response

    def _extract_output_text_blocks(
        self, payload: dict[str, Any]
    ) -> tuple[list[ContentBlock], dict[str, Any]]:
        text_parts: list[str] = []

        output = payload.get("output")
        if isinstance(output, list):
            for item in output:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "message":
                    content = item.get("content")
                    if isinstance(content, list):
                        for part in content:
                            if not isinstance(part, dict):
                                continue
                            ptype = str(part.get("type") or "")
                            if ptype in ("output_text", "text") and isinstance(
                                part.get("text"), str
                            ):
                                text_parts.append(part.get("text") or "")
                    continue

                if item.get("type") in ("output_text", "text") and isinstance(
                    item.get("text"), str
                ):
                    text_parts.append(item.get("text") or "")

        # 兼容：部分实现可能直接给 output_text
        if not text_parts and isinstance(payload.get("output_text"), str):
            text_parts.append(payload.get("output_text") or "")

        blocks: list[ContentBlock] = []
        text = "".join(text_parts)
        if text:
            blocks.append(TextBlock(text=text))

        extra: dict[str, Any] = {"raw": {"openai_cli_output": output}} if output is not None else {}
        return blocks, extra

    def _usage_to_internal(self, usage: Any) -> UsageInfo:
        if not isinstance(usage, dict):
            return UsageInfo()
        input_tokens = int(usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or (input_tokens + output_tokens))
        return UsageInfo(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            extra={"openai_cli": {"usage": usage}},
        )

    def _collapse_internal_text(self, blocks: list[ContentBlock]) -> str:
        parts: list[str] = []
        for block in blocks:
            if isinstance(block, TextBlock) and block.text:
                parts.append(block.text)
        return "".join(parts)

    def _input_to_internal_messages(self, input_data: Any) -> list[InternalMessage]:
        if input_data is None:
            return []

        # input: "text"
        if isinstance(input_data, str):
            return [InternalMessage(role=Role.USER, content=[TextBlock(text=input_data)])]

        # input: {"messages": [...]}
        if isinstance(input_data, dict) and isinstance(input_data.get("messages"), list):
            input_data = input_data.get("messages")

        if not isinstance(input_data, list):
            return [
                InternalMessage(
                    role=Role.USER,
                    content=[UnknownBlock(raw_type="input", payload={"input": input_data})],
                )
            ]

        messages: list[InternalMessage] = []
        for item in input_data:
            if not isinstance(item, dict):
                continue

            item_type = str(item.get("type") or "")

            # 标准 message（有 role 字段）
            if item_type == "message" or item.get("role"):
                role = self._role_from_value(item.get("role"))
                blocks = self._responses_content_to_blocks(item.get("content"))
                messages.append(
                    InternalMessage(
                        role=role,
                        content=blocks,
                        extra=self._extract_extra(item, {"type", "role", "content"}),
                    )
                )
                continue

            # function_call -> assistant 消息 + ToolUseBlock
            if item_type == "function_call":
                tool_id = str(item.get("call_id") or item.get("id") or "")
                tool_name = str(item.get("name") or "")
                args_raw = item.get("arguments") or "{}"
                try:
                    tool_input = (
                        json.loads(args_raw)
                        if isinstance(args_raw, str)
                        else (args_raw if isinstance(args_raw, dict) else {})
                    )
                except (json.JSONDecodeError, TypeError):
                    tool_input = {"_raw": args_raw}
                tool_block = ToolUseBlock(
                    tool_id=tool_id,
                    tool_name=tool_name,
                    tool_input=tool_input,
                    extra={
                        "openai_cli": self._extract_extra(
                            item, {"type", "call_id", "id", "name", "arguments"}
                        )
                    },
                )
                messages.append(InternalMessage(role=Role.ASSISTANT, content=[tool_block]))
                continue

            # function_call_output -> tool 消息 + ToolResultBlock
            if item_type == "function_call_output":
                tool_use_id = str(item.get("call_id") or item.get("id") or "")
                output = item.get("output")
                # output 可能是字符串或结构化数据
                content_text = output if isinstance(output, str) else None
                result_block = ToolResultBlock(
                    tool_use_id=tool_use_id,
                    output=output,
                    content_text=content_text,
                    extra={
                        "openai_cli": self._extract_extra(item, {"type", "call_id", "id", "output"})
                    },
                )
                messages.append(InternalMessage(role=Role.TOOL, content=[result_block]))
                continue

            # reasoning -> assistant 消息，提取 summary 作为文本
            if item_type == "reasoning":
                summary_parts: list[str] = []
                summary = item.get("summary")
                if isinstance(summary, list):
                    for s in summary:
                        if isinstance(s, dict) and s.get("type") == "summary_text":
                            text = s.get("text")
                            if isinstance(text, str) and text:
                                summary_parts.append(text)
                        elif isinstance(s, str) and s:
                            summary_parts.append(s)
                elif isinstance(summary, str) and summary:
                    summary_parts.append(summary)

                # 如果有 summary 文本，创建一个 UnknownBlock 保留原始结构
                reasoning_blocks: list[ContentBlock] = []
                if summary_parts:
                    # 保留 reasoning 的 summary 作为 UnknownBlock，便于输出时决策
                    reasoning_blocks.append(
                        UnknownBlock(
                            raw_type="reasoning",
                            payload={"summary_text": "\n".join(summary_parts), "original": item},
                        )
                    )
                else:
                    reasoning_blocks.append(UnknownBlock(raw_type="reasoning", payload=item))
                messages.append(
                    InternalMessage(
                        role=Role.ASSISTANT,
                        content=reasoning_blocks,
                        extra={"openai_cli": {"type": "reasoning"}},
                    )
                )
                continue

            # 其他未知类型 -> 保留为 UnknownBlock
            messages.append(
                InternalMessage(
                    role=Role.UNKNOWN,
                    content=[UnknownBlock(raw_type=item_type or "unknown", payload=item)],
                )
            )

        return messages

    def _responses_content_to_blocks(self, content: Any) -> list[ContentBlock]:
        if content is None:
            return []
        if isinstance(content, str):
            return [TextBlock(text=content)]
        if isinstance(content, dict) and isinstance(content.get("text"), str):
            return [TextBlock(text=str(content.get("text") or ""))]

        if not isinstance(content, list):
            return [UnknownBlock(raw_type="content", payload={"content": content})]

        blocks: list[ContentBlock] = []
        for part in content:
            if isinstance(part, str):
                if part:
                    blocks.append(TextBlock(text=part))
                continue
            if not isinstance(part, dict):
                continue
            ptype = str(part.get("type") or "")
            if ptype in ("input_text", "output_text", "text") and isinstance(part.get("text"), str):
                text = part.get("text") or ""
                if text:
                    blocks.append(TextBlock(text=text))
                continue
            blocks.append(UnknownBlock(raw_type=ptype or "unknown", payload=part))
        return blocks

    def _internal_messages_to_input(self, messages: list[InternalMessage]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for msg in messages:
            # ToolUseBlock -> function_call
            for block in msg.content:
                if isinstance(block, ToolUseBlock):
                    out.append(
                        {
                            "type": "function_call",
                            "call_id": block.tool_id,
                            "name": block.tool_name,
                            "arguments": (
                                json.dumps(block.tool_input, ensure_ascii=False)
                                if block.tool_input
                                else "{}"
                            ),
                        }
                    )
                    continue

                if isinstance(block, ToolResultBlock):
                    out.append(
                        {
                            "type": "function_call_output",
                            "call_id": block.tool_use_id,
                            "output": (
                                block.content_text
                                if block.content_text is not None
                                else block.output
                            ),
                        }
                    )
                    continue

                # reasoning（UnknownBlock with raw_type="reasoning"）
                if isinstance(block, UnknownBlock) and block.raw_type == "reasoning":
                    payload = block.payload or {}
                    original = payload.get("original")
                    if isinstance(original, dict):
                        # 尽量还原原始结构
                        out.append(original)
                    else:
                        summary_text = payload.get("summary_text", "")
                        out.append(
                            {
                                "type": "reasoning",
                                "summary": (
                                    [{"type": "summary_text", "text": summary_text}]
                                    if summary_text
                                    else []
                                ),
                            }
                        )
                    continue

            # 普通 message（TextBlock）
            role = self._role_to_openai(msg.role)
            content_items: list[dict[str, Any]] = []
            has_text = False

            for block in msg.content:
                if isinstance(block, (ToolUseBlock, ToolResultBlock)):
                    continue  # 已在上面处理
                if isinstance(block, UnknownBlock) and block.raw_type == "reasoning":
                    continue  # 已在上面处理
                if isinstance(block, UnknownBlock):
                    continue  # 跳过其他未知块
                if isinstance(block, TextBlock) and block.text:
                    content_items.append({"type": "input_text", "text": block.text})
                    has_text = True

            if has_text:
                out.append({"type": "message", "role": role, "content": content_items})

        return out

    def _tools_to_internal(self, tools: Any) -> list[ToolDefinition] | None:
        if not isinstance(tools, list):
            return None
        out: list[ToolDefinition] = []
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            if tool.get("type") == "function" and isinstance(tool.get("function"), dict):
                fn = tool["function"]
                name = str(fn.get("name") or "")
                if not name:
                    continue
                out.append(
                    ToolDefinition(
                        name=name,
                        description=fn.get("description"),
                        parameters=(
                            fn.get("parameters") if isinstance(fn.get("parameters"), dict) else None
                        ),
                        extra={
                            "openai_tool": self._extract_extra(tool, {"type", "function"}),
                            "openai_function": self._extract_extra(
                                fn, {"name", "description", "parameters"}
                            ),
                        },
                    )
                )
                continue

            # 兼容：部分实现可能直接给 {name, description, parameters}
            name = str(tool.get("name") or "")
            if name:
                out.append(
                    ToolDefinition(
                        name=name,
                        description=tool.get("description"),
                        parameters=(
                            tool.get("parameters")
                            if isinstance(tool.get("parameters"), dict)
                            else None
                        ),
                        extra={
                            "openai_cli": self._extract_extra(
                                tool, {"name", "description", "parameters"}
                            )
                        },
                    )
                )
        return out or None

    def _tool_choice_to_internal(self, tool_choice: Any) -> ToolChoice | None:
        if tool_choice is None:
            return None
        if isinstance(tool_choice, str):
            if tool_choice == "none":
                return ToolChoice(
                    type=ToolChoiceType.NONE, extra={"openai_cli": {"tool_choice": tool_choice}}
                )
            if tool_choice == "auto":
                return ToolChoice(
                    type=ToolChoiceType.AUTO, extra={"openai_cli": {"tool_choice": tool_choice}}
                )
            return ToolChoice(type=ToolChoiceType.AUTO, extra={"raw": tool_choice})

        if isinstance(tool_choice, dict):
            # OpenAI 兼容结构：{"type":"function","function":{"name":"..."}}
            if tool_choice.get("type") == "function" and isinstance(
                tool_choice.get("function"), dict
            ):
                name = str(tool_choice["function"].get("name") or "")
                return ToolChoice(
                    type=ToolChoiceType.TOOL, tool_name=name, extra={"openai_cli": tool_choice}
                )
            return ToolChoice(type=ToolChoiceType.AUTO, extra={"openai_cli": tool_choice})

        return ToolChoice(type=ToolChoiceType.AUTO, extra={"raw": tool_choice})

    def _tool_choice_to_openai(self, tool_choice: ToolChoice) -> str | dict[str, Any]:
        if tool_choice.type == ToolChoiceType.NONE:
            return "none"
        if tool_choice.type == ToolChoiceType.AUTO:
            return "auto"
        if tool_choice.type == ToolChoiceType.REQUIRED:
            return "required"
        if tool_choice.type == ToolChoiceType.TOOL:
            return {"type": "function", "function": {"name": tool_choice.tool_name or ""}}
        return "auto"

    def _role_from_value(self, role: Any) -> Role:
        value = str(role or "").lower()
        if value == "user":
            return Role.USER
        if value == "assistant":
            return Role.ASSISTANT
        if value == "system":
            return Role.SYSTEM
        if value == "developer":
            return Role.DEVELOPER
        if value == "tool":
            return Role.TOOL
        return Role.UNKNOWN

    def _role_to_openai(self, role: Role) -> str:
        if role == Role.USER:
            return "user"
        if role == Role.ASSISTANT:
            return "assistant"
        if role == Role.SYSTEM:
            return "system"
        if role == Role.DEVELOPER:
            return "developer"
        if role == Role.TOOL:
            return "tool"
        return "user"

    def _optional_int(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _optional_float(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _coerce_str_list(self, value: Any) -> list[str] | None:
        if value is None:
            return None
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            out: list[str] = []
            for item in value:
                if item is None:
                    continue
                out.append(str(item))
            return out
        return [str(value)]

    def _extract_extra(self, payload: dict[str, Any], keep_keys: set[str]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {}
        return {k: v for k, v in payload.items() if k not in keep_keys}

    def _join_instructions(self, internal: InternalRequest) -> str:
        if internal.instructions:
            parts: list[str] = []
            for seg in internal.instructions:
                if seg.text:
                    parts.append(seg.text)
            return "\n\n".join(parts)
        return internal.system or ""

    def _error_type_from_value(self, value: str) -> ErrorType:
        for t in ErrorType:
            if t.value == value:
                return t
        return ErrorType.UNKNOWN


__all__ = ["OpenAICliNormalizer"]
