# Storyteller V3 — Campaign Studio Design Document

**Document version:** 1.3
**Project:** Storyteller V3
**Last updated:** March 2026
**Scope:** Design specification for the Campaign Studio — the authoring
system that produces campaign spines consumed by the Game Engine. Covers
creative methodology (the writers room), system design (automation modes,
validation, import/export), and the interface contract (campaign spine JSON).

**Relationship to other documents:**
- **Vision Document** — answers *what the game should feel like*
- **Game Mechanics Document** — answers *how the Game Engine works at runtime*
- **This Document** — answers *how campaigns are created, validated, and
  structured*
- **Implementation Document** — answers *how both systems are built in code*

**The interface contract:** The campaign spine JSON is the output of the
Campaign Studio and the input of the Game Engine. This document specifies
what that JSON contains, how it is authored, and how it is validated. The
Game Engine consumes the spine without knowing or caring whether it was
hand-authored, collaboratively generated, or fully automated.

---

## 0. Design Principles

Four principles govern Campaign Studio design. When two goals conflict,
these principles break the tie.

**Principle 1: The spine serves the player, not the author.**
Every design decision in the Campaign Studio exists to produce a better
experience for the person reading and choosing. Clever narrative structures,
ambitious NPC networks, and innovative worldbuilding have no value if they
do not translate into compelling turns at the table. The Studio's output
quality is measured by the Game Engine's runtime output quality.

**Principle 2: Authored quality is the ceiling.**
The best campaigns will always be the ones where a skilled human invested
craft and judgment. Automation modes exist to make campaign creation
accessible, not to replace authorial skill. Mode 3 (full collaboration)
should produce results as good as solo authoring but faster. Mode 2
(thematic steering) should produce results that are good enough. Mode 1
(full blind) should produce results that are playable, with a different
and explicitly lower quality contract.

**Principle 3: The contract is sacred.**
The campaign spine JSON is the interface between two independent systems.
A malformed spine corrupts the entire campaign at runtime. Validation is
not optional. Every spine — whether hand-authored, collaboratively
generated, or fully automated — passes through the same validation gates
before the Game Engine touches it.

**Principle 4: Canon is environmental, not personal.**
When campaigns engage with the Star Wars Legends timeline, canon events
function as environmental anchors — galactic-scale forces the player
exists within but does not control. The player's personal story is their
own. The galaxy's story is the galaxy's. The Campaign Studio designs
spines that honor both.

---

## 1. What the Campaign Studio Produces

The Campaign Studio produces a single artifact: a **campaign spine JSON
file** that the Game Engine consumes. This file contains everything the
engine needs to run a complete campaign:

- **Campaign metadata** — name, era, total acts, throughline question
- **Allegiances** — 2-4 faction options per campaign, each containing
  2-4 character variants with narrative pitches, career assignments,
  motivation track defaults, starting situations, starting loadouts
  (Section 18), Force discovery probability (Section 16), and
  protagonist integration layers connecting each variant to the fixed
  thematic spine
- **Prologue scenes** — 3-5 behavioral diagnostic scenes per variant,
  with per-choice axis tags for the psychometric system, drawn from
  career- and allegiance-scoped scene libraries where possible
- **Acts** — ordered narrative units, each containing: an anchor beat,
  tension level, opening situation, galactic context, open threads,
  XP base award and bonus conditions (Section 14), and optional time
  skip data (Section 19) including vignette libraries
- **NPC roster** — every significant NPC with: name, role, starting
  disposition (numeric 0-1), motivation, voice/speech notes, behavioral
  envelope (hard constraints), knowledge state, and per-act trajectory.
  Canon characters include extended profiles with voice, relationship
  dynamics, era-specific notes, and anti-stereotype notes (Section 22)
- **Variation points** — specific moments with 2-3 authored alternatives
  selected by player behavior patterns or random determination
- **Galactic context** — per-act worldbuilding data about the wider
  galaxy that is independent of the player
- **Vehicle registry** — ships available to the character, with stat
  blocks and narrative notes (Section 17)
- **Milestone windows** — optional authored timing for talent and
  specialization milestones, and Force discovery windows (Sections
  14–16)
- **Import interface** — specification of how prior character state
  maps onto this campaign, including specialization mappings,
  motivation track transitions, target XP range, and imported loadout
  (Section 20)

The spine does not contain:
- Prose passages (the Game Engine generates those at runtime)
- Dice results (those are resolved at runtime)
- Player state (that is created and maintained by the Game Engine)
- Choice text (generated by the cloud model per turn)
- Talent tree data (stored in `data/talent_trees/`, loaded by engine)
- Force power data (stored in `data/force_powers/`, loaded by engine)
- Canon character base profiles (stored in `data/canon_profiles/`,
  referenced by the spine's NPC roster entries)

The spine is the skeleton. The Game Engine grows the flesh.

---

## 2. The Writers Room — Craft Principles

The Writers Room is the creative methodology that governs campaign design.
These principles apply whether the author is working solo, collaborating
with an AI in Mode 3, or encoding standards into prompts for Mode 2 and
Mode 1. The Writers Room defines what good looks like. The automation
modes define how you get there.

### 2.1 The Throughline Question

Every campaign is built around a single question that the story pressures
but never answers directly. The player's choices provide the answer — not
through a dialogue option, but through the accumulated pattern of decisions
they make under pressure.

**What makes a good throughline question:**

It must be genuinely debatable. "Is murder wrong?" is not a throughline
question — it has an obvious answer. "What are you willing to do to protect
the people you love?" is a throughline question — reasonable people
disagree, and the answer depends on specifics.

It must be pressurable from multiple directions. A question that only has
one natural pressure point produces a monotone story. "Can a man who has
only ever looked out for himself become someone worth following?" can be
pressured by loyalty tests, leadership moments, betrayal opportunities,
self-sacrifice costs, and trust dynamics — each from a different angle.

It must be answerable through tactics, not declarations. The player never
says "I believe in loyalty." They choose to go back for someone when the
smart move is to run. The throughline question is answered by what the
player does, not what they say.

It must sustain 20+ hours of play. Questions that resolve after one big
decision ("Do you betray the contact or not?") are act-level questions,
not campaign-level questions. The throughline question should still be
generating interesting pressure in Act 4 after the player has been living
with it since Act 1.

### 2.2 Anchor Beat Design

Anchor beats are the load-bearing structure of the campaign — the moments
that happen regardless of player choice. They provide narrative coherence
without constraining player agency.

**Rules for anchor beats:**

An anchor beat is a **situation**, not an **outcome**. "Vossk's people
arrive with their own agenda" is an anchor. "Vossk's people capture Keth"
is not — that predetermines the player's result. The anchor creates the
pressure. The player's choices and dice determine how the pressure resolves.

An anchor beat must work with multiple character archetypes. If the anchor
only produces interesting drama for a bold character, it fails when a
cautious player reaches it. Each anchor should be designed with at least
two character approaches in mind: how does a trusting character experience
this moment? How does a guarded one? The anchor's power comes from its
ability to create drama regardless of the player's behavioral pattern.

An anchor beat should transform the situation irreversibly. After the
anchor, the status quo is different. New information is revealed. An NPC's
role changes. A resource is gained or lost. A relationship shifts. The
player should feel that they have crossed a threshold and cannot go back.

Anchor beats are separated by 5-8 turns of generative space — enough room
for the player to explore, gather information, make preliminary choices,
and develop their relationship with the situation before the anchor
compresses it.

### 2.3 NPC Relationship Architecture

The NPC roster is not a cast list — it is a relationship network designed
to create dramatic pressure.

**The conflict requirement:** Every NPC roster must contain genuine
conflict — not just antagonists opposing the player, but allies who
disagree with each other, contacts who work multiple sides, and
relationships where disposition and motivation point in different
directions. LLMs systematically generate NPC networks that are more
positive and more homogeneously clustered than human-written stories
(Nonaka & Perry, NeurIPS 2025). Campaign authors must actively resist
this by designing conflict into the network architecture.

**Cross-cluster interactions:** Good narrative requires NPCs who defy
simple categorization. Allies who have reasons to distrust each other.
Antagonists who offer the player something genuine. Neutral contacts
whose loyalty depends on which way the wind blows. If the NPC roster
can be cleanly divided into "the player's team" and "the opposition,"
it lacks the complexity that produces interesting choices.

**Disposition as trajectory, not label:** Each NPC's starting disposition
toward the player (numeric 0-1) is just the beginning. The spine should
define a trajectory — how disposition is likely to change across acts
based on the kinds of choices the player makes. An NPC who starts
neutral (0.5) might trend toward loyal if the player is trustworthy, or
toward hostile if the player is manipulative. These trajectories are not
deterministic — the player's actual choices override them. But they give
the campaign author a tool for designing relationships that evolve
meaningfully rather than staying static.

**Behavioral envelopes:** Every significant NPC has hard constraints —
things they would never do regardless of circumstances. These constraints
prevent the LLM from generating out-of-character behavior under narrative
pressure. Vossk never appears in person. Doss never confronts directly.
An Imperial officer never breaks protocol in front of subordinates. The
envelope is a small set of "never" rules that preserve NPC consistency
across the full campaign.

### 2.4 Galactic Context Authoring

The galactic context layer makes the world feel inhabited independently
of the player. Each act includes 2-4 sentences of wider-universe state
that press on the player's situation without being plot points.

**Authoring guidelines:**

Galactic context should be specific, not generic. "The Empire is
tightening its grip" is useless. "Imperial customs interdiction has
tightened across the Y'Toub system following a Rebel supply intercept at
Nal Hutta" gives the GM something concrete to work with.

At least one element per act should have the potential to become relevant
to the player's story — not necessarily, but potentially. This enables
the GM's forward-echoing instruction: planting seeds that might grow.

Context should change between acts to reflect the passage of time and
the evolution of the galaxy around the player. The galaxy does not pause
while the player is busy. New pressures emerge. Old ones resolve. The
world has momentum.

### 2.5 Character Variant Design

Each campaign supports a **character funnel** — a guided sequence of identity
decisions that narrows the galaxy-wide possibility space into a specific
protagonist. The funnel flow is: Timeline → Allegiance → Variant. The
Campaign Studio is responsible for authoring the content at each layer.

**Timeline** is set by the campaign's era. The campaign author does not need
to author multiple timelines — each campaign spine belongs to one era. The
timeline step in the funnel is a campaign selection mechanism, not a
per-campaign authoring task.

**Allegiances** are the faction options available within the campaign.
Each campaign defines 2-4 allegiances appropriate to its era and central
conflict. A Galactic Civil War campaign might offer Empire, Rebellion,
Criminal Underworld, and Independent. A Clone Wars campaign might offer
Republic, Separatist, Jedi Order, and Criminal Underworld. The available
allegiances shape what kinds of protagonists can enter the campaign.

**What an allegiance contains:**

- A display name (what the player sees: "The Empire," "The Rebellion")
- A brief description of what this allegiance means in this campaign
  (1-2 sentences establishing the faction's role in the story)
- A list of character variants available within this allegiance

**Variants** are the character options within an allegiance. Each allegiance
offers 2-4 variants — narrative pitches, not stat blocks.

**What a variant contains:**

- A 1-2 sentence narrative pitch (what the player reads when selecting)
- A career assignment (FFG career and specialization)
- A species (with narrative rationale, not arbitrary assignment)
- A primary motivation track type (Obligation, Duty, or Morality)
- A starting situation that connects to the campaign's fixed thematic spine
  through the protagonist integration layer (Section 2.8)
- A set of 2-3 possible motivation subtypes (refined by the prologue)
- A baseline for voice notes (refined by the prologue)
- Whether the variant is Force-sensitive
- The allegiance it belongs to

**Design constraints:**

Variants within an allegiance should cover meaningfully different play
experiences. If two of three Rebellion variants are "combat pilot with
Duty: Support," the selection is cosmetic. Each variant should produce a
different relationship to the throughline question, different NPC dynamics,
and different emotional textures.

Variants across allegiances should produce structurally different
experiences within the same campaign. An Empire-aligned variant and a
Rebellion-aligned variant entering the same campaign must feel like
different stories, not the same story with different faction labels. The
protagonist integration layer (Section 2.8) is the mechanism for this —
but the variant design must support it by ensuring each allegiance's
variants have genuinely different relationships to the campaign's central
conflict.

At least one variant per campaign should be non-combat-oriented. The
game must work for players who want to solve problems through social
skills, investigation, or resourcefulness rather than violence.

Force-sensitive variants are included within Force-aligned allegiances
(Jedi Order, Force Tradition) when the era and campaign support them.
Not every campaign needs a Force-sensitive allegiance. When they are
included, the non-Force allegiances and variants must be equally
compelling — not lesser alternatives.

**Authoring scale guidance:**

A campaign with 3 allegiances and 3 variants per allegiance produces 9
total variants. This is the recommended starting range. The minimum viable
campaign has 2 allegiances with 2 variants each (4 total). The practical
maximum is 4 allegiances with 4 variants each (16 total), beyond which
the protagonist integration layer authoring becomes prohibitively complex.

Career-type reuse is encouraged across campaigns. A "smuggler" variant
authored for one Galactic Civil War campaign can share prologue scene
libraries (Section 2.6) and Layer 2 mapping tables with smuggler variants
in other campaigns. The variant-specific content — narrative pitch, starting
situation, NPC relationships — is campaign-specific, but the behavioral
profiling infrastructure is reusable.

### 2.6 Prologue Scene Design

Prologue scenes are the diagnostic tool that refines a selected character
variant into a specific character. They are experienced as the opening
chapter of a novel. They are designed as behavioral measurement
instruments.

**Design requirements:**

Each scene presents 3-4 choices. Each choice is pre-tagged (invisible to
the player) on four behavioral axes: Approach (Direct/Indirect), Social
(Trusting/Guarded), Risk (Bold/Cautious), Moral (Principled/Pragmatic).

Scenes must create genuine pressure — situations where the player's
response reveals something real about their instincts, not situations
where one choice is obviously correct.

The first three scenes should each test a different combination of axes.
Scene 1 might pressure Approach and Risk. Scene 2 might pressure Social
and Moral. Scene 3 might pressure Risk and Social. This ensures coverage
across all four dimensions in the minimum number of scenes.

Scenes 4-5 (if needed) are targeted at ambiguous axes. If the first
three scenes produced clear signal on Approach and Risk but ambiguous
signal on Social, scene 4 should present a situation where Trusting and
Guarded produce sharply different responses.

Prologue scenes should feel like they belong in the campaign's story,
not like personality quizzes. The situations should emerge from the
campaign's setting and the variant's starting circumstances.

**Scene library approach:**

The character funnel increases the total number of variants per campaign.
To manage authoring scale, prologue scenes can be organized into a
**career- and allegiance-scoped library.** A scene designed for a "smuggler
in the Criminal allegiance" can be reused across multiple smuggler variants
within that allegiance, and potentially across campaigns set in the same
era.

Scenes carry two scoping tags: `career_type` (e.g., "smuggler,"
"soldier," "spy") and `allegiance` (e.g., "empire," "rebellion,"
"criminal"). A scene library entry is usable by any variant whose career
and allegiance match the tags. Campaign-specific scenes that reference
unique NPCs or locations remain per-variant.

The recommended approach is: 3 library scenes per career-allegiance
combination (covering the required axis spread), plus 2 campaign-specific
scenes per variant for targeted axis testing in scenes that connect to
the campaign's specific narrative.

### 2.7 Prose Variety by Design

Long campaigns risk prose staleness — the cloud model settling into
repetitive patterns of description, pacing, and emotional register.
The Campaign Studio can mitigate this structurally.

**Scene type diversity across acts.** Each act should contain a mix of
scene types — not five consecutive social encounters or three combat
sequences in a row. The spine should alternate between high-tension and
low-tension segments, between action-oriented and reflection-oriented
scenes, between populated spaces and isolated ones.

**Location variety.** Characters who spend the entire campaign in one
location produce monotone environmental description. The spine should
move the player through at least 2-3 distinct environments per act —
different enough in sensory texture that the GM's prose naturally varies.

**Emotional register shifts.** The spine should design moments of
contrast — a quiet scene after a crisis, a moment of humor in a tense
act, a personal conversation amid political drama. These register shifts
prevent the prose from settling into a single emotional frequency.

### 2.8 Protagonist Integration Layer

The character funnel means the campaign must accommodate multiple
protagonist types entering the same thematic spine. The **protagonist
integration layer** is the authored bridge between a specific variant and
the campaign's fixed structure.

**What the fixed thematic spine contains:**

The setting, era, central conflict, act structure, dramatic arc, and
anchor beats. These do not change based on who the protagonist is. "A
story about survival and loyalty in the Nar Shaddaa underworld during
the Imperial era" is a fixed spine. The anchor beats are abstract enough
to work with any protagonist the funnel can produce: "arrival under
pressure," "contact discovered," "obligation triggered," "final
confrontation."

**What the protagonist integration layer adapts:**

- **Entry point.** Why the protagonist is in this setting. An Imperial
  defector is on Nar Shaddaa because they are running. A criminal is
  there because it is home. A student is there because they followed
  someone they should not have. The entry point determines the opening
  situation and the first act's narrative framing.

- **Personal stakes.** What the protagonist stands to lose. This connects
  to the motivation track — a smuggler with Obligation: Debt faces
  financial ruin, a soldier with Duty: Support faces betrayal of their
  unit, a student with Obligation: Family faces danger to the people who
  trust them.

- **NPC relationship configuration.** Which NPCs from the roster are
  allies, obstacles, or unknowns to this specific protagonist. The NPC
  roster is shared across all variants, but each variant's integration
  layer specifies starting dispositions, knowledge states, and
  relationship framing. Doss might be a trusted contact for the smuggler
  variant but a suspicious stranger for the Imperial defector variant.

- **Anchor beat framing.** How each anchor beat manifests for this
  protagonist. The anchor "obligation triggered" is structurally the same
  — external pressure arrives — but the *form* differs. For the smuggler,
  Vossk's people arrive. For the defector, Imperial intelligence catches
  their trail. The narrative event is different; the dramatic function is
  identical.

**Design constraints for the integration layer:**

Each allegiance in the campaign requires at least one fully authored
integration layer path. The integration layer must produce a different
*experience*, not just different flavor text — different NPC dynamics,
different personal stakes, different emotional textures through the same
structural beats.

Anchor beats must be written at a level of abstraction that survives all
integration layer variants. An anchor that says "Vossk's people arrive"
only works for the smuggler. An anchor that says "the protagonist's
obligation source escalates" works for everyone. The integration layer
translates the abstract anchor into the specific narrative event.

Integration layers should be authored and validated in the Campaign Studio
before the campaign is playable. The Game Engine does not perform
integration-layer generation at runtime — it receives a fully resolved
campaign spine with a specific variant already integrated.

---

## 3. Automation Modes

The Campaign Studio supports three modes of campaign creation, ordered
from most to least human involvement. The mode determines how much of
the creative work is done by the human author and how much is delegated
to the AI.

### Mode 3 — Full Collaboration (Build First)

The human author drives the creative process. The AI assists with
execution, consistency checking, and detail generation. The author makes
all structural decisions — throughline question, anchor beats, NPC
architecture, character variants. The AI helps fill in galactic context,
generate prologue scene options, draft NPC voice notes, and identify
gaps the author may have missed.

This is the mode for authors who know what story they want to tell and
want help building it efficiently.

**Workflow:**
1. Author provides throughline question, era, and campaign concept
2. Author designs anchor beats and NPC roster (AI suggests alternatives
   and flags structural issues)
3. AI generates galactic context drafts per act (author reviews and edits)
4. Author designs allegiances, character variants, and integration layers
   (AI generates prologue scene drafts and validates cross-allegiance
   diversity)
5. AI runs validation suite (Section 5); author addresses flags
6. Output: validated campaign spine JSON

**Quality contract:** Equivalent to solo authoring. The AI accelerates
the process but the author's judgment controls the output.

### Mode 2 — Thematic Steering

The human author provides thematic direction — era, tone, throughline
question, a 2-3 sentence campaign concept, and key constraints. The AI
generates the campaign structure, NPC roster, anchor beats, and character
variants. The author reviews, edits, and approves.

This is the mode for authors who have a story idea but not a detailed
design, or who want to explore what the AI can produce from a thematic
seed.

**Workflow:**
1. Author provides: era, location, tone, throughline question, campaign
   concept (2-3 sentences), moral register, and any specific NPCs or
   plot elements they want included
2. AI generates complete campaign spine draft
3. Author reviews and edits all components — can accept, reject, or
   modify any element
4. AI runs validation suite; author addresses flags
5. Output: validated campaign spine JSON

**Quality contract:** Good enough for an engaging experience. May lack
the narrative precision and thematic depth of Mode 3 but should produce
a structurally sound campaign with genuine dramatic interest.

### Mode 1 — Full Blind (Long-Term Aspiration)

The AI generates a complete campaign from minimal input. The human
provides only the minimum viable specification. This is the most
ambitious mode and the last to be built.

**Minimum viable input:**
- Era and general location
- Tone (gritty, heroic, tragic, etc.)
- A 2-3 sentence "this campaign is NOT" description — the negative
  archetype specification that prevents the AI from producing the
  default Star Wars story the training data wants to tell
- Moral register (morally gray, clearly delineated, shifting, etc.)
- Archetype avoidance list (e.g., "No Chosen One narratives. No
  redemption arcs that resolve cleanly. No mentor figures who exist
  only to die.")

Without these anti-default signals, Mode 1 will produce a hero's
journey with a Dark Side antagonist and a redemptive climax — because
that is what LLMs trained on English-language fiction default to
(per Rettberg's AI STORIES hypothesis, confirmed by Latitude's
operational experience).

**Quality contract:** Playable but explicitly lower quality than Modes
2 and 3. Mode 1 campaigns may have thinner NPC networks, less
surprising anchor beats, and more predictable throughline dynamics.
The quality bar is "an engaging campaign that doesn't feel generic"
— not "a campaign that rivals a skilled human author."

---

## 4. The Campaign Spine JSON Format

The campaign spine JSON is the interface contract between the Campaign
Studio and the Game Engine. The format is specified here because this
document owns the output specification.

### 4.1 Top-Level Structure

```json
{
  "name": "The Nar Shaddaa Job",
  "era": "galactic_civil_war",
  "total_acts": 4,
  "throughline_question": "Can a man who has only ever looked out for himself become someone worth following?",
  "allegiances": [ ... ],
  "prologue_scenes": { ... },
  "acts": [ ... ],
  "npc_roster": [ ... ],
  "variation_points": [ ... ]
}
```

### 4.2 Allegiance Schema

```json
{
  "id": "criminal_underworld",
  "display_name": "Criminal Underworld",
  "description": "The syndicates, smugglers, and survivors who operate in Nar Shaddaa's shadow economy. Loyalty is currency, and debts are paid in blood or credits.",
  "character_variants": [ ... ]
}
```

Each campaign defines 2-4 allegiances. Each allegiance contains 2-4
character variants. The allegiance `id` is used as a scoping tag for
prologue scene library matching and NPC disposition calibration.

### 4.3 Character Variant Schema

```json
{
  "id": "keth_varso",
  "allegiance": "criminal_underworld",
  "pitch": "A Bothan smuggler running from a debt that is catching up to him.",
  "species": "bothan",
  "career": "smuggler",
  "career_type": "smuggler",
  "specializations": ["pilot"],
  "primary_game_line": "edge_of_empire",
  "force_sensitive": false,
  "motivation_default": {
    "track": "obligation",
    "possible_types": ["Debt", "Criminal Record", "Oath"]
  },
  "starting_situation": "Keth has just dropped out of hyperspace above Nar Shaddaa. His contact Doss has gone dark. A sealed cargo container sits in his hold.",
  "voice_baseline": "Dry, observational. Dark humor as a defense mechanism. Reads situations and people quickly.",
  "background": "A Bothan smuggler who owes a significant debt to a Hutt crime lord named Vossk the Patient. Operates the ship Mira's Luck on independent contracts.",
  "integration_layer": {
    "entry_point": "Arrived on Nar Shaddaa to deliver cargo and meet a contact who has gone dark. The debt to Vossk makes leaving without resolution impossible.",
    "personal_stakes": "Financial ruin and physical danger from Vossk's organization. The cargo is the only leverage Keth has.",
    "npc_overrides": {
      "doss": { "disposition_start": 0.7, "relationship": "trusted_contact" },
      "vossk": { "disposition_start": 0.2, "relationship": "creditor" }
    },
    "anchor_adaptations": {
      "obligation_triggered": "Vossk's people arrive to collect the debt."
    }
  },
  "characteristics_base": {
    "brawn": 2, "agility": 3, "intellect": 3,
    "cunning": 4, "willpower": 2, "presence": 3
  },
  "skills_base": {
    "deception": 2, "piloting_space": 2, "streetwise": 1,
    "skulduggery": 1, "coordination": 1, "perception": 1
  },
  "wound_threshold": 12,
  "strain_threshold": 12,
  "soak": 2
}
```

The `career_type` field enables prologue scene library matching and Layer 2
mapping table reuse across variants of the same career type. The `allegiance`
field scopes the variant within the funnel and provides context for NPC
disposition calibration. The `integration_layer` object connects this
specific variant to the campaign's fixed thematic spine — entry point,
personal stakes, NPC relationship overrides, and anchor beat adaptations.

### 4.4 Prologue Scene Schema

```json
{
  "variant_id": "keth_varso",
  "career_type": "smuggler",
  "allegiance": "criminal_underworld",
  "scenes": [
    {
      "scene_number": 1,
      "library_reusable": true,
      "situation": "You are approached by a customs officer at the landing bay. Something about your cargo manifest doesn't add up, and he knows it.",
      "choices": [
        {
          "text": "Meet his eyes and smile. You have done this a hundred times.",
          "axis_tags": { "approach": "direct", "risk": "bold" }
        },
        {
          "text": "Offer to buy him a drink after his shift. Everyone on Nar Shaddaa has a price.",
          "axis_tags": { "approach": "indirect", "social": "trusting" }
        },
        {
          "text": "Excuse yourself to make a comm call — and use the moment to slip past while he is distracted.",
          "axis_tags": { "approach": "indirect", "risk": "cautious" }
        }
      ]
    }
  ]
}
```

The `career_type` and `allegiance` fields enable scene library matching.
A scene with `library_reusable: true` can be shared across variants of
the same career type and allegiance. Campaign-specific scenes that
reference unique NPCs or plot elements should set `library_reusable: false`.

### 4.5 Act Schema

```json
{
  "number": 1,
  "name": "The Approach",
  "tension": "rising",
  "opening_situation": "Keth has just dropped out of hyperspace above Nar Shaddaa. His contact Doss has gone dark. An unknown voice on the comm has warned him off the original drop coordinates.",
  "galactic_context": "Imperial customs interdiction has tightened across the Y'Toub system following a Rebel supply intercept at Nal Hutta. Hutt Council territorial disputes between Vossk's faction and the Besadii clan have made landing clearances unpredictable. An unrelated freighter explosion at Dock 14 yesterday has every security team on the Promenade running nervous.",
  "anchor": "arrival_with_hot_cargo",
  "next_anchor": "contact_discovered",
  "open_threads": [
    "Who is the mysterious comm voice?",
    "What happened to Doss?",
    "What is actually in the cargo?"
  ],
  "expected_turns": "8-12"
}
```

### 4.6 NPC Roster Schema

```json
{
  "name": "Vossk the Patient",
  "role": "Hutt crime lord — Keth's creditor",
  "disposition_start": 0.45,
  "disposition_trajectory": "Decreases if player delays payment; increases slightly if player shows competence",
  "motivation": "Profit and reputation, in that order.",
  "voice_notes": "Always through intermediaries. Formal. Indirect. Never threatens directly — observes possibilities.",
  "behavioral_envelope": [
    "Never appears in person during this campaign",
    "Never makes direct threats — always frames consequences as observations",
    "Never forgives a debt without extracting something of equal value"
  ],
  "knows_at_start": ["Keth owes him", "The job exists", "It is late"],
  "doesnt_know_at_start": ["What is actually in the cargo", "That Doss has gone dark"],
  "per_act_state": [
    {
      "act": 1,
      "role_in_act": "Background pressure through intermediaries",
      "disposition_expected": 0.45
    },
    {
      "act": 2,
      "role_in_act": "Active pressure — sends representatives to collect",
      "disposition_expected": 0.35
    },
    {
      "act": 3,
      "role_in_act": "Competing faction — Vossk wants the cargo for his own reasons",
      "disposition_expected": "variable — depends on player actions in Act 2"
    },
    {
      "act": 4,
      "role_in_act": "Resolution — disposition determines available endings",
      "disposition_expected": "variable"
    }
  ],
  "npc_relationships": [
    {
      "npc": "Doss",
      "nature": "Vossk considers Doss a useful but unreliable asset",
      "weight": -0.2
    }
  ]
}
```

### 4.7 Variation Point Schema

```json
{
  "id": "doss_fate",
  "trigger_act": 2,
  "description": "What happened to Doss before the campaign began",
  "selection_method": "random",
  "options": [
    {
      "id": "arrested_by_isb",
      "description": "Doss was arrested by Imperial Security Bureau agents two days ago.",
      "npc_state_changes": {
        "Doss": { "disposition_modifier": 0, "knowledge_add": ["ISB is watching the cargo route"] }
      }
    },
    {
      "id": "sold_keth_out",
      "description": "Doss sold information about Keth's cargo to a competing faction.",
      "npc_state_changes": {
        "Doss": { "disposition_modifier": -0.3, "motivation_override": "Self-preservation — knows Keth will find out" }
      }
    },
    {
      "id": "in_hiding",
      "description": "Doss discovered the true contents of the cargo and went to ground.",
      "npc_state_changes": {
        "Doss": { "disposition_modifier": 0.1, "knowledge_add": ["The truth about the cargo"] }
      }
    }
  ]
}
```

---

## 5. Validation Systems

Every campaign spine — regardless of authoring mode — passes through
the validation suite before the Game Engine can consume it. Validation
catches structural problems at authoring time that would corrupt the
campaign at runtime.

### 5.1 Schema Contract Validation

Structural validation against the campaign spine JSON format. This is
automated, deterministic, and non-negotiable.

**Checks:**
- All acts present and sequentially numbered
- Every NPC referenced in anchor beats or act descriptions exists in
  the NPC roster
- Every NPC has required fields: name, disposition_start (numeric 0-1),
  motivation (non-empty), voice_notes (non-empty)
- Galactic context present and non-empty for each act
- Prologue scenes (if present) have per-choice axis tags on all choices
- No dangling references — NPCs mentioned in act text but absent from
  the roster
- Character variants have all required fields
- Throughline question is present and is a question
- Variation points reference valid NPCs and valid acts

### 5.2 NPC Coherence Validation

Per-NPC action-emotion chain tracing across the full campaign arc.
Flags discontinuities where an NPC's behavior in an anchor beat
requires an emotional state that preceding beats do not establish.

**Example flag:** "Vossk's Act 3 betrayal requires a disposition shift
that is not established in Acts 1-2. Insert an inflection point where
Vossk's interests diverge from the player's before Act 3."

**Mechanism:** For each NPC, extract the sequence of authored states
(disposition, motivation, key actions) per act. Check that each
transition is justified by preceding context. Where transitions are
abrupt, flag for author review (Mode 3) or auto-generate a bridging
element (Mode 2/1).

Uses disposition (continuous 0-1), motivation (FFG-defined types), and
key authored actions from NPC state data — not a simplified emotion
taxonomy.

### 5.3 Relationship Network Validation

Validates that the NPC relationship graph does not exhibit the
LLM-typical positivity skew and homogeneous clustering documented in
empirical research (Nonaka & Perry, NeurIPS 2025).

**Three checks:**
1. If signed edge weights of NPC relationships are overwhelmingly
   positive (mean > 0.5), flag insufficient conflict
2. If allied NPCs cluster together and antagonist NPCs form a separate
   cluster, flag homogeneous clustering — good narrative requires
   cross-cluster interactions
3. If antagonistic relationships are sparse and disconnected, flag thin
   conflict dynamics

Human-written stories demonstrate denser, more clustered negative
relationship networks than LLM-generated stories. The spine should
target the human-written distribution.

### 5.4 Narrative Consistency Audit

A multi-pass LLM audit running at authoring time (not runtime). Three
LLM calls per spine — one per dimension. Trivially affordable at
authoring time.

**Dimension 1 — Narrative coherence.** Does Act 3 contradict anything
established in Acts 1-2? Do NPC motivations still track across acts?
Are open threads resolved or deliberately left open (not accidentally
dropped)?

**Dimension 2 — Mechanical balance.** Are difficulty curves reasonable?
Are there enough recovery pacing opportunities (per Game Mechanics
Document Section 2)? Is there scene type variety across acts?

**Dimension 3 — Prose variety potential.** Does the spine provide enough
variation in scene types, locations, NPC interactions, and emotional
registers to avoid staleness over a full campaign? If the spine is five
acts of tense social negotiation in a cantina, the validator flags
insufficient variety.

### 5.5 Validation in Each Mode

**Mode 3:** All flags are presented to the author for review and
resolution. The author decides which flags to address and which to
accept.

**Mode 2:** The AI automatically addresses schema contract violations
and NPC coherence flags. Relationship network and narrative consistency
flags are presented to the author.

**Mode 1:** The AI automatically addresses all flags, re-generating
problematic components and re-validating until the suite passes. The
human reviews the final output but does not address individual flags.

---

## 6. Cross-Era Campaign Continuity

The Campaign Studio supports campaigns that intake characters from prior
campaigns, enabling cross-era storytelling where a character's history
shapes their experience in a new setting.

### 6.1 The Campaign Import Interface

Campaign spines can declare an **import interface** — a specification
of what prior character state they can accept and how it maps onto the
new campaign.

**What the import interface specifies:**

- Which prior campaigns or eras are compatible
- How existing NPC relationships map onto the new campaign's NPC roster
  (e.g., "If the character has a relationship with Jacen Solo from an
  NJO campaign, map it onto the Legacy of the Force Jacen NPC entry")
- How motivation track state carries forward (Obligation values persist;
  Duty types may change to reflect new institutional commitments)
- How the throughline question evolves (a new campaign may extend or
  transform the prior throughline rather than replacing it)
- Default state for characters without import data (the campaign must
  work for both new and returning characters)

### 6.2 Canon as Environmental Constraint

For campaigns engaging with the Legends timeline, canon events are
authored as **environmental anchors** — galactic-scale events that
occur in the galactic context layer and the anchor beats, but that the
player does not control.

**Design rules for canon integration:**

The player's agency exists at personal scale. They choose who to trust,
who to fight, who to save, and who to sacrifice. They do not choose
whether the Second Galactic Civil War happens.

Canon events create pressure, not predetermination. "Jacen Solo is
forming the GAG" is an environmental anchor that creates specific
choices for the player. It does not determine what the player does
about it.

The player's relationship to canon characters is shaped by play history.
An imported relationship with Jacen Solo means the GM has a state card
full of shared history. The prose reflects that history. The emotional
weight of canon events becomes personal because the player earned that
relationship through actual decisions.

Consequences are real and persistent. If the player sided with Jacen
during his fall and Jacen is subsequently killed, the player carries
that history into whatever comes next — mechanically (Morality drift,
Obligation to Jacen's memory or his enemies) and narratively (NPCs
remember, reputation echoes persist, the player's own interiority
reflects what they did).

### 6.3 Butterfly Effect at Personal Scale

Player actions do not rewrite the galactic timeline. They create
ripples at the scale the player operated — personal, social, local.

The Campaign Studio supports this through **world state variables** in
the campaign spine — named boolean or string values that track
significant player impacts and feed into the galactic context layer of
subsequent acts or campaigns.

**Example:** `helped_corellians_act2: true` causes the Legacy-era
galactic context to include "A Corellian senator remembers a favor from
the war years and has quietly blocked an inquiry into your current
activities." The game engine injects this into the GM's context. The
GM weaves it into the prose. The player feels their past actions
reaching forward.

### 6.4 Saga Layer: Sequel Spine Generation

Sections 6.1–6.3 handle the mechanical transfer of a character from one
campaign to the next — relationships, motivation tracks, world state
variables. But mechanical continuity is not creative continuity. When a
player finishes a campaign and wants a sequel, someone must generate the
sequel campaign spine: a new throughline question, new anchor beats, new
NPC arcs, a new galactic trajectory — all thematically coherent with
the prior campaign but narratively surprising. Having the player step
out of the story to manually author this spine breaks immersion. The
saga layer solves this by generating sequel spines through an automated
Writer's Room.

#### 6.4.1 The Problem: Why Single-Shot Generation Fails

Generating a sequel spine by simply prompting a cloud model with the
prior campaign summary will produce conservative, predictable results.
Five converging lines of research establish why:

**Knowledge aggregation.** LLMs collapse diverse human mental models
into a single centralized probability distribution during pre-training.
Independent generation sessions sample from this same distribution,
producing structurally similar outputs even when prompted differently.
The collective diversity gap is large: in controlled studies, 99
independent LLM sessions produced 88 unique idea combinations vs 206
for 99 humans.

**Seeding does not recover diversity.** Providing the prior campaign as
a diverse starting point produces zero improvement in downstream
diversity. The LLM's unified associative structure reasserts itself
regardless of the seed. This directly invalidates the naive approach of
"feed the prior campaign summary and expect diverse sequel paths."

**RLHF compression creates a safe attractor basin.** Alignment training
systematically reduces output entropy and semantic variety, pushing
models toward conservative, high-probability outputs. Explicit
creativity instructions ("be radically original") cannot escape this
basin. The more capable and aligned the model, the less naturally
diverse its outputs.

**Larger models are less variable.** Counterintuitively, model scaling
decreases output variability as larger models more strongly capture the
dominant mode. The frontier cloud models used for narrative generation
are exactly the worst case for natural diversity.

**Same-prompt generation is the worst case.** The diversity deficit is
largest when multiple outputs are generated from the same prompt — which
is precisely the saga generation scenario (same completed campaign →
multiple possible sequel spines).

These findings establish that the Writer's Room architecture is not an
optimization — it is architecturally necessary to overcome fundamental
properties of current LLMs.

#### 6.4.2 The Writer's Room Architecture

The saga layer generates sequel spines through a multi-stage pipeline
that combines five complementary intervention families. The pipeline
operates at design-time with no latency pressure, which means it can
use compute-intensive methods (structured search, multi-agent debate,
iterative evaluation) that the Game Engine cannot.

**Stage 1 — Persona Assignment (Knowledge Partitioning)**

Each "writer" in the room is assigned a heterogeneous ordinary persona
drawn from a large, diverse pool. Ordinary personas (a retired
politician, a veterinary technician, a marine biologist, a Zumba-loving
college student) function as sampling cues that push generation into
disparate regions of the model's knowledge space, achieving 2.6x the
between-session diversity of default LLM generation and exceeding human
diversity.

Design constraints for the persona pool:

The personas must be ordinary and heterogeneous. "Creative storyteller"
or "sci-fi author" personas are too densely interconnected in training
data to achieve real knowledge-space separation. The diversity comes
from the personas being different from each other, not from them being
creative.

The personas must not be Star Wars-specific. "A Mandalorian warrior" or
"a Jedi historian" would anchor generation to existing Star Wars
narrative patterns. The personas provide cognitive framing, not domain
expertise — the model already has Star Wars domain knowledge.

The pool should be large enough that repeated saga generation draws
different persona combinations. A minimum pool of 50+ personas is
recommended.

**Stage 2 — Divergent Generation with Denial Constraints**

Each persona-primed writer generates candidate sequel directions using
chain-of-thought prompting that explicitly requires revision for
distinctness. The CoT step breaks within-session fixation (the tendency
for early outputs to constrain subsequent generation), complementing
the persona's between-session partitioning effect. Combined persona +
CoT surpasses human diversity by 26% in controlled studies.

Critical design constraint: The prior campaign is NOT provided as input
during divergent generation. Knowledge augmentation from the prior
campaign suppresses diversity by biasing the model toward thematically
conservative extensions. The prior campaign enters the pipeline at
Stage 4 (evaluation), not here.

Denial constraints are applied during this stage to force exploration of
less typical sequel directions. Each writer is explicitly forbidden
from: repeating the prior campaign's primary conflict type, reusing the
prior campaign's resolution structure, defaulting to the most
narratively obvious sequel direction. These constraints push generation
into lower-probability regions of the output distribution.

**Stage 3 — Structured Search (Branching Exploration)**

Candidate sequel directions from Stage 2 are expanded through branching
search — the most promising candidates are elaborated into fuller spine
sketches, evaluated, and the best branches are expanded further while
weak branches are pruned. This tree/beam search approach achieves 4–7x
the quality of single-pass generation in controlled studies.

The search structure allows backtracking: a branch that initially
appears weak may be revisited if later evaluation reveals its
potential. This prevents premature commitment to safe, obvious sequel
paths.

The number of writers, candidates per writer, and search depth are
configurable parameters. The system is designed to degrade gracefully:
a single writer with a single candidate and no branching produces a
valid (if less diverse) sequel spine. As base models improve and become
more naturally diverse, the multi-agent overhead can be reduced.

**Stage 4 — Convergence: Debate, Critique, and Coherence Checking**

The prior campaign enters the pipeline at this stage. Surviving
candidate spines are evaluated for thematic coherence with the prior
campaign — throughline evolution, NPC arc continuity, galactic
trajectory consistency — while preserving the structural novelty
generated in Stages 1–3.

A critic agent (potentially the local model) challenges each candidate
on: coherence with the prior campaign's established narrative facts,
internal structural quality (well-formed anchor beats, viable NPC
trajectories, pressurable throughline question), and thematic
consistency with the import interface (Section 6.1).

This stage uses a debate/critique loop: the critic raises challenges,
the generating writer revises, the critic re-evaluates. Multi-agent
debate produces statistically significant improvements in novelty,
feasibility, and effectiveness over single-agent generation.

**Stage 5 — Evaluation and Selection**

Surviving candidates are evaluated using pairwise comparison with the
prior campaign as shared context. Pairwise comparison (rather than
isolated scoring) improves evaluation consistency from ICC 0.59 to
0.75.

Evaluation decomposes into three independent axes, reflecting the
empirical finding that these dimensions are orthogonal:

Structural quality: Is this a well-constructed campaign spine? Are the
anchor beats compelling, the NPC arcs viable, the throughline question
genuinely pressurable?

Novelty: Does this sequel go in a surprising direction? Does it avoid
the most obvious thematic extension of the prior campaign?

Diversity: Is this sequel meaningfully different from the other
generated candidates? (This axis applies to the candidate set, not to
individual spines.)

The top candidate is presented to the player as the sequel spine. In
Mode 3 (full collaboration), the player may review the top 2–3
candidates and select or modify. In Mode 1 (full blind), the top
candidate is used directly.

#### 6.4.3 Architectural Principles

**Prior campaign is context for convergence, not input for divergence.**
This is the most important architectural constraint. Feeding the prior
campaign into the generation phase suppresses diversity. The prior
campaign ensures coherence (Stage 4) — it does not drive ideation
(Stage 2).

**Diversity is engineered, not expected.** The cloud model's default
generation behavior will produce conservative, similar sequels across
playthroughs. Every stage of the pipeline contributes a specific
diversity mechanism: personas partition the knowledge space, CoT breaks
fixation, denial constraints block obvious paths, branching search
explores alternatives, and pairwise evaluation rewards distinctness.

**The pipeline degrades gracefully.** The Writer's Room works with N
writers where N ≥ 1. As base models become more naturally diverse, the
persona pool can shrink, the search depth can decrease, and the debate
rounds can reduce. The system should not hard-wire a specific agent
count or pipeline depth.

**Design-time compute is the Campaign Studio's advantage.** The Game
Engine operates under real-time single-pass constraints. The Campaign
Studio has no latency pressure. Saga generation can afford minutes of
compute per sequel spine because the player initiates it once per
completed campaign, not once per turn.

#### 6.4.4 Local Model Roles

The local Qwen model has two potential roles in the saga layer:

**Divergent structural ideation.** Research shows no proprietary model
advantage in divergent thinking tasks. The local model can generate the
initial divergent sequel directions in Stage 2 at zero API cost, with
the cloud model handling refinement in later stages where prose quality
and complex reasoning matter.

**Spine quality evaluation.** A trained 7B model outperforms frontier
models at creativity judgment in controlled studies. The local model
could serve as the pairwise evaluator in Stage 5, keeping the
evaluation loop fast and cost-free. This requires training data from
actual spine generation and is not a V1 deliverable, but the
architecture should reserve this capability.

#### 6.4.5 Saga Layer and Automation Modes

The saga layer interacts with the three automation modes:

**Mode 3 (full collaboration):** The Writer's Room generates 2–3
candidate sequel spines. The player reviews them, selects one, and
modifies it through collaborative editing. This is the primary use case
— the player stays in the story while benefiting from curated creative
options.

**Mode 2 (thematic steering):** The player provides a thematic
direction ("I want the sequel to explore betrayal" or "I want to move
to the Outer Rim") which serves as an additional constraint in Stage 2.
The Writer's Room generates within that thematic envelope.

**Mode 1 (full blind):** The Writer's Room generates and selects
autonomously. The player receives a sequel spine without reviewing
alternatives. This mode has an explicitly lower quality contract — the
single-candidate output may not match what a Mode 3 collaboration
would produce, but it preserves complete narrative immersion.

---

## 7. Non-Linear Spine Structures

The V1 campaign spine is linear: Act 1 → Act 2 → Act 3 → Act 4. The
Campaign Studio is designed to support alternative structures as
campaign authoring matures.

### 7.1 Hub-and-Spoke

A central hub location with multiple available story threads the player
can pursue in any order, converging on a final act.

**Spine representation:** Acts are tagged with prerequisites rather than
fixed sequence numbers. Act B requires Act A to be complete. Act C has
no prerequisites. Act D requires either B or C. The engine evaluates
prerequisites when presenting the next available act.

**Authoring challenge:** Anchor beats cannot assume a fixed prior
sequence. The Act 3 anchor must work whether the player completed Act B
before Act C or vice versa. This requires anchors designed around
accumulated state (NPC dispositions, information gathered, resources
spent) rather than specific prior events.

### 7.2 Parallel Tracks

Two simultaneous story threads that the player switches between. The
tension comes from competing demands on the player's time and resources.

**Spine representation:** Acts contain a `track` field ("primary" /
"secondary"). The engine alternates between tracks or lets the player
choose which to advance. The convergence point is an anchor beat that
requires both tracks to reach a specified progress threshold.

**Authoring challenge:** Each track must be independently compelling.
The convergence point must feel like a natural collision of the two
threads, not an arbitrary merge.

---

## 8. Design Decisions Deferred

**Deterministic seeding for reproducible generation.** When the Campaign
Studio generates a spine in Mode 1 or Mode 2, deterministic seeding from
author-provided parameters could enable partial re-generation ("I like
the world but want different NPCs"). The value depends on Campaign Studio
UX decisions not yet made. Filed for evaluation during Studio build.

**NPC voice generation.** Using the cloud model to generate NPC voice
notes from a brief character description. Useful for Mode 1 and Mode 2
where the author does not hand-write every NPC's speech patterns.

**Spine difficulty calibration.** A system for estimating the overall
difficulty curve of a campaign spine before runtime, based on the
authored anchor beats, expected check difficulties, and NPC opposition
patterns.

**Campaign rating and feedback.** A system for players to rate completed
campaigns and for that feedback to inform Campaign Studio generation in
Modes 1 and 2.

**Multi-model ensemble for saga generation.** Using different cloud
models as different "writers" in the saga layer's Writer's Room, with
each writer backed by a different LLM via OpenRouter. Research shows
that ensembles of different models approach human variability levels.
The current architecture is provider-agnostic via env vars and could
support this without structural changes. Deferred because persona + CoT
on a single model is the proven minimum intervention; multi-model
ensembles are a scaling lever, not a prerequisite.

**Trained local evaluator for spine quality.** Training the local Qwen
model as a specialized pairwise spine quality evaluator using data from
actual saga generation runs. Research shows trained 7B models outperform
frontier models at creativity judgment. Deferred because it requires a
corpus of generated spines with quality annotations, which does not
exist until the saga layer is operational.

**Persona pool curation and validation.** Assembling and testing the
50+ ordinary persona pool for the saga layer Writer's Room. The pool
must be empirically validated to confirm that different persona
subsets produce meaningfully different sequel spine directions.
Deferred to saga layer implementation phase.

---

## 9. Revision History

**v1.3 — Game Mechanics v1.5 cross-references (March 2026)**

1. **Section 1 updated.** Campaign spine contents list expanded to
   include new elements specified in Game Mechanics Document v1.5:
   starting loadouts per variant (§18), Force discovery probability
   (§16), XP base awards and bonus conditions per act (§14), time
   skip data with vignette libraries (§19), canon character extended
   profiles (§22), vehicle registry (§17), milestone windows (§14–16),
   and import interface mechanical detail (§20). "Does not contain"
   list updated with talent tree data, Force power data, and canon
   profile base data (stored centrally, referenced by spine).

   These additions expand the campaign spine schema but do not change
   the Campaign Studio's architecture. Spine authoring in Mode 3 now
   includes: XP calibration per act, vignette scene authoring for
   time skips, canon character profile creation for established
   characters, ship stat block authoring, and Force discovery
   probability tuning per era. All new authoring concerns are
   documented in the referenced Game Mechanics sections.

**v1.2 — Character funnel pivot (March 2026)**

1. **Section 2.5 rewritten:** Character Variant Design restructured for the
   character funnel (Timeline → Allegiance → Variant). Allegiance is now a
   first-class organizing layer — each campaign defines 2-4 allegiances, each
   containing 2-4 variants. Variants now carry `allegiance` and `career_type`
   fields. Authoring scale guidance added: 9 variants (3×3) is the
   recommended starting range, 4 (2×2) is minimum viable, 16 (4×4) is
   practical maximum. Career-type reuse across campaigns encouraged.

2. **Section 2.6 expanded:** Prologue Scene Design gains career- and
   allegiance-scoped scene library approach. Scenes carry `career_type` and
   `allegiance` scoping tags and a `library_reusable` flag. Recommended
   approach: 3 library scenes per career-allegiance combination plus 2
   campaign-specific scenes per variant.

3. **New Section 2.8 added:** Protagonist Integration Layer. Defines the
   split between fixed thematic spine (setting, era, conflict, act structure,
   anchor beats) and flexible protagonist integration (entry point, personal
   stakes, NPC relationship configuration, anchor beat framing). Establishes
   that anchor beats must be abstract enough to survive all integration layer
   variants. Integration layers are authored at design-time, not generated at
   runtime.

4. **Section 4 schema restructured:** Top-level structure now contains
   `allegiances` array instead of `character_variants` array. New Section 4.2
   (Allegiance Schema). Section 4.3 (Character Variant Schema) gains
   `allegiance`, `career_type`, and `integration_layer` fields. Section 4.4
   (Prologue Scene Schema) gains `career_type`, `allegiance`, and
   `library_reusable` fields. Sections 4.4–4.6 renumbered to 4.5–4.7.

**v1.1 — Saga layer (March 2026)**

Added Section 6.4 (Saga Layer: Sequel Spine Generation) based on a
five-paper research review covering LLM creativity, diversity
mechanisms, and multi-agent creative systems. Defines the Writer's Room
architecture for sequel spine generation: persona-primed divergent
generation with denial constraints, branching search, debate/critique
convergence, and pairwise evaluation with decomposed quality axes. Key
design constraint: prior campaign content enters during convergence
(for coherence), not during divergent generation (where it suppresses
diversity). Added three saga-related deferred items to Section 8.
Research evidence trail documented in STORYTELLER_V3_SAGA_RESEARCH_
FINDINGS.md.

**v1.0 — Initial document (March 2026)**

Created from Campaign Studio material previously scattered across the
Game Mechanics Document (Section 12), the Research Scoping Document
(Part 2), and design conversations about cross-era continuity and canon
constraint systems. Consolidates all Campaign Studio design into a
single document with three layers: creative methodology (Writers Room),
system design (automation modes, validation), and interface contract
(campaign spine JSON).

---

*Storyteller V3 — Campaign Studio Design Document v1.3*
*The bridge between creative vision and playable campaigns.*
