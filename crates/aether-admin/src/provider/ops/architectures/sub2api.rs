use super::{
    json_object, ProviderOpsActionSpec, ProviderOpsArchitectureSpec, ProviderOpsAuthSpec,
    ProviderOpsBalanceMode, ProviderOpsCheckinMode, ProviderOpsVerifyMode,
};
use serde_json::{json, Map, Value};

pub(super) fn spec() -> ProviderOpsArchitectureSpec {
    let session_login_schema = json!({
        "type": "object",
        "properties": {
            "base_url": {
                "type": "string",
                "title": "站点地址",
                "description": "API 基础地址"
            },
            "email": {
                "type": "string",
                "title": "邮箱",
                "description": "Sub2API 登录邮箱"
            },
            "password": {
                "type": "string",
                "title": "密码",
                "description": "Sub2API 登录密码",
                "x-sensitive": true,
                "x-input-type": "password"
            }
        },
        "required": ["email", "password"],
        "x-auth-method": "jwt",
        "x-auth-type": "session_login",
        "x-field-groups": [
            { "fields": ["base_url"] },
            { "fields": ["email"] },
            { "fields": ["password"] }
        ],
        "x-validation": [
            {
                "type": "required",
                "fields": ["email", "password"],
                "message": "请填写邮箱和密码"
            }
        ]
    });
    let refresh_token_schema = json!({
        "type": "object",
        "properties": {
            "base_url": {
                "type": "string",
                "title": "站点地址",
                "description": "API 基础地址"
            },
            "refresh_token": {
                "type": "string",
                "title": "Refresh Token",
                "description": "从浏览器 F12 > Application > Local Storage 获取",
                "x-sensitive": true,
                "x-input-type": "password",
                "x-help": "浏览器控制台执行 localStorage.getItem('refresh_token') 获取"
            }
        },
        "required": ["refresh_token"],
        "x-auth-method": "bearer",
        "x-auth-type": "api_key",
        "x-field-groups": [
            { "fields": ["base_url"] },
            { "fields": ["refresh_token"] }
        ],
        "x-validation": [
            {
                "type": "required",
                "fields": ["refresh_token"],
                "message": "请填写 Refresh Token"
            }
        ]
    });

    ProviderOpsArchitectureSpec {
        architecture_id: "sub2api",
        display_name: "Sub2API",
        description: "Sub2API 风格中转站的预设配置",
        hidden: false,
        credentials_schema: session_login_schema.clone(),
        verify_endpoint: "/api/v1/auth/me?timezone=Asia/Shanghai",
        verify_mode: ProviderOpsVerifyMode::Sub2ApiExchange,
        balance_mode: ProviderOpsBalanceMode::Sub2ApiDualRequest,
        checkin_mode: ProviderOpsCheckinMode::None,
        query_balance_cookie_auth_errors: false,
        supported_auth_types: vec![
            ProviderOpsAuthSpec {
                auth_type: "session_login",
                display_name: "账号密码",
                credentials_schema: session_login_schema,
            },
            ProviderOpsAuthSpec {
                auth_type: "api_key",
                display_name: "Refresh Token",
                credentials_schema: refresh_token_schema,
            },
        ],
        supported_actions: vec![ProviderOpsActionSpec {
            action_type: "query_balance",
            display_name: "查询余额",
            description: "查询 Sub2API 账户余额和订阅信息",
            config_schema: json!({
                "type": "object",
                "properties": {
                    "currency": {
                        "type": "string",
                        "title": "货币单位",
                        "default": "USD"
                    }
                },
                "required": []
            }),
        }],
        default_connector: Some("session_login"),
    }
}

pub(super) fn default_action_config(action_type: &str) -> Option<Map<String, Value>> {
    match action_type {
        "query_balance" => Some(json_object(json!({
            "endpoint": "/api/v1/auth/me?timezone=Asia/Shanghai",
            "subscription_endpoint": "/api/v1/subscriptions/summary",
            "method": "GET",
            "currency": "USD"
        }))),
        _ => None,
    }
}
