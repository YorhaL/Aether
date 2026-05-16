use std::collections::BTreeMap;
use std::sync::Arc;

use aether_contracts::ResolvedTransportProfile;
use serde_json::Value;

use crate::ai_serving::planner::candidate_preparation::{
    prepare_header_authenticated_candidate, prepare_header_authenticated_candidate_from_auth,
    OauthPreparationContext,
};
use crate::ai_serving::planner::common::{
    endpoint_config_forces_body_stream_field, enforce_provider_body_stream_policy,
    request_requires_body_stream_field, resolve_upstream_is_stream_for_provider,
};
use crate::ai_serving::planner::spec_metadata::local_standard_spec_metadata;
use crate::ai_serving::planner::standard::{
    apply_codex_openai_responses_special_headers, request_body_build_failure_extra_data,
};
use crate::ai_serving::transport::kiro::{
    build_kiro_provider_headers, build_kiro_provider_request_body,
    is_kiro_claude_messages_transport, KiroProviderHeadersInput, KiroRequestAuth,
    KIRO_ENVELOPE_NAME,
};
use crate::ai_serving::transport::{
    build_grok_browser_headers, build_grok_upstream_url, build_kiro_cross_format_upstream_url,
    build_openai_image_headers, build_openai_image_upstream_url,
    build_standard_provider_request_headers, openai_image_transport_unsupported_reason,
    resolve_grok_session_auth, resolve_openai_image_auth, GrokHeaderInput,
    ProviderOpenAiImageHeadersInput, StandardProviderRequestHeadersInput, GROK_CHAT_PATH,
};
use crate::ai_serving::{
    build_openai_image_request_body_from_gemini_image_request, gemini_request_is_image_generation,
    CandidateFailureDiagnostic, GatewayProviderTransportSnapshot, LocalResolvedOAuthRequestAuth,
};
use crate::AppState;

use super::payload::{
    mark_skipped_local_standard_candidate, mark_skipped_local_standard_candidate_with_extra_data,
    mark_skipped_local_standard_candidate_with_failure_diagnostic,
};
use super::{LocalStandardCandidateAttempt, LocalStandardDecisionInput, LocalStandardSpec};

pub(crate) struct LocalStandardCandidatePayloadParts {
    pub(super) auth_header: String,
    pub(super) auth_value: String,
    pub(super) mapped_model: String,
    pub(super) provider_api_format: String,
    pub(super) provider_request_body: Value,
    pub(super) provider_request_headers: BTreeMap<String, String>,
    pub(super) upstream_url: String,
    pub(super) upstream_is_stream: bool,
    pub(super) envelope_name: Option<&'static str>,
    pub(super) transport: Arc<GatewayProviderTransportSnapshot>,
    pub(super) transport_profile: Option<ResolvedTransportProfile>,
}

fn is_grok_text_provider_api_format(provider_api_format: &str) -> bool {
    matches!(
        crate::ai_serving::normalize_api_format_alias(provider_api_format).as_str(),
        "openai:chat" | "openai:responses" | "openai:responses:compact" | "claude:messages"
    )
}

pub(crate) async fn resolve_local_standard_candidate_payload_parts(
    state: &AppState,
    parts: &http::request::Parts,
    trace_id: &str,
    body_json: &serde_json::Value,
    input: &LocalStandardDecisionInput,
    attempt: &LocalStandardCandidateAttempt,
    spec: LocalStandardSpec,
) -> Option<LocalStandardCandidatePayloadParts> {
    let spec_metadata = local_standard_spec_metadata(spec);
    let planner_state = crate::ai_serving::PlannerAppState::new(state);
    let candidate = &attempt.eligible.candidate;
    let transport = &attempt.eligible.transport;
    let transport_profile = crate::ai_serving::transport::resolve_transport_profile(transport);
    let provider_api_format = attempt.eligible.provider_api_format.as_str();
    let is_grok = transport
        .provider
        .provider_type
        .trim()
        .eq_ignore_ascii_case("grok");
    if spec_metadata.api_format == "gemini:generate_content"
        && provider_api_format == "openai:image"
        && gemini_request_is_image_generation(body_json)
    {
        return resolve_local_gemini_image_to_openai_image_candidate_payload_parts(
            state, parts, trace_id, body_json, input, attempt,
        )
        .await;
    }
    let is_kiro_claude_cli = is_kiro_claude_messages_transport(transport, provider_api_format);
    if is_grok && is_grok_text_provider_api_format(provider_api_format) {
        let prepared_candidate = match prepare_header_authenticated_candidate(
            planner_state,
            transport,
            candidate,
            resolve_grok_session_auth(transport),
            OauthPreparationContext {
                trace_id,
                api_format: provider_api_format,
                operation: "standard_family_grok_text_request",
            },
        )
        .await
        {
            Ok(prepared) => prepared,
            Err(skip_reason) => {
                mark_skipped_local_standard_candidate(
                    state,
                    input,
                    trace_id,
                    candidate,
                    attempt.candidate_index,
                    &attempt.candidate_id,
                    skip_reason,
                )
                .await;
                return None;
            }
        };

        let mut provider_request_body = body_json.clone();
        if let Some(object) = provider_request_body.as_object_mut() {
            object.insert(
                "model".to_string(),
                serde_json::Value::String(prepared_candidate.mapped_model.clone()),
            );
        }

        let upstream_is_stream = resolve_upstream_is_stream_for_provider(
            transport.endpoint.config.as_ref(),
            transport.provider.provider_type.as_str(),
            provider_api_format,
            spec_metadata.require_streaming,
            false,
        );
        let force_body_stream_field =
            endpoint_config_forces_body_stream_field(transport.endpoint.config.as_ref());
        enforce_provider_body_stream_policy(
            &mut provider_request_body,
            provider_api_format,
            upstream_is_stream,
            request_requires_body_stream_field(body_json, force_body_stream_field),
        );

        let upstream_url = build_grok_upstream_url(transport, GROK_CHAT_PATH);
        let Some(provider_request_headers) = build_grok_browser_headers(GrokHeaderInput {
            transport,
            transport_profile: transport_profile.as_ref(),
            request_headers: Some(&parts.headers),
            content_type: "application/json",
            accept: "text/event-stream",
            header_rules: transport.endpoint.header_rules.as_ref(),
            provider_request_body: &provider_request_body,
            original_request_body: body_json,
        }) else {
            mark_skipped_local_standard_candidate_with_failure_diagnostic(
                state,
                input,
                trace_id,
                candidate,
                attempt.candidate_index,
                &attempt.candidate_id,
                "transport_header_rules_apply_failed",
                CandidateFailureDiagnostic::header_rules_apply_failed(
                    spec_metadata.api_format,
                    provider_api_format,
                    "grok_standard_family_headers",
                ),
            )
            .await;
            return None;
        };

        return Some(LocalStandardCandidatePayloadParts {
            auth_header: prepared_candidate.auth_header,
            auth_value: prepared_candidate.auth_value,
            mapped_model: prepared_candidate.mapped_model,
            provider_api_format: provider_api_format.to_string(),
            provider_request_body,
            provider_request_headers,
            upstream_url,
            upstream_is_stream,
            envelope_name: None,
            transport: Arc::clone(transport),
            transport_profile,
        });
    }

    let Some(conversion_kind) =
        crate::ai_serving::request_conversion_kind(spec_metadata.api_format, provider_api_format)
    else {
        return None;
    };

    if let Some(skip_reason) = crate::ai_serving::request_conversion_transport_unsupported_reason(
        transport,
        conversion_kind,
    ) {
        mark_skipped_local_standard_candidate(
            state,
            input,
            trace_id,
            candidate,
            attempt.candidate_index,
            &attempt.candidate_id,
            skip_reason,
        )
        .await;
        return None;
    }

    let oauth_context = OauthPreparationContext {
        trace_id,
        api_format: provider_api_format,
        operation: "standard_family_cross_format",
    };
    let kiro_auth = if is_kiro_claude_cli {
        match crate::ai_serving::planner::candidate_preparation::resolve_candidate_oauth_auth(
            planner_state,
            transport,
            oauth_context,
        )
        .await
        {
            Some(LocalResolvedOAuthRequestAuth::Kiro(auth)) => Some(auth),
            _ => {
                mark_skipped_local_standard_candidate(
                    state,
                    input,
                    trace_id,
                    candidate,
                    attempt.candidate_index,
                    &attempt.candidate_id,
                    "transport_auth_unavailable",
                )
                .await;
                return None;
            }
        }
    } else {
        None
    };

    let prepared_candidate = if let Some(kiro_auth) = kiro_auth.as_ref() {
        match prepare_header_authenticated_candidate_from_auth(
            candidate,
            kiro_auth.name.to_string(),
            kiro_auth.value.clone(),
        ) {
            Ok(prepared) => prepared,
            Err(skip_reason) => {
                mark_skipped_local_standard_candidate(
                    state,
                    input,
                    trace_id,
                    candidate,
                    attempt.candidate_index,
                    &attempt.candidate_id,
                    skip_reason,
                )
                .await;
                return None;
            }
        }
    } else {
        match prepare_header_authenticated_candidate(
            planner_state,
            transport,
            candidate,
            crate::ai_serving::request_conversion_direct_auth(transport, conversion_kind),
            oauth_context,
        )
        .await
        {
            Ok(prepared) => prepared,
            Err(skip_reason) => {
                mark_skipped_local_standard_candidate(
                    state,
                    input,
                    trace_id,
                    candidate,
                    attempt.candidate_index,
                    &attempt.candidate_id,
                    skip_reason,
                )
                .await;
                return None;
            }
        }
    };

    let upstream_is_stream = resolve_upstream_is_stream_for_provider(
        transport.endpoint.config.as_ref(),
        transport.provider.provider_type.as_str(),
        provider_api_format,
        spec_metadata.require_streaming,
        is_kiro_claude_cli,
    );
    let force_body_stream_field =
        endpoint_config_forces_body_stream_field(transport.endpoint.config.as_ref());
    let enable_model_directives =
        crate::system_features::reasoning_model_directive_enabled_for_api_format_and_model(
            state,
            provider_api_format,
            Some(&input.requested_model),
        )
        .await;
    let mut provider_request_body =
        match crate::ai_serving::planner::standard::build_standard_request_body_with_model_directives_and_request_headers(
            body_json,
            spec_metadata.api_format,
            &prepared_candidate.mapped_model,
            transport.provider.provider_type.as_str(),
            provider_api_format,
            parts.uri.path(),
            upstream_is_stream,
            if is_kiro_claude_cli {
                None
            } else {
                transport.endpoint.body_rules.as_ref()
            },
            Some(input.auth_context.api_key_id.as_str()),
            Some(&parts.headers),
            enable_model_directives,
        ) {
            Some(body) => body,
            None => {
                mark_skipped_local_standard_candidate_with_extra_data(
                    state,
                    input,
                    trace_id,
                    candidate,
                    attempt.candidate_index,
                    &attempt.candidate_id,
                    "provider_request_body_build_failed",
                    request_body_build_failure_extra_data(
                        body_json,
                        spec_metadata.api_format,
                        provider_api_format,
                    ),
                )
                .await;
                return None;
            }
        };
    enforce_provider_body_stream_policy(
        &mut provider_request_body,
        provider_api_format,
        upstream_is_stream,
        request_requires_body_stream_field(body_json, force_body_stream_field),
    );
    if let Some(mapping) =
        crate::system_features::reasoning_model_directive_mapping_for_api_format_and_model(
            state,
            provider_api_format,
            Some(&input.requested_model),
        )
        .await
    {
        crate::ai_serving::apply_model_directive_mapping_patch(
            &mut provider_request_body,
            &mapping,
        );
        // Directive mapping is a deep-merge patch and may overwrite/add `stream`;
        // re-enforce stream-field policy afterward.
        enforce_provider_body_stream_policy(
            &mut provider_request_body,
            provider_api_format,
            upstream_is_stream,
            request_requires_body_stream_field(body_json, force_body_stream_field),
        );
    }

    if let Some(kiro_auth) = kiro_auth.as_ref() {
        return build_kiro_cross_format_payload_parts(
            state,
            parts,
            trace_id,
            body_json,
            input,
            attempt,
            transport,
            provider_api_format,
            prepared_candidate.mapped_model,
            prepared_candidate.auth_header,
            prepared_candidate.auth_value,
            provider_request_body,
            upstream_is_stream,
            kiro_auth,
        )
        .await;
    }

    let upstream_url = match crate::ai_serving::planner::standard::build_standard_upstream_url(
        parts,
        transport,
        &prepared_candidate.mapped_model,
        provider_api_format,
        upstream_is_stream,
    ) {
        Some(url) => url,
        None => {
            mark_skipped_local_standard_candidate_with_failure_diagnostic(
                state,
                input,
                trace_id,
                candidate,
                attempt.candidate_index,
                &attempt.candidate_id,
                "upstream_url_missing",
                CandidateFailureDiagnostic::upstream_url_missing(
                    spec_metadata.api_format,
                    provider_api_format,
                    "standard_family_url",
                ),
            )
            .await;
            return None;
        }
    };
    let Some(resolved_headers) =
        build_standard_provider_request_headers(StandardProviderRequestHeadersInput {
            transport,
            provider_api_format,
            same_format: false,
            headers: &parts.headers,
            auth_header: &prepared_candidate.auth_header,
            auth_value: &prepared_candidate.auth_value,
            extra_headers: &BTreeMap::new(),
            header_rules: transport.endpoint.header_rules.as_ref(),
            provider_request_body: &provider_request_body,
            original_request_body: body_json,
            upstream_is_stream,
        })
    else {
        mark_skipped_local_standard_candidate_with_failure_diagnostic(
            state,
            input,
            trace_id,
            candidate,
            attempt.candidate_index,
            &attempt.candidate_id,
            "transport_header_rules_apply_failed",
            CandidateFailureDiagnostic::header_rules_apply_failed(
                spec_metadata.api_format,
                provider_api_format,
                "standard_family_headers",
            ),
        )
        .await;
        return None;
    };
    let mut provider_request_headers = resolved_headers.headers;
    apply_codex_openai_responses_special_headers(
        &mut provider_request_headers,
        &provider_request_body,
        &parts.headers,
        transport.provider.provider_type.as_str(),
        provider_api_format,
        Some(trace_id),
        transport.key.decrypted_auth_config.as_deref(),
    );

    Some(LocalStandardCandidatePayloadParts {
        auth_header: resolved_headers.auth_header,
        auth_value: resolved_headers.auth_value,
        mapped_model: prepared_candidate.mapped_model,
        provider_api_format: provider_api_format.to_string(),
        provider_request_body,
        provider_request_headers,
        upstream_url,
        upstream_is_stream,
        envelope_name: None,
        transport: Arc::clone(transport),
        transport_profile: None,
    })
}

async fn resolve_local_gemini_image_to_openai_image_candidate_payload_parts(
    state: &AppState,
    parts: &http::request::Parts,
    trace_id: &str,
    body_json: &serde_json::Value,
    input: &LocalStandardDecisionInput,
    attempt: &LocalStandardCandidateAttempt,
) -> Option<LocalStandardCandidatePayloadParts> {
    let client_api_format = "gemini:generate_content";
    let provider_api_format = "openai:image";
    let planner_state = crate::ai_serving::PlannerAppState::new(state);
    let candidate = &attempt.eligible.candidate;
    let transport = &attempt.eligible.transport;

    if let Some(skip_reason) =
        openai_image_transport_unsupported_reason(transport, provider_api_format)
    {
        mark_skipped_local_standard_candidate(
            state,
            input,
            trace_id,
            candidate,
            attempt.candidate_index,
            &attempt.candidate_id,
            skip_reason,
        )
        .await;
        return None;
    }

    let prepared_candidate = match prepare_header_authenticated_candidate(
        planner_state,
        transport,
        candidate,
        resolve_openai_image_auth(transport),
        OauthPreparationContext {
            trace_id,
            api_format: provider_api_format,
            operation: "gemini_image_to_openai_image_candidate_request",
        },
    )
    .await
    {
        Ok(prepared) => prepared,
        Err(skip_reason) => {
            mark_skipped_local_standard_candidate(
                state,
                input,
                trace_id,
                candidate,
                attempt.candidate_index,
                &attempt.candidate_id,
                skip_reason,
            )
            .await;
            return None;
        }
    };

    let Some(converted) = build_openai_image_request_body_from_gemini_image_request(
        body_json,
        parts.uri.path(),
        &prepared_candidate.mapped_model,
    ) else {
        mark_skipped_local_standard_candidate_with_extra_data(
            state,
            input,
            trace_id,
            candidate,
            attempt.candidate_index,
            &attempt.candidate_id,
            "provider_request_body_build_failed",
            request_body_build_failure_extra_data(
                body_json,
                client_api_format,
                provider_api_format,
            ),
        )
        .await;
        return None;
    };

    let upstream_is_stream = true;
    let upstream_url = build_openai_image_upstream_url(transport, None);
    let Some(mut provider_request_headers) =
        build_openai_image_headers(ProviderOpenAiImageHeadersInput {
            headers: &parts.headers,
            auth_header: &prepared_candidate.auth_header,
            auth_value: &prepared_candidate.auth_value,
            header_rules: transport.endpoint.header_rules.as_ref(),
            provider_request_body: &converted.body_json,
            original_request_body: body_json,
        })
    else {
        mark_skipped_local_standard_candidate_with_failure_diagnostic(
            state,
            input,
            trace_id,
            candidate,
            attempt.candidate_index,
            &attempt.candidate_id,
            "transport_header_rules_apply_failed",
            CandidateFailureDiagnostic::header_rules_apply_failed(
                client_api_format,
                provider_api_format,
                "gemini_image_to_openai_image_headers",
            ),
        )
        .await;
        return None;
    };
    apply_codex_openai_responses_special_headers(
        &mut provider_request_headers,
        &converted.body_json,
        &parts.headers,
        transport.provider.provider_type.as_str(),
        provider_api_format,
        Some(trace_id),
        transport.key.decrypted_auth_config.as_deref(),
    );

    Some(LocalStandardCandidatePayloadParts {
        auth_header: prepared_candidate.auth_header,
        auth_value: prepared_candidate.auth_value,
        mapped_model: converted.mapped_model,
        provider_api_format: provider_api_format.to_string(),
        provider_request_body: converted.body_json,
        provider_request_headers,
        upstream_url,
        upstream_is_stream,
        envelope_name: None,
        transport: Arc::clone(transport),
        transport_profile: None,
    })
}

#[allow(clippy::too_many_arguments)]
async fn build_kiro_cross_format_payload_parts(
    state: &AppState,
    parts: &http::request::Parts,
    trace_id: &str,
    original_body_json: &serde_json::Value,
    input: &LocalStandardDecisionInput,
    attempt: &LocalStandardCandidateAttempt,
    transport: &Arc<GatewayProviderTransportSnapshot>,
    provider_api_format: &str,
    mapped_model: String,
    auth_header: String,
    auth_value: String,
    claude_request_body: Value,
    upstream_is_stream: bool,
    kiro_auth: &KiroRequestAuth,
) -> Option<LocalStandardCandidatePayloadParts> {
    let candidate = &attempt.eligible.candidate;
    let provider_request_body = match build_kiro_provider_request_body(
        &claude_request_body,
        &mapped_model,
        &kiro_auth.auth_config,
        transport.endpoint.body_rules.as_ref(),
        Some(&parts.headers),
    ) {
        Some(body) => body,
        None => {
            mark_skipped_local_standard_candidate_with_extra_data(
                state,
                input,
                trace_id,
                candidate,
                attempt.candidate_index,
                &attempt.candidate_id,
                "provider_request_body_build_failed",
                request_body_build_failure_extra_data(
                    &claude_request_body,
                    provider_api_format,
                    provider_api_format,
                ),
            )
            .await;
            return None;
        }
    };
    let upstream_url = match build_kiro_cross_format_upstream_url(
        transport,
        &mapped_model,
        provider_api_format,
        upstream_is_stream,
        parts.uri.query(),
        kiro_auth.auth_config.effective_api_region(),
    ) {
        Some(url) => url,
        None => {
            mark_skipped_local_standard_candidate_with_failure_diagnostic(
                state,
                input,
                trace_id,
                candidate,
                attempt.candidate_index,
                &attempt.candidate_id,
                "upstream_url_missing",
                CandidateFailureDiagnostic::upstream_url_missing(
                    provider_api_format,
                    provider_api_format,
                    "standard_family_kiro_url",
                ),
            )
            .await;
            return None;
        }
    };
    let provider_request_headers = match build_kiro_provider_headers(KiroProviderHeadersInput {
        headers: &parts.headers,
        provider_request_body: &provider_request_body,
        original_request_body: original_body_json,
        header_rules: transport.endpoint.header_rules.as_ref(),
        auth_header: &auth_header,
        auth_value: &auth_value,
        auth_config: &kiro_auth.auth_config,
        machine_id: kiro_auth.machine_id.as_str(),
    }) {
        Some(headers) => headers,
        None => {
            mark_skipped_local_standard_candidate_with_failure_diagnostic(
                state,
                input,
                trace_id,
                candidate,
                attempt.candidate_index,
                &attempt.candidate_id,
                "transport_header_rules_apply_failed",
                CandidateFailureDiagnostic::header_rules_apply_failed(
                    provider_api_format,
                    provider_api_format,
                    "standard_family_kiro_headers",
                ),
            )
            .await;
            return None;
        }
    };

    Some(LocalStandardCandidatePayloadParts {
        auth_header,
        auth_value,
        mapped_model,
        provider_api_format: provider_api_format.to_string(),
        provider_request_body,
        provider_request_headers,
        upstream_url,
        upstream_is_stream,
        envelope_name: Some(KIRO_ENVELOPE_NAME),
        transport: Arc::clone(transport),
        transport_profile: None,
    })
}
