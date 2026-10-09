# Provider setup

The UI chooses a provider per question. Environment variables set startup defaults and server connections. Keys never go to browser code. There is no live-to-demo fallback.

| Provider | Decision mechanism | Where evidence goes | Meaning of scores |
| --- | --- | --- | --- |
| `demo` | Lexical rules | Local process | Illustrative simulation |
| `ollama` | JSON from a generative model | Configured Ollama server | Self-reported weights, normalized, uncalibrated |
| `openai` | JSON from any OpenAI-compatible chat model | Configured `/chat/completions` endpoint | Self-reported weights, normalized, uncalibrated |
| `laya` | Choice head over explicit labels | Configured Laya server | Mean distribution across label rotations by default; validate calibration |
| `jev` | TypeSafe hosted decision API | Configured Jev endpoint | Provider distribution; validate on your task |

## Ollama

Invalid decision JSON receives at most one schema-repair retry using the same model. The retry is recorded in `decision.usage.validation_retries` and the trace warnings. Provider connection errors are not retried or replaced with demo. Token usage fields describe the valid response, while decision timing includes any retry.

Default endpoint: `http://127.0.0.1:11434`. Default model: `qwen3.5:4b`.

```sh
ollama list
ollama serve
```

Run `ollama serve` only if the service is not already running. Pull the model only if absent. You can choose another installed model with `NOCAP_OLLAMA_MODEL`.

Requests use `/api/chat`, temperature 0, a JSON schema and explicit schema instructions. Output is validated. A single Markdown JSON fence is accepted; prose with a JSON fragment is rejected. Decision weights must contain all four finite values between 0 and 1 and at least one positive value. They are normalized to sum to one; **original weights remain in `decision.raw_probabilities`**. Normalization does not calibrate them.

Some Ollama / Qwen versions have reported structured-output issues with disabled thinking ([upstream report](https://github.com/ollama/ollama/issues/14645)). NoCap validates actual responses rather than assuming `format` was enforced. Malformed outputs produce visible errors. Generation validates every claimed citation ID against the evidence sent to the model; it does not establish semantic entailment.

## OpenAI-compatible APIs

One provider covers OpenAI, DeepSeek, Qwen (DashScope), Moonshot, Zhipu, OpenRouter, Groq, Together, and local servers such as vLLM, LM Studio, llama.cpp `llama-server` and SGLang. It is used both as a judge (`provider: "openai"`) and as an answer generator (`generator: "openai"`).

```dotenv
NOCAP_OPENAI_URL=https://api.deepseek.com/v1
NOCAP_OPENAI_MODEL=deepseek-chat
NOCAP_OPENAI_API_KEY=sk-...
```

| Service | `NOCAP_OPENAI_URL` |
| --- | --- |
| OpenAI | `https://api.openai.com/v1` |
| DeepSeek | `https://api.deepseek.com/v1` |
| Qwen / DashScope | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| OpenRouter | `https://openrouter.ai/api/v1` |
| LM Studio | `http://127.0.0.1:1234/v1` |
| vLLM | `http://127.0.0.1:8000/v1` |
| Ollama's OpenAI endpoint | `http://127.0.0.1:11434/v1` |

Local servers usually need no key; leave `NOCAP_OPENAI_API_KEY` empty and no `Authorization` header is sent. Requests use `temperature: 0` and `response_format: {"type": "json_object"}` (JSON mode), which is more widely supported than strict JSON schema. The expected shape is included in the system prompt and every response is validated exactly like Ollama output, including one disclosed schema-repair retry. If your server rejects `response_format`, use a model or server version with JSON mode.

The API key stays in the server process; the browser never receives it. Hosted APIs receive the question and judged excerpts.

## Laya

Primary upstream: [NandhaKishorM/laya](https://github.com/NandhaKishorM/laya). Install `laya[serve]` in a suitable environment, then use `laya-serve`.

For a CPU-only setup without changing the core project's lockfile:

```sh
uv venv .laya-venv --python 3.12
uv pip install --python .laya-venv/Scripts/python.exe "laya[serve]" --torch-backend cpu
```

The interpreter path above is for Windows. On macOS / Linux use `.laya-venv/bin/python`. Alternatively, `uv sync --extra laya` installs the project's optional extra with platform-default torch wheels. Do not run `uv sync` without the extra while using that same environment for Laya: uv may remove optional packages.

PowerShell:

```powershell
$env:LAYA_HOST="127.0.0.1"
$env:LAYA_PORT="8123"
$env:LAYA_MODELS="english"
$env:LAYA_DEVICE="cpu"
$env:LAYA_THREADS="4"
$env:LAYA_MAX_LOADED="1"
.\.laya-venv\Scripts\laya-serve.exe
```

macOS / Linux:

```sh
LAYA_HOST=127.0.0.1 LAYA_PORT=8123 LAYA_MODELS=english LAYA_DEVICE=cpu LAYA_THREADS=4 .laya-venv/bin/laya-serve
```

For multilingual evidence, use `LAYA_MODELS=multilingual` and `NOCAP_LAYA_MODEL=multilingual`. For supported GPUs, choose the appropriate PyTorch backend and follow upstream hardware instructions. First load needs Hugging Face network access. `HF_HOME` can select a cache directory.

Set `.env`:

```dotenv
NOCAP_PROVIDER=laya
NOCAP_LAYA_URL=http://127.0.0.1:8123
NOCAP_LAYA_MODEL=english
NOCAP_LAYA_STATE_CHARS=1600
NOCAP_LAYA_BALANCE_OPTIONS=true
```

The character budget limits submitted excerpts; it is **not a token-count guarantee**. Upstream checkpoint limits can truncate the state again. Inspect the trace, use an appropriate checkpoint, and test the specific question schema. Only judged excerpts reach the generator.

Balanced mode sends four questions named `coverage_0` to `coverage_3`, with cyclic `option_order` permutations. Every label appears once in every position; the four validated distributions are averaged. The exact question schema is saved in the trace. This addresses one documented order effect; wording bias, context loss and calibration remain. Disable it with `NOCAP_LAYA_BALANCE_OPTIONS=false` for a single ordinary question or older servers lacking `option_order`.

Upstream describes option-order sensitivity and checkpoint-specific limits in its [README](https://github.com/NandhaKishorM/laya). We use the probability of the named outcome, not the provider's differently defined `confidence` field.

## Hosted Jev

[Official API reference](https://docs.typesafe.ai/api).

```dotenv
NOCAP_JEV_URL=https://api.typesafe.ai
NOCAP_JEV_MODEL=jev-latest
NOCAP_JEV_API_KEY=your-key
```

The server sends a `choice` question to `/v1/systemone`. This sends your question and evidence to the hosted endpoint and uses your API account. No key is included in traces or browser config. Never commit `.env`.

## Docker

`docker compose up --build` publishes only `127.0.0.1:8787` and stores SQLite in a named volume. The image does not include model weights or torch. It connects to host Ollama and Laya using `host.docker.internal`.

Docker's ability to reach a host service depends on the platform and the model server's bind address. If it cannot reach a loopback-only model server, use the native Python application, or deliberately configure a bind address reachable from Docker and restrict access with your firewall. Do not expose this single-user application publicly.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Provider error | Server is running; model installed; URL / key matches; response schema valid |
| Laya first startup stalls | Hugging Face access and available cache disk space |
| Laya rejects balanced questions | Upgrade Laya or disable `NOCAP_LAYA_BALANCE_OPTIONS` |
| Sources omitted | Provider character budget and retrieval rank; inspect `input_state` |
| Wrong decision | Model, checkpoint, schema wording, token budget and labelled evaluation |
| Ollama refuses to answer | Selected threshold, evidence completeness and actual normalized weights |
| Deleted source in an old export | Traces are snapshots; deleting a document does not redact past traces |
