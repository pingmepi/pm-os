# PM-OS Collateral

Share materials for PM-OS, for leadership and product audiences, with one shared visual identity.

| File | Audience | Use |
|---|---|---|
| `PM-OS-Business-Overview.pptx` | Director of Product · BU head | 11-slide deck for a ~30-min slot with a live demo. Slide `03` ("What works today") is the demo hand-off. Slides `06`/`07` quote figures measured from real project telemetry — re-measure before restating them. Slide `04` (gates) is the safest cut if the slot runs short. |
| `PM-OS-Technical-Walkthrough.pptx` | Director of Product | 8-slide deck for a live technical walkthrough. |
| `PM-OS-Technical-Brief.docx` | Director of Product | Reference doc to read/forward async. Source of truth the decks distill from. |
| `PM-OS-v1.5-Overview.html` / `.pdf` | Leadership · rollout audience | Single-page v1.5 overview (HTML source + printed PDF). Not produced by the `build/` generators. |

**How current each one is.** The two decks and the Technical Brief date from June 2026 (around v0.5): they list context intake, enhancement mode, traceability and dev handoff as planned, and all of those have since shipped. Regenerate them from current repo state before reusing them. The v1.5 overview is stamped v1.5.0; it predates the external designer path (v1.5.1) and the handoff release record (v1.5.6).

## Regenerating

Generators live in `build/` (Node). `build/theme.js` and `build/pptx_lib.js` hold the shared palette/typography.

```bash
cd collateral
npm install docx pptxgenjs        # one-time
node build/technical_doc.js       # → PM-OS-Technical-Brief.docx
node build/technical_deck.js      # → PM-OS-Technical-Walkthrough.pptx
node build/business_deck.js       # → PM-OS-Business-Overview.pptx
```

Edit the content arrays in each `build/*.js` script, then re-run. Palette/fonts are centralized in the two shared modules.
