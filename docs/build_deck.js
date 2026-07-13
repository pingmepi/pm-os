const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.author = "Karan";
pres.title = "PM-OS — PM-led PDLC operating layer";

// ---- palette ----
const INK = "0B2430", INK2 = "12303B", LIGHT = "F4F7F6";
const TEAL = "0E7C86", MINT = "13C4A3", CORAL = "EF6461";
const AMBER = "E2A23B", GREEN = "2E9E6B";
const TEXT = "13232B", MUTED = "5C6B70", WHITE = "FFFFFF";
const HF = "Georgia", BF = "Calibri";
const W = 13.33, H = 7.5, M = 0.7;
const shadow = () => ({ type: "outer", color: "0B2430", blur: 7, offset: 3, angle: 135, opacity: 0.13 });

function footer(slide, n, dark) {
  const c = dark ? "7FA0A8" : MUTED;
  slide.addText("PM-OS", { x: M, y: H - 0.5, w: 4, h: 0.3, fontFace: BF, fontSize: 9, color: c, align: "left", margin: 0, charSpacing: 2 });
  slide.addText(`${n} / 8`, { x: W - M - 1.5, y: H - 0.5, w: 1.5, h: 0.3, fontFace: BF, fontSize: 9, color: c, align: "right", margin: 0 });
}
function kicker(slide, text) {
  slide.addText(text.toUpperCase(), { x: M, y: 0.6, w: W - 2 * M, h: 0.32, fontFace: BF, fontSize: 12, bold: true, color: TEAL, charSpacing: 3, margin: 0 });
}
function title(slide, text) {
  slide.addText(text, { x: M, y: 0.94, w: W - 2 * M, h: 0.9, fontFace: HF, fontSize: 31, bold: true, color: TEXT, margin: 0 });
}

// ============================================================ 1. TITLE
(() => {
  const s = pres.addSlide();
  s.background = { color: INK };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.18, h: H, fill: { color: MINT } });
  s.addText("PM-OS", { x: M, y: 1.95, w: 11, h: 1.3, fontFace: HF, fontSize: 72, bold: true, color: WHITE, margin: 0 });
  s.addText("A PM-led operating layer for the product development lifecycle", {
    x: M, y: 3.3, w: 10.8, h: 0.7, fontFace: BF, fontSize: 22, color: "CFE6E3", margin: 0 });
  s.addText("From the context you already have to a gated, reviewable product spec — without losing the thread.", {
    x: M, y: 4.0, w: 11.2, h: 0.6, fontFace: BF, fontSize: 15, italic: true, color: "8FB7B5", margin: 0 });
  const tags = ["Local-first", "Human-gated", "Agent-powered", "Context-aware"];
  let tx = M;
  tags.forEach(t => {
    const w = 0.25 + t.length * 0.105;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: tx, y: 5.05, w, h: 0.45, fill: { color: INK2 }, line: { color: TEAL, width: 1 }, rectRadius: 0.08 });
    s.addText(t, { x: tx, y: 5.05, w, h: 0.45, fontFace: BF, fontSize: 12, color: "CFE6E3", align: "center", valign: "middle", margin: 0 });
    tx += w + 0.25;
  });
  s.addText("Demo: RepAssist  ·  Karan  ·  PM team walkthrough", { x: M, y: H - 0.7, w: 10, h: 0.4, fontFace: BF, fontSize: 12, color: "6E9098", margin: 0 });
})();

// ============================================================ 2. PROBLEM
(() => {
  const s = pres.addSlide();
  s.background = { color: LIGHT };
  kicker(s, "Why this exists");
  title(s, "Product definition is slow, inconsistent, and ungated");
  const cards = [
    { t: "The thread breaks", d: "Research, brief, scope, PRD, design, QA live in different docs and tools. Decisions drift; nobody can trace why a requirement exists." },
    { t: "Quality is uneven", d: "Every PM writes specs differently. The output depends on who wrote it and how much time they had that week." },
    { t: "Nothing is enforced", d: "Work races ahead of approval. Design builds on an unsigned-off scope; QA tests a PRD that already changed." },
  ];
  const cw = (W - 2 * M - 2 * 0.4) / 3, ch = 3.0, cy = 2.3;
  cards.forEach((c, i) => {
    const cx = M + i * (cw + 0.4);
    s.addShape(pres.shapes.RECTANGLE, { x: cx, y: cy, w: cw, h: ch, fill: { color: WHITE }, line: { color: "E2E8E7", width: 1 }, shadow: shadow() });
    s.addShape(pres.shapes.RECTANGLE, { x: cx, y: cy, w: cw, h: 0.12, fill: { color: CORAL } });
    s.addText(c.t, { x: cx + 0.3, y: cy + 0.42, w: cw - 0.6, h: 0.6, fontFace: HF, fontSize: 19, bold: true, color: TEXT, margin: 0 });
    s.addText(c.d, { x: cx + 0.3, y: cy + 1.15, w: cw - 0.6, h: ch - 1.4, fontFace: BF, fontSize: 14, color: MUTED, margin: 0, lineSpacingMultiple: 1.15 });
  });
  s.addText("The cost: rework, slow handoffs, and — in regulated work — real compliance risk.", {
    x: M, y: cy + ch + 0.3, w: W - 2 * M, h: 0.5, fontFace: BF, fontSize: 15, italic: true, color: TEAL, margin: 0 });
  footer(s, 2);
})();

// ============================================================ 3. WHAT IT IS
(() => {
  const s = pres.addSlide();
  s.background = { color: LIGHT };
  kicker(s, "What PM-OS is");
  title(s, "A gated pipeline that turns context into approved artifacts");
  s.addText([
    { text: "Not an app. Not a doc generator. ", options: { bold: true, color: TEXT } },
    { text: "A lifecycle state machine that the PM drives and an AI agent powers.", options: { color: MUTED } },
  ], { x: M, y: 1.9, w: W - 2 * M, h: 0.5, fontFace: BF, fontSize: 16, margin: 0 });
  const pillars = [
    { n: "1", t: "A skill suite", d: "Runs inside your AI agent (Claude / Codex): /pm-new, /pm-stage-NN, /pm-approve. No service to stand up." },
    { n: "2", t: "Plain files", d: "Every stage is Markdown + YAML on your machine. Portable, diff-able, yours. Nothing locked in a tool." },
    { n: "3", t: "Human gates", d: "Each stage is a draft until you approve it. The next stage cannot run until you do." },
    { n: "4", t: "The PM decides", d: "The agent prepares and validates; you judge and approve. Nothing progresses autonomously." },
  ];
  const cw = (W - 2 * M - 3 * 0.35) / 4, ch = 3.0, cy = 2.7;
  pillars.forEach((p, i) => {
    const cx = M + i * (cw + 0.35);
    s.addShape(pres.shapes.RECTANGLE, { x: cx, y: cy, w: cw, h: ch, fill: { color: WHITE }, line: { color: "E2E8E7", width: 1 }, shadow: shadow() });
    s.addShape(pres.shapes.OVAL, { x: cx + 0.3, y: cy + 0.32, w: 0.7, h: 0.7, fill: { color: TEAL } });
    s.addText(p.n, { x: cx + 0.3, y: cy + 0.32, w: 0.7, h: 0.7, fontFace: HF, fontSize: 24, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
    s.addText(p.t, { x: cx + 0.3, y: cy + 1.2, w: cw - 0.6, h: 0.5, fontFace: HF, fontSize: 17, bold: true, color: TEXT, margin: 0 });
    s.addText(p.d, { x: cx + 0.3, y: cy + 1.75, w: cw - 0.6, h: ch - 2.0, fontFace: BF, fontSize: 12.5, color: MUTED, margin: 0, lineSpacingMultiple: 1.1 });
  });
  const stripY = cy + ch + 0.25;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y: stripY, w: W - 2 * M, h: 0.55, fill: { color: "EAF5F2" }, line: { color: MINT, width: 1 }, rectRadius: 0.06 });
  s.addText([
    { text: "Plus:  ", options: { bold: true, color: TEAL } },
    { text: "runtime-agnostic — same skills on Claude or Codex", options: { color: MUTED } },
    { text: "      ·      ", options: { color: MINT } },
    { text: "every step traceable & contract-checked", options: { color: MUTED } },
  ], { x: M + 0.35, y: stripY, w: W - 2 * M - 0.7, h: 0.55, fontFace: BF, fontSize: 13, align: "center", valign: "middle", margin: 0 });
  footer(s, 3);
})();

// ============================================================ 4. CONTEXT (NEW)
(() => {
  const s = pres.addSlide();
  s.background = { color: LIGHT };
  kicker(s, "It starts with what you already know");
  title(s, "Bring your context in — it doesn't start from a blank page");
  const colW = (W - 2 * M - 0.5) / 2, cy = 2.25, ch = 3.4;
  // Left: two ways in
  const lx = M;
  s.addShape(pres.shapes.RECTANGLE, { x: lx, y: cy, w: colW, h: ch, fill: { color: WHITE }, line: { color: "E2E8E7", width: 1 }, shadow: shadow() });
  s.addShape(pres.shapes.RECTANGLE, { x: lx, y: cy, w: 0.12, h: ch, fill: { color: TEAL } });
  s.addText("Two ways in", { x: lx + 0.4, y: cy + 0.3, w: colW - 0.7, h: 0.5, fontFace: HF, fontSize: 19, bold: true, color: TEXT, margin: 0 });
  s.addText([
    { text: "Start from one line", options: { bold: true, color: TEXT, breakLine: true } },
    { text: "A single business statement — and the pipeline builds from there.", options: { color: MUTED, breakLine: true } },
    { text: " ", options: { breakLine: true, fontSize: 6 } },
    { text: "Or import what you have", options: { bold: true, color: TEXT, breakLine: true } },
    { text: "Existing research, briefs, a PRD — PM-OS reads it and builds a gated context wiki + an understanding doc you approve, then seeds the pipeline.", options: { color: MUTED } },
  ], { x: lx + 0.4, y: cy + 0.95, w: colW - 0.7, h: ch - 1.2, fontFace: BF, fontSize: 13.5, margin: 0, lineSpacingMultiple: 1.12 });
  // Right: company overlay
  const rx = M + colW + 0.5;
  s.addShape(pres.shapes.RECTANGLE, { x: rx, y: cy, w: colW, h: ch, fill: { color: WHITE }, line: { color: "E2E8E7", width: 1 }, shadow: shadow() });
  s.addShape(pres.shapes.RECTANGLE, { x: rx, y: cy, w: 0.12, h: ch, fill: { color: MINT } });
  s.addText("A company context overlay", { x: rx + 0.4, y: cy + 0.3, w: colW - 0.7, h: 0.5, fontFace: HF, fontSize: 19, bold: true, color: TEXT, margin: 0 });
  s.addText("Your company, team, glossary, and guardrails are injected into every stage automatically — so artifacts speak your domain (HCP, MLR, Veeva) and respect your rules, without you repeating them.", {
    x: rx + 0.4, y: cy + 0.95, w: colW - 0.7, h: 1.3, fontFace: BF, fontSize: 13.5, color: MUTED, margin: 0, lineSpacingMultiple: 1.12 });
  const tags = ["company", "team", "glossary", "guardrails"];
  let tx = rx + 0.4;
  tags.forEach(t => {
    const w = 0.3 + t.length * 0.1;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: tx, y: cy + ch - 0.85, w, h: 0.4, fill: { color: "EAF5F2" }, line: { color: MINT, width: 1 }, rectRadius: 0.06 });
    s.addText(t, { x: tx, y: cy + ch - 0.85, w, h: 0.4, fontFace: BF, fontSize: 11.5, color: TEAL, align: "center", valign: "middle", margin: 0 });
    tx += w + 0.18;
  });
  s.addText([
    { text: "In production", options: { bold: true, color: TEAL } },
    { text: " the Indegene overlay is installed once into each PM's PM-OS, so it applies to every project. ", options: { color: TEAL } },
    { text: "For today's demo", options: { bold: true, color: TEAL } },
    { text: " it's scoped to just this project — nothing here touches your setup.", options: { color: TEAL } },
  ], { x: M, y: cy + ch + 0.28, w: W - 2 * M, h: 0.6, fontFace: BF, fontSize: 13, italic: true, margin: 0, lineSpacingMultiple: 1.1 });
  footer(s, 4);
})();

// ============================================================ 5. PIPELINE
(() => {
  const s = pres.addSlide();
  s.background = { color: LIGHT };
  kicker(s, "How it works");
  title(s, "Understanding first, then seven gated stages");

  const u = { w: 1.95 };
  const core = [["01","Brief"],["02","Scope"],["03","PRD"],["04","Design"],["05","Prototype"],["06","QA plan"],["07","Metrics"]];
  const gap = 0.16, n = core.length;
  const cw = (W - 2 * M - u.w - (n + 1) * gap) / n, ch = 1.5, cy = 2.45;
  // 00 understanding node
  const ux = M;
  s.addShape(pres.shapes.RECTANGLE, { x: ux, y: cy, w: u.w, h: ch, fill: { color: WHITE }, line: { color: "BFE0D6", width: 1.5 }, shadow: shadow() });
  s.addShape(pres.shapes.RECTANGLE, { x: ux, y: cy, w: u.w, h: 0.1, fill: { color: GREEN } });
  s.addText("00", { x: ux, y: cy + 0.18, w: u.w, h: 0.45, fontFace: HF, fontSize: 20, bold: true, color: TEAL, align: "center", margin: 0 });
  s.addText("Understanding", { x: ux, y: cy + 0.62, w: u.w, h: 0.35, fontFace: BF, fontSize: 12, bold: true, color: TEXT, align: "center", margin: 0 });
  s.addText("business stmt · wiki · understanding", { x: ux + 0.1, y: cy + 0.98, w: u.w - 0.2, h: 0.45, fontFace: BF, fontSize: 8.5, color: MUTED, align: "center", margin: 0 });
  s.addText("›", { x: ux + u.w, y: cy + 0.5, w: gap + 0.05, h: 0.5, fontFace: BF, fontSize: 22, bold: true, color: MUTED, align: "center", valign: "middle", margin: 0 });
  // core chips
  core.forEach((c, i) => {
    const cx = ux + u.w + gap + i * (cw + gap);
    const approved = i <= 4; // 01-05 approved, 06-07 pending
    const accent = approved ? GREEN : AMBER;
    s.addShape(pres.shapes.RECTANGLE, { x: cx, y: cy, w: cw, h: ch, fill: { color: WHITE }, line: { color: "DDE6E4", width: 1 }, shadow: shadow() });
    s.addShape(pres.shapes.RECTANGLE, { x: cx, y: cy, w: cw, h: 0.1, fill: { color: accent } });
    s.addText(c[0], { x: cx, y: cy + 0.24, w: cw, h: 0.5, fontFace: HF, fontSize: 21, bold: true, color: TEAL, align: "center", margin: 0 });
    s.addText(c[1], { x: cx + 0.02, y: cy + 0.8, w: cw - 0.04, h: 0.5, fontFace: BF, fontSize: 10.5, color: TEXT, align: "center", margin: 0 });
    if (i < n - 1) {
      const gx = cx + cw + (gap - 0.16) / 2;
      s.addText("›", { x: gx - 0.04, y: cy + 0.5, w: 0.24, h: 0.5, fontFace: BF, fontSize: 18, bold: true, color: MUTED, align: "center", valign: "middle", margin: 0 });
    }
  });
  // overlay band
  const by = cy + ch + 0.35, bw = W - 2 * M;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y: by, w: bw, h: 0.62, fill: { color: "EAF5F2" }, line: { color: MINT, width: 1 }, rectRadius: 0.06 });
  s.addText([
    { text: "Company context overlay", options: { bold: true, color: TEAL } },
    { text: "  —  company · team · glossary · guardrails, injected into every stage above", options: { color: MUTED } },
  ], { x: M + 0.3, y: by, w: bw - 0.6, h: 0.62, fontFace: BF, fontSize: 13, valign: "middle", margin: 0 });

  // legend
  const ly = by + 0.85;
  s.addShape(pres.shapes.RECTANGLE, { x: M, y: ly, w: 0.26, h: 0.26, fill: { color: GREEN } });
  s.addText("Approved in today's example (00–05)", { x: M + 0.36, y: ly - 0.02, w: 4.4, h: 0.32, fontFace: BF, fontSize: 12, color: TEXT, valign: "middle", margin: 0 });
  s.addShape(pres.shapes.RECTANGLE, { x: M + 4.9, y: ly, w: 0.26, h: 0.26, fill: { color: AMBER } });
  s.addText("Pending — generated live (06–07)", { x: M + 5.26, y: ly - 0.02, w: 4.5, h: 0.32, fontFace: BF, fontSize: 12, color: TEXT, valign: "middle", margin: 0 });
  s.addText([
    { text: "+ optional capstones: ", options: { bold: true, color: TEAL } },
    { text: "08 TRD · 09 Roadmap", options: { color: MUTED } },
  ], { x: W - M - 3.4, y: ly - 0.02, w: 3.4, h: 0.32, fontFace: BF, fontSize: 12, align: "right", valign: "middle", margin: 0 });

  s.addText("Every “›” is a gate — a human approval the agent cannot cross on its own.", {
    x: M, y: ly + 0.45, w: W - 2 * M, h: 0.35, fontFace: BF, fontSize: 13, italic: true, color: MUTED, margin: 0 });
  footer(s, 5);
})();

// ============================================================ 6. THE GATE
(() => {
  const s = pres.addSlide();
  s.background = { color: LIGHT };
  kicker(s, "The control that matters");
  title(s, "What a gate actually does");
  const items = [
    { t: "Blocks unapproved work", d: "A stage refuses to run while any upstream stage is pending, draft, or stale. Enforced by the pre-stage gate — not a guideline." },
    { t: "Detects silent edits", d: "It re-hashes upstream artifacts. Change an approved doc after the fact and it's flagged “edited” — you can't quietly rewrite history." },
    { t: "Cascades staleness", d: "Re-approve an upstream stage and every downstream stage built on it is marked “stale,” so nothing rests on an outdated decision." },
  ];
  const rh = 1.15, ry = 2.4;
  items.forEach((it, i) => {
    const y = ry + i * (rh + 0.25);
    s.addShape(pres.shapes.RECTANGLE, { x: M, y, w: W - 2 * M, h: rh, fill: { color: WHITE }, line: { color: "E2E8E7", width: 1 }, shadow: shadow() });
    s.addShape(pres.shapes.RECTANGLE, { x: M, y, w: 0.12, h: rh, fill: { color: TEAL } });
    s.addText(it.t, { x: M + 0.45, y: y + 0.18, w: 3.7, h: rh - 0.36, fontFace: HF, fontSize: 17, bold: true, color: TEXT, valign: "middle", margin: 0 });
    s.addText(it.d, { x: M + 4.4, y: y + 0.12, w: W - 2 * M - 4.7, h: rh - 0.24, fontFace: BF, fontSize: 13.5, color: MUTED, valign: "middle", margin: 0, lineSpacingMultiple: 1.1 });
  });
  s.addText("Net effect: the document set can never lie about what's been reviewed.", {
    x: M, y: 6.4, w: W - 2 * M, h: 0.4, fontFace: BF, fontSize: 15, italic: true, bold: true, color: TEAL, margin: 0 });
  footer(s, 6);
})();

// ============================================================ 7. ROADMAP
(() => {
  const s = pres.addSlide();
  s.background = { color: LIGHT };
  kicker(s, "Where it's going");
  title(s, "From product-definition kernel to full PDLC layer");
  s.addText([
    { text: "Today's demo is the kernel. ", options: { bold: true, color: TEXT } },
    { text: "The same gated, PM-led model extends across the whole lifecycle.", options: { color: MUTED } },
  ], { x: M, y: 1.9, w: W - 2 * M, h: 0.5, fontFace: BF, fontSize: 16, margin: 0 });

  const cols = [
    { t: "Shipped — today", accent: GREEN, items: [
      "Gated product definition (00–09)",
      "Company context overlay",
      "Drift, staleness & approval metrics",
      "Claude + Codex",
    ] },
    { t: "Next — deeper context", accent: TEAL, items: [
      "Multi-page, compounding context packs",
      "Codebase understanding (brownfield mode)",
      "Requirement ↔ test traceability IDs",
      "Dev-ready handoff packets",
    ] },
    { t: "Later — rest of the lifecycle", accent: AMBER, items: [
      "QA bug triage & fix guidance",
      "Release readiness",
      "Feedback → iteration loop",
      "Integrations: Jira/Linear, GitHub, Figma",
      "Gemini runtime",
    ] },
  ];
  const gx = 0.4, cw = (W - 2 * M - 2 * gx) / 3, ch = 3.5, cy = 2.55;
  cols.forEach((c, i) => {
    const cx = M + i * (cw + gx);
    s.addShape(pres.shapes.RECTANGLE, { x: cx, y: cy, w: cw, h: ch, fill: { color: WHITE }, line: { color: "E2E8E7", width: 1 }, shadow: shadow() });
    s.addShape(pres.shapes.RECTANGLE, { x: cx, y: cy, w: cw, h: 0.12, fill: { color: c.accent } });
    s.addText(c.t, { x: cx + 0.3, y: cy + 0.34, w: cw - 0.6, h: 0.5, fontFace: HF, fontSize: 16, bold: true, color: TEXT, margin: 0 });
    s.addText(
      c.items.map(it => ({ text: it, options: { bullet: { code: "2022", indent: 12 }, breakLine: true } })),
      { x: cx + 0.32, y: cy + 1.0, w: cw - 0.6, h: ch - 1.25, fontFace: BF, fontSize: 12.5, color: MUTED, margin: 0, lineSpacingMultiple: 1.18, valign: "top" }
    );
  });
  s.addText("The PM stays the decision-maker at every new stage — same gated model, wider lifecycle.", {
    x: M, y: cy + ch + 0.3, w: W - 2 * M, h: 0.45, fontFace: BF, fontSize: 14, italic: true, bold: true, color: TEAL, margin: 0 });
  footer(s, 7);
})();

// ============================================================ 8. NOW LET ME SHOW YOU
(() => {
  const s = pres.addSlide();
  s.background = { color: INK };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.18, h: H, fill: { color: MINT } });
  s.addText("NOW LET ME SHOW YOU", { x: M, y: 0.85, w: 11, h: 0.4, fontFace: BF, fontSize: 13, bold: true, color: MINT, charSpacing: 3, margin: 0 });
  s.addText("RepAssist, live", { x: M, y: 1.3, w: 11, h: 0.9, fontFace: HF, fontSize: 36, bold: true, color: WHITE, margin: 0 });
  s.addText("A field-rep companion that surfaces only MLR-approved content for a specific HCP. Built from real field research; stages 00–05 are approved. We finish it live.", {
    x: M, y: 2.25, w: 11.6, h: 0.8, fontFace: BF, fontSize: 14.5, color: "CFE6E3", margin: 0, lineSpacingMultiple: 1.15 });
  const steps = [
    ["See the thread", "pm-status — the understanding group + five approved stages, each signed off."],
    ["Show it understood my research", "Open the context wiki + understanding doc it built from the interviews."],
    ["Hit the gate", "Try to skip to stage 07 — the gate blocks it because QA isn't approved."],
    ["Do it properly", "Generate the QA plan, review, approve — then the metrics plan."],
    ["Share", "Export the whole approved thread for eng, design, and QA."],
  ];
  const ry = 3.2, rh = 0.66;
  steps.forEach((st, i) => {
    const y = ry + i * (rh + 0.05);
    s.addShape(pres.shapes.OVAL, { x: M, y: y + 0.04, w: 0.46, h: 0.46, fill: { color: TEAL } });
    s.addText(String(i + 1), { x: M, y: y + 0.04, w: 0.46, h: 0.46, fontFace: HF, fontSize: 17, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
    s.addText([
      { text: st[0] + "   ", options: { bold: true, color: WHITE } },
      { text: st[1], options: { color: "9FC1BF" } },
    ], { x: M + 0.7, y, w: 11.6, h: rh, fontFace: BF, fontSize: 13.5, valign: "middle", margin: 0 });
  });
})();

pres.writeFile({ fileName: "/Users/Karans/pm-projects/repassist/PM-OS-demo.pptx" }).then(f => console.log("wrote", f));
