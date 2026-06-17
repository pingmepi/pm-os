# PM-OS Collateral

Share materials for PM-OS. Two audiences, one shared visual identity.

| File | Audience | Use |
|---|---|---|
| `PM-OS-Business-Overview.pptx` | Director of Product (→ BU head later) | 6-slide deck for a ~30-min slot with a live demo. Slide 4 ("What works today") is the demo hand-off. |
| `PM-OS-Technical-Walkthrough.pptx` | Director of Product | 8-slide deck for a live technical walkthrough. |
| `PM-OS-Technical-Brief.docx` | Director of Product | Reference doc to read/forward async. Source of truth the decks distill from. |
| `PM-OS-Roadmap.png` | Director of Product | 16:9 slide image — upcoming phases (2–6) as additive roadmap around the shipped kernel. |
| `PM-OS-Adoption-Plan.png` | Director of Product | 16:9 slide image — staged rollout (pilot with my team → multiple PMs → gated org-wide). |

All are grounded in actual repo state: v1 (product-definition pipeline, Phase 1) shipped; Phases 2–6 framed as roadmap.

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

The two slide images are authored as SVG (`build/roadmap.svg`, `build/adoption.svg`) in the same palette and rendered to PNG with headless Chrome:

```bash
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
"$CHROME" --headless=new --disable-gpu --force-device-scale-factor=2 \
  --screenshot=PM-OS-Roadmap.png --window-size=1920,1080 "file://$PWD/build/roadmap.svg"
"$CHROME" --headless=new --disable-gpu --force-device-scale-factor=2 \
  --screenshot=PM-OS-Adoption-Plan.png --window-size=1920,1080 "file://$PWD/build/adoption.svg"
```

Edit the SVG (palette mirrors `build/theme.js`), then re-render. Output is 3840×2160 (2× of 16:9).
