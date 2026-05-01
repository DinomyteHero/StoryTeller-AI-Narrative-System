> **SPECIALIST SPEC** - Reusable content packs for sample campaigns and
> future campaign families.
>
> **Design authority for:** campaign content pack shape, sample campaign
> content audits, funnel expansion seeds, prologue seeds, and campaign-
> specific terminology.

# Content Packs

## Purpose

Content packs sit between broad era packs and playable campaign spines.
They are not the runtime contract. The campaign spine remains the contract
between Campaign Studio and Game Engine.

A content pack explains and extends a campaign's reusable content:

- campaign-specific terminology
- dramatic identity
- faction guidance
- NPC usage notes
- funnel expansion seeds
- prologue scene seeds
- scene-type outcome guidance
- known content gaps

The goal is to keep sample campaigns from becoming one-off JSON artifacts.
If a campaign is good enough to teach the system, it should also teach future
authors how to expand it.

## Current Pack

The first campaign content pack is:

`data/content_packs/shadows_of_the_custodian.json`

It updates the current sample campaign's content foundation without changing
runtime behavior.

## Pack Shape

| Section | Purpose |
|---------|---------|
| `schema_version` | Campaign content pack format. Current seed: `campaign_content_pack.v0.1`. |
| `id` | Stable campaign pack id. Should match the sample campaign id where possible. |
| `source_spine` | Path to the playable campaign spine that remains authoritative. |
| `campaign_identity` | Era, premise, CDQ, story promise, and thematic throughline. |
| `design_contract` | What the campaign must and must not feel like. |
| `terminology` | Campaign-specific terms and usage notes. |
| `runtime_assets_snapshot` | Counts and key content assets currently present in the spine. |
| `funnel_state` | Current allegiances plus expansion variant seeds. |
| `npc_content_cards` | How to use major NPCs without flattening them. |
| `faction_guidance` | Campaign role and pressure vectors for each faction. |
| `act_content_guidance` | Act-by-act dramatic and scene texture notes. |
| `ffg_scene_guidance` | Era/campaign-specific Advantage, Threat, Triumph, and Despair expression. |
| `prologue_scene_seeds` | Candidate scenes for future Phase 18 prologue authoring. |
| `content_gaps` | Known content gaps with recommended actions. |

## Shadows of the Custodian Audit

The current spine is playable and structurally rich:

- 5 acts
- 2 allegiances
- 2 current variants
- 5 major NPCs
- 3 factions
- 2 vehicles
- 2 variation points
- 4 foreshadow links

The content pack identifies the main gaps:

- no era-pack loader in Campaign Studio or runtime wiring yet
- one variant per allegiance
- no authored prologue scene sets
- canon profiles are inline rather than reusable
- exact talent tree coverage for current variants is incomplete
- no content-pack loader in Campaign Studio yet

## Relationship to Era Packs

Era packs answer: "What does this timeline feel like?"

Campaign content packs answer: "What does this specific campaign need, and
how can it expand without losing its identity?"

For example, the New Republic / Jedi Praxeum era pack defines the timeline's
institutions, terminology, and anachronism guardrails. The Praxeum content
pack defines Kira, Malakai, Luke's fragile academy, and the loyalty question
at the heart of this sample campaign. The NJO era pack does the same work for
Yuuzhan Vong War campaigns.
