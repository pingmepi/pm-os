---
stage: 04-design-spec
project: mlr-review-queue
status: draft
approved_at: null
approved_by: null
content_hash: null
generated_hash: 8f3c1a9e2b7d4506
pm_os_version: 1.5.0
genai_flag: false
artifact_contract_version: 7
generation_notes:
  - "BRIEF-ONLY run: design authority is external. Do not declare SCR-### screens, components or tokens."
---

# Design Spec: MLR Review Queue

> **This is a design brief, not a finished design spec.** Information architecture,
> screens, components and tokens are owned by design and are pending external input —
> see `design-in/ia.yaml`. The sections that *are* written below are binding
> constraints, not suggestions.

## Information Architecture

_Pending external design input — see design-in/ia.yaml._

## Journey-to-Flow Traceability

_Pending external design input — see design-in/ia.yaml._

## Key User Flows

_Pending external design input — see design-in/ia.yaml._

## Input Behavior Reconciliation

Carried forward from the PRD's `## Edge Cases` and per-story edge cases. Each row is
a required behaviour, not a suggested one.

| Condition | Required response | Copy / hint | Focus behaviour |
|---|---|---|---|
| Return submitted with empty comment (FR-002) | Block submission; inline error on the comment field | "A reason is required when returning an asset." | Focus moves to the comment field, error announced |
| Comment exceeds 2,000 characters | Block submission; show remaining count from 1,800 onward | "2,000 character limit." | Focus stays in field, count is announced politely |
| Queue has no assigned assets (FR-001) | Empty state, not a zero-row table | "Nothing assigned to you right now." | Focus lands on the filter control |
| Reviewer opens an asset assigned to someone else (REQ-001) | Permission-denied state; no partial content | "This asset is assigned to another reviewer." | Focus on the back-to-queue action |
| Due-date filter returns nothing (FR-003) | Filtered-empty state, distinct from the unfiltered empty state | "No assets match this filter." Offer clearing it. | Focus stays on the filter |
| Decision saved (FR-002) | Confirmation the reviewer cannot miss; queue reflects the change | "Returned to originator." | Focus returns to the queue list |
| Save fails on the network | Recoverable error; the comment is never lost | "Couldn't save. Your comment is kept — try again." | Focus on retry |

**Discoverability:** every input needs a visible label or persistent helper text. The
due-date filter and the comment field must not rely on placeholder text alone — a
placeholder disappears on focus and is not read reliably by screen readers.

### Required state inventory

**This is the work order.** Every state below must exist as its own designed frame or
component variant. A state that is not listed here will not be designed; a state that
is listed and not delivered is a gap at the verification gate. Transient states count —
a developer must be able to open the exact frame rather than reconstruct the
interaction that produces it.

| # | Serves | State | Trigger |
|---|---|---|---|
| 1 | US-001, FR-001 | Queue — default | Reviewer lands with assets assigned |
| 2 | US-001, FR-001 | Queue — loading | Initial fetch |
| 3 | US-001, FR-001 | Queue — empty | No assets assigned |
| 4 | US-003, FR-003 | Queue — filtered empty | Filter matches nothing |
| 5 | US-003, FR-003 | Queue — filter applied | Due-date filter active |
| 6 | US-001 | Asset detail — default | Reviewer opens an assigned asset |
| 7 | US-001, REQ-001 | Asset detail — permission denied | Asset assigned to another reviewer |
| 8 | US-002, FR-002 | Return dialog — default | Reviewer chooses "Return for revision" |
| 9 | US-002, FR-002 | Return dialog — validation error | Submit attempted with empty comment |
| 10 | US-002, FR-002 | Return dialog — submitting | Submit in flight |
| 11 | US-002, FR-002 | **Toast — returned to originator** | Return succeeds |
| 12 | US-002 | **Toast — save failed, retry** | Return fails on the network |
| 13 | US-001, US-002 | Asset detail — decision recorded | Any decision saved; asset is read-only |

### Data fields per requirement

Every field below must appear on at least one screen. This is the checklist the
returned design is reconciled against.

**US-001 — Review an assigned asset**

| Field | Type | Mandatory |
|---|---|---|
| asset_id | string | yes |
| asset_title | string | yes |
| material_type | enum | yes |
| submitted_by | string | yes |
| due_date | date | yes |
| review_status | enum | yes |
| asset_preview | file reference | yes |

**US-002 — Return an asset with required changes**

| Field | Type | Mandatory |
|---|---|---|
| decision | enum (approve, return) | yes |
| reviewer_comment | text (≤2000) | yes when decision = return |
| decided_at | timestamp | system-set |
| decided_by | string | system-set |

**US-003 — Filter the queue by due date**

| Field | Type | Mandatory |
|---|---|---|
| due_before | date | no |
| due_after | date | no |

## Product UX Guardrails

**Interaction model: non-AI.** This product retrieves, displays and records human
decisions. Nothing is generated, summarised or suggested by a model. Do not introduce
confidence indicators, AI-authored comment drafts, streaming output, or any surface
implying automated judgment.

**Product mental model.** A reviewer works a queue of assets assigned to them. They
open one, read it, and record a decision. The decision is final and audited. The queue
is a worklist, not an inbox — it is not browsable beyond one's own assignments.

**Approved vocabulary.** Use *asset* (not document, item, or file), *reviewer* (not
approver or user), *return for revision* (not reject, decline, or fail), *originator*
(not submitter or author), *decision* (not action, verdict, or outcome).

**Prohibited patterns.**
- No bulk approve or bulk return. Every decision is per-asset and deliberate.
- No optimistic UI on a decision — the reviewer must see the recorded outcome, not an
  assumed one. Decisions are audited (REQ-001) and cannot appear to succeed and then
  silently fail.
- No destructive action without a comment. A return is not reversible from this surface.
- No infinite scroll on the queue; pagination keeps position stable and auditable.
- Do not surface other reviewers' assignments, even greyed out.

**Screens, overlays and states.** A screen is a navigable surface with its own entry
point. An overlay is modal and returns to its parent. A state is a condition of a
screen or overlay and never gets its own entry point — the loading, empty and error
conditions above belong to their owning surface.

## Design Principles

1. **The decision is the product.** Everything else is context for it. The recorded
   decision and its comment must be the most legible thing on screen after the asset.
2. **No ambiguity about what was saved.** Audited work demands that state be visible,
   not inferred.
3. **Read before decide.** The asset must be readable at length without the decision
   controls competing for attention.
4. **Recover without loss.** A reviewer's typed comment survives every failure path.
5. **Build on the system.** Reuse before extension; a new component is a decision with
   a written reason.

## Component Inventory

_Pending external design input — see design-in/ia.yaml._

## Responsive & Platform Behavior

Desktop web only, ≥1280px, landscape, mouse and keyboard. Reviewers work at a desk
against a queue; there is no mobile or tablet target for this release. Do not design
a small-viewport variant. Assume corporate network latency but not offline use.

## UX Content Rules

- Use the approved vocabulary above for every label, button, heading and message.
- Buttons name the action taken: **Approve**, **Return for revision**, **Save comment**.
  Never *Submit*, *OK*, or *Confirm*.
- Status language matches the PRD's `review_status` enum exactly: *Pending review*,
  *In review*, *Approved*, *Returned for revision*. Do not invent intermediate labels.
- Errors state what happened and what to do, in that order. No apologies, no "oops",
  no error codes shown to the reviewer.
- Dates render as `DD Mmm YYYY`. Relative dates ("in 2 days") may appear alongside but
  never replace the absolute date — this is audited work.

## Typography

_Pending external design input — cite the existing design system; see design-in/ia.yaml._

## Color Tokens

_Pending external design input — cite the existing design system; see design-in/ia.yaml._

## Spacing Tokens

_Pending external design input — cite the existing design system; see design-in/ia.yaml._

## Iconography

_Pending external design input — cite the existing design system; see design-in/ia.yaml._

## Accessibility Notes

Target WCAG 2.2 AA. These are acceptance conditions, not aspirations.

- **Keyboard:** every flow completable without a mouse, including opening an asset,
  entering a comment, and submitting a decision. The return dialog traps focus and
  closes on Escape, returning focus to the control that opened it.
- **Focus order:** follows visual order. On the queue, order is filter → table →
  pagination. Focus is never lost after a state change; each row in the state
  inventory names where focus lands.
- **Labels:** every input has a programmatic label. Placeholder text is never the only
  label. Icon-only controls carry an accessible name.
- **Contrast:** 4.5:1 for text, 3:1 for UI boundaries and focus indicators, sourced
  from design-system tokens rather than one-off values.
- **Error messaging:** programmatically associated with its field, announced on
  occurrence, and never conveyed by colour alone. `review_status` must be
  distinguishable without colour.
- **Toasts:** announced via a live region. The success toast is polite; the failure
  toast is assertive and does not auto-dismiss before the reviewer can act.
- **Targets:** minimum 24×24px with adequate spacing.
- **Screen reader:** the queue is a real table with row and column headers. Row count
  and applied filters are announced when the queue updates.

---

_Design brief ends. Information architecture, screens, components and tokens arrive
from design via `design-in/ia.yaml`, are reconciled against this brief and the
approved PRD, and are then written into this same artefact before approval._
