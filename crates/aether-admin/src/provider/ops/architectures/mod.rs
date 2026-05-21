mod anyrouter;
mod cubence;
mod done_hub;
mod generic_api;
mod nekocode;
mod new_api;
mod sub2api;
mod yescode;

use serde_json::{json, Map, Value};
use std::sync::LazyLock;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ProviderOpsVerifyMode {
    DirectGet,
    Sub2ApiExchange,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ProviderOpsBalanceMode {
    SingleRequest,
    YescodeCombined,
    Sub2ApiDualRequest,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ProviderOpsCheckinMode {
    None,
    NewApiCompatible,
}

#[derive(Clone, Debug)]
pub struct ProviderOpsAuthSpec {
    pub auth_type: &'static str,
    pub display_name: &'static str,
    pub credentials_schema: Value,
}

#[derive(Clone, Debug)]
pub struct ProviderOpsActionSpec {
    pub action_type: &'static str,
    pub display_name: &'static str,
    pub description: &'static str,
    pub config_schema: Value,
}

#[derive(Clone, Debug)]
pub struct ProviderOpsArchitectureSpec {
    pub architecture_id: &'static str,
    pub display_name: &'static str,
    pub description: &'static str,
    pub hidden: bool,
    pub credentials_schema: Value,
    pub verify_endpoint: &'static str,
    pub verify_mode: ProviderOpsVerifyMode,
    pub balance_mode: ProviderOpsBalanceMode,
    pub checkin_mode: ProviderOpsCheckinMode,
    pub query_balance_cookie_auth_errors: bool,
    pub supported_auth_types: Vec<ProviderOpsAuthSpec>,
    pub supported_actions: Vec<ProviderOpsActionSpec>,
    pub default_connector: Option<&'static str>,
}

impl ProviderOpsArchitectureSpec {
    pub fn api_payload(&self) -> Value {
        json!({
            "architecture_id": self.architecture_id,
            "display_name": self.display_name,
            "description": self.description,
            "credentials_schema": self.credentials_schema,
            "supported_auth_types": self.supported_auth_types.iter().map(|item| {
                json!({
                    "type": item.auth_type,
                    "display_name": item.display_name,
                    "credentials_schema": item.credentials_schema,
                })
            }).collect::<Vec<_>>(),
            "supported_actions": self.supported_actions.iter().map(|item| {
                json!({
                    "type": item.action_type,
                    "display_name": item.display_name,
                    "description": item.description,
                    "config_schema": item.config_schema,
                })
            }).collect::<Vec<_>>(),
            "default_connector": self.default_connector,
        })
    }
}

static PROVIDER_OPS_ARCHITECTURES: LazyLock<Vec<ProviderOpsArchitectureSpec>> =
    LazyLock::new(|| {
        vec![
            anyrouter::spec(),
            cubence::spec(),
            done_hub::spec(),
            generic_api::spec(),
            nekocode::spec(),
            new_api::spec(),
            sub2api::spec(),
            yescode::spec(),
        ]
    });

pub fn list_architectures(include_hidden: bool) -> Vec<ProviderOpsArchitectureSpec> {
    PROVIDER_OPS_ARCHITECTURES
        .iter()
        .filter(|spec| include_hidden || !spec.hidden)
        .cloned()
        .collect()
}

pub fn get_architecture(architecture_id: &str) -> Option<ProviderOpsArchitectureSpec> {
    let normalized = normalize_architecture_id(architecture_id);
    PROVIDER_OPS_ARCHITECTURES
        .iter()
        .find(|spec| spec.architecture_id == normalized)
        .cloned()
}

pub fn normalize_architecture_id(architecture_id: &str) -> &'static str {
    match architecture_id.trim() {
        "" => "generic_api",
        "generic_api" => "generic_api",
        "new_api" => "new_api",
        "cubence" => "cubence",
        "done_hub" => "done_hub",
        "yescode" => "yescode",
        "nekocode" => "nekocode",
        "anyrouter" => "anyrouter",
        "sub2api" => "sub2api",
        _ => "generic_api",
    }
}

pub fn admin_provider_ops_is_supported_auth_type(auth_type: &str) -> bool {
    matches!(
        auth_type,
        "api_key" | "session_login" | "oauth" | "cookie" | "none"
    )
}

pub fn resolve_action_config(
    architecture_id: &str,
    provider_ops_config: &Map<String, Value>,
    action_type: &str,
    request_override: Option<&Map<String, Value>>,
) -> Option<Map<String, Value>> {
    let mut resolved =
        default_action_config(normalize_architecture_id(architecture_id), action_type)?;

    if let Some(saved) = provider_action_config_object(provider_ops_config, action_type) {
        for (key, value) in saved {
            resolved.insert(key.clone(), value.clone());
        }
    }

    if let Some(request_override) = request_override {
        for (key, value) in request_override {
            resolved.insert(key.clone(), value.clone());
        }
    }

    Some(resolved)
}

fn provider_action_config_object<'a>(
    provider_ops_config: &'a Map<String, Value>,
    action_type: &str,
) -> Option<&'a Map<String, Value>> {
    provider_ops_config
        .get("actions")
        .and_then(Value::as_object)
        .and_then(|actions| actions.get(action_type))
        .and_then(Value::as_object)
        .and_then(|action| action.get("config"))
        .and_then(Value::as_object)
}

fn default_action_config(architecture_id: &str, action_type: &str) -> Option<Map<String, Value>> {
    match architecture_id {
        "anyrouter" => anyrouter::default_action_config(action_type),
        "cubence" => cubence::default_action_config(action_type),
        "done_hub" => done_hub::default_action_config(action_type),
        "generic_api" => generic_api::default_action_config(action_type),
        "nekocode" => nekocode::default_action_config(action_type),
        "new_api" => new_api::default_action_config(action_type),
        "sub2api" => sub2api::default_action_config(action_type),
        "yescode" => yescode::default_action_config(action_type),
        _ => None,
    }
}

pub(super) fn json_object(value: Value) -> Map<String, Value> {
    value.as_object().cloned().unwrap_or_default()
}

#[cfg(test)]
mod tests {
    use super::{
        get_architecture, list_architectures, normalize_architecture_id, resolve_action_config,
    };
    use serde_json::json;

    #[test]
    fn list_architectures_hides_generic_api_by_default() {
        let visible = list_architectures(false);
        assert_eq!(visible.len(), 7);
        assert!(visible
            .iter()
            .all(|item| item.architecture_id != "generic_api"));

        let all = list_architectures(true);
        assert_eq!(all.len(), 8);
        assert!(all.iter().any(|item| item.architecture_id == "generic_api"));
    }

    #[test]
    fn normalize_architecture_id_falls_back_to_generic_api() {
        assert_eq!(normalize_architecture_id(""), "generic_api");
        assert_eq!(normalize_architecture_id("done_hub"), "done_hub");
        assert_eq!(normalize_architecture_id("new_api"), "new_api");
        assert_eq!(normalize_architecture_id("unknown"), "generic_api");
    }

    #[test]
    fn done_hub_uses_profile_balance_without_checkin() {
        let architecture = get_architecture("done_hub").expect("architecture should exist");
        assert_eq!(architecture.architecture_id, "done_hub");
        assert_eq!(architecture.verify_endpoint, "/api/user/profile");

        let resolved = resolve_action_config(
            "done_hub",
            &json!({})
                .as_object()
                .cloned()
                .expect("config should be object"),
            "query_balance",
            None,
        )
        .expect("action config should resolve");

        assert_eq!(resolved.get("endpoint"), Some(&json!("/api/user/profile")));
        assert_eq!(resolved.get("quota_divisor"), Some(&json!(500000)));
        assert_eq!(resolved.get("method"), Some(&json!("GET")));
        assert!(resolved.get("checkin_endpoint").is_none());
    }

    #[test]
    fn get_architecture_returns_generic_api_for_unknown_id() {
        let architecture = get_architecture("unknown").expect("architecture should exist");
        assert_eq!(architecture.architecture_id, "generic_api");
        assert!(architecture.hidden);
    }

    #[test]
    fn resolve_action_config_merges_default_saved_and_request_values() {
        let resolved = resolve_action_config(
            "new_api",
            &json!({
                "actions": {
                    "query_balance": {
                        "config": {
                            "endpoint": "/custom/path",
                            "currency": "CNY"
                        }
                    }
                }
            })
            .as_object()
            .cloned()
            .expect("config should be object"),
            "query_balance",
            Some(
                &json!({
                    "quota_divisor": 42
                })
                .as_object()
                .cloned()
                .expect("override should be object"),
            ),
        )
        .expect("action config should resolve");

        assert_eq!(resolved.get("endpoint"), Some(&json!("/custom/path")));
        assert_eq!(resolved.get("currency"), Some(&json!("CNY")));
        assert_eq!(resolved.get("quota_divisor"), Some(&json!(42)));
        assert_eq!(resolved.get("method"), Some(&json!("GET")));
    }
}
