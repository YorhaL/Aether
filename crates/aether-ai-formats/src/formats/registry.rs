use serde_json::Value;

use crate::formats::{
    claude::messages as claude_messages,
    doubao,
    gemini::{self, generate_content as gemini_generate_content},
    id::FormatId,
    jina,
    openai::{self, chat as openai_chat, responses as openai_responses},
};
use crate::protocol::canonical::{CanonicalRequest, CanonicalResponse};

pub use crate::formats::context::{FormatContext, FormatError};

pub fn parse_request(
    source_format: &str,
    body: &Value,
    ctx: &FormatContext,
) -> Result<CanonicalRequest, FormatError> {
    let source = parse_format(source_format)?;
    match source {
        FormatId::OpenAiChat => openai_chat::request::from(body, ctx),
        FormatId::OpenAiResponses | FormatId::OpenAiResponsesCompact => {
            openai_responses::request::from(body, ctx)
        }
        FormatId::ClaudeMessages => claude_messages::request::from(body, ctx),
        FormatId::GeminiGenerateContent => gemini_generate_content::request::from(body, ctx),
        FormatId::OpenAiEmbedding => openai::embedding::request::from(body, ctx),
        FormatId::JinaEmbedding => jina::embedding::request::from(body, ctx),
        FormatId::OpenAiRerank => openai::rerank::request::from(body, ctx),
        FormatId::JinaRerank => jina::rerank::request::from(body, ctx),
        FormatId::GeminiEmbedding | FormatId::DoubaoEmbedding => None,
    }
    .ok_or_else(|| FormatError::RequestParseFailed {
        format: source.as_str().to_string(),
    })
}

pub fn emit_request(
    target_format: &str,
    request: &CanonicalRequest,
    ctx: &FormatContext,
) -> Result<Value, FormatError> {
    let target = parse_format(target_format)?;
    let mut request = request.clone();
    if let Some(mapped_model) = ctx
        .mapped_model
        .as_deref()
        .filter(|value| !value.trim().is_empty())
    {
        request.model = mapped_model.to_string();
    }
    match target {
        FormatId::OpenAiChat => openai_chat::request::to(&request, ctx),
        FormatId::OpenAiResponses => openai_responses::request::to(&request, ctx),
        FormatId::OpenAiResponsesCompact => openai_responses::request::to_compact(&request, ctx),
        FormatId::ClaudeMessages => claude_messages::request::to(&request, ctx),
        FormatId::GeminiGenerateContent => gemini_generate_content::request::to(&request, ctx),
        FormatId::OpenAiEmbedding => openai::embedding::request::to(&request, ctx),
        FormatId::JinaEmbedding => jina::embedding::request::to(&request, ctx),
        FormatId::OpenAiRerank => openai::rerank::request::to(&request, ctx),
        FormatId::JinaRerank => jina::rerank::request::to(&request, ctx),
        FormatId::GeminiEmbedding => gemini::embedding::request::to(&request, ctx),
        FormatId::DoubaoEmbedding => doubao::embedding::request::to(&request, ctx),
    }
    .ok_or_else(|| FormatError::RequestEmitFailed {
        format: target.as_str().to_string(),
    })
}

pub fn convert_request(
    source_format: &str,
    target_format: &str,
    body: &Value,
    ctx: &FormatContext,
) -> Result<Value, FormatError> {
    let request = parse_request(source_format, body, ctx)?;
    emit_request(target_format, &request, ctx)
}

pub fn parse_response(
    source_format: &str,
    body: &Value,
    ctx: &FormatContext,
) -> Result<CanonicalResponse, FormatError> {
    let source = parse_format(source_format)?;
    match source {
        FormatId::OpenAiChat => openai_chat::response::from(body, ctx),
        FormatId::OpenAiResponses | FormatId::OpenAiResponsesCompact => {
            openai_responses::response::from(body, ctx)
        }
        FormatId::ClaudeMessages => claude_messages::response::from(body, ctx),
        FormatId::GeminiGenerateContent => gemini_generate_content::response::from(body, ctx),
        FormatId::OpenAiEmbedding
        | FormatId::JinaEmbedding
        | FormatId::OpenAiRerank
        | FormatId::JinaRerank
        | FormatId::GeminiEmbedding
        | FormatId::DoubaoEmbedding => None,
    }
    .ok_or_else(|| FormatError::ResponseParseFailed {
        format: source.as_str().to_string(),
    })
}

pub fn emit_response(
    target_format: &str,
    response: &CanonicalResponse,
    ctx: &FormatContext,
) -> Result<Value, FormatError> {
    let target = parse_format(target_format)?;
    match target {
        FormatId::OpenAiChat => openai_chat::response::to(response, ctx),
        FormatId::OpenAiResponses => openai_responses::response::to(response, ctx),
        FormatId::OpenAiResponsesCompact => openai_responses::response::to_compact(response, ctx),
        FormatId::ClaudeMessages => claude_messages::response::to(response, ctx),
        FormatId::GeminiGenerateContent => gemini_generate_content::response::to(response, ctx),
        FormatId::OpenAiEmbedding
        | FormatId::JinaEmbedding
        | FormatId::OpenAiRerank
        | FormatId::JinaRerank
        | FormatId::GeminiEmbedding
        | FormatId::DoubaoEmbedding => None,
    }
    .ok_or_else(|| FormatError::ResponseEmitFailed {
        format: target.as_str().to_string(),
    })
}

pub fn convert_response(
    source_format: &str,
    target_format: &str,
    body: &Value,
    ctx: &FormatContext,
) -> Result<Value, FormatError> {
    let mut response = parse_response(source_format, body, ctx)?;
    if response.model.trim().is_empty() || response.model == "unknown" {
        if let Some(mapped_model) = ctx
            .mapped_model
            .as_deref()
            .filter(|value| !value.trim().is_empty())
        {
            response.model = mapped_model.to_string();
        }
    }
    emit_response(target_format, &response, ctx)
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StreamTranscoderSpec {
    pub source: FormatId,
    pub target: FormatId,
}

pub fn build_stream_transcoder(
    source_format: &str,
    target_format: &str,
    _ctx: &FormatContext,
) -> Result<StreamTranscoderSpec, FormatError> {
    Ok(StreamTranscoderSpec {
        source: parse_format(source_format)?,
        target: parse_format(target_format)?,
    })
}

fn parse_format(format: &str) -> Result<FormatId, FormatError> {
    FormatId::parse(format).ok_or_else(|| FormatError::UnsupportedFormat(format.to_string()))
}

#[cfg(test)]
mod tests {
    use serde_json::json;

    use super::{convert_request, FormatContext};
    use crate::formats::id::FormatId;

    #[test]
    fn openai_cli_alias_is_not_a_primary_format() {
        assert_eq!(FormatId::parse("openai:cli"), None);
    }

    #[test]
    fn converts_openai_chat_to_responses_via_registry() {
        let body = json!({
            "model": "gpt-source",
            "messages": [{"role": "user", "content": "hello"}]
        });
        let ctx = FormatContext::default().with_mapped_model("gpt-target");

        let converted = convert_request("openai:chat", "openai:responses", &body, &ctx)
            .expect("request conversion should succeed");

        assert_eq!(converted["model"], "gpt-target");
        assert_eq!(converted["input"][0]["type"], "message");
        assert_eq!(converted["input"][0]["content"][0]["type"], "input_text");
    }

    #[test]
    fn converts_openai_embedding_to_jina_without_chat_fields() {
        let body = json!({
            "model": "text-embedding-3-small",
            "input": ["alpha", "beta"],
            "dimensions": 2
        });
        let ctx = FormatContext::default().with_mapped_model("jina-embeddings-v3");

        let converted = convert_request("openai:embedding", "jina:embedding", &body, &ctx)
            .expect("embedding request conversion should succeed");

        assert_eq!(converted["model"], "jina-embeddings-v3");
        assert_eq!(converted["task"], "text-matching");
        assert_eq!(converted["input"], json!(["alpha", "beta"]));
        assert!(converted.get("messages").is_none());
    }

    #[test]
    fn converts_openai_embedding_to_gemini_and_doubao_payload_shapes() {
        let body = json!({
            "model": "text-embedding-3-small",
            "input": ["alpha", "beta"],
            "dimensions": 2
        });

        let gemini = convert_request(
            "openai:embedding",
            "gemini:embedding",
            &body,
            &FormatContext::default().with_mapped_model("gemini-embedding-001"),
        )
        .expect("gemini embedding conversion should succeed");
        assert!(gemini.get("model").is_none());
        assert_eq!(
            gemini["requests"][0]["model"],
            "models/gemini-embedding-001"
        );
        assert_eq!(
            gemini["requests"][0]["content"]["parts"][0]["text"],
            "alpha"
        );
        assert_eq!(gemini["requests"][0]["outputDimensionality"], 2);
        assert!(gemini.get("messages").is_none());

        let doubao = convert_request(
            "openai:embedding",
            "doubao:embedding",
            &body,
            &FormatContext::default().with_mapped_model("doubao-embedding-text-240515"),
        )
        .expect("doubao embedding conversion should succeed");
        assert_eq!(doubao["model"], "doubao-embedding-text-240515");
        assert_eq!(doubao["input"], json!(["alpha", "beta"]));
        assert!(doubao.get("messages").is_none());
    }

    #[test]
    fn embedding_registry_keeps_gemini_and_doubao_emit_only() {
        let body = json!({
            "model": "gemini-embedding-001",
            "content": {"parts": [{"text": "alpha"}]}
        });
        let ctx = FormatContext::default();

        assert!(convert_request("gemini:embedding", "openai:embedding", &body, &ctx).is_err());
        assert!(convert_request("doubao:embedding", "openai:embedding", &body, &ctx).is_err());
    }

    #[test]
    fn embedding_registry_rejects_chat_payload_for_embedding_format() {
        let body = json!({
            "model": "gpt-5",
            "messages": [{"role": "user", "content": "hello"}]
        });
        let ctx = FormatContext::default();

        assert!(convert_request("openai:embedding", "jina:embedding", &body, &ctx).is_err());
    }

    #[test]
    fn converts_openai_rerank_to_jina_without_chat_fields() {
        let body = json!({
            "model": "rerank-source",
            "query": "best document",
            "documents": ["alpha", {"text": "beta"}],
            "top_n": 1,
            "return_documents": true
        });
        let ctx = FormatContext::default().with_mapped_model("jina-reranker-v2-base-multilingual");

        let converted = convert_request("openai:rerank", "jina:rerank", &body, &ctx)
            .expect("rerank request conversion should succeed");

        assert_eq!(converted["model"], "jina-reranker-v2-base-multilingual");
        assert_eq!(converted["query"], "best document");
        assert_eq!(converted["documents"], json!(["alpha", {"text": "beta"}]));
        assert_eq!(converted["top_n"], 1);
        assert_eq!(converted["return_documents"], true);
        assert!(converted.get("messages").is_none());
    }

    #[test]
    fn rerank_registry_rejects_invalid_payloads() {
        let ctx = FormatContext::default();
        for body in [
            json!({"model": "rerank", "documents": ["alpha"]}),
            json!({"model": "rerank", "query": "q", "documents": []}),
            json!({"model": "rerank", "query": "q", "documents": [""]}),
            json!({"model": "rerank", "query": "q", "documents": ["alpha"], "top_n": 0}),
        ] {
            assert!(convert_request("openai:rerank", "jina:rerank", &body, &ctx).is_err());
        }
    }

    #[test]
    fn registry_does_not_call_wire_specific_canonical_functions_directly() {
        let implementation = include_str!("registry.rs")
            .split("#[cfg(test)]")
            .next()
            .expect("registry implementation should be readable");
        for forbidden in [
            "canonical_to_openai",
            "canonical_to_claude",
            "canonical_to_gemini",
            "from_openai_chat_to_canonical",
            "from_openai_responses_to_canonical",
            "from_claude_to_canonical",
            "from_gemini_to_canonical",
        ] {
            assert!(
                !implementation.contains(forbidden),
                "registry should dispatch through formats::<provider>::<surface> adapters, found {forbidden}"
            );
        }
    }
}
