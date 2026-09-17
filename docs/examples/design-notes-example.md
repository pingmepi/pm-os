# Design notes — MLR Review Queue

**Designer:** A. Rao · **Date:** 13 Aug 2026
**Figma:** [MLR Review Queue](https://www.figma.com/design/7Kq2mXvLpR8nD4sYtBcW1e/MLR-Review-Queue) · version `2891447306512334019`
**Brief:** `04-design-spec.md` (design-brief run, status `draft`)
**Design system:** Core Web Library v4.2 · Core Tokens Light/Dark

This carries what `ia.yaml` cannot: reasoning, rejected directions, and the places the
brief left room for more than one defensible answer. The machine-readable index is the
contract; this is the context behind it.

---

## Self-check against the brief

| # | Check | Result |
|---|---|---|
| 1 | Every `UJ-###` has at least one screen | **PASS** — UJ-001, UJ-002 |
| 2 | Every `US-###` maps to a screen | **PASS** — US-001, US-002 direct; US-003 via Review queue |
| 3 | Every state in `Required state inventory` exists as a frame | **PASS** — 13 of 13 |
| 4 | Every field in `Data fields per requirement` appears on a screen | **PASS** — 13 of 13 |
| 5 | `tokens.outside_system` empty | **PASS** — no literals outside the system |
| 6 | Every new component has a rationale | **PASS** — 2 new, both justified below |
| 7 | No canonical frame missing; no excluded frame load-bearing | **PASS** — 3 excluded, all non-canonical |

Two open questions are recorded in `ia.yaml` and repeated below. Neither blocks review.

## Decisions and why

**The decision controls sit below the asset preview, not beside it.** The brief's third
design principle asks that the asset be readable at length without decision controls
competing. A side rail kept the buttons permanently in view, which read as pressure to
decide before finishing. Placing them after the preview means a reviewer scrolls
through the asset to reach them — the reading is the path to the decision.

**"Return for revision" is a modal, not an inline panel.** The brief prohibits
destructive action without a comment and says a return is not reversible from this
surface. A modal makes the comment unavoidable and gives the validation error a single
obvious home. An inline panel could be scrolled away from with the comment half-typed.

**The filtered-empty state is visually distinct from the empty state.** The brief
requires this, and it matters more than it looks: an unfiltered empty queue is *good
news* (work finished), a filtered-empty queue is *a dead end* (clear the filter). They
use different illustrations and different primary actions, not just different copy.

**Both toasts live on the Review queue, not on Asset detail.** The brief says focus
returns to the queue after a decision, so that is where the reviewer is when the
outcome arrives. The failure toast does not auto-dismiss and carries the retry action
inline, because the brief requires the typed comment survive the failure path.

**`StatusPill` renders all four `review_status` values** even though the queue shows
only two, so Asset detail's decision-recorded state can reuse the same component
rather than forcing a second status treatment. See open question 2.

## Rejected directions

**Card layout for the queue** (`12:120`, excluded). Read well with six assets and badly
with sixty. The brief specifies pagination with stable position for auditability, which
a card grid undermines — position shifts as cards reflow.

**Bulk actions on the queue** (`12:168`, excluded). Drawn before I had read the
guardrails properly; the brief prohibits bulk approve and bulk return outright. Kept in
the file only so nobody redraws it. Should be deleted once this is approved.

**Inline comment on the queue row.** Would have let a reviewer return an asset without
opening it. Fast, and wrong — the brief's mental model is read-then-decide, and a
decision recorded without opening the asset would be indefensible in an audit.

## New components, in detail

**`CharacterCount`** — a composition over the library's `TextArea`, not a fork. The
brief requires a remaining count from 1,800 of 2,000, announced politely. `TextArea`'s
helper-text slot is static and not a live region, so the count would be invisible to
screen readers. Uses only library tokens and adds no new visual language. **This is
worth promoting into the library** — the constraint is not specific to this product.

**`ReadOnlyBanner`** — the decision-recorded state needs a persistent, non-dismissible
notice that the surface is audited and final. The library's `Alert` auto-dismisses and
reads as transient, which would misrepresent the state. Deliberately plainer than
`Alert`: this is a statement of fact, not a warning.

## Open questions for the PM

1. **Focus target after a decision.** The brief says focus returns to the queue list
   but not to *which* row. The decided asset leaves the queue, so I moved focus to the
   row now occupying that position. The alternative is the filter control, which is
   safer but loses the reviewer's place. Please confirm against REQ-001's audit
   expectations.

2. **Should the queue show one's own completed work?** `review_status` has four values;
   the queue only surfaces two. The brief prohibits showing *other* reviewers'
   assignments but is silent on one's own approved or returned assets. I designed them
   out entirely. Greyed-out rows would give a sense of throughput, at the cost of a
   longer worklist.

## What I left for engineering

- Animation timings and easing for the toasts and the modal — the library's motion
  tokens cover both; I have not overridden them.
- Table column widths at viewports above 1280px. Columns are proportional; `asset_title`
  takes the remaining space.
- Empty-state illustration assets — referenced from the library, not redrawn.

## What I did not do

Nothing in `ia.yaml` is invented to satisfy a check. Where the brief was ambiguous I
designed one answer and flagged it above rather than picking silently. No frame was
created that the brief did not call for, and no state in the inventory was skipped.
