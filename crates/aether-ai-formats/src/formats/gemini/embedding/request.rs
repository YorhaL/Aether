use serde_json::{json, Map, Value};

use crate::formats::context::FormatContext;
use crate::formats::openai::embedding::request::mapped_embedding_model;
use crate::protocol::canonical::{CanonicalEmbeddingRequest, CanonicalRequest};

pub fn to(request: &CanonicalRequest, ctx: &FormatContext) -> Option<Value> {
    let embedding = request.embedding.as_ref()?;
    let items = embedding.input.as_string_items()?;
    if items.is_empty() || items.iter().any(|value| value.trim().is_empty()) {
        return None;
    }
    let model = mapped_embedding_model(request, ctx.mapped_model_or(request.model.as_str()));
    if items.len() == 1 {
        return Some(Value::Object(gemini_embedding_request_object(
            &model, items[0], embedding,
        )));
    }
    let model_resource = gemini_embedding_model_resource_name(&model);
    let requests = items
        .into_iter()
        .map(|text| {
            Value::Object(gemini_embedding_request_object(
                &model_resource,
                text,
                embedding,
            ))
        })
        .collect::<Vec<_>>();
    Some(json!({ "requests": requests }))
}

fn gemini_embedding_request_object(
    model: &str,
    text: &str,
    embedding: &CanonicalEmbeddingRequest,
) -> Map<String, Value> {
    let mut object = Map::new();
    object.insert("model".to_string(), Value::String(model.to_string()));
    object.insert(
        "content".to_string(),
        json!({
            "parts": [{"text": text}]
        }),
    );
    insert_gemini_embedding_options(&mut object, embedding);
    object
}

fn gemini_embedding_model_resource_name(model: &str) -> String {
    let trimmed = model.trim();
    if trimmed.starts_with("models/") {
        trimmed.to_string()
    } else {
        format!("models/{trimmed}")
    }
}

fn insert_gemini_embedding_options(
    object: &mut Map<String, Value>,
    embedding: &CanonicalEmbeddingRequest,
) {
    if let Some(dimensions) = embedding.dimensions {
        object.insert("outputDimensionality".to_string(), Value::from(dimensions));
    }
    if let Some(task_type) = embedding
        .task
        .as_deref()
        .and_then(normalize_gemini_embedding_task_type)
    {
        object.insert("taskType".to_string(), Value::String(task_type));
    }
}

fn normalize_gemini_embedding_task_type(value: &str) -> Option<String> {
    let normalized = value.trim();
    if normalized.is_empty() {
        return None;
    }
    let key = normalized.replace(['-', ' '], "_").to_ascii_uppercase();
    let task_type = match key.as_str() {
        "QUERY" | "RETRIEVAL_QUERY" => "RETRIEVAL_QUERY",
        "DOCUMENT" | "RETRIEVAL_DOCUMENT" => "RETRIEVAL_DOCUMENT",
        "TEXT_MATCHING" | "SEMANTIC_SIMILARITY" => "SEMANTIC_SIMILARITY",
        "CLASSIFICATION" => "CLASSIFICATION",
        "CLUSTERING" => "CLUSTERING",
        "QUESTION_ANSWERING" => "QUESTION_ANSWERING",
        "FACT_VERIFICATION" => "FACT_VERIFICATION",
        "CODE_RETRIEVAL_QUERY" => "CODE_RETRIEVAL_QUERY",
        _ => key.as_str(),
    };
    Some(task_type.to_string())
}

#[cfg(test)]
mod tests {
    use std::collections::BTreeMap;

    use serde_json::json;

    use super::to;
    use crate::formats::context::FormatContext;
    use crate::protocol::canonical::{
        CanonicalEmbeddingInput, CanonicalEmbeddingRequest, CanonicalRequest,
    };

    fn canonical_embedding(input: CanonicalEmbeddingInput) -> CanonicalRequest {
        CanonicalRequest {
            model: "text-embedding-3-small".to_string(),
            embedding: Some(CanonicalEmbeddingRequest {
                input,
                encoding_format: None,
                dimensions: None,
                task: None,
                user: None,
                extensions: BTreeMap::new(),
            }),
            ..CanonicalRequest::default()
        }
    }

    #[test]
    fn single_string_array_item_uses_single_embed_content_body() {
        let request = canonical_embedding(CanonicalEmbeddingInput::StringArray(vec![
            "hello".to_string()
        ]));
        let body = to(
            &request,
            &FormatContext::default().with_mapped_model("gemini-embedding-2-preview"),
        )
        .expect("gemini embedding request");

        assert_eq!(body["model"], "gemini-embedding-2-preview");
        assert_eq!(body["content"]["parts"][0]["text"], "hello");
        assert!(body.get("requests").is_none());
    }

    #[test]
    fn multiple_string_items_use_gemini_batch_request_body() {
        let request = canonical_embedding(CanonicalEmbeddingInput::StringArray(vec![
            "alpha".to_string(),
            "beta".to_string(),
        ]));
        let body = to(
            &request,
            &FormatContext::default().with_mapped_model("gemini-embedding-2-preview"),
        )
        .expect("gemini embedding request");

        assert!(body.get("model").is_none());
        assert_eq!(body["requests"].as_array().map(Vec::len), Some(2));
        assert_eq!(
            body["requests"][0]["model"],
            "models/gemini-embedding-2-preview"
        );
        assert_eq!(body["requests"][0]["content"]["parts"][0]["text"], "alpha");
        assert_eq!(
            body["requests"][1]["model"],
            "models/gemini-embedding-2-preview"
        );
        assert_eq!(body["requests"][1]["content"]["parts"][0]["text"], "beta");
    }

    #[test]
    fn explicit_embedding_options_are_preserved_without_defaults() {
        let mut request = canonical_embedding(CanonicalEmbeddingInput::String("query".to_string()));
        let embedding = request.embedding.as_mut().expect("embedding request");
        embedding.dimensions = Some(768);
        embedding.task = Some("retrieval_query".to_string());

        let body = to(
            &request,
            &FormatContext::default().with_mapped_model("gemini-embedding-2-preview"),
        )
        .expect("gemini embedding request");

        assert_eq!(body["outputDimensionality"], json!(768));
        assert_eq!(body["taskType"], "RETRIEVAL_QUERY");
    }
}
