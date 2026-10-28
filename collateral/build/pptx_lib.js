// Shared pptx visual system for PM-OS decks. Widescreen 13.333 x 7.5.
const C = {
  navy:    "1F3A5F",
  navyDeep:"142537",
  teal:    "0E7C7B",
  mint:    "17A2A2",  // brighter accent for dark bgs
  ice:     "D8E4F0",
  iceSoft: "EEF3F8",
  paper:   "FAFBFC",
  ink:     "1A2230",
  slate:   "5A6B7B",
  rule:    "C9D4E0",
  white:   "FFFFFF",
  good:    "1E7A46",
  goodBg:  "E2F0E8",
  plan:    "B5742A",
  planBg:  "F7EEDF",
};

const FONT_H = "Georgia";
const FONT_B = "Calibri";

const W = 13.333, H = 7.5, M = 0.62;

// ---- dark title / closing slide ----
function darkSlide(pptx, { kicker, title, subtitle, footer }) {
  const s = pptx.addSlide();
  s.background = { color: C.navy };
  // motif: thick mint bar on the left edge
  s.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 0.18, h: H, fill: { color: C.mint } });
  if (kicker) s.addText(kicker.toUpperCase(), { x: M, y: 1.5, w: 11, h: 0.4, fontFace: FONT_B, fontSize: 14, color: C.mint, bold: true, charSpacing: 3 });
  s.addText(title, { x: M, y: 1.95, w: 11.6, h: 2.2, fontFace: FONT_H, fontSize: 44, color: C.white, bold: true, lineSpacingMultiple: 1.02 });
  if (subtitle) s.addText(subtitle, { x: M, y: 4.25, w: 11.4, h: 1.4, fontFace: FONT_B, fontSize: 19, color: C.ice, lineSpacingMultiple: 1.1 });
  if (footer) s.addText(footer, { x: M, y: H - 0.7, w: 12, h: 0.4, fontFace: FONT_B, fontSize: 12, color: "9DB2C9" });
  return s;
}

// ---- light content slide w/ header ----
function contentSlide(pptx, { num, title }) {
  const s = pptx.addSlide();
  s.background = { color: C.paper };
  // header band
  if (num) s.addText(num, { x: M, y: 0.5, w: 0.9, h: 0.7, fontFace: FONT_H, fontSize: 30, color: C.mint, bold: true });
  s.addText(title, { x: num ? M + 0.85 : M, y: 0.52, w: 11.4, h: 0.8, fontFace: FONT_H, fontSize: 28, color: C.navy, bold: true, valign: "middle" });
  // thin divider via rule rectangle (NOT under-title accent — full-width hairline separating header)
  s.addShape(pptx.ShapeType.line, { x: M, y: 1.42, w: W - 2 * M, h: 0, line: { color: C.rule, width: 1 } });
  return s;
}

// ---- card ----
function card(pptx, s, { x, y, w, h, fill = C.white, line = C.rule, accent }) {
  s.addShape(pptx.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.08, fill: { color: fill }, line: { color: line, width: 1 } });
  if (accent) s.addShape(pptx.ShapeType.rect, { x, y, w: 0.09, h, fill: { color: accent } });
}

// ---- status pill ----
function pill(pptx, s, { x, y, text, kind }) {
  const bg = kind === "done" ? C.goodBg : C.planBg;
  const fg = kind === "done" ? C.good : C.plan;
  s.addShape(pptx.ShapeType.roundRect, { x, y, w: 1.05, h: 0.34, rectRadius: 0.17, fill: { color: bg }, line: { type: "none" } });
  s.addText(text, { x, y, w: 1.05, h: 0.34, align: "center", valign: "middle", fontFace: FONT_B, fontSize: 11, bold: true, color: fg });
}

module.exports = { C, FONT_H, FONT_B, W, H, M, darkSlide, contentSlide, card, pill };
