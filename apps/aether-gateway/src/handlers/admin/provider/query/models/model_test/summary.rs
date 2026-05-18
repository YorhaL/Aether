use std::collections::BTreeMap;

use super::super::provider_query_key_display_name;
use super::{ProviderQueryExecutionOutcome, ProviderQueryTestCandidate};
use serde_json::{json, Value};

pub(super) fn provider_query_test_attempt_payload(
    candidate_index: usize,
    candidate: &ProviderQueryTestCandidate,
    execution: &ProviderQueryExecutionOutcome,
) -> Value {
    let endpoint_route = provider_query_endpoint_route_payload(candidate, execution);
    let endpoint_product = endpoint_route
        .get("product")
        .cloned()
        .unwrap_or(Value::Null);
    let endpoint_variant = endpoint_route
        .get("variant")
        .cloned()
        .unwrap_or(Value::Null);
    let endpoint_action = endpoint_route.get("action").cloned().unwrap_or(Value::Null);
    let endpoint_batch_strategy = endpoint_route
        .get("batch_strategy")
        .cloned()
        .unwrap_or(Value::Null);
    json!({
        "candidate_index": candidate_index,
        "retry_index": 0,
        "endpoint_api_format": candidate.endpoint.api_format,
        "endpoint_base_url": candidate.endpoint.base_url,
        "endpoint_product": endpoint_product,
        "endpoint_variant": endpoint_variant,
        "endpoint_action": endpoint_action,
        "endpoint_batch_strategy": endpoint_batch_strategy,
        "key_name": provider_query_key_display_name(&candidate.key),
        "key_id": candidate.key.id,
        "auth_type": candidate.key.auth_type,
        "effective_model": candidate.effective_model,
        "status": execution.status,
        "skip_reason": execution.skip_reason,
        "error_message": execution.error_message,
        "status_code": execution.status_code,
        "latency_ms": execution.latency_ms,
        "request_url": execution.request_url,
        "request_headers": provider_query_redact_diagnostic_headers(&execution.request_headers),
        "request_body": execution.request_body,
        "response_headers": provider_query_redact_diagnostic_headers(&execution.response_headers),
        "response_body": execution.response_body,
    })
}

fn provider_query_endpoint_route_payload(
    candidate: &ProviderQueryTestCandidate,
    execution: &ProviderQueryExecutionOutcome,
) -> Value {
    let api_format = aether_ai_formats::normalize_api_format_alias(&candidate.endpoint.api_format);
    let request_url = execution.request_url.to_ascii_lowercase();
    let base_url = candidate.endpoint.base_url.to_ascii_lowercase();
    let is_vertex = request_url.contains("aiplatform.googleapis.com")
        || base_url.contains("aiplatform.googleapis.com");
    let is_gemini_api = request_url.contains("generativelanguage.googleapis.com")
        || base_url.contains("generativelanguage.googleapis.com");
    let is_openai_compat =
        request_url.contains("/endpoints/openapi") || request_url.contains("/openai/");
    let is_batch = execution
        .request_body
        .get("requests")
        .and_then(Value::as_array)
        .is_some_and(|items| !items.is_empty());
    let vertex_instance_count = execution
        .request_body
        .get("instances")
        .and_then(Value::as_array)
        .map(Vec::len)
        .unwrap_or(0);

    let (product, variant, action, batch_strategy) = match api_format.as_str() {
        "gemini:embedding" if is_vertex => (
            "Vertex AI",
            "vertex_native",
            "predict",
            if vertex_instance_count > 1 {
                "predict_instances"
            } else {
                "single_instance"
            },
        ),
        "gemini:embedding" if is_gemini_api => (
            "Gemini API",
            "gemini_native",
            if is_batch {
                "batchEmbedContents"
            } else {
                "embedContent"
            },
            if is_batch {
                "native_batch"
            } else {
                "single_native"
            },
        ),
        "gemini:embedding" => (
            "Gemini native",
            "gemini_native",
            if is_batch {
                "batchEmbedContents"
            } else {
                "embedContent"
            },
            if is_batch {
                "native_batch"
            } else {
                "single_native"
            },
        ),
        "gemini:generate_content" if is_vertex => {
            ("Vertex AI", "vertex_native", "generateContent", "")
        }
        "gemini:generate_content" if is_gemini_api => {
            ("Gemini API", "gemini_native", "generateContent", "")
        }
        "gemini:generate_content" => ("Gemini native", "gemini_native", "generateContent", ""),
        "openai:embedding" if is_vertex && is_openai_compat => (
            "Vertex AI OpenAI-compatible",
            "openai_compatible",
            "embeddings",
            "openai_batch",
        ),
        "openai:embedding" if is_gemini_api && is_openai_compat => (
            "Gemini API OpenAI-compatible",
            "openai_compatible",
            "embeddings",
            "openai_batch",
        ),
        "openai:embedding" => (
            "OpenAI-compatible",
            "openai_compatible",
            "embeddings",
            "openai_batch",
        ),
        "openai:chat" if is_vertex && is_openai_compat => (
            "Vertex AI OpenAI-compatible",
            "openai_compatible",
            "chat/completions",
            "",
        ),
        "openai:chat" if is_gemini_api && is_openai_compat => (
            "Gemini API OpenAI-compatible",
            "openai_compatible",
            "chat/completions",
            "",
        ),
        "openai:chat" => (
            "OpenAI-compatible",
            "openai_compatible",
            "chat/completions",
            "",
        ),
        _ => (
            "Provider endpoint",
            "provider_native",
            "provider_request",
            "",
        ),
    };

    json!({
        "product": product,
        "variant": variant,
        "action": action,
        "batch_strategy": batch_strategy,
    })
}

fn provider_query_redact_diagnostic_headers(
    headers: &BTreeMap<String, String>,
) -> BTreeMap<String, String> {
    headers
        .iter()
        .map(|(name, value)| {
            if provider_query_header_is_sensitive(name) {
                (name.clone(), "<redacted>".to_string())
            } else {
                (name.clone(), value.clone())
            }
        })
        .collect()
}

fn provider_query_header_is_sensitive(name: &str) -> bool {
    matches!(
        name.trim().to_ascii_lowercase().as_str(),
        "authorization"
            | "proxy-authorization"
            | "cookie"
            | "set-cookie"
            | "x-api-key"
            | "api-key"
            | "x-goog-api-key"
            | "anthropic-api-key"
            | "openai-api-key"
    )
}

pub(super) fn provider_query_candidate_summary_payload(
    total_candidates: usize,
    total_attempts: usize,
    attempts: &[Value],
) -> Value {
    let success_count = attempts
        .iter()
        .filter(|attempt| attempt.get("status").and_then(Value::as_str) == Some("success"))
        .count();
    let failed_count = attempts
        .iter()
        .filter(|attempt| {
            matches!(
                attempt.get("status").and_then(Value::as_str),
                Some("failed") | Some("cancelled") | Some("stream_interrupted")
            )
        })
        .count();
    let skipped_count = attempts
        .iter()
        .filter(|attempt| attempt.get("status").and_then(Value::as_str) == Some("skipped"))
        .count();
    let pending_count = attempts
        .iter()
        .filter(|attempt| {
            matches!(
                attempt.get("status").and_then(Value::as_str),
                Some("pending") | Some("streaming")
            )
        })
        .count();
    let available_count = attempts
        .iter()
        .filter(|attempt| attempt.get("status").and_then(Value::as_str) == Some("available"))
        .count();
    let unused_count = if success_count > 0 {
        total_candidates.saturating_sub(success_count + failed_count + skipped_count)
    } else {
        0
    };
    let stop_reason = if total_candidates == 0 {
        "no_candidate"
    } else if success_count > 0 {
        "first_success"
    } else if total_attempts == 0 && skipped_count > 0 {
        "all_skipped"
    } else if failed_count > 0 || skipped_count > 0 {
        "exhausted"
    } else {
        "pending"
    };
    let winning_attempt = attempts
        .iter()
        .find(|attempt| attempt.get("status").and_then(Value::as_str) == Some("success"));

    json!({
        "total_candidates": total_candidates,
        "attempted": total_attempts,
        "success": success_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "unused": unused_count,
        "pending": pending_count,
        "available": available_count,
        "completed": success_count + failed_count + skipped_count + unused_count,
        "stop_reason": stop_reason,
        "winning_candidate_index": winning_attempt
            .and_then(|attempt| attempt.get("candidate_index"))
            .cloned()
            .unwrap_or(Value::Null),
        "winning_key_name": winning_attempt
            .and_then(|attempt| attempt.get("key_name"))
            .cloned()
            .unwrap_or(Value::Null),
        "winning_key_id": winning_attempt
            .and_then(|attempt| attempt.get("key_id"))
            .cloned()
            .unwrap_or(Value::Null),
        "winning_auth_type": winning_attempt
            .and_then(|attempt| attempt.get("auth_type"))
            .cloned()
            .unwrap_or(Value::Null),
        "winning_effective_model": winning_attempt
            .and_then(|attempt| attempt.get("effective_model"))
            .cloned()
            .unwrap_or(Value::Null),
        "winning_endpoint_api_format": winning_attempt
            .and_then(|attempt| attempt.get("endpoint_api_format"))
            .cloned()
            .unwrap_or(Value::Null),
        "winning_endpoint_base_url": winning_attempt
            .and_then(|attempt| attempt.get("endpoint_base_url"))
            .cloned()
            .unwrap_or(Value::Null),
        "winning_latency_ms": winning_attempt
            .and_then(|attempt| attempt.get("latency_ms"))
            .cloned()
            .unwrap_or(Value::Null),
        "winning_status_code": winning_attempt
            .and_then(|attempt| attempt.get("status_code"))
            .cloned()
            .unwrap_or(Value::Null),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn provider_query_diagnostic_headers_redact_credentials() {
        let headers = BTreeMap::from([
            ("cookie".to_string(), "sso=secret".to_string()),
            ("authorization".to_string(), "Bearer secret".to_string()),
            ("x-goog-api-key".to_string(), "secret".to_string()),
            ("content-type".to_string(), "application/json".to_string()),
        ]);

        let redacted = provider_query_redact_diagnostic_headers(&headers);

        assert_eq!(
            redacted.get("cookie").map(String::as_str),
            Some("<redacted>")
        );
        assert_eq!(
            redacted.get("authorization").map(String::as_str),
            Some("<redacted>")
        );
        assert_eq!(
            redacted.get("x-goog-api-key").map(String::as_str),
            Some("<redacted>")
        );
        assert_eq!(
            redacted.get("content-type").map(String::as_str),
            Some("application/json")
        );
    }
}
