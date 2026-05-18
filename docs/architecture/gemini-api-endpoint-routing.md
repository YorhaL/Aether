# Gemini API Endpoint Routing Design

**状态:** implementation design
**最后更新:** 2026-05-18
**目标:** 把 Gemini Developer API 和 Vertex AI 的端点语义在 Aether 内部做成明确、可测试、可审计的一等路由语义，根治 `generativelanguage.googleapis.com` 与 `aiplatform.googleapis.com` 混用、批量 embedding 伪成功、provider 能力声明不完整等问题。

---

## 速查结论

Aether 里同一个 `api_format` 只描述请求/响应数据形态，不等于实际 Google 后端产品面。

| Aether 语义 | 默认后端产品面 | 官方 host | 主要认证形态 | 说明 |
| --- | --- | --- | --- | --- |
| Google / Gemini Developer API | Gemini Developer API, 也就是 AI Studio 这条 Gemini API | `generativelanguage.googleapis.com` | API key | 默认 Gemini provider 应走这里 |
| Vertex AI | Vertex AI Gemini API | `aiplatform.googleapis.com` 或 `{region}-aiplatform.googleapis.com` | service account / Vertex API key | `provider_type = vertex_ai` 应走这里 |

Aether 还必须区分 Google 官方的 OpenAI-compatible 表面。它们使用 OpenAI request/response schema，但不等于 native `generateContent` / `embedContent` endpoint：

| OpenAI-compatible 表面 | 后端产品面 | 官方 API root | 主要认证形态 | Aether 处理原则 |
| --- | --- | --- | --- | --- |
| Gemini Developer API OpenAI compatibility | Gemini Developer API / AI Studio | `https://generativelanguage.googleapis.com/v1beta/openai` | Gemini API key as Bearer | 只在 provider format 是 `openai:*` 且显式配置该 root 时使用 |
| Vertex AI OpenAI compatibility | Vertex AI / Google Cloud | `https://aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/endpoints/openapi` | Google Cloud access token / service account | 只在显式 OpenAI-compatible endpoint 上使用；不得替代 native Vertex provider 主链 |

端点动作必须按后端产品面区分：

| 能力 | Gemini Developer API | Vertex AI | Aether 处理原则 |
| --- | --- | --- | --- |
| Generate Content | `models/{model}:generateContent` | `projects/{project}/locations/{location}/publishers/google/models/{model}:generateContent` | 两边都支持，但 URL 构造不同 |
| Stream Generate Content | `models/{model}:streamGenerateContent?alt=sse` | `projects/{project}/locations/{location}/publishers/google/models/{model}:streamGenerateContent?alt=sse` | 两边都支持，但 URL 构造不同 |
| Single Embedding | `models/{model}:embedContent` | `projects/{project}/locations/{location}/publishers/google/models/{model}:predict` | Vertex 文本 embedding 使用 Predict contract：`instances[]` + `parameters` |
| Batch Embedding | `models/{model}:batchEmbedContents` | 同一个 `:predict`，由 `instances[]` 表达多输入 | Aether 不切到 Developer API；模型自身的批量限制由 Vertex 明确返回 |

工程不变量：

1. 默认 Gemini provider 只能生成 Gemini Developer API URL，不得因为模型名是 Gemini 就走 Vertex。
2. `provider_type = vertex_ai` 或明确的 Vertex auth/host 只能生成 Vertex URL，不得回退到 Gemini Developer API URL。
3. Vertex embedding 请求必须使用 Vertex Predict contract，不得把 Developer API 的 `model/content/requests` body 原样发给 `:predict`。
4. 任何“不支持”的情况必须在调度/URL 构造阶段显式暴露为不可用，不能伪成功。
5. Provider 模板、runtime policy、URL builder、conversion policy、测试连接、live DB reconciliation 必须消费同一个语义模型。
6. Google 官方 OpenAI-compatible root 已经包含 API root，Aether 不得额外拼接 `/v1`，否则会生成 `.../openai/v1/...` 或 `.../endpoints/openapi/v1/...` 这类错误 URL。
7. Native Gemini endpoint 与 Google OpenAI-compatible endpoint 不是互相 fallback 的关系。显式配置 `openai:*` 才能走 OpenAI-compatible；显式配置 `gemini:*` 才能走 native Gemini REST。

---

## 官方资料依据

本节只记录影响工程设计的官方事实。实现前必须以这些来源为真源，而不是以旧代码行为为真源。

### Gemini Developer API / AI Studio

官方 Gemini API 文档把 Developer API 作为可直接用 API key 调用的产品面。其 REST API host 是 `generativelanguage.googleapis.com`，常见路径是 `/v1beta/models/{model}:...`。

关键资料：

- Gemini API reference: <https://ai.google.dev/api>
- Gemini API Generate Content: <https://ai.google.dev/api/generate-content>
- Gemini API Embeddings guide: <https://ai.google.dev/gemini-api/docs/embeddings>
- Gemini API embeddings reference: <https://ai.google.dev/api/embeddings>
- Gemini API OpenAI compatibility: <https://ai.google.dev/gemini-api/docs/openai>
- Gemini API migrate to cloud / Vertex AI: <https://ai.google.dev/gemini-api/docs/migrate-to-cloud>

工程含义：

- `generateContent` 与 `streamGenerateContent` 可以走 Developer API host。
- `embedContent` 是单条 embedding。
- `batchEmbedContents` 是 Developer API 的批量 embedding 方法；批量 body 形态是顶层 `requests[]`，每项包含 `model` 和 `content`。
- Developer API key 不应被拼进 path；Aether URL builder 应继续过滤或独立处理 `key` query，避免 query 重复或泄露。
- Developer API 的 OpenAI-compatible root 是 `/v1beta/openai`，其 chat / embedding path 是 `/chat/completions` 与 `/embeddings`，不是 `/v1/chat/completions` 与 `/v1/embeddings`。

### Vertex AI Gemini API

Vertex AI 的 Gemini API REST reference 使用 `aiplatform.googleapis.com` 或 region host，路径包含 GCP project 与 location。

关键资料：

- Vertex AI Generate Content REST: <https://docs.cloud.google.com/vertex-ai/generative-ai/docs/reference/rest/v1/projects.locations.publishers.models/generateContent>
- Vertex AI Stream Generate Content REST: <https://docs.cloud.google.com/vertex-ai/generative-ai/docs/reference/rest/v1/projects.locations.publishers.models/streamGenerateContent>
- Vertex AI Embed Content REST: <https://docs.cloud.google.com/vertex-ai/generative-ai/docs/reference/rest/v1/projects.locations.publishers.models/embedContent>
- Vertex AI Predict REST: <https://docs.cloud.google.com/vertex-ai/generative-ai/docs/reference/rest/v1/projects.locations.publishers.models/predict>
- Vertex AI REST resources: <https://docs.cloud.google.com/vertex-ai/generative-ai/docs/reference/rest/v1/projects.locations.publishers.models>
- Vertex AI Model Garden publisher model list: <https://docs.cloud.google.com/vertex-ai/docs/reference/rest/v1beta1/publishers.models/list>
- Vertex AI text embeddings API: <https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/text-embeddings-api>
- Vertex AI OpenAI compatibility: <https://cloud.google.com/vertex-ai/generative-ai/docs/start/openai>

工程含义：

- Vertex service account 路径必须包含 project 和 location：
  - `https://{region}-aiplatform.googleapis.com/v1/projects/{project}/locations/{region}/publishers/google/models/{model}:{action}`
  - 对 `global` location，可使用 `https://aiplatform.googleapis.com/v1/projects/{project}/locations/global/...`
- Vertex API key 路径可走：
  - `https://aiplatform.googleapis.com/v1/publishers/google/models/{model}:{action}?key=...`
- Vertex 模型目录拉取不是推理请求，必须走 Model Garden publisher list：
  - `https://aiplatform.googleapis.com/v1beta1/publishers/{publisher}/models`
  - 不得使用 `projects/{project}/locations/{location}/publishers/{publisher}/models`；`projects.locations.publishers.models` 资源没有 list 方法，只有 generate / stream / predict / embed 等动作。
- Vertex 文本 embedding API 文档使用 `:predict`，请求体是 `instances[]`，可选参数在 `parameters` 下；响应是 `predictions[].embeddings.values`。
- Vertex REST reference 也列出 `embedContent`，但 Aether 当前 text embedding 主链使用 text embeddings guide 和 Predict API 的 contract。
- Vertex `instances[]` 是在线 Predict 请求体，不等同于异步 batch prediction job。模型级输入数量限制由 Vertex 返回；Aether 不把超出限制的请求静默改走其他产品面。
- Vertex OpenAI-compatible root 是 `/v1/projects/{project}/locations/{location}/endpoints/openapi`，其 OpenAI path 直接挂在这个 root 之后。
- 自定义 Vertex OpenAI-compatible endpoint 可以使用 service account token 刷新，但只有 base URL 明确落在 `/endpoints/openapi` 时才能启用该 Vertex auth 语义。普通 `aiplatform.googleapis.com` + `openai:*` 不能被误判成 Vertex OpenAI compatibility。

### Google Gen AI SDK 的后端切换语义

官方 SDK 同时支持 Gemini Developer API 与 Vertex AI，但二者需要显式选择后端。SDK 层面的 `vertexai=true` / `GOOGLE_GENAI_USE_VERTEXAI=true` 说明：这不是“同一 URL 自动兼容”的关系，而是同一 SDK 下的两个后端产品面。

关键资料：

- Google Gen AI SDK docs: <https://googleapis.github.io/python-genai/>
- Vertex AI SDK overview: <https://cloud.google.com/vertex-ai/generative-ai/docs/sdks/overview>
- Gemini API migrate to cloud / Vertex AI: <https://ai.google.dev/gemini-api/docs/migrate-to-cloud>

工程含义：

- Aether 也应把“选择 Gemini Developer API 还是 Vertex AI”作为显式路由语义，而不是让 URL builder 通过零散 host 字符串猜测。
- `api_format = gemini:generate_content` 与 `api_format = gemini:embedding` 只是数据格式。真正的后端产品面由 provider family / auth / endpoint host 决定。

---

## Aether 当前相关链路

这一节说明在 Aether 内部，哪些对象共同决定一次 Gemini 请求实际打到哪里。

| 层 | 代表文件 | 当前职责 | 设计要求 |
| --- | --- | --- | --- |
| 请求格式转换 | `crates/aether-ai-formats/src/formats/...` | OpenAI / Gemini / Claude 等格式互转 | 只负责 body 形态，不决定 Google 后端产品面 |
| Provider 类型模板 | `crates/aether-provider-transport/src/provider_types.rs` | 固定 provider 默认 endpoint、runtime policy | Vertex 模板必须声明 generate + embedding 能力 |
| Runtime policy | `crates/aether-provider-transport/src/provider_types.rs` 和 provider policy | 判断 provider 是否本地可消费 | Vertex embedding 必须进入支持矩阵 |
| URL builder | `crates/aether-provider-transport/src/request_url/mod.rs` | 把 transport + mapped_model + api_format 转成 upstream URL | 必须按后端产品面构造 URL |
| Vertex helpers | `crates/aether-provider-transport/src/vertex/url.rs` | 构造 Vertex 特有 URL | 必须覆盖 generate / stream / embedding |
| Conversion policy | `crates/aether-provider-transport/src/conversion.rs` | 判定跨格式请求能否走某个 transport | OpenAI embedding -> Gemini embedding 在 Vertex 上必须可判定、可认证、可 URL |
| Gateway 测试连接 | `apps/aether-gateway/src/handlers/public/support/test_connection/route.rs` | 测试 provider endpoint 是否可用 | 不得用过低 token 或伪成功规则误判 Gemini 3 |
| Live provider reconciliation | gateway admin/provider 初始化与 DB | 把固定模板同步到 live DB | 新 endpoint 不应只存在源码里，必须进入 live provider/endpoints |

---

## 目标语义模型

新增或显式固化一个内部概念：`GeminiEndpointFamily`。

```rust
enum GeminiEndpointFamily {
    DeveloperApi,
    VertexAi,
}
```

该概念不一定必须以公开 enum 落地，但所有相关函数必须在行为上遵守同一判定：

| 判定输入 | 结果 | 备注 |
| --- | --- | --- |
| `provider_type == "vertex_ai"` | `VertexAi` | 固定 provider 主判据 |
| endpoint host 看起来是 `aiplatform.googleapis.com` 或 `{region}-aiplatform.googleapis.com` | `VertexAi` | 支持自定义 Vertex provider，但不可反客为主覆盖固定 provider |
| Vertex service account auth 可解析 | `VertexAi` | service account 是 Vertex 强语义 |
| Vertex API key query auth 可解析 | `VertexAi` | Vertex API key 仍是 Vertex 后端 |
| 普通 Google/Gemini provider + `generativelanguage.googleapis.com` | `DeveloperApi` | 默认 Gemini API |

禁止规则：

- 不得因为 `api_format` 是 `gemini:*` 就默认走 Vertex。
- 不得因为 Vertex 缺少某个 endpoint 就回退到 Developer API。
- 不得在 URL builder 里用“host 像谁就算谁”覆盖固定 provider 的 provider_type。
- 不得在 body converter 里偷偷决定 endpoint family；body converter 只能做数据形态转换。

---

## URL 构造矩阵

### Developer API URL

| Aether api_format | stream | batch | URL 形态 |
| --- | --- | --- | --- |
| `gemini:generate_content` | false | 不适用 | `/v1beta/models/{model}:generateContent` |
| `gemini:generate_content` | true | 不适用 | `/v1beta/models/{model}:streamGenerateContent?alt=sse` |
| `gemini:embedding` | false | false | `/v1beta/models/{model}:embedContent` |
| `gemini:embedding` | false | true | `/v1beta/models/{model}:batchEmbedContents` |

Developer API 的批量 embedding 支持顶层 `requests[]`。Aether 可以继续用 body 检测来决定单条还是批量 URL，但该检测只允许影响 Developer API URL。

### Vertex AI URL

| Aether api_format | stream | batch | URL 形态 |
| --- | --- | --- | --- |
| `gemini:generate_content` | false | 不适用 | `/v1/projects/{project}/locations/{location}/publishers/google/models/{model}:generateContent` |
| `gemini:generate_content` | true | 不适用 | `/v1/projects/{project}/locations/{location}/publishers/google/models/{model}:streamGenerateContent?alt=sse` |
| `gemini:embedding` | false | false | `/v1/projects/{project}/locations/{location}/publishers/google/models/{model}:predict` |
| `gemini:embedding` | false | true | `/v1/projects/{project}/locations/{location}/publishers/google/models/{model}:predict` |

Vertex text embedding 的模型由 URL path 承载，body 不得重复携带顶层 `model` 字段，否则会触发 Vertex `oneof field '_model' is already set` 一类错误。Aether 在 Vertex transport context 下必须把 Gemini Developer API embedding body 转成 Predict body：

```json
{
  "instances": [
    { "content": "text", "task_type": "RETRIEVAL_QUERY", "title": "optional" }
  ],
  "parameters": {
    "outputDimensionality": 768,
    "autoTruncate": true
  }
}
```

如果输入已经是 Predict body，Aether 只移除重复的顶层 `model`。如果输入仍是 OpenAI body 或无法确定可转换，调度阶段必须显式失败，不得把未转换 body 发到 Vertex native endpoint。

### Google OpenAI-Compatible URL

OpenAI-compatible URL 属于显式 passthrough root，不参与 native Gemini URL builder。

| Aether api_format | Gemini Developer API OpenAI compatibility | Vertex AI OpenAI compatibility | Aether 处理原则 |
| --- | --- | --- | --- |
| `openai:chat` | `/v1beta/openai/chat/completions` | `/v1/projects/{project}/locations/{location}/endpoints/openapi/chat/completions` | root 已含 API 版本，不再补 `/v1` |
| `openai:embedding` | `/v1beta/openai/embeddings` | `/v1/projects/{project}/locations/{location}/endpoints/openapi/embeddings` | root 已含 API 版本，不再补 `/v1` |

这条链路的关键边界：

1. `openai:*` provider format 走 OpenAI-compatible schema，不做 OpenAI -> Gemini native body 转换。
2. `gemini:*` provider format 走 native Gemini schema，不因目标是 Google provider 就切到 OpenAI-compatible endpoint。
3. 如果用户请求 `openai:*`、provider endpoint 是 `gemini:*`，Aether 走格式转换后打 native Gemini endpoint。
4. 如果用户请求 `openai:*`、provider endpoint 也是 `openai:*`，Aether 保持 OpenAI schema 并打显式 OpenAI-compatible root。
5. 以上两条都是正式主链，不能互相静默顶替。

---

## 请求体转换边界

`aether-ai-formats` 中的 Gemini embedding converter 当前负责：

- 单条 input -> `embedContent` body
- 多条 input -> Developer API `batchEmbedContents` body
- `dimensions` -> `outputDimensionality`
- embedding task -> Gemini `taskType`

设计要求：

1. 该 converter 可以继续生成 Gemini Developer API 的 `embedContent` / `batchEmbedContents` body。
2. Transport 层必须在 Vertex context 下把该 body 转成 Predict body，并在无法转换时 fail closed。
3. 所有 taskType / outputDimensionality 必须保持显式传递；不得默认注入会改变语义的 task 或维度。
4. Vertex Predict 的 `instances[]` 只能表示在线 Predict 请求的一次调用；它不是异步 batch prediction job，也不是 Developer API `batchEmbedContents` 的静默替身。
5. Developer API 单条 embedding body 可以保留 `model`；Vertex 单条 embedding 在 gateway transport 语义层必须删除顶层 `model`，因为 Vertex 模型已在 path 中指定。

### 格式转换矩阵

端点族和格式转换是两层语义：

- 端点族决定请求发往 `generativelanguage.googleapis.com` 还是 `aiplatform.googleapis.com`。
- 格式转换决定客户端传入的 body 如何变成 provider 所需 body，以及 provider response 如何变回客户端期望 body。

`gemini:generate_content` 在 Developer API 与 Vertex AI 上使用同一 Gemini generate-content body 形态，因此格式转换器不应区分这两个产品面。产品面差异只留给 URL/auth 层处理。

`gemini:embedding` 在格式层仍先表达为 Gemini Developer API 的 embedding body。进入 Vertex transport context 时，transport 层再把它收敛到 Vertex Predict body。这样格式转换器不需要知道认证方式，URL/body transport 也不会把 Developer API body 原样发给 Vertex。

| 客户端格式 | Provider 格式 | Developer API | Vertex AI | 处理要求 |
| --- | --- | --- | --- | --- |
| `openai:chat` | `gemini:generate_content` | 支持 | 支持 | OpenAI chat -> Gemini contents / generationConfig |
| `gemini:generate_content` | `openai:chat` | 支持 | 支持 | Gemini contents -> OpenAI messages |
| `openai:embedding` | `gemini:embedding` 单条 | 支持 | 支持 | OpenAI input string 或单项数组 -> Gemini `embedContent` body；Vertex transport 再转 `instances[]` |
| `openai:embedding` | `gemini:embedding` 多条 | 支持 | 支持于 transport 层 | Developer API -> `batchEmbedContents`；Vertex transport -> Predict `instances[]`，模型限制由 Vertex 返回 |
| `gemini:embedding` 单条 | `openai:embedding` | 支持 | 支持 | Gemini `content.parts[].text` -> OpenAI `input` string |
| `gemini:embedding` 批量 | `openai:embedding` | 支持 | 支持 | Gemini `requests[]` -> OpenAI `input[]`；Vertex Predict response 同样可转 |
| `gemini:embedding` response | `openai:embedding` response | 支持 | 支持 | Gemini `embedding.values` / `embeddings[].values` / Vertex `predictions[].embeddings.values` -> OpenAI `data[].embedding` |
| `openai:embedding` response | `gemini:embedding` response | 支持 | 支持于格式层 | OpenAI `data[]` -> Gemini single `embedding` 或 batch `embeddings[]` |
| `openai:chat` | `openai:chat` on Google OpenAI-compatible root | 支持 | 支持 | passthrough OpenAI schema，不做 native Gemini 转换 |
| `openai:embedding` | `openai:embedding` on Google OpenAI-compatible root | 支持 | 支持 | passthrough OpenAI schema，不做 native Gemini 转换 |

这张矩阵的关键点：

1. 格式层必须能双向理解 Gemini native embedding request/response 与 OpenAI embedding request/response。
2. Vertex text embedding 使用 Predict contract；多输入由 `instances[]` 表达，不构造不存在的 `:batchEmbedContents`。
3. 一旦 provider family 是 Vertex，任何 embedding 请求都不能借格式转换之名回退到 Developer API。
4. 对 OpenAI embedding 单项数组，转换器必须生成 Gemini 单条 body，避免把“单条业务请求”误判成 Vertex batch。
5. Google OpenAI-compatible passthrough 与 OpenAI -> Gemini native conversion 是两条显式路径。管理员通过 provider endpoint format 选择路径，Aether 不得自动“择优”改路。

---

## Provider 能力声明与调度

Vertex provider 的固定模板必须包含：

- `gemini:generate_content`
- `gemini:embedding`
- `claude:messages`，如果当前上游 Vertex Claude 支持仍保留

Runtime policy 必须表达：

- Vertex 能本地消费 Gemini generate content。
- Vertex 能本地消费 Gemini embedding，并在 transport 层生成 Predict URL/body。
- Vertex text embedding 的模型级输入数量限制由 Vertex 返回；Aether 不静默拆分、不静默降级到 Developer API。
- 全局模型名与 Vertex 实际 provider 模型名必须可以分离。例如客户端继续请求全局 `gemini-embedding-2-preview` 时，Vertex provider model 可以映射到官方可用的 `gemini-embedding-2`；调度、key allowed_models、URL builder 必须消费映射后的 provider model，不得拿全局 preview 名直打 Vertex。

调度与 conversion policy 必须表达：

- `openai:embedding -> gemini:embedding` 可以被 Vertex provider 接收，transport 层负责把 Gemini Developer API body 转成 Vertex Predict body。
- 对批量 input，不能生成 Vertex `:batchEmbedContents`，也不能回退到 `generativelanguage.googleapis.com`。
- `request_pair_direct_auth` 对 Vertex API key 必须返回 `key` query auth；service account auth 由 OAuth refresh path 处理，不能伪造成普通 bearer key。

---

## 测试设计

必须覆盖这些测试面：

1. Developer API generate URL:
   - non-stream -> `generativelanguage.googleapis.com/...:generateContent`
   - stream -> `...:streamGenerateContent?alt=sse`
2. Developer API embedding URL:
   - 单条 body -> `...:embedContent`
   - 多条 body -> `...:batchEmbedContents`
3. Vertex generate URL:
   - API key auth -> `aiplatform.googleapis.com/v1/publishers/google/models/...`
   - service account -> project/location path
4. Vertex embedding URL:
   - API key auth -> `...:predict?key=...`
   - service account -> project/location `...:predict`
5. Vertex embedding body:
   - 单条 `model/content` body -> `instances[]`，且移除顶层 `model`
   - body 含顶层 `requests[]` 时 -> `instances[]`
   - body 已经是 `instances[]` 时只清理重复 `model`
   - 无法映射的 body 在调度/模型测试阶段显式失败
   - 不得生成 `generativelanguage.googleapis.com`
   - 不得生成 `aiplatform.googleapis.com/...:batchEmbedContents`
6. Provider template:
   - Vertex fixed template 包含 `gemini:embedding`
   - provider embedding support 矩阵包含 Vertex -> Gemini embedding
7. Conversion:
   - OpenAI embedding 可以被转换到 Gemini embedding provider format
   - Vertex embedding transport 可通过支持检查
   - Vertex embedding execution plan 的 URL 使用 mapped provider model，body 不含顶层 `model`
   - Vertex embedding execution plan 的 body 使用 `instances[]` / `parameters`
8. Gateway test connection:
   - Gemini generate content 测试不能强制 `maxOutputTokens = 5`
   - Google OpenAI-compatible `openai:chat` 测试不能强制 `max_tokens = 5`，否则 Gemini thinking 模型仍可能只返回 thought token / 空 visible content
   - Gemini 3 / thinking 模型返回 HTTP 200 但无 visible content 时必须判失败，不能写成成功
9. Google OpenAI-compatible roots:
   - Developer API OpenAI root `.../v1beta/openai` 打 `openai:chat` 时生成 `.../chat/completions`，不得生成 `.../openai/v1/chat/completions`
   - Developer API OpenAI root `.../v1beta/openai` 打 `openai:embedding` 时生成 `.../embeddings`，不得生成 `.../openai/v1/embeddings`
   - Vertex OpenAI root `.../endpoints/openapi` 打 `openai:chat` / `openai:embedding` 时直接挂对应 OpenAI path
   - 自定义 Vertex OpenAI-compatible service account endpoint 必须进入 Vertex auth refresh 上下文；普通 `aiplatform.googleapis.com` + `openai:*` 不得被误认成 Vertex OpenAI-compatible
10. Admin write validation:
   - Vertex API key key formats 允许 `gemini:generate_content` 与 `gemini:embedding`
   - Vertex service account key formats 允许 `claude:messages`、`gemini:generate_content` 与 `gemini:embedding`

测试断言必须检查具体 URL、具体 action、具体 body contract 和具体失败原因，不能只检查 `Some(url)` 或状态码。

---

## Live 迁移与验证

上线后必须做四类验证：

1. 源码测试：
   - `cargo test -p aether-provider-transport --lib`
   - 必要时补 `cargo test -p aether-ai-formats --lib`
   - 必要时补 gateway 相关 test
2. Live DB reconciliation：
   - `vertex_ai` provider 的 endpoints 中必须出现 `gemini:embedding`
   - Google/Gemini provider 的 embedding endpoint 仍指向 Developer API，不被 Vertex 改写
3. Live HTTP smoke：
   - Developer API embedding 单条可用
   - Developer API embedding 批量可用
   - Vertex generate content 返回 visible content 才算成功
   - Vertex embedding 单输入可用
   - Vertex embedding 多输入如果模型拒绝，必须暴露 Vertex 原始失败，不能降级成 Developer API 成功
4. 接入方地址核验：
   - astrbot plugin ltm
   - codex cli config
   - 其它容器中引用 Aether 的配置

接入方默认应使用容器网络内稳定地址：

```text
http://aether-app:8084/v1
```

只有在调用方不在 `edge-stack-aether-internal` 这类 Docker 内网、或需要从宿主机/外网访问时，才使用宿主机映射地址或域名。

---

## 明确不做的事

1. 不把 Vertex embedding 多输入写成隐藏循环。隐藏 fan-out 会改变成本、延迟、断路器行为和重试语义，必须另开设计。
2. 不为了测试通过把 Vertex 请求降级到 Developer API。
3. 不为了让 HTTP 200 看起来成功而接受空 candidate / MAX_TOKENS 无 visible content。
4. 不改前端视觉定制、字体、品牌名、landing page 设计。
5. 不用旧 provider endpoint 继续承担新主链。
6. 不把 Google OpenAI-compatible endpoint 当成 native Gemini endpoint 的隐藏 fallback；它只能通过显式 `openai:*` endpoint 进入。

---

## 施工顺序

1. 固化 endpoint family 判定与 URL helper。
2. 为 Vertex `gemini:embedding` 补齐 provider template、runtime policy、conversion policy。
3. 让 request URL builder 对 Vertex embedding 走 Vertex Predict helper。
4. 让 transport body semantics 对 Vertex embedding 生成 `instances[]` / `parameters`，无法转换时 fail closed。
5. 移除测试连接中对 Gemini generate content 的过低 `maxOutputTokens` 硬编码，防止 Gemini 3 thinking 被预算挤空。
6. 移除公开 test-connection 对 OpenAI-compatible chat 的过低 `max_tokens` 硬编码，防止 Google OpenAI-compatible root 复发同类空输出。
7. 跑 red/green 测试。
8. 部署 live。
9. 校验 live DB provider endpoints 与外部接入方地址。

---

## 后续可选增强

如果 7 天 embedding 重算必须在 Vertex 上高吞吐完成，建议后续单独实现 `VertexEmbeddingFanoutExecutor`：

- 输入 OpenAI embedding 数组。
- 按配置分片，每片发单条或有限并发 Vertex `predict`。
- 合并为 OpenAI embedding response。
- 将每个子请求的失败、重试、成本、断路器状态独立记录。

这项增强不能混入本次 endpoint 语义修复，否则会扩大风险面。
