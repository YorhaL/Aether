use super::{
    build_auth_error_response, build_auth_json_response, build_wallet_daily_usage_payload,
    build_wallet_live_today_usage_payload_for_user, build_wallet_payload,
    build_wallet_zero_today_entry, http, parse_wallet_limit, parse_wallet_offset,
    resolve_authenticated_local_user, unix_secs_to_rfc3339, wallet_fixed_offset,
    wallet_transaction_payload_from_record, AppState, Body, GatewayPublicRequestContext, Response,
    WALLET_LEGACY_TIMEZONE,
};
use serde_json::json;

fn wallet_flow_sort_key(item_type: &str, payload: &serde_json::Value) -> (String, u8, String) {
    match item_type {
        "daily_usage" => {
            let data = payload.get("data").unwrap_or(payload);
            let date = data
                .get("date")
                .and_then(serde_json::Value::as_str)
                .unwrap_or("");
            let sort_dt = data
                .get("last_finalized_at")
                .and_then(serde_json::Value::as_str)
                .or_else(|| {
                    data.get("aggregated_at")
                        .and_then(serde_json::Value::as_str)
                })
                .unwrap_or("");
            (date.to_string(), 1, sort_dt.to_string())
        }
        _ => {
            let data = payload.get("data").unwrap_or(payload);
            let created_at = data
                .get("created_at")
                .and_then(serde_json::Value::as_str)
                .unwrap_or("");
            let local_date = chrono::DateTime::parse_from_rfc3339(created_at)
                .ok()
                .map(|value| {
                    value
                        .with_timezone(&wallet_fixed_offset())
                        .date_naive()
                        .to_string()
                })
                .unwrap_or_default();
            (local_date, 0, created_at.to_string())
        }
    }
}

pub(super) async fn handle_wallet_flow(
    state: &AppState,
    request_context: &GatewayPublicRequestContext,
    headers: &http::HeaderMap,
) -> Response<Body> {
    let auth = match resolve_authenticated_local_user(state, request_context, headers).await {
        Ok(value) => value,
        Err(response) => return response,
    };
    let query = request_context.request_query_string.as_deref();
    let limit = match parse_wallet_limit(query) {
        Ok(value) => value,
        Err(detail) => {
            return build_auth_error_response(http::StatusCode::BAD_REQUEST, detail, false)
        }
    };
    let offset = match parse_wallet_offset(query) {
        Ok(value) => value,
        Err(detail) => {
            return build_auth_error_response(http::StatusCode::BAD_REQUEST, detail, false)
        }
    };
    let wallet = match state
        .find_wallet(aether_data::repository::wallet::WalletLookupKey::UserId(
            &auth.user.id,
        ))
        .await
    {
        Ok(value) => value,
        Err(err) => {
            return build_auth_error_response(
                http::StatusCode::INTERNAL_SERVER_ERROR,
                format!("wallet lookup failed: {err:?}"),
                false,
            )
        }
    };
    let Some(wallet) = wallet else {
        let mut payload = json!({
            "today_entry": serde_json::Value::Null,
            "items": [],
            "total": 0,
            "limit": limit,
            "offset": offset,
        });
        if let Some(object) = payload.as_object_mut() {
            if let Some(wallet_payload) = build_wallet_payload(None).as_object() {
                object.extend(wallet_payload.clone());
            }
        }
        return build_auth_json_response(http::StatusCode::OK, payload, None);
    };

    let mut today_entry =
        match build_wallet_live_today_usage_payload_for_user(state, &auth.user.id).await {
            Ok(Some(today_usage)) => today_usage,
            _ => build_wallet_zero_today_entry(),
        };
    if today_entry
        .get("total_requests")
        .and_then(serde_json::Value::as_u64)
        .unwrap_or_default()
        == 0
    {
        if let Ok(Some(today_usage)) = state
            .find_wallet_today_usage(&wallet.id, WALLET_LEGACY_TIMEZONE)
            .await
        {
            today_entry = build_wallet_daily_usage_payload(
                today_usage.id,
                today_usage.billing_date,
                today_usage.billing_timezone,
                today_usage.total_cost_usd,
                today_usage.total_requests,
                today_usage.input_tokens,
                today_usage.output_tokens,
                today_usage.cache_creation_tokens,
                today_usage.cache_read_tokens,
                today_usage
                    .first_finalized_at_unix_secs
                    .and_then(unix_secs_to_rfc3339),
                today_usage
                    .last_finalized_at_unix_secs
                    .and_then(unix_secs_to_rfc3339),
                today_usage
                    .aggregated_at_unix_secs
                    .and_then(unix_secs_to_rfc3339),
                true,
            );
        }
    }

    let fetch_size = offset.saturating_add(limit).min(5200);
    let (transactions, tx_total) = state
        .list_admin_wallet_transactions(&wallet.id, fetch_size, 0)
        .await
        .unwrap_or((Vec::new(), 0));
    let daily_page = state
        .list_wallet_daily_usage_history(&wallet.id, WALLET_LEGACY_TIMEZONE, fetch_size)
        .await
        .unwrap_or_default();

    let mut merged = transactions
        .iter()
        .map(|record| json!({ "type": "transaction", "data": wallet_transaction_payload_from_record(record) }))
        .collect::<Vec<_>>();
    merged.extend(daily_page.items.iter().map(|entry| {
        json!({
            "type": "daily_usage",
            "data": build_wallet_daily_usage_payload(
                entry.id.clone(),
                entry.billing_date.clone(),
                entry.billing_timezone.clone(),
                entry.total_cost_usd,
                entry.total_requests,
                entry.input_tokens,
                entry.output_tokens,
                entry.cache_creation_tokens,
                entry.cache_read_tokens,
                entry.first_finalized_at_unix_secs.and_then(unix_secs_to_rfc3339),
                entry.last_finalized_at_unix_secs.and_then(unix_secs_to_rfc3339),
                entry.aggregated_at_unix_secs.and_then(unix_secs_to_rfc3339),
                false,
            )
        })
    }));
    merged.sort_by(|left, right| {
        let left_type = left
            .get("type")
            .and_then(serde_json::Value::as_str)
            .unwrap_or("");
        let right_type = right
            .get("type")
            .and_then(serde_json::Value::as_str)
            .unwrap_or("");
        wallet_flow_sort_key(right_type, right).cmp(&wallet_flow_sort_key(left_type, left))
    });
    let items = merged
        .into_iter()
        .skip(offset)
        .take(limit)
        .collect::<Vec<_>>();
    let total = tx_total.saturating_add(daily_page.total);

    let mut payload = json!({
        "today_entry": today_entry,
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    });
    if let Some(object) = payload.as_object_mut() {
        if let Some(wallet_payload) = build_wallet_payload(Some(&wallet)).as_object() {
            object.extend(wallet_payload.clone());
        }
    }
    build_auth_json_response(http::StatusCode::OK, payload, None)
}
