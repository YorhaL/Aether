use serde_json::{Map, Value};

use crate::snapshot::GatewayProviderTransportSnapshot;

#[derive(Debug, Clone, PartialEq)]
pub enum GeminiCliRequestEnvelopeSupport {
    Supported(Value),
    Unsupported(GeminiCliRequestEnvelopeUnsupportedReason),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum GeminiCliRequestEnvelopeUnsupportedReason {
    NonObjectBody,
    MissingContents,
    MissingProjectId,
    MissingUserPromptId,
    MissingModel,
}

pub fn resolve_gemini_cli_project_id(
    transport: &GatewayProviderTransportSnapshot,
) -> Option<String> {
    transport
        .key
        .upstream_metadata
        .as_ref()
        .and_then(|metadata| {
            find_string_by_paths(
                metadata,
                &[
                    &["gemini_cli", "project_id"],
                    &["gemini_cli", "projectId"],
                    &["gemini_cli", "cloudaicompanionProject"],
                    &["gemini_cli", "cloudaicompanionProject", "id"],
                    &["project_id"],
                    &["projectId"],
                ],
            )
        })
        .or_else(|| {
            transport
                .key
                .decrypted_auth_config
                .as_deref()
                .and_then(parse_project_id_from_auth_config)
        })
}

fn parse_project_id_from_auth_config(raw_auth_config: &str) -> Option<String> {
    let auth_config = serde_json::from_str::<Value>(raw_auth_config).ok()?;
    find_string_by_paths(
        &auth_config,
        &[
            &["project_id"],
            &["projectId"],
            &["project", "id"],
            &["project", "project_id"],
            &["project", "projectId"],
            &["gemini_cli", "project_id"],
            &["gemini_cli", "projectId"],
            &["metadata", "project_id"],
            &["metadata", "projectId"],
        ],
    )
}

pub fn build_gemini_cli_v1internal_request(
    project_id: &str,
    user_prompt_id: &str,
    model: &str,
    request_body: &Value,
) -> GeminiCliRequestEnvelopeSupport {
    let project_id = project_id.trim();
    if project_id.is_empty() {
        return GeminiCliRequestEnvelopeSupport::Unsupported(
            GeminiCliRequestEnvelopeUnsupportedReason::MissingProjectId,
        );
    }
    let user_prompt_id = user_prompt_id.trim();
    if user_prompt_id.is_empty() {
        return GeminiCliRequestEnvelopeSupport::Unsupported(
            GeminiCliRequestEnvelopeUnsupportedReason::MissingUserPromptId,
        );
    }
    let model = model.trim();
    if model.is_empty() {
        return GeminiCliRequestEnvelopeSupport::Unsupported(
            GeminiCliRequestEnvelopeUnsupportedReason::MissingModel,
        );
    }

    let Value::Object(source) = request_body else {
        return GeminiCliRequestEnvelopeSupport::Unsupported(
            GeminiCliRequestEnvelopeUnsupportedReason::NonObjectBody,
        );
    };
    if !source.contains_key("contents") {
        return GeminiCliRequestEnvelopeSupport::Unsupported(
            GeminiCliRequestEnvelopeUnsupportedReason::MissingContents,
        );
    }

    let mut inner_request: Map<String, Value> = source.clone();
    inner_request.remove("model");
    inner_request.remove("stream");

    GeminiCliRequestEnvelopeSupport::Supported(serde_json::json!({
        "model": model,
        "project": project_id,
        "user_prompt_id": user_prompt_id,
        "request": Value::Object(inner_request),
    }))
}

fn find_string_by_paths(value: &Value, paths: &[&[&str]]) -> Option<String> {
    for path in paths {
        let mut current = value;
        let mut matched = true;
        for segment in *path {
            let Some(next) = current.get(*segment) else {
                matched = false;
                break;
            };
            current = next;
        }
        if !matched {
            continue;
        }
        if let Some(string) = current
            .as_str()
            .map(str::trim)
            .filter(|item| !item.is_empty())
        {
            return Some(string.to_string());
        }
    }

    None
}

#[cfg(test)]
mod tests {
    use crate::snapshot::{
        GatewayProviderTransportEndpoint, GatewayProviderTransportKey,
        GatewayProviderTransportProvider, GatewayProviderTransportSnapshot,
    };
    use serde_json::json;

    use super::{
        build_gemini_cli_v1internal_request, resolve_gemini_cli_project_id,
        GeminiCliRequestEnvelopeSupport,
    };

    fn sample_transport() -> GatewayProviderTransportSnapshot {
        GatewayProviderTransportSnapshot {
            provider: GatewayProviderTransportProvider {
                id: "provider-1".to_string(),
                name: "Gemini CLI".to_string(),
                provider_type: "gemini_cli".to_string(),
                website: None,
                is_active: true,
                keep_priority_on_conversion: false,
                enable_format_conversion: false,
                concurrent_limit: None,
                max_retries: None,
                proxy: None,
                request_timeout_secs: None,
                stream_first_byte_timeout_secs: None,
                config: None,
            },
            endpoint: GatewayProviderTransportEndpoint {
                id: "endpoint-1".to_string(),
                provider_id: "provider-1".to_string(),
                api_format: "gemini:generate_content".to_string(),
                api_family: None,
                endpoint_kind: None,
                is_active: true,
                base_url: "https://cloudcode-pa.googleapis.com".to_string(),
                header_rules: None,
                body_rules: None,
                max_retries: None,
                custom_path: None,
                config: None,
                format_acceptance_config: None,
                proxy: None,
            },
            key: GatewayProviderTransportKey {
                id: "key-1".to_string(),
                provider_id: "provider-1".to_string(),
                name: "key".to_string(),
                auth_type: "oauth".to_string(),
                is_active: true,
                api_formats: None,
                auth_type_by_format: None,
                allow_auth_channel_mismatch_formats: None,
                allowed_models: None,
                capabilities: None,
                rate_multipliers: None,
                global_priority_by_format: None,
                expires_at_unix_secs: None,
                proxy: None,
                fingerprint: None,
                upstream_metadata: Some(json!({
                    "gemini_cli": {
                        "project_id": "metadata-project"
                    }
                })),
                decrypted_api_key: String::new(),
                decrypted_auth_config: Some(r#"{"project_id":"auth-project"}"#.to_string()),
            },
        }
    }

    #[test]
    fn project_id_prefers_upstream_metadata_then_auth_config() {
        let mut transport = sample_transport();
        assert_eq!(
            resolve_gemini_cli_project_id(&transport).as_deref(),
            Some("metadata-project")
        );

        transport.key.upstream_metadata = None;
        assert_eq!(
            resolve_gemini_cli_project_id(&transport).as_deref(),
            Some("auth-project")
        );
    }

    #[test]
    fn wraps_gemini_body_in_code_assist_envelope() {
        let body = json!({
            "model": "ignored",
            "stream": true,
            "contents": [{"role": "user", "parts": [{"text": "hi"}]}],
            "generationConfig": {"temperature": 0.2}
        });

        let envelope = match build_gemini_cli_v1internal_request(
            "project-1",
            "trace-1",
            "gemini-2.5-pro",
            &body,
        ) {
            GeminiCliRequestEnvelopeSupport::Supported(value) => value,
            other => panic!("expected supported envelope, got {other:?}"),
        };

        assert_eq!(envelope["project"], json!("project-1"));
        assert_eq!(envelope["user_prompt_id"], json!("trace-1"));
        assert_eq!(envelope["model"], json!("gemini-2.5-pro"));
        assert_eq!(
            envelope["request"]["generationConfig"]["temperature"],
            json!(0.2)
        );
        assert!(envelope["request"].get("model").is_none());
        assert!(envelope["request"].get("stream").is_none());
    }
}
