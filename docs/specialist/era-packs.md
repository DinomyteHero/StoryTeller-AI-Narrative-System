> **SPECIALIST SPEC** - Reusable era content packs for Star Wars Legends
> campaign generation and runtime narration.
>
> **Design authority for:** era pack file shape, era terminology, reusable
> faction/allegiance/variant seeds, and period-specific narration guardrails.

# Era Packs

## Purpose

Era packs are reusable content bibles for Star Wars timelines. A campaign
spine still owns the actual playable campaign, but an era pack gives the
Campaign Studio a stable source for:

- era voice and anachronism guardrails
- faction templates
- allegiance options
- character variant seeds
- Force tradition guidance
- canon profile seeds
- FFG outcome interpretation by scene type
- campaign template starters

This lets "New Jedi Order," "Clone Wars," or "Old Republic" mean more than
a label in `era_voice`.

## Current Packs

The current packs are:

`data/era_packs/new_jedi_order.json`

It covers the Star Wars Legends New Jedi Order era, with the Yuuzhan Vong
War as the primary play window and the postwar era as sequel space.

`data/era_packs/new_republic_praxeum.json`

It covers the Star Wars Legends New Republic / Jedi Praxeum era, with broad
support for 4-24 ABY and primary support for the 11-14 ABY Praxeum window
used by `Shadows of the Praxeum`.

## Pack Shape

An era pack is a JSON object with these top-level sections:

| Section | Purpose |
|---------|---------|
| `schema_version` | Era pack format version. Current seed: `era_pack.v0.1`. |
| `id` | Stable machine id, e.g. `new_jedi_order`. |
| `display_name` | Human-facing era name. |
| `continuity` | `legends`, `canon`, or `custom`. |
| `date_range` | Era-wide and play-window dates. |
| `era_voice` | Directly maps to the campaign spine's `EraVoice` shape. |
| `timeline_bands` | Sub-era slices with distinct campaign uses. |
| `terminology` | Era terms, definitions, and words to contextualize. |
| `faction_templates` | Reusable faction entries compatible with the spine's faction concept. |
| `allegiance_templates` | Player entry lanes and variant seeds for funnel authoring. |
| `force_traditions` | Era-specific Force assumptions and GM guidance. |
| `scene_pressures` | Scene-type texture for narration prompts. |
| `ffg_outcome_guidance` | How Advantage, Threat, Triumph, and Despair should feel in this era. |
| `canon_profile_seeds` | Starting points for future `data/canon_profiles/` entries. |
| `campaign_templates` | Reusable campaign premise starters. |
| `implementation_gaps` | Known places where the content pack exceeds current runtime support. |

## Design Rules

Era packs are **content seeds**, not executable campaign spines.

The Campaign Studio should use them to draft or validate a spine, but the
Game Engine should still consume a resolved campaign spine. This preserves
the existing invariant: the campaign spine is the contract between Studio
and Engine.

Era packs should not script canon outcomes. They should define pressure:
what institutions exist, what people fear, what technology belongs, what
anachronisms to avoid, and what kinds of moral choices feel native to the
era.

Era packs should include implementation gaps when they require mechanics the
engine does not yet support. For example, the NJO pack intentionally marks
Yuuzhan Vong player support as custom because the current character species
model is enum-based and limited.

## New Republic / Jedi Praxeum Notes

The New Republic / Jedi Praxeum pack is the era backbone for the sample
campaign. Its core premise is not "the Empire still rules" or "the Jedi are
fully restored." The intended texture is:

- the New Republic is legitimate but stretched thin
- Imperial threats are Remnant forces, holdouts, warlords, agents, and old
  consequences
- Luke's Praxeum is intimate, hopeful, experimental, and vulnerable
- recovered Jedi lore is useful but incomplete
- Yavin 4 and the Massassi ruins make the past physically present
- canon mentors create pressure without solving the player's central choices

The north-star sentence is: **the Jedi are returning, but not restored.**

This pack is deliberately aligned with
`data/content_packs/shadows_of_the_praxeum.json`, which now lists
`new_republic_praxeum` as an available era pack.

## New Jedi Order Notes

The NJO pack is deliberately different from the current Praxeum campaign.
The Praxeum campaign is early New Republic training drama. NJO is wartime
catastrophe:

- the Jedi are visible but unsettled
- the New Republic is strained and politically fractured
- the Yuuzhan Vong use biological technology
- refugee corridors and triage are central textures
- the Force is less clean as an information channel
- the Imperial Remnant can become an uneasy ally

The best NJO campaigns should not feel like "Imperials, but scarier." They
should feel like a galaxy realizing the old victory did not prepare it for
this war.

## Next Packs

Recommended order after the New Republic and NJO seeds:

1. Clone Wars
2. Galactic Civil War / Imperial Era
3. Old Republic
4. Legacy of the Force / Fate of the Jedi
5. Legacy comics era

Each new pack should start with the same v0.1 shape and a focused validation
test before any runtime loader work begins.
