use super::{
    json_object, ProviderOpsActionSpec, ProviderOpsArchitectureSpec, ProviderOpsAuthSpec,
    ProviderOpsBalanceMode, ProviderOpsCheckinMode, ProviderOpsVerifyMode,
};
use serde_json::{json, Map, Value};

pub(super) fn spec() -> ProviderOpsArchitectureSpec {
    let credentials_schema = json!({
        "type": "object",
        "properties": {
            "api_key": {
                "type": "string",
                "title": "访问令牌 (API Key)",
                "description": "New API 的访问令牌，与 Cookie 二选一",
                "x-sensitive": true,
                "x-input-type": "password"
            },
            "base_url": {
                "type": "string",
                "title": "站点地址",
                "description": "API 基础地址"
            },
            "cookie": {
                "type": "string",
                "title": "Cookie",
                "description": "用于 Cookie 认证，与访问令牌二选一",
                "x-sensitive": true,
                "x-input-type": "password"
            },
            "user_id": {
                "type": "string",
                "title": "用户 ID",
                "description": "使用访问令牌时必填，使用 Cookie 时可选"
            }
        },
        "required": [],
        "x-auth-method": "bearer",
        "x-auth-type": "api_key",
        "x-currency": "USD",
        "x-field-groups": [
            { "fields": ["base_url"] },
            {
                "fields": ["cookie"],
                "x-help": "从浏览器开发者工具复制完整 Cookie"
            },
            {
                "fields": ["api_key", "user_id"],
                "layout": "inline",
                "x-flex": {
                    "api_key": 3,
                    "user_id": 1
                }
            }
        ],
        "x-field-hooks": {
            "cookie": {
                "action": "parse_new_api_user_id",
                "target": "user_id"
            }
        },
        "x-quota-divisor": 500000,
        "x-validation": [
            {
                "type": "any_required",
                "fields": ["api_key", "cookie"],
                "message": "访问令牌和 Cookie 至少需要填写一个"
            },
            {
                "type": "conditional_required",
                "if": "api_key",
                "then": ["user_id"],
                "unless": "cookie",
                "message": "使用访问令牌时，用户 ID 不能为空"
            }
        ]
    });

    ProviderOpsArchitectureSpec {
        architecture_id: "new_api",
        display_name: "New API",
        description: "New API 风格中转站的预设配置",
        hidden: false,
        credentials_schema: credentials_schema.clone(),
        verify_endpoint: "/api/user/self",
        verify_mode: ProviderOpsVerifyMode::DirectGet,
        balance_mode: ProviderOpsBalanceMode::SingleRequest,
        checkin_mode: ProviderOpsCheckinMode::NewApiCompatible,
        query_balance_cookie_auth_errors: false,
        supported_auth_types: vec![ProviderOpsAuthSpec {
            auth_type: "api_key",
            display_name: "New API Key",
            credentials_schema,
        }],
        supported_actions: vec![ProviderOpsActionSpec {
            action_type: "query_balance",
            display_name: "查询余额",
            description: "查询 New API 账户余额信息",
            config_schema: json!({
                "type": "object",
                "properties": {
                    "endpoint": {
                        "type": "string",
                        "title": "API 路径",
                        "description": "余额查询 API 路径",
                        "default": "/api/user/self"
                    },
                    "method": {
                        "type": "string",
                        "title": "请求方法",
                        "enum": ["GET", "POST"],
                        "default": "GET"
                    },
                    "quota_divisor": {
                        "type": "number",
                        "title": "额度除数",
                        "description": "将原始额度值转换为美元的除数",
                        "default": 500000
                    },
                    "currency": {
                        "type": "string",
                        "title": "货币单位",
                        "default": "USD"
                    }
                },
                "required": []
            }),
        }],
        default_connector: Some("api_key"),
    }
}

pub(super) fn default_action_config(action_type: &str) -> Option<Map<String, Value>> {
    match action_type {
        "query_balance" => Some(json_object(json!({
            "endpoint": "/api/user/self",
            "method": "GET",
            "quota_divisor": 500000,
            "checkin_endpoint": "/api/user/checkin",
            "currency": "USD"
        }))),
        "checkin" => Some(json_object(json!({
            "endpoint": "/api/user/checkin",
            "method": "POST"
        }))),
        _ => None,
    }
}
