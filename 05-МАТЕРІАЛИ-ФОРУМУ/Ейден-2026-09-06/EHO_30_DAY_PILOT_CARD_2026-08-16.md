# EHO 30-Day Pilot Card 2026-08-16

status: LOCAL_DRAFT_NO_EXTERNAL_USE
owner: Eiden
content_authority: Lumial
queue: RESOURCE / B0.1 / EHO_30_DAY_PILOT_DEFINITION
scope_boundary: EHO for enterprises only; not Hromada Intelligence, not YSU/Hromada, not YSU/LFU

## 1. Causal question

Який найраніший безпечний незавершений крок зараз дасть нову здатність,
зменшить attention tax і наблизить перший оплачуваний пілот без зовнішніх дій?

Відповідь цього інкременту: зібрати одну локальну pilot card для найнижчого
ризику входу `SYNTONIA EXO`, щоб buyer/problem/outcome, межа MVP і вимоги до
партнера більше не були розсипаними між планом і forum draft.

## 2. Facts, inferences, unknowns

### Facts from canonical local sources

- Integrated plan keeps active RESOURCE milestone `B0.1 / EHO_30_DAY_PILOT_DEFINITION`
  with required outputs: one use case, buyer/user/outcome/metric, MVP boundary,
  one-pager/demo, and follow-up preparation.
- Forum demo contract already separates three arenas and marks `SYNTONIA EXO`
  as the enterprise line, not YSU/Hromada and not LFU.
- Forum draft names the initial audience for `SYNTONIA EXO` as `director and team
  of a municipal enterprise`.
- Forum draft names `communication module` as the current low-risk candidate
  entry because it is faster to show, does not require immediate access to
  critical enterprise systems, has lower data risk, and lets the director see
  effect in the daily work cycle.
- Forum draft explicitly forbids inventing price, pilot scope, or integrations
  without Lumial's decision and threat modeling.

### Bounded inferences used in this card

- If the safest initial surface is a communication module, the first pilot
  should target one narrow inbound-to-decision workflow rather than whole-enterprise
  automation.
- A 30-day pilot can stay local and manual-first if it proves that one daily
  coordination loop becomes clearer, faster, and less lossy before any system
  integration.

### Unknowns that remain open

- Exact enterprise vertical and exact municipal enterprise partner.
- Real pain ranking between communications, task coordination, incident intake,
  approvals, and reporting.
- Allowed data classes, channel inventory, and whether the partner can supply a
  low-risk historical sample.
- Price, commercial packaging, and external promise boundary.

## 3. Gap, expected delta, kill-test, action boundary

- Fact: the queue already had a named B0.1 milestone and a forum-side EXO
  candidate entry.
- Gap: there was no single local decision surface that turned those fragments
  into one concrete 30-day pilot hypothesis with buyer/problem/outcome and MVP
  boundary.
- Expected delta: one local artifact that can drive the next one-pager, effect
  calculator, and address-draft steps without mixing EHO with Hromada or YSU/LFU.
- Kill-test: if no single buyer-owned 30-day outcome can be stated without
  promising integrations or if the director cannot see effect from one narrow
  communication loop, then the `communication module` entry is not the right
  first EHO pilot and must stay `HOLD`.
- Action boundary: local draft only. No outreach, no pricing, no public claims,
  no integration promises, no legal commitments.

## 4. Proposed first pilot hypothesis

### Pilot name

`SYNTONIA EXO / Communication Loop Pilot for a Municipal Enterprise`

### Buyer

Director of a municipal enterprise or another person with authority over the
operational coordination loop and pilot access.

### Primary users

- Director.
- One designated coordinator from the enterprise team.

### Problem

Important inbound items are scattered across chat, calls, email, and documents.
The director must repeatedly reconstruct context, assign an owner, restate the
next action, and track whether anything moved. This creates delay, dropped
follow-ups, and avoidable attention tax.

### 30-day pilot outcome

For one chosen coordination loop, every inbound item enters one shared queue
with:

- a human-readable summary;
- proposed next step;
- proposed owner;
- proposed due date;
- visible approval state;
- daily digest and audit trail.

The human still decides and approves; AI only structures, proposes, and keeps
the loop visible.

### Success metrics for the pilot

- `coverage_rate`: share of chosen-loop items that entered the queue.
- `owner_clarity_rate`: share of items with an explicit owner after review.
- `deadline_clarity_rate`: share of items with an explicit due date after review.
- `response_cycle_time`: median time from intake to human-approved next step.
- `digest_usefulness`: weekly operator verdict whether the digest replaced at
  least one manual reconstruction step.

These metrics are intentionally local and operational. They do not claim business
ROI yet.

## 5. MVP boundary for the first 30 days

### Included

- One enterprise partner.
- One chosen workflow only.
- Manual or semi-manual intake from low-risk sources.
- AI summary plus proposed next step/owner/due date.
- Human approval before any state change.
- Daily digest and searchable decision trail.
- Weekly review of missed or stuck items.

### Excluded

- Direct integration into critical enterprise systems.
- Autonomous sending, deleting, escalating, or external communication.
- Financial, HR, or legally binding automation.
- Enterprise-wide rollout.
- Claims about full `enterprise exoskeleton`.

## 6. Demo surface

One low-risk demo should show exactly this cycle:

`incoming item -> AI summary -> proposed next step -> human approval -> assigned owner/deadline -> digest/audit`

The demo must show the human decision point explicitly. It should not simulate
full enterprise control.

## 7. Partner requirements

- One sponsor with authority to define the chosen loop.
- One operational coordinator for weekly review.
- One low-risk sample set or agreed synthetic dataset for the chosen loop.
- Agreement on allowed data classes and forbidden data classes.
- One weekly 30-minute review slot during the pilot.

## 8. Simple effect calculator seed

The first local calculator can stay simple:

`items_per_week x minutes_saved_per_item x loaded_hour_cost`

Until a real partner exists, this remains a placeholder formula, not a claim.

## 9. Exact next trigger

Proceed to the next local RESOURCE increment only when Lumial confirms that
this is the preferred first EHO entry or replaces it with another buyer-owned
loop. The exact next artifact after that decision is:

`one-page external-safe pilot brief + first effect calculator values + first address-draft shell`

If Lumial does not confirm this entry, keep this card as a falsifiable branch
and do not build outreach around it.
