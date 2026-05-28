mod request;
mod url;

pub use request::{
    build_gemini_cli_v1internal_request, resolve_gemini_cli_project_id,
    GeminiCliRequestEnvelopeSupport, GeminiCliRequestEnvelopeUnsupportedReason,
};
pub use url::{
    build_gemini_cli_v1internal_url, GeminiCliRequestUrlAction,
    GEMINI_CLI_RETRIEVE_USER_QUOTA_PATH, GEMINI_CLI_USER_AGENT,
    GEMINI_CLI_V1INTERNAL_PATH_TEMPLATE,
};

use crate::snapshot::GatewayProviderTransportSnapshot;

pub const GEMINI_CLI_PROVIDER_TYPE: &str = "gemini_cli";
pub const GEMINI_CLI_V1INTERNAL_ENVELOPE_NAME: &str = "gemini_cli:v1internal";

pub fn is_gemini_cli_provider_transport(transport: &GatewayProviderTransportSnapshot) -> bool {
    transport
        .provider
        .provider_type
        .trim()
        .eq_ignore_ascii_case(GEMINI_CLI_PROVIDER_TYPE)
}
