use crate::contracts::{
    CLAUDE_CHAT_STREAM_PLAN_KIND, CLAUDE_CHAT_SYNC_PLAN_KIND, CLAUDE_CLI_STREAM_PLAN_KIND,
    CLAUDE_CLI_SYNC_PLAN_KIND, GEMINI_CHAT_STREAM_PLAN_KIND, GEMINI_CHAT_SYNC_PLAN_KIND,
    GEMINI_CLI_STREAM_PLAN_KIND, GEMINI_CLI_SYNC_PLAN_KIND, GEMINI_EMBEDDING_SYNC_PLAN_KIND,
    GEMINI_EMBEDDING_SYNC_SUCCESS_REPORT_KIND, OPENAI_EMBEDDING_SYNC_PLAN_KIND,
    OPENAI_RERANK_SYNC_PLAN_KIND,
};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LocalSameFormatProviderFamily {
    Standard,
    Gemini,
}

#[derive(Debug, Clone, Copy)]
pub struct LocalSameFormatProviderSpec {
    pub api_format: &'static str,
    pub decision_kind: &'static str,
    pub report_kind: &'static str,
    pub family: LocalSameFormatProviderFamily,
    pub require_streaming: bool,
}

pub fn resolve_sync_spec(plan_kind: &str) -> Option<LocalSameFormatProviderSpec> {
    match plan_kind {
        CLAUDE_CHAT_SYNC_PLAN_KIND => Some(LocalSameFormatProviderSpec {
            api_format: "claude:messages",
            decision_kind: CLAUDE_CHAT_SYNC_PLAN_KIND,
            report_kind: "claude_chat_sync_success",
            family: LocalSameFormatProviderFamily::Standard,
            require_streaming: false,
        }),
        CLAUDE_CLI_SYNC_PLAN_KIND => Some(LocalSameFormatProviderSpec {
            api_format: "claude:messages",
            decision_kind: CLAUDE_CLI_SYNC_PLAN_KIND,
            report_kind: "claude_cli_sync_success",
            family: LocalSameFormatProviderFamily::Standard,
            require_streaming: false,
        }),
        GEMINI_CHAT_SYNC_PLAN_KIND => Some(LocalSameFormatProviderSpec {
            api_format: "gemini:generate_content",
            decision_kind: GEMINI_CHAT_SYNC_PLAN_KIND,
            report_kind: "gemini_chat_sync_success",
            family: LocalSameFormatProviderFamily::Gemini,
            require_streaming: false,
        }),
        GEMINI_CLI_SYNC_PLAN_KIND => Some(LocalSameFormatProviderSpec {
            api_format: "gemini:generate_content",
            decision_kind: GEMINI_CLI_SYNC_PLAN_KIND,
            report_kind: "gemini_cli_sync_success",
            family: LocalSameFormatProviderFamily::Gemini,
            require_streaming: false,
        }),
        GEMINI_EMBEDDING_SYNC_PLAN_KIND => Some(LocalSameFormatProviderSpec {
            api_format: "gemini:embedding",
            decision_kind: GEMINI_EMBEDDING_SYNC_PLAN_KIND,
            report_kind: GEMINI_EMBEDDING_SYNC_SUCCESS_REPORT_KIND,
            family: LocalSameFormatProviderFamily::Gemini,
            require_streaming: false,
        }),
        OPENAI_EMBEDDING_SYNC_PLAN_KIND => Some(LocalSameFormatProviderSpec {
            api_format: "openai:embedding",
            decision_kind: OPENAI_EMBEDDING_SYNC_PLAN_KIND,
            report_kind: "openai_embedding_sync_success",
            family: LocalSameFormatProviderFamily::Standard,
            require_streaming: false,
        }),
        OPENAI_RERANK_SYNC_PLAN_KIND => Some(LocalSameFormatProviderSpec {
            api_format: "openai:rerank",
            decision_kind: OPENAI_RERANK_SYNC_PLAN_KIND,
            report_kind: "openai_rerank_sync_success",
            family: LocalSameFormatProviderFamily::Standard,
            require_streaming: false,
        }),
        _ => None,
    }
}

pub fn resolve_stream_spec(plan_kind: &str) -> Option<LocalSameFormatProviderSpec> {
    match plan_kind {
        CLAUDE_CHAT_STREAM_PLAN_KIND => Some(LocalSameFormatProviderSpec {
            api_format: "claude:messages",
            decision_kind: CLAUDE_CHAT_STREAM_PLAN_KIND,
            report_kind: "claude_chat_stream_success",
            family: LocalSameFormatProviderFamily::Standard,
            require_streaming: true,
        }),
        CLAUDE_CLI_STREAM_PLAN_KIND => Some(LocalSameFormatProviderSpec {
            api_format: "claude:messages",
            decision_kind: CLAUDE_CLI_STREAM_PLAN_KIND,
            report_kind: "claude_cli_stream_success",
            family: LocalSameFormatProviderFamily::Standard,
            require_streaming: true,
        }),
        GEMINI_CHAT_STREAM_PLAN_KIND => Some(LocalSameFormatProviderSpec {
            api_format: "gemini:generate_content",
            decision_kind: GEMINI_CHAT_STREAM_PLAN_KIND,
            report_kind: "gemini_chat_stream_success",
            family: LocalSameFormatProviderFamily::Gemini,
            require_streaming: true,
        }),
        GEMINI_CLI_STREAM_PLAN_KIND => Some(LocalSameFormatProviderSpec {
            api_format: "gemini:generate_content",
            decision_kind: GEMINI_CLI_STREAM_PLAN_KIND,
            report_kind: "gemini_cli_stream_success",
            family: LocalSameFormatProviderFamily::Gemini,
            require_streaming: true,
        }),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::{resolve_stream_spec, resolve_sync_spec};

    #[test]
    fn resolves_claude_sync_same_format_spec() {
        let spec = resolve_sync_spec("claude_chat_sync").expect("spec");
        assert_eq!(spec.api_format, "claude:messages");
        assert_eq!(spec.report_kind, "claude_chat_sync_success");
        assert!(!spec.require_streaming);
    }

    #[test]
    fn resolves_gemini_stream_same_format_spec() {
        let spec = resolve_stream_spec("gemini_cli_stream").expect("spec");
        assert_eq!(spec.api_format, "gemini:generate_content");
        assert_eq!(spec.report_kind, "gemini_cli_stream_success");
        assert!(spec.require_streaming);
    }

    #[test]
    fn resolves_openai_embedding_sync_same_format_spec() {
        let spec = resolve_sync_spec("openai_embedding_sync").expect("spec");
        assert_eq!(spec.api_format, "openai:embedding");
        assert_eq!(spec.report_kind, "openai_embedding_sync_success");
        assert!(!spec.require_streaming);
    }

    #[test]
    fn resolves_gemini_embedding_sync_same_format_spec() {
        let spec = resolve_sync_spec("gemini_embedding_sync").expect("spec");
        assert_eq!(spec.api_format, "gemini:embedding");
        assert_eq!(spec.report_kind, "gemini_embedding_sync_success");
        assert_eq!(spec.family, super::LocalSameFormatProviderFamily::Gemini);
        assert!(!spec.require_streaming);
    }

    #[test]
    fn resolves_openai_rerank_sync_same_format_spec() {
        let spec = resolve_sync_spec("openai_rerank_sync").expect("spec");
        assert_eq!(spec.api_format, "openai:rerank");
        assert_eq!(spec.report_kind, "openai_rerank_sync_success");
        assert!(!spec.require_streaming);
    }
}
