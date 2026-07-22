# RepAssist Demo — Run of Show

**Audience:** PM team · **Goal:** show what PM-OS does, end to end, on a relatable pharma example.
**Total live time:** ~10–12 min after the deck.

Everything for the demo lives in `~/pm-projects/repassist/` — the project, the deck (`PM-OS-demo.pptx`), this script, and `research-inputs/` (the "prior research" we imported).

---

## 0. Before the room (do this 10 min early)

```bash
cd ~/pm-projects/repassist
python3 ~/.pm-os/scripts/pm_status.py
```

You should see **00, 00w, 00u, 01–05 approved**, **06 a draft** (the QA plan is pre-generated), and **07 pending**. If not, stop and tell me.

> ⚠️ **Do not approve 06 before the gate beat (§4).** The gate-block "money moment" depends on 06 being un-approved. You approve it in §5, not before.

Have open and ready:
- The deck: `~/pm-projects/repassist/PM-OS-demo.pptx`
- `00-context-wiki.md` and `00-context-understanding.md` (the "it understood my research" beat)
- `03-prd.md` (the meatiest artifact) and `05-prototype-mockup.html` (open in a browser)
- `~/.pm-os/lib/text_metrics.py` (30-line Levenshtein — for the edit-distance beat in §5)
- Terminal font size up; window wide enough that the gate error doesn't wrap.
- Optional: a Figma build of the Find flow — [Play prototype](https://www.figma.com/proto/yUCRswEgBSJsAVmhQ4yFMy/RepAssist---Prototype-Screens?node-id=1-2&starting-point-node-id=1-2&scaling=scale-down) · [file](https://www.figma.com/design/yUCRswEgBSJsAVmhQ4yFMy). Covers 3 of the 8 screens in `05-prototype-brief.md` (empty → loading → results, wired with click/timeout transitions); useful if a reviewer wants a native-feeling click-through instead of the HTML mockup. Not a replacement for the approved 05 artifact.

---

## 1. Deck (you narrate) — ~5 min

Walk slides 1→8. Land these ideas:
1. Product definition today is slow, inconsistent, **ungated**.
2. PM-OS **doesn't start from a blank page** — it ingests the context you already have (slide 4) and carries your company context into every stage.
3. It turns that into **staged, reviewable artifacts**, and a human approves **every gate** (slides 5–6).
4. **Nothing moves to the next stage without you.**
5. It's early — slide 7 shows where it's going: **deeper/compounding context, codebase understanding, and the rest of the PDLC lifecycle** (handoff → QA triage → release → feedback), all under the same gated, PM-led model.

End on slide 8 ("Now let me show you") → switch to terminal.

---

## 2. Live: the example already exists — ~2 min

> "I started this the way any of you would — but not from one sentence. I had **discovery research already**: field-rep interviews, a note on our MLR/Veeva content setup, a market scan. I gave PM-OS those."

```bash
cd ~/pm-projects/repassist
python3 ~/.pm-os/scripts/pm_status.py
```

Talk over the output: the **00 understanding group** (business statement + context wiki + understanding doc) plus **01–05 approved** — each a real artifact a human signed off.

---

## 3. Live: "it understood my research" (the context beat) — ~2 min

> "Before any spec, PM-OS read my research and built a knowledge base it carries into every stage."

Open **`00-context-wiki.md`** — point at: source tags (`src_001/002/003`), confidence tiers, the locked decisions (selection-only, approved-only, Veeva, single-region pilot), and the open questions it flagged (e.g. the approval-staleness window).

Open **`00-context-understanding.md`** — "this is the human approval surface: what it understood, how much it trusts each source, and the assumptions it'll carry. I approved this before the pipeline could run."

> "And our company context — HCP, MLR, Veeva, our guardrails — is injected into every stage automatically. I scoped that overlay to just this project for the demo; normally you'd set it once."

Then open **`03-prd.md`** — show how that context shows up downstream: Veeva sync, the approval hard-gate requirement, 21 CFR Part 11 audit trail, GenAI sections. Optionally open `05-prototype-mockup.html` — "auto-rendered when I approved stage 05."

---

## 4. Live: the gate stops you (the money moment) — ~1 min

> "Watch what happens if I try to skip ahead to the metrics plan — stage 07 — while QA, stage 06, isn't approved."

```bash
PM_OS_STAGE=07 python3 ~/.pm-os/hooks/pre-stage.py
```

It **blocks**: `Cannot run stage — upstream stages are not approved: Stage 06 (qa-plan): draft`.
*(It says `draft` because the QA plan is generated but not yet approved — a draft blocks downstream work exactly like a pending stage does. That's the point.)*

> "It will not generate downstream work on top of something a human hasn't approved. Enforced, not a convention."

---

## 5. Live: approve a gate — and watch it measure your edit — ~4 min

> "So let's do it properly. The QA plan — stage 06 — is already drafted. *(Optional: regenerate it live with `/pm-stage-06-qa-plan` to show generation — it runs the gate, reads every approved upstream + the context wiki + overlay, and writes a **draft**, not an approval.)* I review it before signing off."

Open **`06-qa-plan.md`**, skim it. Then — the key beat — **make a real edit in front of the room.** For example, tighten a threshold:

> "I don't fully agree with the AI's draft. Watch — I'll change the latency target."

Edit one line (e.g. `NFT-1 — Latency P90 ≤ 3s` → `≤ 2.5s`), save. Then show the code that's about to run, then approve:

```bash
cat ~/.pm-os/lib/text_metrics.py     # 30 lines, pure-stdlib Levenshtein — no black box
```

```
/pm-approve 06
```

> "On approval, it diffs what I approved against what the AI generated — and records exactly how much I changed."

Show the populated metric:

```bash
python3 -c "import json; rows=[json.loads(l) for l in open('telemetry.jsonl')]; r=[e for e in rows if e.get('event_type')=='stage_approved' and e.get('stage')=='06'][-1]; print(json.dumps(r['payload'],indent=2))"
```

Point at: `generated_hash` ≠ `approved_hash` (the human touched it), `char_edit_distance` (how many characters), `normalized_edit_distance` (as a % of the doc), `semantic_distance` (the agent's judgment of *how meaningful*), and `time_to_approve_seconds`.

> "Cosmetic or substantive — the record knows the difference. The document set can't lie about what was reviewed *or how much it changed*."

Then finish the pipeline:

```
/pm-stage-07-metrics-plan
/pm-approve 07
```

Show the finish line:

```bash
python3 ~/.pm-os/scripts/pm_status.py
```

All core stages green. Optional close:

```
/pm-share
```

> "And I can export the whole approved thread for eng, design, and QA."

---

## 6. Optional bonus: drift detection (only if there's time + appetite)

> "One more guardrail. §5 measured an edit I made *before* approving. This is what happens if I edit something **already approved**, after the fact…"

Add a line to the body of `02-scope.md`, save, then:

```bash
python3 ~/.pm-os/scripts/pm_status.py
```

It flags the stage **edited** (hash drift) and downstream **stale** — you can't quietly change an approved decision and pretend everything downstream still holds. *(After the demo, re-approve 02 to clean up.)*

---

## Fallbacks if something stalls live

- **A stage generation hangs or looks off:** don't fight it. "In the interest of time, here's one I prepared earlier" and show the pre-built artifacts. The *concept* (context-grounded, gated, human-approved) is the point, not live latency.
- **Gate error doesn't show:** widen the terminal, re-run the `PM_OS_STAGE=07` line.
- **Edit-distance one-liner prints nothing / you forgot to edit 06:** stage 05 already has a real populated record from an earlier edit — swap `'06'` for `'05'` in the one-liner (it prints the most recent 05 approval: `char_edit_distance: 50`, `semantic_distance: 0.05`) and tell that story instead.
- **"Is this just a doc generator?":** No — the value is the *state machine* + *context*: it ingests what you already know, grounds every stage in it, and enforces gates, hash-drift, and staleness. The docs are the artifacts; the control is the system.

---

## One-liners to have in your pocket

- "It doesn't start from a blank page — it starts from the research I already did."
- "The PM decides; PM-OS prepares and enforces. Nothing ships itself."
- "Change an upstream decision and everything downstream is marked stale."
- "It doesn't just record *that* I approved — it records *how much I changed* from what the AI proposed."
- "It's all just files on my machine — Markdown, YAML, JSONL. No app, no server."
- "Our company context — HCP, MLR, Veeva, guardrails — flows into every stage automatically."
- "Same skills run on Claude or Codex — the agent is the engine, PM-OS is the lifecycle."
