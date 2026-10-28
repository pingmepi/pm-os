const path = require("path");
const PptxGenJS = require("pptxgenjs");
const { C, FONT_H, FONT_B, W, H, M, darkSlide, contentSlide, card } = require("./pptx_lib.js");

const pptx = new PptxGenJS();
pptx.defineLayout({ name: "W", width: W, height: H });
pptx.layout = "W";
pptx.author = "PM-OS";
pptx.title = "PM-OS Business Overview";

const bodyOpt = { fontFace: FONT_B, fontSize: 15, color: C.ink, lineSpacingMultiple: 1.12 };

// ---- 1. Title ----
darkSlide(pptx, {
  kicker: "Product Overview",
  title: "PM-OS",
  subtitle: "A PM-led operating layer for the product lifecycle. One coherent thread from idea to ship — with the PM in control at every decision point.",
  footer: "Prepared for: Director of Product · BU Head",
});

// ---- 2. The problem ----
{
  const s = contentSlide(pptx, { num: "01", title: "The problem with running the lifecycle by hand" });
  s.addText("A PM drives every product through the same stages — brief, scope, PRD, design, QA, metrics. Built by hand each time, the lifecycle is slow, uneven in quality, and easy to break.", { x: M, y: 1.7, w: W - 2 * M, h: 0.95, ...bodyOpt, fontSize: 16 });

  const pains = [
    ["Inconsistent output", "Quality and consistency of artifacts swing by PM, by product, and by how close the deadline is. There’s no repeatable standard to lean on."],
    ["Slow end-to-end", "Every stage starts from a blank page. Running the full lifecycle is time-consuming, and the busywork crowds out the actual product thinking."],
    ["Costly late rework", "An upstream change quietly invalidates downstream docs. Gaps and contradictions surface late — when they’re slowest and most expensive to fix."],
  ];
  const cw = (W - 2 * M - 0.8) / 3;
  pains.forEach((p, i) => {
    const x = M + i * (cw + 0.4);
    card(pptx, s, { x, y: 3.0, w: cw, h: 3.35, accent: C.teal });
    s.addShape(pptx.ShapeType.ellipse, { x: x + 0.35, y: 3.3, w: 0.55, h: 0.55, fill: { color: C.iceSoft }, line: { color: C.teal, width: 1.5 } });
    s.addText(["≠", "↻", "✗"][i], { x: x + 0.35, y: 3.3, w: 0.55, h: 0.55, align: "center", valign: "middle", fontFace: FONT_H, fontSize: 22, bold: true, color: C.teal });
    s.addText(p[0], { x: x + 0.35, y: 4.05, w: cw - 0.7, h: 0.5, fontFace: FONT_H, fontSize: 18, bold: true, color: C.navy });
    s.addText(p[1], { x: x + 0.35, y: 4.6, w: cw - 0.7, h: 1.6, ...bodyOpt, fontSize: 13.5 });
  });
}

// ---- 3. What PM-OS is + principle (the spine) ----
{
  const s = contentSlide(pptx, { num: "02", title: "What PM-OS is" });
  s.addText([
    { text: "An operating layer that keeps one coherent thread across the product lifecycle. ", options: { bold: true } },
    { text: "It runs on the PM’s own machine — no new app to adopt, no central system, nothing leaves the PM’s control.", options: {} },
  ], { x: M, y: 1.7, w: W - 2 * M, h: 0.9, ...bodyOpt, fontSize: 16 });

  card(pptx, s, { x: M, y: 2.8, w: W - 2 * M, h: 1.25, fill: C.navy, line: C.navy });
  s.addText("PM decides  ·  PM-OS prepares & validates  ·  Dev & QA execute", { x: M, y: 2.92, w: W - 2 * M, h: 0.6, align: "center", valign: "middle", fontFace: FONT_H, fontSize: 24, bold: true, color: C.white });
  s.addText("This is the whole philosophy: PM-OS removes the busywork, never the judgment.", { x: M, y: 3.55, w: W - 2 * M, h: 0.4, align: "center", fontFace: FONT_B, fontSize: 14, italic: true, color: C.ice });

  const roles = [
    ["The PM decides", "Scope, trade-offs, approvals, priority, release calls.", C.mint],
    ["PM-OS prepares & validates", "Drafts artifacts, checks consistency, flags drift, recommends the next step.", C.teal],
    ["Dev & QA execute", "Implementation and testing stay with the team. PM-OS never replaces them.", C.navy],
  ];
  const cw = (W - 2 * M - 0.8) / 3;
  roles.forEach((r, i) => {
    const x = M + i * (cw + 0.4);
    card(pptx, s, { x, y: 4.35, w: cw, h: 2.0, accent: r[2] });
    s.addText(r[0], { x: x + 0.3, y: 4.55, w: cw - 0.6, h: 0.7, fontFace: FONT_H, fontSize: 16, bold: true, color: C.navy });
    s.addText(r[1], { x: x + 0.3, y: 5.25, w: cw - 0.6, h: 1.0, ...bodyOpt, fontSize: 13.5 });
  });
}

// ---- 4. What works today (DEMO CUE) ----
{
  const s = contentSlide(pptx, { num: "03", title: "What works today" });
  s.addText([
    { text: "Live now (v1): ", options: { bold: true, color: C.good } },
    { text: "a gated pipeline that turns a one-line idea — or the research you already have — into a reviewed set of product-definition artifacts.", options: {} },
  ], { x: M, y: 1.7, w: W - 2 * M, h: 0.7, ...bodyOpt, fontSize: 16 });

  // flow strip
  const flow = ["Your idea\nor your research", "Brief", "Scope", "PRD", "Design", "QA", "Metrics"];
  const n = flow.length;
  const gap = 0.22;
  const cw = (W - 2 * M - gap * (n - 1)) / n;
  const y = 2.55, ch = 1.0;
  flow.forEach((t, i) => {
    const x = M + i * (cw + gap);
    card(pptx, s, { x, y, w: cw, h: ch, fill: i === 0 ? C.iceSoft : C.white, accent: C.teal });
    s.addText(t, { x: x + 0.04, y, w: cw - 0.08, h: ch, align: "center", valign: "middle", fontFace: FONT_B, fontSize: i === 0 ? 11.5 : 12.5, bold: i === 0, color: C.navy });
    if (i < n - 1) s.addText("→", { x: x + cw - 0.02, y, w: gap + 0.04, h: ch, align: "center", valign: "middle", fontFace: FONT_B, fontSize: 16, bold: true, color: C.mint });
  });
  s.addText("Each step pauses for the PM’s review before the next one runs.", { x: M, y: 3.65, w: W - 2 * M, h: 0.4, align: "center", fontFace: FONT_B, fontSize: 13, italic: true, color: C.slate });

  // three proof points
  const props = [
    ["Human-gated", "Every stage pauses for the PM’s review — the PM decides when to move on."],
    ["Catches drift", "Change an approved doc and PM-OS flags what downstream may no longer hold."],
    ["Local & portable", "Plain Markdown files on the PM’s machine. Runs on Claude Code or Codex."],
  ];
  const pw = (W - 2 * M - 0.8) / 3;
  props.forEach((p, i) => {
    const x = M + i * (pw + 0.4);
    card(pptx, s, { x, y: 4.25, w: pw, h: 1.3, fill: C.iceSoft, line: C.rule });
    s.addText(p[0], { x: x + 0.25, y: 4.4, w: pw - 0.5, h: 0.4, fontFace: FONT_H, fontSize: 15, bold: true, color: C.navy });
    s.addText(p[1], { x: x + 0.25, y: 4.8, w: pw - 0.5, h: 0.7, ...bodyOpt, fontSize: 12.5 });
  });

  // demo banner
  card(pptx, s, { x: M, y: 5.8, w: W - 2 * M, h: 0.85, fill: C.navy, line: C.navy });
  s.addShape(pptx.ShapeType.ellipse, { x: M + 0.35, y: 6.0, w: 0.45, h: 0.45, fill: { color: C.mint } });
  s.addText("▶", { x: M + 0.35, y: 6.0, w: 0.45, h: 0.45, align: "center", valign: "middle", fontFace: FONT_B, fontSize: 14, color: C.navy });
  s.addText([
    { text: "Live demo:  ", options: { bold: true, color: C.white } },
    { text: "scaffold a project → generate a brief → approve → watch the next stage unlock.", options: { color: C.ice } },
  ], { x: M + 1.0, y: 5.8, w: W - 2 * M - 1.3, h: 0.85, valign: "middle", fontFace: FONT_B, fontSize: 15 });
}

// ---- 5. What a gate actually does ----
{
  const s = contentSlide(pptx, { num: "04", title: "What a gate actually does" });
  s.addText("Fast output is only worth having if it can be trusted. “Approval” here is enforced by the tool, not left to discipline.", { x: M, y: 1.6, w: W - 2 * M, h: 0.5, ...bodyOpt, fontSize: 16 });

  const gates = [
    ["Blocks unapproved work", "A stage refuses to run while anything upstream of it is still unreviewed. This is enforced, not a guideline — the PM cannot accidentally build on an unapproved decision."],
    ["Detects silent edits", "Approved documents are fingerprinted. Change one after the fact and it is flagged as edited — nobody can quietly rewrite a decision after sign-off."],
    ["Cascades staleness", "Re-approve something upstream and everything built on it is marked stale, so no downstream document rests on a decision that has since moved."],
  ];
  const rh = 1.15, ry = 2.35;
  gates.forEach((g, i) => {
    const y = ry + i * (rh + 0.22);
    card(pptx, s, { x: M, y, w: W - 2 * M, h: rh, accent: C.teal });
    s.addText(g[0], { x: M + 0.42, y, w: 3.5, h: rh, valign: "middle", fontFace: FONT_H, fontSize: 17, bold: true, color: C.navy });
    s.addText(g[1], { x: M + 4.15, y: y + 0.12, w: W - 2 * M - 4.6, h: rh - 0.24, valign: "middle", ...bodyOpt, fontSize: 13 });
  });

  card(pptx, s, { x: M, y: 6.4, w: W - 2 * M, h: 0.85, fill: C.navy, line: C.navy });
  s.addText("The net effect: the document set can never lie about what has been reviewed.",
    { x: M + 0.4, y: 6.4, w: W - 2 * M - 0.8, h: 0.85, valign: "middle", fontFace: FONT_H, fontSize: 19, bold: true, color: C.white });
}

// ---- 6. What you walk away with (assets + formats) ----
{
  const s = contentSlide(pptx, { num: "05", title: "What you walk away with" });
  s.addText("Every project leaves behind a reviewed set of artifacts — and builds up a company asset that makes the next project faster.", { x: M, y: 1.6, w: W - 2 * M, h: 0.5, ...bodyOpt, fontSize: 15 });

  // Tier 1 — the per-project artifact trail
  s.addText("PER PROJECT", { x: M, y: 2.15, w: 4, h: 0.28, fontFace: FONT_B, fontSize: 11, bold: true, color: C.slate, charSpacing: 2 });
  const assets = ["Brief", "Scope", "PRD", "Design spec\n+ HTML", "Prototype brief\n+ working HTML", "QA plan", "Metrics plan", "TRD\noptional", "Roadmap\noptional"];
  {
    const n = assets.length, gap = 0.13;
    const cw = (W - 2 * M - gap * (n - 1)) / n;
    const y = 2.5, ch = 0.92;
    assets.forEach((t, i) => {
      const x = M + i * (cw + gap);
      const later = i >= 7;
      card(pptx, s, { x, y, w: cw, h: ch, fill: later ? C.paper : C.white, accent: later ? C.plan : C.teal });
      s.addText(t, { x: x + 0.11, y, w: cw - 0.16, h: ch, align: "center", valign: "middle", fontFace: FONT_B, fontSize: 10.5, bold: true, color: C.navy, lineSpacingMultiple: 1.0 });
    });
  }
  s.addText("Plus a per-story handoff package — the PRD and QA plan carry stable requirement and test ids, so every story traces to the journey and the tests that cover it.",
    { x: M, y: 3.5, w: W - 2 * M, h: 0.35, align: "center", fontFace: FONT_B, fontSize: 12.5, italic: true, color: C.slate });

  // Tier 2 — the asset that compounds
  card(pptx, s, { x: M, y: 3.95, w: W - 2 * M, h: 1.35, fill: C.navy, line: C.navy });
  s.addText("Write your standards once. Every future product inherits them.", { x: M + 0.4, y: 4.08, w: W - 2 * M - 0.8, h: 0.5, valign: "middle", fontFace: FONT_H, fontSize: 21, bold: true, color: C.white });
  s.addText("A context layer holds your company profile, team, glossary and guardrails — plus your own format and a worked example for each stage. It is applied automatically to every project, and it gets richer with each one.",
    { x: M + 0.4, y: 4.6, w: W - 2 * M - 0.8, h: 0.6, fontFace: FONT_B, fontSize: 13.5, color: C.ice, lineSpacingMultiple: 1.1 });

  // Footer — what the PM actually touches
  const fmt = [
    ["Plain Markdown", "No proprietary format and no app to open. Every artifact is readable, editable and diffable text."],
    ["Your formats, not a vendor's", "PM-OS imposes no external framework. Your templates can extend — or entirely replace — each stage's structure."],
    ["Two surfaces", "Commands inside the agent, and a browser for the design preview and the clickable prototype. That's the whole surface area."],
  ];
  const fw = (W - 2 * M - 0.8) / 3;
  fmt.forEach((f, i) => {
    const x = M + i * (fw + 0.4);
    card(pptx, s, { x, y: 5.55, w: fw, h: 1.4, fill: C.iceSoft, line: C.rule });
    s.addText(f[0], { x: x + 0.28, y: 5.68, w: fw - 0.56, h: 0.35, fontFace: FONT_H, fontSize: 14.5, bold: true, color: C.navy });
    s.addText(f[1], { x: x + 0.28, y: 6.05, w: fw - 0.56, h: 0.8, ...bodyOpt, fontSize: 12 });
  });
}

// ---- 7. Time saved per stage ----
{
  const s = contentSlide(pptx, { num: "06", title: "What it saves — time per stage" });
  s.addText("PM hands-on time to a reviewable first draft — generate, then review. The PM-OS column is measured, not projected.", { x: M, y: 1.6, w: W - 2 * M, h: 0.45, ...bodyOpt, fontSize: 15 });

  const barX0 = 2.65, barMax = 7.45, pillX = 10.45, pillW = 1.55, barH = 0.34;
  const maxHrs = 24, scale = barMax / maxHrs;

  // column headers
  s.addText("BY HAND — ESTIMATE", { x: barX0, y: 2.15, w: 4, h: 0.3, fontFace: FONT_B, fontSize: 11, bold: true, color: C.slate, charSpacing: 2 });
  s.addText("PM-OS, MEASURED", { x: pillX - 0.3, y: 2.15, w: pillW + 0.6, h: 0.3, align: "center", fontFace: FONT_B, fontSize: 11, bold: true, color: C.teal, charSpacing: 1 });

  const stages = [
    ["Product brief", 8, "1 day", "20 min", 0.33],
    ["Scope", 8, "1 day", "15 min", 0.25],
    ["PRD", 24, "3 days", "1 hr", 1],
    ["Design spec", 16, "2 days", "40 min", 0.67],
    ["QA plan", 16, "2 days", "30 min", 0.5],
    ["Metrics plan", 8, "1 day", "20 min", 0.33],
  ];
  const y0 = 2.55, pitch = 0.485;
  stages.forEach((st, i) => {
    const [name, hrs, mLabel, pLabel, pHrs] = st;
    const ry = y0 + i * pitch;
    const mW = hrs * scale;
    const pW = Math.max(pHrs * scale, 0.09);
    s.addText(name, { x: M, y: ry - 0.02, w: 1.9, h: barH + 0.04, valign: "middle", fontFace: FONT_B, fontSize: 13, bold: true, color: C.navy });
    // manual bar
    s.addShape(pptx.ShapeType.roundRect, { x: barX0, y: ry, w: mW, h: barH, rectRadius: 0.04, fill: { color: "DCE3EB" }, line: { type: "none" } });
    // PM-OS sliver overlaid at start
    s.addShape(pptx.ShapeType.roundRect, { x: barX0, y: ry, w: pW, h: barH, rectRadius: 0.04, fill: { color: C.teal }, line: { type: "none" } });
    // manual label inside right end
    s.addText(mLabel, { x: barX0, y: ry, w: mW - 0.14, h: barH, align: "right", valign: "middle", fontFace: FONT_B, fontSize: 11.5, bold: true, color: C.navy });
    // PM-OS pill
    s.addShape(pptx.ShapeType.roundRect, { x: pillX, y: ry, w: pillW, h: barH, rectRadius: 0.17, fill: { color: C.teal } });
    s.addText(pLabel, { x: pillX, y: ry, w: pillW, h: barH, align: "center", valign: "middle", fontFace: FONT_B, fontSize: 12, bold: true, color: C.white });
  });

  // headline band
  card(pptx, s, { x: M, y: 5.55, w: W - 2 * M, h: 1.0, fill: C.navy, line: C.navy });
  s.addText([
    { text: "≈ 2 working weeks", options: { bold: true, color: C.white } },
    { text: "  of authoring  →  ", options: { color: C.ice } },
    { text: "half a day", options: { bold: true, color: C.mint } },
  ], { x: M + 0.4, y: 5.62, w: 8.4, h: 0.55, valign: "middle", fontFace: FONT_H, fontSize: 22 });
  s.addText("Measured across 7 real projects and 40+ recorded stage runs — not a projection.", { x: M + 0.4, y: 6.12, w: 8.4, h: 0.35, fontFace: FONT_B, fontSize: 13, italic: true, color: C.ice });
  s.addText([{ text: "~3 hrs", options: { bold: true, color: C.mint } }, { text: "\ntotal, PM-OS", options: { color: C.ice } }],
    { x: W - M - 2.6, y: 5.62, w: 2.2, h: 0.85, align: "right", valign: "middle", fontFace: FONT_B, fontSize: 14 });

  s.addText("PM-OS column measured from the tool's own tamper-evident event log. The by-hand column is an estimate. Both exclude stakeholder review cycles, which apply either way, and vary with product complexity.",
    { x: M, y: 6.65, w: W - 2 * M, h: 0.35, fontFace: FONT_B, fontSize: 10, italic: true, color: C.slate });
}

// ---- 8. Idea → clickable prototype ----
{
  const s = contentSlide(pptx, { num: "07", title: "Idea → clickable prototype" });
  s.addText("The most common question: how fast can I put something in front of a user? This is one real project, start to finish, on a single afternoon.", { x: M, y: 1.6, w: W - 2 * M, h: 0.5, ...bodyOpt, fontSize: 15 });

  const track = ["Import the\nresearch I had", "Brief", "Scope", "PRD", "Design\nspec", "Prototype brief\n+ working HTML"];
  {
    const n = track.length, gap = 0.28;
    const cw = (W - 2 * M - gap * (n - 1)) / n;
    const y = 2.35, ch = 1.05;
    track.forEach((t, i) => {
      const x = M + i * (cw + gap);
      const last = i === n - 1;
      card(pptx, s, { x, y, w: cw, h: ch, fill: i === 0 ? C.iceSoft : last ? C.goodBg : C.white, line: last ? "BBD8C6" : C.rule, accent: last ? C.good : C.teal });
      s.addText(t, { x: x + 0.1, y, w: cw - 0.2, h: ch, align: "center", valign: "middle", fontFace: FONT_B, fontSize: 12.5, bold: true, color: C.navy });
      if (!last) s.addText("→", { x: x + cw - 0.04, y, w: gap + 0.08, h: ch, align: "center", valign: "middle", fontFace: FONT_B, fontSize: 17, bold: true, color: C.mint });
    });
  }
  s.addText("Existing research in, working prototype out — no stage ever starts from a blank page.", { x: M, y: 3.5, w: W - 2 * M, h: 0.35, align: "center", fontFace: FONT_B, fontSize: 12.5, italic: true, color: C.slate });

  const stats = [
    ["~10 min", "of machine time", "What the tool itself spends generating the whole chain from brief to prototype."],
    ["~1.5 hrs", "to a clickable prototype", "Idea to an approved, interactive prototype — including genuine PM review at every gate."],
    ["~3 hrs", "for the full pipeline", "Everything through the technical requirements doc and the roadmap. Same afternoon."],
  ];
  const sw = (W - 2 * M - 0.8) / 3;
  stats.forEach((st, i) => {
    const x = M + i * (sw + 0.4);
    card(pptx, s, { x, y: 3.95, w: sw, h: 1.85, accent: i === 1 ? C.good : C.teal });
    s.addText(st[0], { x: x + 0.3, y: 4.1, w: sw - 0.6, h: 0.6, fontFace: FONT_H, fontSize: 30, bold: true, color: i === 1 ? C.good : C.teal });
    s.addText(st[1], { x: x + 0.3, y: 4.7, w: sw - 0.6, h: 0.35, fontFace: FONT_B, fontSize: 13.5, bold: true, color: C.navy });
    s.addText(st[2], { x: x + 0.3, y: 5.06, w: sw - 0.6, h: 0.7, ...bodyOpt, fontSize: 12 });
  });

  card(pptx, s, { x: M, y: 6.0, w: W - 2 * M, h: 0.95, fill: C.navy, line: C.navy });
  s.addText("The machine takes about ten minutes. The rest is your review — and that's the design, not the overhead.",
    { x: M + 0.4, y: 6.0, w: W - 2 * M - 0.8, h: 0.95, valign: "middle", fontFace: FONT_H, fontSize: 19, bold: true, color: C.white });
}

// ---- 9. Where it's going ----
{
  const s = contentSlide(pptx, { num: "08", title: "Where it’s going" });
  s.addText([
    { text: "v1 is the product-definition kernel. ", options: { bold: true } },
    { text: "The vision is to cover the full lifecycle — built as additive phases around that kernel, not a rewrite.", options: {} },
  ], { x: M, y: 1.7, w: W - 2 * M, h: 0.7, ...bodyOpt, fontSize: 16 });

  // lifecycle arc
  const arc = [
    ["Intake", false], ["Definition", true], ["Design", true], ["Dev handoff", false],
    ["QA & triage", false], ["Release", false], ["Feedback", false],
  ];
  const n = arc.length;
  const gap = 0.18;
  const cw = (W - 2 * M - gap * (n - 1)) / n;
  const y = 2.55, ch = 1.15;
  arc.forEach(([t, done], i) => {
    const x = M + i * (cw + gap);
    card(pptx, s, { x, y, w: cw, h: ch, fill: done ? C.goodBg : C.white, line: done ? "BBD8C6" : C.rule, accent: done ? C.good : C.plan });
    s.addText(t, { x: x + 0.04, y: y + 0.1, w: cw - 0.08, h: 0.6, align: "center", valign: "middle", fontFace: FONT_B, fontSize: 12, bold: true, color: C.navy });
    s.addText(done ? "Live" : "Planned", { x: x + 0.04, y: y + 0.72, w: cw - 0.08, h: 0.3, align: "center", fontFace: FONT_B, fontSize: 10, bold: true, color: done ? C.good : C.plan });
  });

  // value of the vision
  const vals = [
    ["Faster idea→ship", "Less time spent re-stitching context at every handoff."],
    ["More consistent", "Every product follows the same gated, reviewable path."],
    ["Lower risk", "Drift and gaps surface early — while they’re cheap to fix."],
  ];
  const vw = (W - 2 * M - 0.8) / 3;
  vals.forEach((v, i) => {
    const x = M + i * (vw + 0.4);
    card(pptx, s, { x, y: 4.25, w: vw, h: 2.1, accent: C.mint });
    s.addText(v[0], { x: x + 0.3, y: 4.5, w: vw - 0.6, h: 0.6, fontFace: FONT_H, fontSize: 17, bold: true, color: C.navy });
    s.addText(v[1], { x: x + 0.3, y: 5.15, w: vw - 0.6, h: 1.0, ...bodyOpt, fontSize: 14 });
  });
}

// ---- 10. What it takes to run ----
{
  const s = contentSlide(pptx, { num: "09", title: "What it takes to run" });
  s.addText([
    { text: "The infrastructure cost is close to zero. ", options: { bold: true } },
    { text: "There is one real decision to make, and two housekeeping items before we widen the rollout.", options: {} },
  ], { x: M, y: 1.6, w: W - 2 * M, h: 0.5, ...bodyOpt, fontSize: 16 });

  const asks = [
    ["On the laptop", C.teal, "Everything runs locally on the PM's own machine — a standard Python runtime, two small open-source libraries, and the agent tool itself.", "No server. No database. No open ports. Nothing to host."],
    ["One real decision", C.navy, "Sign-off to send product artifacts — and, when we're extending an existing product, source-code excerpts — to the agent's underlying AI provider.", "Everything else on this slide is secondary to this one approval."],
    ["Two things to move", C.plan, "The engine and the usage log currently sit on a personal repository. Both need to point at company-owned ones before we go wider.", "A configuration change on each. No rebuild, no new code."],
  ];
  const cw = (W - 2 * M - 0.8) / 3;
  asks.forEach((a, i) => {
    const x = M + i * (cw + 0.4);
    card(pptx, s, { x, y: 2.35, w: cw, h: 3.1, accent: a[1] });
    s.addText(a[0], { x: x + 0.3, y: 2.55, w: cw - 0.6, h: 0.45, fontFace: FONT_H, fontSize: 18, bold: true, color: C.navy });
    s.addText(a[2], { x: x + 0.3, y: 3.05, w: cw - 0.6, h: 1.35, ...bodyOpt, fontSize: 13 });
    s.addText(a[3], { x: x + 0.3, y: 4.5, w: cw - 0.6, h: 0.8, fontFace: FONT_B, fontSize: 12.5, bold: true, italic: true, color: a[1] });
  });

  card(pptx, s, { x: M, y: 5.65, w: W - 2 * M, h: 1.0, fill: C.navy, line: C.navy });
  s.addText([
    { text: "Later phases: ", options: { bold: true, color: C.mint } },
    { text: "connecting to the ticket tracker, the design tool and the code repositories will each need a scoped access token — requested phase by phase, as we earn the case for them.", options: { color: C.ice } },
  ], { x: M + 0.4, y: 5.65, w: W - 2 * M - 0.8, h: 1.0, valign: "middle", fontFace: FONT_B, fontSize: 14.5, lineSpacingMultiple: 1.1 });

  s.addText("Two things worth flagging openly: artifacts are stored unencrypted on the PM's disk, so pre-launch content warrants a data-classification check; and usage logging is on by design, with no per-PM opt-out.",
    { x: M, y: 6.75, w: W - 2 * M, h: 0.35, fontFace: FONT_B, fontSize: 10, italic: true, color: C.slate });
}

// ---- 11. Why it matters / the ask ----
darkSlide(pptx, {
  kicker: "Why it matters",
  title: "Faster, more consistent delivery — without taking the call out of the PM’s hands.",
  subtitle: "PM-OS is a low-risk bet: it runs locally today, adopts incrementally, and earns trust phase by phase. The decision authority never leaves the PM.",
  footer: "Discussion  ·  Live demo  ·  Companion: PM-OS Technical Brief (detailed)",
});

const out = path.join(__dirname, "..", "PM-OS-Business-Overview.pptx");
pptx.writeFile({ fileName: out }).then(() => console.log("Wrote " + out));
