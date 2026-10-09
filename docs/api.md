# REST API

Default base URL: `http://127.0.0.1:8787`. Interactive OpenAPI docs: `/docs`.

## Add knowledge

```sh
curl -X POST http://127.0.0.1:8787/api/documents \
  -H 'Content-Type: application/json' \
  -d '{"name":"refund.md","text":"Customers can request a refund within 30 days."}'
```

`POST /api/upload` accepts multipart field `file`, a UTF-8 `.md` or `.txt` file, up to 200 KB. JSON document text is limited to 200,000 characters. The workspace holds up to 100 documents. Re-importing identical name + content is idempotent. Use `GET /api/documents` and `DELETE /api/documents/{id}` to manage sources. Deleting sources preserves saved traces.

## Inspect a question

```sh
curl -X POST http://127.0.0.1:8787/api/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"How many days to request a refund?","provider":"ollama","generator":"ollama","top_k":4,"policy":{"support_threshold":0.7,"conflict_threshold":0.35}}'
```

PowerShell:

```powershell
$body = @{
  question="How many days to request a refund?"
  provider="ollama"
  generator="ollama"
} | ConvertTo-Json
$trace = Invoke-RestMethod http://127.0.0.1:8787/api/query -Method Post -ContentType "application/json" -Body $body
$trace.action
```

Providers: `demo`, `ollama`, `openai` (any OpenAI-compatible API), `laya`, `jev`; omit to use the configured default. Generators: `extractive` (verbatim excerpts), `ollama`, `openai`, or `none` (decision only). `top_k`: 1–8, default 4. Questions: 3–500 nonblank characters. `support_threshold`: 0.25–1; `conflict_threshold`: 0.05–1.

The response is a saved trace with `schema_version=1`, `id`, `created` (UTC), `action`, `reason`, `decision`, `evidence`, `claims`, `policy`, `timing_ms` and `input_state`. New traces identify `evidence_origin` as `bm25` or `external`; older bundled traces may omit it. `generator_called` distinguishes a generator call from evidence-only output; `generation_error` records generation failures. `decision.raw_probabilities` preserves Ollama's original scores. `decision.question_schema` preserves the System One questions.

Routing order: no evidence → abstain; conflict threshold → review; support threshold → answer; combined support + partial ≥ 0.5 → retrieve more; otherwise abstain. The last boundary is fixed in this release.

Provider-reported truncation overrides the route with `retrieve_more` and blocks generation, including replay. Extra Laya usage fields such as `truncated_questions` are retained.

Provider failures return HTTP 502 without switching to demo. Generation failures preserve the judged trace and surface an empty answer with `generation_error`. They do not replace a failed model response with synthetic claims.

## Judge existing retrieval results

`POST /api/decide` accepts a question, provider, policy and an `evidence` list from your own retriever. It does not retrieve from the workspace, import documents, or generate an answer. See the [integration guide](integration.md) and [runnable adapter](../examples/external_rag.py).

```sh
curl -X POST http://127.0.0.1:8787/api/decide \
  -H 'Content-Type: application/json' \
  -d '{"question":"How long do refunds take?","provider":"demo","evidence":[{"id":"refund-1","source":"policy.md","text":"Refunds take 5 days."}]}'
```

Each chunk needs a unique `id` and nonblank `text`; `source` defaults to `external`. Accepts 0–8 chunks, each up to 12,000 characters and 48,000 text characters in total. IDs allow letters/digits and `_ . : -`, with a 120-character limit. The source limit is 240 characters. Extra fields are rejected; bad inputs return 422.

The saved trace uses `generator: "none"`, `generator_called: false`, `claims: []`, and `evidence_origin: "external"`. External scores are unused zeros, not BM25 scores. Empty external evidence abstains without provider calls. On `answer`, your application may generate using the returned `evidence`, which preserves IDs and exposes any input trimming. Provider errors return 502; never generate after a gate error. Your external generator's output is not saved or validated by this endpoint.

## Replay an existing judgment

```sh
curl -X POST http://127.0.0.1:8787/api/traces/TRACE_ID/replay \
  -H 'Content-Type: application/json' \
  -d '{"policy":{"support_threshold":0.95,"conflict_threshold":0.35}}'
```

Returns the new `action`, `original_action`, policy and `inference_calls: 0`. Does not retrieve, generate, or mutate the original trace.

## Other endpoints

| Method | Path                      | Purpose                                           |
| ------ | ------------------------- | ------------------------------------------------- |
| GET    | `/health`                 | Process health and version                        |
| GET    | `/api/config`             | Public defaults; no credentials                   |
| POST   | `/api/samples`            | Add original fictional sample knowledge           |
| POST   | `/api/samples/conflict`   | Add sample knowledge and conflicting refund draft |
| GET    | `/api/traces`             | Most recent 30 decisions                          |
| GET    | `/api/traces/{id}`        | Complete saved snapshot                           |
| GET    | `/api/traces/{id}/export` | Download JSON with evidence text                  |

The workbench accepts localhost hosts and rejects cross-origin browser writes. CLI clients need no Origin header. It has no user authentication; it is intended to bind to loopback. Exported traces include questions and source text, so inspect them before sharing.
