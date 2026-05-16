use crate::ai_serving::OpenAiImageNormalizeOptions;

const DEFAULT_OPENAI_IMAGE_MAX_GENERATION_COUNT: u64 = 1;
const GROK_OPENAI_IMAGE_MAX_GENERATION_COUNT: u64 = 4;

pub(crate) fn openai_image_gateway_max_generation_count() -> u64 {
    GROK_OPENAI_IMAGE_MAX_GENERATION_COUNT
}

pub(crate) fn openai_image_gateway_max_generation_count_for_model(model: Option<&str>) -> u64 {
    if model.is_some_and(is_grok_openai_image_model) {
        GROK_OPENAI_IMAGE_MAX_GENERATION_COUNT
    } else {
        DEFAULT_OPENAI_IMAGE_MAX_GENERATION_COUNT
    }
}

pub(crate) fn openai_image_provider_max_generation_count(provider_type: &str) -> u64 {
    if provider_type.trim().eq_ignore_ascii_case("grok") {
        GROK_OPENAI_IMAGE_MAX_GENERATION_COUNT
    } else {
        DEFAULT_OPENAI_IMAGE_MAX_GENERATION_COUNT
    }
}

pub(crate) fn openai_image_normalize_options_for_provider(
    provider_type: &str,
) -> OpenAiImageNormalizeOptions {
    OpenAiImageNormalizeOptions::with_max_generation_count(
        openai_image_provider_max_generation_count(provider_type),
    )
}

fn is_grok_openai_image_model(model: &str) -> bool {
    model
        .trim()
        .to_ascii_lowercase()
        .contains("grok-imagine-image")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn grok_owns_gateway_wide_image_generation_count_ceiling() {
        assert_eq!(openai_image_gateway_max_generation_count(), 4);
        assert_eq!(
            openai_image_gateway_max_generation_count_for_model(Some("grok-imagine-image-lite")),
            4
        );
        assert_eq!(
            openai_image_gateway_max_generation_count_for_model(Some("gpt-image-2")),
            1
        );
        assert_eq!(openai_image_gateway_max_generation_count_for_model(None), 1);
        assert_eq!(openai_image_provider_max_generation_count("grok"), 4);
        assert_eq!(openai_image_provider_max_generation_count("openai"), 1);
    }
}
