"use strict";
const $ = (id) => document.getElementById(id);
const labels = {
  supported: "Supported",
  partial: "Partial",
  missing: "Missing",
  conflicting: "Conflicting",
};
const colors = {
  supported: "var(--green)",
  partial: "var(--amber)",
  missing: "var(--blue)",
  conflicting: "var(--red)",
};
const actions = {
  answer: "Ready to answer",
  retrieve_more: "More evidence needed",
  abstain: "Abstain from answering",
  review_conflict: "Conflicting evidence",
};
let activeTrace = null;
let replaySequence = 0;
let busy = false;
let replayTimer;

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}
function notice(message) {
  $("notice").textContent = message;
  $("notice").hidden = !message;
}
async function api(path, options = {}) {
  const response = await fetch(path, options);
  const body = await response.json();
  if (!response.ok)
    throw new Error(
      typeof body.detail === "string" ? body.detail : "Request failed. Check your inputs.",
    );
  return body;
}
const post = (path, body) =>
  api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
const policy = () => ({
  support_threshold: Number($("support").value) / 100,
  conflict_threshold: Number($("conflict").value) / 100,
});

async function refreshDocuments() {
  const docs = await api("/api/documents");
  $("document-count").textContent = docs.length;
  $("documents").replaceChildren();
  if (!docs.length)
    $("documents").append(el("p", "hint", "Start with samples or add your own documents."));
  docs.forEach((d) => {
    const row = el("div", "doc-row");
    row.append(el("span", "doc-icon", "▤"));
    const name = el("span", "doc-name", d.name);
    name.title = d.name;
    row.append(name);
    const remove = el("button", "delete-doc", "×");
    remove.setAttribute("aria-label", `Delete ${d.name}`);
    remove.addEventListener("click", async () => {
      try {
        await api(`/api/documents/${d.id}`, { method: "DELETE" });
        await refreshDocuments();
        notice("Document removed. Existing traces retain their original evidence excerpts.");
      } catch (e) {
        notice(e.message);
      }
    });
    row.append(remove);
    $("documents").append(row);
  });
}
async function refreshHistory() {
  const traces = await api("/api/traces");
  $("history").replaceChildren();
  if (!traces.length) $("history").append(el("p", "hint", "Your traces will appear here."));
  traces.slice(0, 6).forEach((t) => {
    const button = el("button", "history-item");
    button.title = t.question;
    button.append(el("span", `history-dot ${t.action}`), el("span", "", t.question));
    button.addEventListener("click", async () => {
      if (busy) return;
      try {
        render(await api(`/api/traces/${t.id}`));
        notice("");
      } catch (e) {
        notice(e.message);
      }
    });
    $("history").append(button);
  });
}
function render(trace) {
  activeTrace = trace;
  // A permalink to this decision in the local workbench.
  history.replaceState(null, "", "#trace=" + trace.id);
  replaySequence++;
  $("support").value = Math.round(trace.policy.support_threshold * 100);
  $("conflict").value = Math.round(trace.policy.conflict_threshold * 100);
  updateSliderLabels();
  $("replay-result").textContent = "Original policy · " + actions[trace.action];
  $("question").value = trace.question;
  $("provider").value = trace.decision.provider;
  $("generator").value = trace.generator;
  modeNote();
  $("decision-empty").hidden = true;
  $("decision-content").hidden = false;
  $("action-title").textContent = actions[trace.action];
  $("action-icon").textContent = trace.action === "answer" ? "↗" : "◎";
  $("reason").textContent = trace.reason;
  $("latency").textContent = `${Math.round(trace.timing_ms.total)} ms`;
  $("semantics").textContent = trace.decision.semantics;
  $("model-name").textContent = trace.decision.model;
  $("input-size").textContent = `${trace.decision.input_chars} input chars`;
  $("distribution").replaceChildren();
  Object.entries(labels).forEach(([key, label]) => {
    const row = el("div", "prob-row");
    const track = el("div", "prob-track");
    const fill = el("div", "prob-fill");
    const percentage = trace.decision.probabilities[key] * 100;
    fill.style.width = `${percentage}%`;
    fill.style.background = colors[key];
    track.append(fill);
    row.append(
      el("span", "prob-label", label),
      track,
      el("span", "prob-value", `${Math.round(percentage)}%`),
    );
    $("distribution").append(row);
  });
  $("evidence").replaceChildren();
  $("evidence-count").textContent = `${trace.evidence.length} excerpts`;
  trace.evidence.forEach((e, index) => {
    const card = el("article", "evidence-card");
    card.id = `evidence-${e.id}`;
    const heading = el("div", "evidence-source");
    heading.append(
      el("span", "", e.source),
      el("span", "source-chip", `SOURCE ${String(index + 1).padStart(2, "0")}`),
    );
    card.append(
      heading,
      el("p", "", e.text),
      el(
        "div",
        "evidence-id mono",
        trace.evidence_origin === "external"
          ? `External evidence · ${e.id}`
          : `BM25 ${e.score.toFixed(2)} · ${e.id}`,
      ),
    );
    $("evidence").append(card);
  });
  if (!trace.evidence.length)
    $("evidence").append(
      el("p", "empty-line", "No matching excerpts. Add relevant sources and try again."),
    );
  $("answer").replaceChildren();
  trace.claims.forEach((claim) => {
    const block = el("div", "answer-claim", claim.text),
      citations = el("div", "citations");
    claim.evidence_ids.forEach((id) => {
      const source = trace.evidence.find((e) => e.id === id);
      const a = el("a", "citation", `▤ ${source?.source || id}`);
      a.href = `#evidence-${id}`;
      citations.append(a);
    });
    block.append(citations);
    $("answer").append(block);
  });
  if (!trace.claims.length) {
    const block = el("div", "answer-state");
    block.append(
      el(
        "strong",
        "",
        trace.generation_error
          ? "Generation failed"
          : trace.generator === "none"
            ? "Decision only"
            : actions[trace.action],
      ),
      el(
        "span",
        "",
        trace.generation_error ||
          (trace.generator === "none"
            ? "No answer was generated. Use this route and the judged excerpts in your application."
            : trace.reason),
      ),
    );
    $("answer").append(block);
  }
  $("generation-badge").textContent = trace.generator_called
    ? `${trace.generator.toUpperCase()} CALLED`
    : trace.generator === "none"
      ? "DECISION ONLY"
      : trace.action === "answer"
        ? "EXCERPTS ONLY"
        : "GENERATOR SKIPPED";
  $("warnings").replaceChildren();
  trace.warnings.forEach((w) => $("warnings").append(el("p", "", w)));
  $("step-retrieve").textContent =
    trace.evidence_origin === "external"
      ? `${trace.retrieved_count} supplied excerpts`
      : `${trace.retrieved_count} candidates`;
  $("step-decide").textContent = trace.decision.provider;
  $("step-gate").textContent = trace.action.replaceAll("_", " ");
  $("step-respond").textContent = trace.generator_called
    ? trace.generator
    : trace.claims.length
      ? "Evidence excerpts"
      : "Skipped";
  $("trace-label").textContent = `Trace ${trace.id.slice(0, 8)} · saved locally`;
  $("trace-json").textContent = JSON.stringify(trace, null, 2);
  $("show-trace").disabled = false;
  $("export").href = `/api/traces/${trace.id}/export`;
  $("export").classList.remove("disabled");
  $("export").setAttribute("aria-disabled", "false");
}
function updateSliderLabels() {
  $("support-value").textContent = $("support").value + "%";
  $("conflict-value").textContent = $("conflict").value + "%";
}
function modeNote() {
  const provider = $("provider").value;
  const notes = {
    demo: "Demo uses a lexical simulation. Its scores are illustrative, not AI probabilities.",
    ollama: "Local Ollama estimates support. Its self-reported probabilities are uncalibrated.",
    openai:
      "Any OpenAI-compatible API (OpenAI, DeepSeek, vLLM, LM Studio…). Self-reported estimates are uncalibrated.",
    laya: "Uses your self-hosted Laya /v1/systemone server. Validate the checkpoint, token budget and thresholds.",
    jev: "Hosted Jev receives the question and retrieved excerpts. Configure your server-side API key first.",
  };
  $("mode-note").textContent = notes[provider];
  $("provider-badge").textContent = provider === "demo" ? "LEXICAL DEMO" : provider === "openai" ? "OPENAI-COMPATIBLE" : provider.toUpperCase();
}
function scheduleReplay() {
  updateSliderLabels();
  clearTimeout(replayTimer);
  const sequence = ++replaySequence;
  if (!activeTrace) {
    $("replay-result").textContent = "Your policy applies to the next question.";
    return;
  }
  const id = activeTrace.id;
  const nextPolicy = policy();
  replayTimer = setTimeout(async () => {
    try {
      const r = await post(`/api/traces/${id}/replay`, { policy: nextPolicy });
      if (sequence === replaySequence && activeTrace.id === id)
        $("replay-result").textContent =
          `Replay → ${actions[r.action]} · 0 model calls. Original response is unchanged.`;
    } catch (e) {
      if (sequence === replaySequence) notice(e.message);
    }
  }, 130);
}
$("support").addEventListener("input", scheduleReplay);
$("conflict").addEventListener("input", scheduleReplay);
$("provider").addEventListener("change", modeNote);
$("query-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (busy) return;
  busy = true;
  $("run").disabled = true;
  $("run").textContent = "Inspecting…";
  notice("");
  try {
    render(
      await post("/api/query", {
        question: $("question").value,
        provider: $("provider").value,
        generator: $("generator").value,
        policy: policy(),
      }),
    );
    await refreshHistory();
  } catch (e) {
    notice(e.message);
  } finally {
    busy = false;
    $("run").disabled = false;
    $("run").replaceChildren(document.createTextNode("Inspect evidence "), el("span", "", "↗"));
  }
});
$("question").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
    $("query-form").requestSubmit();
  }
});
$("load-samples").addEventListener("click", async () => {
  try {
    await post("/api/samples", {});
    await refreshDocuments();
    notice("Sample knowledge loaded. Ask a question to explore the evidence gate.");
  } catch (e) {
    notice(e.message);
  }
});
$("load-conflict").addEventListener("click", async () => {
  try {
    await post("/api/samples/conflict", {});
    await refreshDocuments();
    $("question").value = "How many days do I have to request a refund?";
    notice(
      "Conflicting policy added: 14 days vs 30 days. Inspect the evidence, then delete the draft to resolve it.",
    );
  } catch (e) {
    notice(e.message);
  }
});
$("file").addEventListener("change", async () => {
  const file = $("file").files[0];
  if (!file) return;
  try {
    if (file.size > 200000) throw new Error("File must be 200 KB or smaller.");
    const form = new FormData();
    form.append("file", file);
    await api("/api/upload", { method: "POST", body: form });
    await refreshDocuments();
    notice(`${file.name} added to your knowledge sources.`);
  } catch (e) {
    notice(e.message);
  } finally {
    $("file").value = "";
  }
});
$("show-trace").addEventListener("click", () => {
  const raw = $("raw-trace");
  raw.hidden = !raw.hidden;
  raw.open = !raw.hidden;
  if (!raw.hidden) raw.scrollIntoView({ block: "nearest" });
});
async function init() {
  try {
    const config = await api("/api/config");
    $("version").textContent = "v" + config.version;
    $("provider").value = config.provider;
    modeNote();
    config.scenarios.forEach((s) => {
      const button = el("button", "scenario", s.label);
      button.addEventListener("click", () => {
        $("question").value = s.question;
        $("question").focus();
      });
      $("scenarios").append(button);
    });
    await Promise.all([refreshDocuments(), refreshHistory()]);
    const linked = /^#trace=([0-9a-f]{32})$/.exec(location.hash);
    if (linked) render(await api(`/api/traces/${linked[1]}`));
  } catch (e) {
    notice(e.message);
  }
}
init();
