const path = require("path");
const PptxGenJS = require("pptxgenjs");
const { C, FONT_H, FONT_B, W, H, M, darkSlide, contentSlide, card, pill } = require("./pptx_lib.js");

const pptx = new PptxGenJS();
pptx.defineLayout({ name: "W", width: W, height: H });
pptx.layout = "W";
pptx.author = "PM-OS";
pptx.title = "PM-OS Technical Walkthrough";

const bodyOpt = { fontFace: FONT_B, fontSize: 14, color: C.ink, lineSpacingMultiple: 1.08 };

// ---- 1. Title ----
darkSlide(pptx, {
  kicker: "Technical Walkthrough",
  title: "PM-OS",
  subtitle: "A PM-led PDLC operating layer — built as an agent skill suite, not an app. Local-first, file-based, human-gated.",
  footer: "Prepared for: Director of Product   ·   v1 shipped · Phases 2–6 planned",
});

// ---- 2. What it is + core principle ----
{
  const s = contentSlide(pptx, { num: "", title: "What PM-OS is" });
  s.addText([
    { text: "No frontend, no backend, no database. ", options: { bold: true } },
    { text: "PM-OS is a set of skills for Claude Code and OpenAI Codex plus small Python helpers. All state is plain files on the PM’s machine — Markdown, YAML, JSONL.", options: {} },
  ], { x: M, y: 1.7, w: W - 2 * M, h: 0.9, ...bodyOpt, fontSize: 15 });

  // principle band
  card(pptx, s, { x: M, y: 2.75, w: W - 2 * M, h: 1.15, fill: C.navy, line: C.navy });
  s.addText("PM decides  ·  PM-OS prepares & validates  ·  Dev & QA execute", { x: M, y: 2.82, w: W - 2 * M, h: 0.55, align: "center", valign: "middle", fontFace: FONT_H, fontSize: 22, bold: true, color: C.white });
  s.addText("No stage progresses without explicit PM approval. Nothing is autonomous.", { x: M, y: 3.4, w: W - 2 * M, h: 0.4, align: "center", fontFace: FONT_B, fontSize: 13, italic: true, color: C.ice });

  // two responsibility split cards
  const cw = (W - 2 * M - 0.4) / 2;
  card(pptx, s, { x: M, y: 4.25, w: cw, h: 2.3, accent: C.mint });
  s.addText("The generation engine", { x: M + 0.25, y: 4.45, w: cw - 0.4, h: 0.4, fontFace: FONT_H, fontSize: 16, bold: true, color: C.navy });
  s.addText([
    { text: "The agent runs the prompts.\n", options: { bold: true } },
    { text: "Each stage ships a SKILL.md with the prompt + the inline bash the agent runs. Generation and judgment live here.", options: {} },
  ], { x: M + 0.25, y: 4.9, w: cw - 0.5, h: 1.5, ...bodyOpt });

  card(pptx, s, { x: M + cw + 0.4, y: 4.25, w: cw, h: 2.3, accent: C.teal });
  s.addText("The mechanical state", { x: M + cw + 0.65, y: 4.45, w: cw - 0.4, h: 0.4, fontFace: FONT_H, fontSize: 16, bold: true, color: C.navy });
  s.addText([
    { text: "Python only does deterministic work.\n", options: { bold: true } },
    { text: "scripts / lib / hooks handle scaffold, hash, approve, gate, telemetry. No judgment in Python.", options: {} },
  ], { x: M + cw + 0.65, y: 4.9, w: cw - 0.5, h: 1.5, ...bodyOpt });
}

// ---- 3. Stage pipeline ----
{
  const s = contentSlide(pptx, { num: "", title: "The stage pipeline (v1: product definition)" });
  s.addText("Eight fixed, linear stages. Each writes one Markdown artifact, waits for review, and only proceeds after explicit approval. Later stages read approved upstream artifacts as their source of truth.", { x: M, y: 1.65, w: W - 2 * M, h: 0.7, ...bodyOpt });

  const stages = [
    ["01", "Brief"], ["02", "Scope"], ["03", "PRD"], ["04", "Design spec"],
    ["05", "Prototype brief"], ["06", "QA plan"], ["07", "Metrics plan"], ["08", "TRD*"],
  ];
  const n = stages.length;
  const gap = 0.16;
  const cw = (W - 2 * M - gap * (n - 1)) / n;
  const y = 2.7, ch = 1.5;
  stages.forEach((st, i) => {
    const x = M + i * (cw + gap);
    const isTrd = i === n - 1;
    card(pptx, s, { x, y, w: cw, h: ch, fill: isTrd ? C.iceSoft : C.white, accent: i === 2 || i === 5 || i === 7 ? C.mint : C.teal });
    s.addText(st[0], { x, y: y + 0.18, w: cw, h: 0.5, align: "center", fontFace: FONT_H, fontSize: 22, bold: true, color: C.navy });
    s.addText(st[1], { x: x + 0.05, y: y + 0.72, w: cw - 0.1, h: 0.7, align: "center", valign: "top", fontFace: FONT_B, fontSize: 11.5, color: C.slate });
  });
  s.addText("* TRD is the optional technical capstone.   Mint = deep-reasoning stages (03 PRD, 06 QA plan, 08 TRD) run on the strongest model.", { x: M, y: 4.4, w: W - 2 * M, h: 0.35, fontFace: FONT_B, fontSize: 11, italic: true, color: C.slate });

  // status legend
  s.addText("Each stage carries a status:", { x: M, y: 5.05, w: 2.6, h: 0.4, fontFace: FONT_B, fontSize: 13, bold: true, color: C.ink });
  const statuses = [["pending", C.slate], ["draft", C.plan], ["approved", C.good], ["edited", C.plan], ["stale", C.plan]];
  let lx = M + 2.9;
  statuses.forEach(([t, col]) => {
    s.addShape(pptx.ShapeType.roundRect, { x: lx, y: 5.02, w: 1.5, h: 0.42, rectRadius: 0.21, fill: { color: C.iceSoft }, line: { color: col, width: 1.5 } });
    s.addText(t, { x: lx, y: 5.02, w: 1.5, h: 0.42, align: "center", valign: "middle", fontFace: FONT_B, fontSize: 12, bold: true, color: col });
    lx += 1.65;
  });
  s.addText("On-path: pending → draft → approved.   Off-path signals: edited (body changed after approval, caught by hash drift) and stale (an upstream was re-approved).", { x: M, y: 5.7, w: W - 2 * M, h: 0.7, ...bodyOpt, fontSize: 13 });
}

// ---- 4. Gate flow ----
{
  const s = contentSlide(pptx, { num: "", title: "Where approval is enforced — the gate flow" });
  const steps = [
    ["1", "Pre-stage gate", "pre-stage.py flags any upstream that is pending / draft / stale and exits with an error the skill surfaces. It's advisory, not a hard lock — the PM can still proceed. It also re-hashes upstreams to catch post-approval edits."],
    ["2", "Approval", "pm_approve.py validates status, writes the approval to artifact frontmatter AND .meta.yaml, and logs a stage_approved telemetry event."],
    ["3", "Post-approve", "post-approve.py renders HTML companions (04/05), cascades stale to downstream approved stages, and pushes telemetry / feedback."],
  ];
  const cw = (W - 2 * M - 0.6) / 3;
  steps.forEach((st, i) => {
    const x = M + i * (cw + 0.3);
    card(pptx, s, { x, y: 1.85, w: cw, h: 3.0 });
    s.addShape(pptx.ShapeType.ellipse, { x: x + 0.3, y: 2.15, w: 0.7, h: 0.7, fill: { color: C.navy } });
    s.addText(st[0], { x: x + 0.3, y: 2.15, w: 0.7, h: 0.7, align: "center", valign: "middle", fontFace: FONT_H, fontSize: 26, bold: true, color: C.white });
    s.addText(st[1], { x: x + 0.3, y: 3.0, w: cw - 0.6, h: 0.45, fontFace: FONT_H, fontSize: 16, bold: true, color: C.navy });
    s.addText(st[2], { x: x + 0.3, y: 3.5, w: cw - 0.6, h: 1.25, ...bodyOpt, fontSize: 12.5 });
    if (i < 2) s.addText("→", { x: x + cw + 0.02, y: 1.85, w: 0.26, h: 3.0, align: "center", valign: "middle", fontFace: FONT_B, fontSize: 22, bold: true, color: C.mint });
  });
  card(pptx, s, { x: M, y: 5.15, w: W - 2 * M, h: 1.5, fill: C.iceSoft, accent: C.teal });
  s.addText([
    { text: "Cooperative enforcement: ", options: { bold: true } },
    { text: "gates are plain scripts; the skill instructs the agent to halt on a non-zero exit, and the PM keeps authority to proceed. State flows via the PM_OS_STAGE env var. Every prompt has an env-var / flag escape and a non-TTY branch, so the gates never hang when run unattended.", options: {} },
  ], { x: M + 0.3, y: 5.35, w: W - 2 * M - 0.6, h: 1.1, ...bodyOpt, fontSize: 13.5 });
}

// ---- 5. State integrity + telemetry ----
{
  const s = contentSlide(pptx, { num: "", title: "State integrity & telemetry" });
  const cw = (W - 2 * M - 0.4) / 2;
  card(pptx, s, { x: M, y: 1.8, w: cw, h: 4.6, accent: C.mint });
  s.addText("Two synchronized sources of truth", { x: M + 0.3, y: 2.05, w: cw - 0.6, h: 0.5, fontFace: FONT_H, fontSize: 18, bold: true, color: C.navy });
  s.addText([
    { text: "Stage state lives in both .meta.yaml (a stages[] list) and each artifact’s YAML frontmatter — kept in lockstep.\n\n", options: {} },
    { text: "The content hash is computed over the body only ", options: { bold: true } },
    { text: "(everything after the closing frontmatter), so editing frontmatter never triggers a false drift signal. Hash drift is what flags an ", options: {} },
    { text: "edited", options: { italic: true } },
    { text: " artifact.", options: {} },
  ], { x: M + 0.3, y: 2.65, w: cw - 0.6, h: 3.5, ...bodyOpt, fontSize: 14.5 });

  card(pptx, s, { x: M + cw + 0.4, y: 1.8, w: cw, h: 4.6, accent: C.teal });
  s.addText("Hash-chained telemetry", { x: M + cw + 0.7, y: 2.05, w: cw - 0.6, h: 0.5, fontFace: FONT_H, fontSize: 18, bold: true, color: C.navy });
  s.addText([
    { text: "Each project keeps an append-only telemetry.jsonl. Every event links to the previous one:\n", options: {} },
  ], { x: M + cw + 0.7, y: 2.65, w: cw - 0.6, h: 0.8, ...bodyOpt, fontSize: 14.5 });
  // chain motif
  const cx = M + cw + 0.7;
  s.addShape(pptx.ShapeType.roundRect, { x: cx, y: 3.6, w: cw - 0.6, h: 0.55, rectRadius: 0.08, fill: { color: C.iceSoft }, line: { color: C.rule, width: 1 } });
  s.addText("prev_event_hash  →  event_hash", { x: cx, y: 3.6, w: cw - 0.6, h: 0.55, align: "center", valign: "middle", fontFace: "Consolas", fontSize: 13, color: C.navyDeep, bold: true });
  s.addText([
    { text: "Tamper-evident, append-only history. ", options: { bold: true } },
    { text: "Telemetry calls are wrapped so a logging failure warns but never breaks the workflow.", options: {} },
  ], { x: M + cw + 0.7, y: 4.4, w: cw - 0.6, h: 1.8, ...bodyOpt, fontSize: 14.5 });
}

// ---- 6. Runtime agnosticism ----
{
  const s = contentSlide(pptx, { num: "", title: "Runtime agnosticism & model policy" });
  const rows = [
    ["Identical on Claude & Codex", "Every skill ships a SKILL.md (Claude) and an agents/openai.yaml (Codex). The installer routes skills to the right directory per runtime."],
    ["Gate parity — verified, not assumed", "Gates run as plain shell/Python from ~/.pm-os/hooks, not native hooks. A deterministic self-test runs the real gate in a throwaway project and asserts it exits non-zero on an unapproved upstream and allows the first stage."],
    ["Config-driven model choice", "lib/config.py stores default_model_tier and deep_reasoning_stages = [\"03\",\"06\",\"08\"]. Skills advise the strongest available model for those — no hardcoded provider model id."],
  ];
  let y = 1.75;
  rows.forEach((r, i) => {
    const h = 1.5;
    card(pptx, s, { x: M, y, w: W - 2 * M, h, accent: [C.mint, C.teal, C.navy][i] });
    s.addText(r[0], { x: M + 0.35, y: y + 0.18, w: 4.0, h: h - 0.3, valign: "middle", fontFace: FONT_H, fontSize: 16.5, bold: true, color: C.navy });
    s.addText(r[1], { x: M + 4.5, y: y + 0.18, w: W - 2 * M - 4.85, h: h - 0.3, valign: "middle", ...bodyOpt, fontSize: 13.5 });
    y += h + 0.2;
  });
}

// ---- 7. Current state vs roadmap ----
{
  const s = contentSlide(pptx, { num: "", title: "Current state vs. roadmap" });
  const cw = (W - 2 * M - 0.4) / 2;
  // shipped
  card(pptx, s, { x: M, y: 1.75, w: cw, h: 4.85, fill: C.goodBg, line: "BBD8C6" });
  s.addText("SHIPPED — v1 product-definition kernel", { x: M + 0.3, y: 1.95, w: cw - 0.6, h: 0.5, fontFace: FONT_B, fontSize: 14, bold: true, color: C.good, charSpacing: 1 });
  const shipped = [
    "Local scaffold from a business statement",
    "Linear 8-stage definition pipeline",
    "Human approval gates between every stage",
    "Hash drift detection + staleness cascade",
    "Hash-chained telemetry + feedback capture",
    "HTML companions (design spec & prototype)",
    "Cross-runtime install (Claude + Codex)",
    "Runtime-neutral model policy + install verifier",
  ];
  s.addText(shipped.map((t) => ({ text: t, options: { bullet: { code: "2022", indent: 14 }, color: C.ink } })),
    { x: M + 0.35, y: 2.5, w: cw - 0.65, h: 3.9, fontFace: FONT_B, fontSize: 13, lineSpacingMultiple: 1.18 });

  // roadmap
  card(pptx, s, { x: M + cw + 0.4, y: 1.75, w: cw, h: 4.85, fill: C.planBg, line: "E8D4B0" });
  s.addText("PLANNED — additive phases, not a rewrite", { x: M + cw + 0.7, y: 1.95, w: cw - 0.6, h: 0.5, fontFace: FONT_B, fontSize: 14, bold: true, color: C.plan, charSpacing: 1 });
  const planned = [
    ["2", "Flexible intake & ingest (start from a PRD/scope, not just a one-liner)"],
    ["3", "Brownfield mode + codebase understanding"],
    ["3.5", "Traceability spine — stable REQ-/TC- IDs"],
    ["4", "Dev handoff packet; opt-in tracker export"],
    ["5", "QA bug triage + fix-plan suggestions"],
    ["6", "Release-readiness report + feedback loop"],
  ];
  let y = 2.55;
  planned.forEach(([ph, t]) => {
    s.addShape(pptx.ShapeType.roundRect, { x: M + cw + 0.7, y, w: 0.62, h: 0.42, rectRadius: 0.08, fill: { color: C.plan } });
    s.addText("P" + ph, { x: M + cw + 0.7, y, w: 0.62, h: 0.42, align: "center", valign: "middle", fontFace: FONT_B, fontSize: 12, bold: true, color: C.white });
    s.addText(t, { x: M + cw + 1.45, y: y - 0.03, w: cw - 1.75, h: 0.55, valign: "middle", ...bodyOpt, fontSize: 12.5 });
    y += 0.62;
  });
}

// ---- 8. Closing ----
darkSlide(pptx, {
  kicker: "Security & data posture",
  title: "Local-first. Reference, don’t copy. PM in control.",
  subtitle: "All canonical state stays on the PM’s machine as plain files — sanitized product-planning inputs only. Future connectors are opt-in and read-before-write, storing IDs and summaries, never bulk copies; secrets stay out of artifacts and telemetry.",
  footer: "PM-OS Technical Walkthrough   ·   Companion to the PM-OS Technical Brief",
});

const out = path.join(__dirname, "..", "PM-OS-Technical-Walkthrough.pptx");
pptx.writeFile({ fileName: out }).then(() => console.log("Wrote " + out));
