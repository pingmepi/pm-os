const fs = require("fs");
const path = require("path");
const T = require("./theme.js");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, LevelFormat, HeadingLevel, BorderStyle, WidthType,
  ShadingType, TableOfContents, PageBreak, Header, Footer, PageNumber,
} = require("docx");

const CONTENT_W = 9360; // US Letter, 1" margins

// ---------- helpers ----------
const H1 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(text)] });
const H2 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(text)] });

const P = (text, opts = {}) =>
  new Paragraph({
    spacing: { after: 140, line: 276 },
    children: Array.isArray(text) ? text : [new TextRun({ text, ...opts })],
  });

const bullet = (runs, level = 0) =>
  new Paragraph({
    numbering: { reference: "bul", level },
    spacing: { after: 70, line: 268 },
    children: Array.isArray(runs) ? runs : [new TextRun(runs)],
  });

const num = (runs) =>
  new Paragraph({
    numbering: { reference: "ord", level: 0 },
    spacing: { after: 70, line: 268 },
    children: Array.isArray(runs) ? runs : [new TextRun(runs)],
  });

const b = (t) => new TextRun({ text: t, bold: true });
const code = (t) => new TextRun({ text: t, font: "Consolas", size: 20, color: T.navyDeep });
const tx = (t) => new TextRun(t);

// horizontal accent rule via paragraph border
const rule = () => new Paragraph({
  spacing: { before: 40, after: 160 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: T.teal, space: 1 } },
  children: [new TextRun("")],
});

// callout box (single-cell shaded table)
const callout = (children, fill = T.fill) =>
  new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: [CONTENT_W],
    borders: {
      top: { style: BorderStyle.SINGLE, size: 2, color: T.teal },
      bottom: { style: BorderStyle.SINGLE, size: 2, color: T.teal },
      left: { style: BorderStyle.SINGLE, size: 18, color: T.teal },
      right: { style: BorderStyle.SINGLE, size: 2, color: T.teal },
    },
    rows: [
      new TableRow({
        children: [
          new TableCell({
            width: { size: CONTENT_W, type: WidthType.DXA },
            shading: { fill, type: ShadingType.CLEAR },
            margins: { top: 120, bottom: 120, left: 200, right: 200 },
            children,
          }),
        ],
      }),
    ],
  });

// generic table builder
function makeTable(headers, rows, widths) {
  const border = { style: BorderStyle.SINGLE, size: 1, color: T.rule };
  const borders = { top: border, bottom: border, left: border, right: border };
  const headRow = new TableRow({
    tableHeader: true,
    children: headers.map((h, i) =>
      new TableCell({
        borders,
        width: { size: widths[i], type: WidthType.DXA },
        shading: { fill: T.tblHead, type: ShadingType.CLEAR },
        margins: { top: 80, bottom: 80, left: 120, right: 120 },
        children: [new Paragraph({ children: [new TextRun({ text: h, bold: true, color: T.tblHeadTx, size: 20 })] })],
      })
    ),
  });
  const bodyRows = rows.map((r, ri) =>
    new TableRow({
      children: r.map((cell, i) =>
        new TableCell({
          borders,
          width: { size: widths[i], type: WidthType.DXA },
          shading: { fill: ri % 2 === 0 ? T.tblZebra : T.tblZebra2, type: ShadingType.CLEAR },
          margins: { top: 70, bottom: 70, left: 120, right: 120 },
          children: [Array.isArray(cell) ? new Paragraph({ children: cell, spacing: { line: 252 } })
                                         : new Paragraph({ children: [new TextRun({ text: cell, size: 20 })], spacing: { line: 252 } })],
        })
      ),
    })
  );
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: widths,
    rows: [headRow, ...bodyRows],
  });
}

const tag = (text, color) => new TextRun({ text, bold: true, color, size: 20 });

// ---------- document ----------
const children = [];

// Title block
children.push(
  new Paragraph({ spacing: { before: 1200, after: 0 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 18, color: T.teal, space: 6 } },
    children: [new TextRun({ text: "PM-OS", bold: true, size: 72, color: T.navy })] }),
  new Paragraph({ spacing: { before: 160, after: 0 },
    children: [new TextRun({ text: "Technical Brief", size: 36, color: T.slate })] }),
  new Paragraph({ spacing: { before: 80, after: 0 },
    children: [new TextRun({ text: "A PM-led PDLC operating layer — architecture, state model, and roadmap", size: 24, color: T.slate, italics: true })] }),
  new Paragraph({ spacing: { before: 600 },
    children: [new TextRun({ text: "Prepared for: Director of Product · Fellow PM", size: 22, color: T.ink })] }),
  new Paragraph({ spacing: { after: 0 },
    children: [new TextRun({ text: "Status: v1 shipped (product-definition pipeline) · Phases 2–6 planned", size: 22, color: T.ink })] }),
  new Paragraph({ children: [new PageBreak()] }),
);

// TOC
children.push(
  new Paragraph({ spacing: { after: 160 }, children: [new TextRun({ text: "Contents", bold: true, size: 30, color: T.navy })] }),
  new TableOfContents("Contents", { hyperlink: true, headingStyleRange: "1-2" }),
  new Paragraph({ children: [new PageBreak()] }),
);

// 1. What PM-OS is
children.push(H1("1. What PM-OS Is"));
children.push(rule());
children.push(P("PM-OS is a local-first, PM-led operating layer for the Product Development Life Cycle (PDLC). It keeps one coherent thread from idea to ship — intake, product definition, design, dev handoff, QA, release readiness, and feedback — with the PM in control at every decision point."));
children.push(P([
  b("Why it exists. "),
  tx("Run by hand, the lifecycle is slow, uneven in quality, and easy to break: artifact quality swings by PM, product, and deadline pressure; every stage starts from a blank page; and an upstream change can silently invalidate downstream docs, with the gap surfacing late and expensive to fix. PM-OS makes the path repeatable, faster to run, and self-checking — without removing the PM’s judgment."),
]));
children.push(P([
  b("It is built as an agent skill suite, not an app. "),
  tx("There is no frontend and no backend service. PM-OS is a set of skills for Claude Code and OpenAI Codex plus small Python helpers. All project state is plain files on the PM’s own machine — Markdown artifacts, YAML metadata, and JSONL logs."),
]));
children.push(callout([
  new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: "Decision authority — the spine of the whole system", bold: true, color: T.navy, size: 24 })] }),
  bullet([b("The PM decides: "), tx("scope, trade-offs, approvals, priority, and release calls.")]),
  bullet([b("PM-OS suggests, prepares, and validates: "), tx("it drafts artifacts, checks upstream consistency, recommends next actions, and tracks lifecycle state.")]),
  bullet([b("Developers and QAs execute: "), tx("implementation and testing stay with the team.")]),
  new Paragraph({ spacing: { before: 60 }, children: [new TextRun({ text: "No stage progresses without explicit PM approval. Nothing is autonomous.", italics: true, color: T.slate })] }),
]));

// 2. Architecture
children.push(H1("2. Architecture at a Glance"));
children.push(rule());
children.push(P([
  b("The agent is the generation engine; Python only handles mechanical state. "),
  tx("Each stage ships a "), code("SKILL.md"), tx(" that contains the prompt plus the inline bash the agent runs. The Python in "),
  code("scripts/"), tx(", "), code("lib/"), tx(", and "), code("hooks/"), tx(" handles only deterministic operations — scaffold, hash, approve, gate, telemetry. Generation and judgment live in the skill; mechanical state lives in Python."),
]));
children.push(H2("Repository layout"));
children.push(makeTable(
  ["Directory", "Responsibility"],
  [
    [[code("skills/")], "Agent skills: project commands and per-stage generation prompts"],
    [[code("scripts/")], "Python wrappers for mechanical operations (new, approve, status, share, verify)"],
    [[code("lib/")], "Shared helpers: project state, hashing, config, telemetry"],
    [[code("hooks/")], "Stage gates and approval hooks (pre-stage, post-approve)"],
    [[code("templates/")], "Markdown/YAML templates for generated artifacts"],
  ],
  [2600, 6760],
));
children.push(new Paragraph({ spacing: { before: 80 } }));
children.push(callout([
  new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: "Source repo vs. running system", bold: true, color: T.navy, size: 24 })] }),
  P([tx("The repo is checked out to "), code("~/.pm-os"), tx(" (the canonical install), which is then synced to each runtime’s discovery directories — skills to "), code("~/.claude/skills"), tx(" for Claude, "), code("~/.agents/skills"), tx(" for Codex. The gate hooks always execute from "), code("~/.pm-os/hooks"), tx(" on both runtimes.")]),
], "FBF6EC"));

// 3. Stage pipeline & state machine
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(H1("3. Stage Pipeline and State Machine"));
children.push(rule());
children.push(P([
  b("v1 covers product definition: "),
  tx("a fixed, linear pipeline of eight stages. Each stage produces one Markdown artifact that a human reviews and explicitly approves before the next stage can run."),
]));
children.push(makeTable(
  ["#", "Stage", "Artifact"],
  [
    ["01", "Product brief", "01-brief.md"],
    ["02", "Scope", "02-scope.md"],
    ["03", "PRD", "03-prd.md"],
    ["04", "Design spec", "04-design-spec.md (+ HTML companion)"],
    ["05", "Prototype brief", "05-prototype-brief.md (+ lo-fi HTML mockup)"],
    ["06", "QA plan", "06-qa-plan.md"],
    ["07", "Metrics plan", "07-metrics-plan.md"],
    ["08", "TRD (optional technical capstone)", "08-trd.md"],
  ],
  [700, 4660, 4000],
));
children.push(new Paragraph({ spacing: { before: 120 } }));
children.push(H2("Stage status model"));
children.push(P("Every stage carries a status. Three are on-path; two are off-path signals that protect artifact integrity:"));
children.push(makeTable(
  ["Status", "Meaning"],
  [
    [[tag("pending", T.slate)], "Not yet generated"],
    [[tag("draft", T.plan)], "Generated, awaiting PM review"],
    [[tag("approved", T.good)], "Explicitly approved by the PM"],
    [[tag("edited", T.plan)], "Off-path: artifact body changed after approval (detected by hash drift)"],
    [[tag("stale", T.plan)], "Off-path: an upstream stage was re-approved, so this one may no longer hold"],
  ],
  [2000, 7360],
));

// 4. Gate flow
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(H1("4. Gate Flow — Where Approval Is Enforced"));
children.push(rule());
children.push(P("Approval is coordinated in three steps. State flows between them via the PM_OS_STAGE environment variable, not arguments."));
children.push(num([b("Pre-stage gate. "), tx("Before generating, a stage runs "), code("pre-stage.py"), tx(". It flags any upstream stage that is pending, draft, or stale by exiting non-zero, re-hashes upstream artifacts to catch post-approval edits (marking them "), tag("edited", T.plan), tx("), and prompts for implicit re-approval when upstreams changed.")]));
children.push(num([b("Approval. "), code("pm_approve.py"), tx(" validates status, then writes the approval to both the artifact frontmatter and "), code(".meta.yaml"), tx(", and logs a "), code("stage_approved"), tx(" telemetry event.")]));
children.push(num([b("Post-approve. "), code("post-approve.py"), tx(" renders HTML companions for stages 04/05, cascades "), tag("stale", T.plan), tx(" to downstream approved stages, and pushes telemetry/feedback.")]));
children.push(new Paragraph({ spacing: { before: 80 } }));
children.push(callout([
  new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: "The gate is advisory, not a hard lock", bold: true, color: T.navy, size: 24 })] }),
  P([tx("Enforcement is cooperative. The gates are plain scripts — there is no native hook registration that forcibly halts execution. "), code("pre-stage.py"), tx(" exits non-zero, and each stage skill instructs the agent to surface that error and stop. The PM keeps authority to proceed anyway, re-approve, or regenerate — so a stale or unapproved upstream is flagged and discouraged, not technically prevented. This is by design and consistent with the decision-authority model: PM-OS recommends and gates; the PM decides.")]),
]));
children.push(new Paragraph({ spacing: { before: 80 } }));
children.push(callout([
  P([b("Non-interactive safety. "), tx("Any code that prompts has an environment-variable / flag escape and a non-TTY branch, so the gates never hang when run unattended inside an agent. The edited-upstream prompt, for example, reads "), code("PM_OS_EDITED_UPSTREAM_CHOICE"), tx(" when there is no terminal.")]),
], "F4F6F8"));

// 5. Two sources of truth + telemetry
children.push(H1("5. State Integrity and Telemetry"));
children.push(rule());
children.push(H2("Two synchronized sources of truth"));
children.push(P([
  tx("Stage state lives in "), b("both"), tx(" "), code(".meta.yaml"), tx(" (a "), code("stages[]"), tx(" list) "), b("and"),
  tx(" each artifact’s YAML frontmatter, and the code keeps them in lockstep. The content hash is computed over the "),
  b("body only"), tx(" — everything after the closing frontmatter — so editing frontmatter never triggers a false drift signal."),
]));
children.push(H2("Telemetry"));
children.push(P([
  tx("Each project keeps a hash-chained "), code("telemetry.jsonl"), tx(": every event links to the previous one ("),
  code("prev_event_hash"), tx(" → "), code("event_hash"), tx("), giving a tamper-evident, append-only history. Telemetry calls are wrapped so a logging failure warns but never breaks the workflow."),
]));

// 6. Runtime agnosticism
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(H1("6. Runtime Agnosticism and Model Policy"));
children.push(rule());
children.push(P([
  b("PM-OS runs identically on Claude Code and OpenAI Codex. "),
  tx("Every skill ships a "), code("SKILL.md"), tx(" (Claude) and an "), code("agents/openai.yaml"), tx(" (Codex) side by side. The installer routes skills to the right directory per runtime."),
]));
children.push(P([
  b("Gate parity is verified, not assumed. "),
  tx("The gates were never Claude-native hooks — they run as plain shell/Python from "), code("~/.pm-os/hooks"), tx(", invoked by skill bash and by "), code("pm_approve.py"), tx(". A deterministic self-test runs the real gate in a throwaway project and asserts it exits non-zero on an unapproved upstream and allows the first stage. Identical behavior on both runtimes."),
]));
children.push(P([
  b("Model choice is config-driven, not hardcoded. "),
  code("lib/config.py"), tx(" stores "), code("default_model_tier"), tx(" and "), code("deep_reasoning_stages"), tx(" ("),
  code('["03","06","08"]'), tx("). Skills advise running deep-reasoning stages on the strongest available model rather than naming a specific provider model id."),
]));

// 7. Data model
children.push(H1("7. Data Model — Local-First, File-Based"));
children.push(rule());
children.push(P("PM-OS runs per-PM on the PM’s own machine. State is flat files at the project root — no server, no shared service, no central database. A generated project looks like:"));
children.push(callout([
  new Paragraph({ children: [code(".meta.yaml            stage status, approvals, config, genai_flag")] }),
  new Paragraph({ children: [code("00-business-statement.md")] }),
  new Paragraph({ children: [code("01-brief.md … 08-trd.md   numbered stage artifacts")] }),
  new Paragraph({ children: [code("04-design-spec.html / 05-prototype-mockup.html   HTML companions")] }),
  new Paragraph({ children: [code("telemetry.jsonl       hash-chained event log")] }),
  new Paragraph({ children: [code("feedback.jsonl        captured stage feedback")] }),
  new Paragraph({ children: [code(".history/             prior versions")] }),
], "F4F6F8"));
children.push(P([
  b("Schema versioning. "),
  tx("Both "), code(".meta.yaml"), tx(" and "), code("config.yaml"), tx(" carry a "), code("schema_version"),
  tx(". Planned data-model additions (traceability IDs, external-source registry, lifecycle phase) fold into this same flat-file convention with versioned migrations, so existing projects keep working."),
]));

// 8. Current state vs roadmap
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(H1("8. Current State vs. Roadmap"));
children.push(rule());
children.push(P([b("Honest framing: "), tx("v1 is a strong local-first product-definition kernel. The full PDLC vision is sequenced as additive phases around that kernel — not a rewrite.")]));
children.push(H2("Shipped today (v1)"));
children.push(makeTable(
  ["Capability", "Status"],
  [
    ["Local project scaffold from a business statement", [tag("Shipped", T.good)]],
    ["Linear 8-stage product-definition pipeline", [tag("Shipped", T.good)]],
    ["Human approval gates between every stage", [tag("Shipped", T.good)]],
    ["Hash-based drift detection + downstream staleness cascade", [tag("Shipped", T.good)]],
    ["Hash-chained telemetry + feedback capture", [tag("Shipped", T.good)]],
    ["HTML companions for design spec & prototype", [tag("Shipped", T.good)]],
    ["Cross-runtime install (Claude + Codex), verified gate parity", [tag("Shipped", T.good)]],
    ["Runtime-neutral model policy + install verifier", [tag("Shipped", T.good)]],
  ],
  [7360, 2000],
));
children.push(new Paragraph({ spacing: { before: 120 } }));
children.push(H2("Roadmap (phased)"));
children.push(makeTable(
  ["Phase", "Goal", "Status"],
  [
    ["1 · Runtime agnosticism", "Claude + Codex parity, verifier", [tag("Done", T.good)]],
    ["2 · Flexible intake & ingest", "Start from existing PRD/scope, not just a one-liner", [tag("Planned", T.plan)]],
    ["3 · Brownfield mode", "Existing-product changes + codebase understanding", [tag("Planned", T.plan)]],
    ["3.5 · Traceability spine", "Stable REQ-/TC- IDs linking requirements to tests", [tag("Planned", T.plan)]],
    ["4 · Handoff & trackers", "Dev-ready packet; opt-in Jira/Linear export", [tag("Planned", T.plan)]],
    ["5 · QA bug triage", "Classify bugs, map to requirements; fix-plan suggestions", [tag("Planned", T.plan)]],
    ["6 · Release & feedback loop", "Release-readiness report; feedback intake", [tag("Planned", T.plan)]],
  ],
  [2500, 5060, 1800],
));

// 9. Security & data posture
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(H1("9. Security and Data Posture"));
children.push(rule());
children.push(bullet([b("Local-first by design. "), tx("All canonical state stays on the PM’s machine as plain files. No backend, no shared database.")]));
children.push(bullet([b("Sanitized inputs only. "), tx("PM-OS is intended for product-planning content — not confidential customer data, PHI, PII, secrets, or credentials, unless policy explicitly allows it.")]));
children.push(bullet([b("Reference, don’t copy (future connectors). "), tx("Planned external integrations store IDs, URIs, and summaries locally — never bulk copies of external systems. Each connector is opt-in and read-before-write, with a dry-run → confirm flow.")]));
children.push(bullet([b("Secrets stay out of artifacts. "), tx("Connectors read credentials from environment / local config; secrets are never written into project files or telemetry.")]));
children.push(bullet([b("Feedback push is configurable. "), tx("Telemetry/feedback default to a public feedback repo and can be overridden to a private/org repo at setup.")]));

// 10. Key risks
children.push(H1("10. Key Risks and Mitigations"));
children.push(rule());
children.push(makeTable(
  ["Risk", "Mitigation"],
  [
    ["Becoming another competing source of truth", "Reference and consume external artifacts; do not copy blindly"],
    ["Over-automation undermining PM authority", "Recommendation-first UX with explicit approval gates"],
    ["Linear stages not matching real PDLC entry points", "Add flexible intake + artifact graph around the pipeline (Phase 2+)"],
    ["Bug/code analysis producing false confidence", "Label as suggestions, cite evidence, require dev execution & verification"],
    ["Cross-runtime behavior drift", "One source of truth + per-runtime install/gate self-test"],
  ],
  [4000, 5360],
));

// ---------- assemble ----------
const doc = new Document({
  creator: "PM-OS",
  title: "PM-OS Technical Brief",
  styles: {
    default: { document: { run: { font: T.font, size: 22, color: T.ink } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 30, bold: true, font: T.font, color: T.navy },
        paragraph: { spacing: { before: 280, after: 80 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: T.font, color: T.navyDeep },
        paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 1 } },
    ],
  },
  numbering: {
    config: [
      { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
        style: { run: { color: T.teal }, paragraph: { indent: { left: 460, hanging: 260 } } } }] },
      { reference: "ord", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 460, hanging: 260 } } } }] },
    ],
  },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    footers: {
      default: new Footer({ children: [new Paragraph({
        alignment: AlignmentType.CENTER,
        border: { top: { style: BorderStyle.SINGLE, size: 4, color: T.rule, space: 6 } },
        children: [new TextRun({ text: "PM-OS Technical Brief   ·   ", size: 16, color: T.slate }),
                   new TextRun({ children: [PageNumber.CURRENT], size: 16, color: T.slate })] })] }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  const out = path.join(__dirname, "..", "PM-OS-Technical-Brief.docx");
  fs.writeFileSync(out, buf);
  console.log("Wrote " + out);
});
