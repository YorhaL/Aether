use crate::ai_serving::resolve_openai_embedding_sync_spec as resolve_surface_sync_spec;
use crate::ai_serving::GatewayControlDecision;
use crate::{AiExecutionDecision, AppState, GatewayError};

use super::super::family::maybe_build_sync_via_standard_family_payload;

pub(crate) fn resolve_sync_spec(
    plan_kind: &str,
) -> Option<super::super::family::LocalStandardSpec> {
    resolve_surface_sync_spec(plan_kind)
}

pub(crate) async fn maybe_build_sync_local_openai_embedding_decision_payload(
    state: &AppState,
    parts: &http::request::Parts,
    trace_id: &str,
    decision: &GatewayControlDecision,
    body_json: &serde_json::Value,
    plan_kind: &str,
) -> Result<Option<AiExecutionDecision>, GatewayError> {
    maybe_build_sync_via_standard_family_payload(
        state,
        parts,
        trace_id,
        decision,
        body_json,
        plan_kind,
        resolve_sync_spec,
    )
    .await
}
