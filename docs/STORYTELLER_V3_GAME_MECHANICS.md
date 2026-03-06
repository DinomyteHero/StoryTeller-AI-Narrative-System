# Storyteller V3 — Game Mechanics Design Document

**Document version:** 1.8
**Project:** Storyteller V3
**Last updated:** March 2026
**Scope:** Systematic game design decisions that sit between the Vision
Document (creative intent) and the Implementation Document (architecture and
code). Each section addresses a specific design problem with a decision,
rationale, and implementation notes.

**Relationship to other documents:**
- **Vision Document** — answers *what the game should feel like*
- **Campaign Studio Document** — answers *how campaigns are created and validated*
- **Implementation Document** — answers *how the code is structured*
- **This Document** — answers *how the game mechanics actually work in practice*

---

## 0. Design Principles

Before the specific mechanics, four principles govern every decision in this
document. When two design goals conflict, these principles break the tie.

**Principle 1: The story is the reward.**
The player's primary motivation is narrative — discovering what happens next
as a consequence of what they did. Every mechanical system exists to make the
story feel more consequential, not to provide a separate reward track. If a
mechanic does not serve the story, it does not belong in V1.

**Principle 2: Invisible mechanics, visible consequences.**
The player should never need to understand a system to enjoy its effects. They
feel the world responding to them. They do not see the numbers producing that
response. Systems that require player understanding to function are designed
wrong for this format.

**Principle 3: Failure is interesting, not punishing.**
The FFG dice system guarantees that every outcome has narrative texture. The
game's job is to ensure that a string of bad rolls produces a compelling story
about a character under pressure — not a frustrating experience of a broken
system.

**Principle 4: Earned asymmetry.**
Two players making different choices should have meaningfully different
experiences. Not just different flavor text on the same outcome — different
available options, different NPC relationships, different information, different
story shapes. The choices must matter enough that the player can feel the
difference.

---

## 1. Core Engagement Loop

### The Problem

The Vision Document describes a page-turner reading compulsion. But reading
compulsion alone does not sustain a game. The player needs to feel that their
agency produces outcomes they *own* — that the story is theirs in a way that
a novel, however compelling, never is. Without a tangible feedback loop, the
game risks feeling like a very good story generator that the player happens
to be clicking through.

### The Design

The engagement loop operates on three interlocking timescales:

**Turn-level (immediate):** Each turn produces a visible consequence of the
player's choice. The prose explicitly reflects what the player did — not
generically, but specifically. If the player chose to observe from across
the street rather than enter the shop, the next passage opens from that
vantage point and reveals information only available from that position. The
player should be able to point to a sentence in the passage and say "that
happened because of what I chose." This is the micro-reward: I chose, and
the world moved.

**Arc-level (session):** Across 10-20 turns within an act, the player
accumulates visible changes to their situation. NPC dispositions shift in
ways the prose reflects — a character who was guarded in Act 1 speaks more
openly in Act 2 because of how the player treated them. Doors open and close
based on prior choices. Information the player gathered (or missed) in earlier
turns constrains or expands what is available now. The player should feel,
by mid-act, that this story could not have gone this way for anyone else.

**Campaign-level (long-term):** Across the full campaign, three concrete
feedback systems give the player evidence that their character's identity
has shaped the world:

1. **Reputation echoes.** NPCs the player has never met reference things the
   player did. A dockworker mentions "that Bothan who helped out Reeska's crew."
   An Imperial officer has a note in a file. The player's actions have traveled
   beyond the scenes where they occurred. This is not a reputation *score* — it
   is specific narrative callbacks to specific actions, delivered through NPC
   dialogue and environmental detail.

2. **Conditional path availability.** Choices accumulate into patterns, and
   patterns unlock (or foreclose) specific story paths. A player who has
   consistently prioritized people over profit may find an NPC offering them
   a leadership role that a self-interested player would never be offered. A
   player who has burned every bridge may find that the "call for help" option
   simply does not appear when they need it most. These are never announced.
   The player discovers them by their presence or absence.

3. **Motivation track movement.** Obligation decreasing, Duty increasing,
   Morality drifting — these produce prose-level changes that the player can
   feel even if they cannot name the mechanic. A character whose Obligation
   has dropped from 15 to 5 feels *lighter* in the prose — the interiority
   is less strained, the humor is less defensive, the world feels less like
   it is closing in. This is the most subtle feedback system and the most
   powerful one.

### Implementation Notes

Turn-level consequence reflection requires the GM narration prompt to include
an explicit instruction: "The opening of your passage must clearly reflect
the player's specific choice. Do not write a passage that could follow from
any choice." This is a Phase 3 prompt addition.

Arc-level accumulation is handled by the existing NPC state card system and
the context package's open threads tracking.

**Anti-positivity-bias instruction (prompt addition):** Empirical research
on LLM story generation (Nonaka & Perry, NeurIPS 2025 Workshop) demonstrates
a statistically significant bias: across 1,200+ stories and four LLMs,
character relationship networks are systematically skewed toward positive
dynamics compared to human-written stories (mean edge weight 0.235–0.659
for LLMs vs. −0.061 for humans). Left uncorrected, the cloud model will
default to writing NPCs as more cooperative and more uniformly supportive
than their mechanical states warrant.

The GM narration prompt includes an explicit counterbalance in the
`YOUR TASK` section: "NPC interactions must reflect their mechanical
disposition. NPCs with disposition below 0.5 should exhibit visible
friction, reluctance, conditional cooperation, or underlying tension — not
smooth alliance. NPCs with conflicted states (high competence respect +
low trust, or grudging cooperation) should express both dimensions
simultaneously. Avoid uniformly warm interactions unless the NPC state
explicitly warrants them. Conflict, tension, and friction between characters
are features of good storytelling, not problems to resolve."

This is a Phase 3 prompt addition alongside the turn-level consequence
reflection instruction above.

Campaign-level reputation echoes require a new lightweight data structure:
a **reputation log** in the session state that records notable player actions
in one-sentence summaries (e.g., "Helped Reeska's crew escape the customs
sweep without asking for payment"). The GM prompt receives the 3-5 most
recent reputation entries and is instructed to occasionally surface them
through NPC dialogue or environmental detail — not every turn, but often
enough that the player feels the world is paying attention.

#### 1.1 Reputation Echo Delivery Mechanism

**Population.** The reconciliation step (Section 26) produces a
`reputation_event` field per turn — a one-sentence summary of a notable
action that could reasonably be known beyond the immediate scene. Most
turns produce null. When non-null, the engine writes the event to the
`reputation_log` table with `faction_tags` (a JSON array of faction/
location identifiers that determine where the reputation travels, e.g.
`["smuggler_network", "nar_shaddaa_promenade"]`).

The reconciliation prompt includes guidance for when to generate a
reputation event: the action must have at least one witness (NPC present,
public location, or visible consequences) AND be significant enough that
someone would mention it to someone else.

**Selection.** Each turn, before context assembly, the engine scores
reputation log entries by relevance to the current scene: faction tag
overlap with scene NPCs/location (+3), recency (+0 to +2), novelty
based on `surfaced_count` (+0 to +2), and NPC connection to the event's
faction (+2). The top 3 entries scoring above a minimum threshold of 3
are selected. If no entries qualify, the block is omitted.

**Surfacing frequency.** A cooldown of 3 turns after a reputation echo
appears prevents systematic feeling. The cooldown is tracked via
`last_reputation_echo_turn` in the arc state.

**Prompt injection.** Selected entries are injected as a REPUTATION
ECHOES block in the narration prompt, within the STORY CONTEXT section:

```
REPUTATION ECHOES (use sparingly — not every turn):
The character's actions have traveled beyond the scenes where they
occurred. The following are things that people in this world may have
heard about:
{reputation_entries}

Do NOT reference all of these. Pick AT MOST one, and only if it fits
naturally — through NPC dialogue, overheard conversation, a reaction
from someone who recognizes the character, or environmental detail.
Most turns should NOT include a reputation echo. When you do include
one, it should feel like a surprise — the world remembering something
the player did.
```

When the GM uses an echo, the engine increments `surfaced_count` for
that entry via lightweight string matching against the narration.

**Cross-campaign.** Reputation entries persist through campaign imports
(Section 21.4). In a new campaign, older entries have lower recency
scores but can surface when faction/NPC connections match — producing
moments where the galaxy remembers the player across eras.

---

## 2. Failure States and Recovery Pacing

### The Problem

The Vision Document commits to "failure is failure, the dice are truth." This
is correct for narrative integrity. But accumulated failure in a tabletop RPG
is managed by the human GM reading the room — noticing when a player is
frustrated versus engaged-by-adversity and adjusting accordingly. The AI GM
cannot read the room. Without explicit guidance, a sequence of bad rolls
produces a mechanical death spiral: accumulated wounds and strain make
subsequent checks harder, which produces more failures, which produces more
wounds and strain, until the character is incapacitated and the story stalls.

### The Design

**Recovery pacing follows the two-beat rule:** After two consecutive turns
that produced net-negative outcomes (failure_threat or failure with Despair),
the GM must generate at least one choice on the next turn that does not
require a skill check. This is not mercy — it is pacing. Even in the worst
tabletop sessions, the GM provides moments to breathe. The player still faces
consequences from their failures, but they get a turn where success is
guaranteed and the only question is *which* safe action they choose.

**Strain recovery is narratively integrated:** FFG rules allow strain recovery
through rest, advantage spending, and cool/discipline checks. In Storyteller
V3, strain recovery happens between acts (a full night's rest recovers strain
to threshold) and during narrative downtime within acts. When the GM writes a
scene transition — moving from one location to another, a time skip of hours,
a quiet moment between crises — the system recovers 2 strain automatically.
This is not displayed mechanically. It is simply reflected in the prose:
the character feels less frayed, the interiority eases slightly.

**Wound recovery requires narrative action:** Unlike strain, wounds do not
heal passively. Recovery requires either medical attention (an NPC or the
player's own Medicine skill) or time (between-campaign recovery). A wounded
character remains wounded, and the prose reflects it — movement costs more,
decisions are colored by pain, the character's physical limits are present in
every scene. This maintains the weight of combat consequences while preventing
the death spiral through the strain recovery system.

**Incapacitation is a story beat, not a game-over:** If wounds reach the
wound threshold, the character is incapacitated — but this is narrated as a
dramatic moment, not a failure screen. The story continues from the
consequences of incapacitation: captured, rescued by an NPC, waking up in
an unfamiliar location. The campaign spine accommodates this by treating
incapacitation as a redirection rather than a termination. The player loses
agency for the duration of the incapacitation (one turn where the passage
describes what happens to them rather than what they do) and then regains it
in the new situation.

**The hidden mercy mechanic — difficulty calibration:** The local model's
check decision prompt already includes tension level from the arc state. This
document adds an additional input: **recent failure count**. When the player
has failed 2+ checks in the last 4 turns, the local model receives a note:
"The character is under sustained pressure. Prefer average difficulty over
hard. Reserve hard/daunting for actions that are genuinely reckless in
context." This does not remove difficulty — it biases the system toward the
lower end of the appropriate range. The player never knows. The effect is
simply that the story stops compounding punishment.

### Implementation Notes

The two-beat rule requires tracking the last two outcome quadrants in the
context package. This is already available through `recent_turns` in the
context assembly — the implementation adds a derived field
`consecutive_negative_outcomes` that the GM prompt uses.

Strain recovery on scene transitions requires a trigger in the turn
processing logic: when the GM's narration indicates a location change or
time skip (detectable via the choices or a simple heuristic), the system
applies automatic strain recovery before the next turn.

The difficulty calibration note is injected into the check decision prompt
template as an additional conditional block when the failure count exceeds
the threshold.

---

## 3. Combat and Action Sequence Abstraction

### The Problem

FFG Star Wars combat in tabletop is round-by-round tactical play: initiative
order, range bands, cover, maneuvers, actions, weapon qualities triggering on
advantage spending, critical injury tables. A single encounter might run 10+
rounds at the table. The prose-first, one-check-per-turn format cannot
accommodate this granularity without destroying the reading experience.

### The Design

Combat in Storyteller V3 is **resolved at the encounter level, not the round
level.** A blaster fight is not ten turns of "roll Ranged (Light)." It is one
to three turns where:

1. The player's choice determines the **shape** of the engagement — are they
   aggressive, defensive, tactical, evasive? Are they trying to win, to
   escape, to protect someone, to buy time?

2. A single skill check resolves the **outcome** of the engagement at that
   scale. The check uses the skill most relevant to the player's approach
   (Ranged (Light) for a direct firefight, Coordination for a running escape
   under fire, Leadership for directing allies, Cool for holding position
   under suppression).

3. The four-quadrant result determines how the engagement went and what it
   cost. Success with threat: you drove them off but took a hit. Failure with
   advantage: you couldn't hold the position but you spotted their commander
   and now you know who is running this operation.

**Extended action sequences** — ship chases, multi-stage infiltrations,
running battles across multiple locations — use a **beat structure** of 2-3
turns, each resolving one stage of the sequence:

*Example — Chase through Nar Shaddaa's maintenance corridors:*

Turn 1: The chase begins. The player chooses their escape route (up through
the ventilation system, down into the undercity, or through the crowded
market). A Coordination or Athletics check determines how the first stage
goes.

Turn 2: Consequence of Turn 1 + new complication. If they went through the
market, the crowd is both cover and obstacle. A new choice: blend into the
crowd and lose the pursuit, or use the crowd as cover for an ambush. The
check matches the new approach.

Turn 3 (if needed): Resolution. The sequence ends with a definitive outcome.
Escaped clean, escaped but compromised, caught, or — with a Triumph — turned
the tables entirely.

Each turn in a multi-beat sequence is a full 250-600 word passage with its
own choices. The player never feels like they are in "combat mode" — they are
making decisions in a story that happens to involve violence or pursuit. The
pacing within these passages shifts: shorter sentences, compressed paragraphs,
visceral interiority. The prose acceleration conveys urgency without the
mechanical overhead of round-by-round play.

**Critical injuries** use FFG's critical injury table but are resolved as
narrative consequences rather than mechanical debuffs. A critical injury from
a Triumph or Despair is described in the prose — a blaster bolt that scorches
across the ribs, a concussion from a falling bulkhead — and tracked in the
character state as a narrative tag that the GM incorporates into future
passages. The mechanical effect (if any) is simplified: minor critical =
1 setback die on physical checks until healed; major critical = specific
narrative constraint (e.g., "cannot use left arm" restricts certain choices).

**Weapon qualities and advantage spending** are abstracted into the GM's
narration. When a combat check produces net advantages, the GM decides
whether those manifest as weapon qualities (Stun, Knockdown, Pierce) or
situational benefits, based on what the character is wielding and what serves
the scene. The player never chooses to "spend 2 advantage to activate Stun."
The GM writes: "The stun bolt catches him square in the chest and he drops,
limbs locked, his blaster clattering across the deck plating."

### Implementation Notes

The GM narration prompt needs a **scene type tag** in the context package:
`scene_type: combat | chase | infiltration | social | exploration | introspection`. This
tag signals the GM to adjust prose pacing and to expect that the choices
may lead to a multi-beat sequence. The local model's check decision includes
the scene type when selecting skills and difficulty.

Multi-beat sequences require tracking **sequence state** — which beat the
player is on, what happened in prior beats of this sequence, and what the
possible resolution states are. This is a lightweight addition to the turn
memory: a `sequence` field that is `null` for normal turns and populated
during extended sequences.

Critical injury tracking is a new field on the character state:
`active_injuries: list[str]` containing narrative descriptions that the GM
prompt receives.

---

## 4. Galactic Context Layer

### The Problem

The Vision Document's Luceno voice target requires the world to feel inhabited
and operational independently of the player. The current architecture gives
the GM everything about the player's immediate situation but nothing about
the wider galaxy. Without this, Nar Shaddaa feels like a stage set rather
than a place that existed before the player arrived and will continue after
they leave.

### The Design

Each act in the campaign spine includes a `galactic_context` field: 2-4
sentences of wider-universe state that is not directly about the player but
that presses on their situation. This context is injected into the GM's
narration prompt alongside the existing story context.

*Example for The Nar Shaddaa Job, Act 1:*

> Imperial customs interdiction has tightened across the Y'Toub system
> following a Rebel supply intercept at Nal Hutta. Hutt Council territorial
> disputes between Vossk's faction and the Besadii clan have made landing
> clearances unpredictable — bribes that worked last month now go to the wrong
> people. An unrelated freighter explosion at Dock 14 yesterday has every
> security team on the Promenade running nervous.

None of these are plot points. The player may never interact with the Besadii
dispute or the Dock 14 explosion directly. But the GM has them, and a good
prose model will use them: the customs scan lingers longer than usual, a
dockworker mentions Dock 14 in passing, Vossk's intermediary is distracted
by clan politics when the player expected their full attention. The world
breathes.

**Forward-echoing instruction:** The GM narration prompt includes an explicit
craft instruction: "When introducing environmental or NPC details, prefer
details that could become relevant later over details that are purely
atmospheric. Plant seeds. Not every seed needs to grow — but the ones that
do should feel like they were always there."

**Consequence-at-scale instruction:** The GM narration prompt includes:
"When the player makes a choice with significant social or political
implications, within the next 2-3 turns, show at least one moment where the
ripple of that choice has reached beyond the immediate scene — a rumor
traveling, an NPC reacting to secondhand information, an environmental shift
that reflects what the player set in motion."

### Implementation Notes

`galactic_context` is a new string field in the campaign spine JSON, per act.
The context package assembly in `gm/context.py` injects it into the prompt
alongside `situation` and `location`.

The forward-echoing and consequence-at-scale instructions are additions to
the narration prompt template (`gm/prompts/narration.txt`), added to the
`YOUR TASK` section.

---

## 5. Psychometric Prologue — Inference Design

### The Problem

The Vision Document describes a multi-stage character creation system: the
player navigates a character funnel (Timeline → Allegiance → Variant) that
narrows the galaxy-wide possibility space into a specific protagonist, then
a 3-5 scene psychometric prologue refines the selected variant along four
behavioral axes to produce a specific mechanical profile, motivation subtype,
throughline question, and narrative voice. The funnel ensures the player
arrives at the prologue with a character concept they chose and a faction
context they care about. The prologue does not infer the character from
scratch — it determines *what kind of this person* the player is within the
variant's constrained space. This design needs a concrete inference model
before implementation, or the refinement will either feel meaningless (every
smuggler plays the same) or overreach (the prologue contradicts the variant
the player chose).

### The Design

**V1 scope: Keth Varso is pre-built. The prologue system is not built in V1.**
This section exists to document the design for the version where it is built,
so the architecture does not preclude it.

**The inference operates on three layers, in order of difficulty:**

**Layer 1 — Behavioral archetype (easiest to infer).**

Each prologue scene presents 3-4 choices. Each choice is pre-tagged by the
campaign designer with behavioral dimensions — not visible to the player, not
generated by the AI:

- **Approach axis:** Direct (confronts problems head-on) ↔ Indirect
  (maneuvers around problems)
- **Social axis:** Trusting (extends goodwill, builds relationships) ↔
  Guarded (self-reliant, information-conservative)
- **Risk axis:** Bold (accepts uncertainty for potential gain) ↔ Cautious
  (minimizes exposure, preserves options)
- **Moral axis:** Principled (acts on values even at cost) ↔ Pragmatic
  (acts on outcomes regardless of method)

Three scenes with 3-4 choices each produce 3 data points per axis — enough
to identify a behavioral cluster. The system does not need perfect resolution.
A player who is 60% Direct / 40% Indirect gets a character who leans Direct
but has moments of subtlety. That ambiguity is a feature, not a limitation.

Prologue scenes may be drawn from a **career- and allegiance-scoped library**
rather than authored per specific named variant. A "smuggler prologue" scene
library contains scenes that test the behavioral axes through situations
relevant to smuggler characters. The campaign author selects or authors
scenes appropriate to the variant, but scenes designed for the same career
type within the same allegiance can be shared across campaigns. This reduces
authoring overhead as the funnel's combinatorial space grows.

**Layer 2 — Mechanical profile (moderate difficulty).**

The behavioral archetype maps to a characteristic and skill profile through
a hand-authored mapping table. This is not LLM-generated — it is designed
by the campaign author and validated before deployment. The player's career
is already set by their variant selection in the funnel — Layer 2 determines
the stat distribution *within* that career.

The mapping table is scoped by **career type**, not by specific named variant.
A "smuggler" mapping table works for any smuggler variant regardless of which
campaign or allegiance produced it. This is the key scalability mechanism:
the funnel's combinatorial space does not require a proportional increase in
mapping tables, because the career type is the mechanical grouping unit.

*Mapping example (simplified, for a Smuggler career type):*

A Direct + Guarded + Bold + Pragmatic smuggler maps to a profile emphasizing
Agility and Cunning, with skill ranks in combat and skulduggery — the
smuggler who shoots first. An Indirect + Trusting + Cautious + Principled
smuggler maps to Cunning and Presence, with ranks in negotiation and
streetwise — the smuggler who talks their way through.

The mapping does not produce a single fixed profile per cluster. It produces
a **profile range** — a set of characteristics and skills with 1-2 points
of variance that are resolved by the specific choices within the cluster.
Two Direct + Bold players may differ on Brawn vs. Agility based on whether
their directness manifested as physical confrontation or quick decisive
action.

**Layer 3 — Narrative identity (hardest to infer, most valuable).**

Motivation subtype, throughline question, and voice notes are inferred by the
cloud model from the full set of prologue choices. The primary motivation track
(Obligation, Duty, or Morality) is already set by the character variant — Layer
3 determines the specific *form* it takes (e.g., Obligation: Debt vs.
Obligation: Family) and produces the throughline question and voice notes. This
is the one inference step that requires LLM judgment. The cloud model receives:
the variant definition, the scene descriptions, the choices available, and the
choices the player made. It returns: a motivation subtype (from the variant's
list of possible types), a seed value, a throughline question, and 2-3
sentences of voice notes.

This is a single cloud call. It runs after the prologue concludes, before the
main campaign begins. The player experiences a brief transition — perhaps a
hyperspace jump or a time-skip — during which the inference runs. The result
is validated by the system (motivation subtype must be from the variant's
`possible_types` list, throughline question must be a question, voice notes
must not exceed 100 words) and injected into the character state.

**Adaptive depth works as described in the Vision Document:** 3 scenes
minimum, 5 maximum. After each scene, the system evaluates signal strength
across the four behavioral axes. If all four axes show a clear majority
direction (≥2/3 data points consistent), the prologue ends. If any axis is
ambiguous (50/50 split or no data), a targeted scene is generated that forces
a choice specifically along the ambiguous axis.

The signal evaluation is algorithmic, not LLM-based. It is a simple count
of axis-tagged choices.

### Implementation Notes

The prologue system requires: pre-tagged prologue scene data (campaign
author responsibility, potentially drawn from a career-scoped scene library),
a behavioral axis scoring function (pure Python), a hand-authored mapping
table from clusters to mechanical profiles scoped by career type (JSON data
file), and one cloud LLM call for Layer 3 inference.

The prologue scene data format extends the campaign spine JSON with a
`prologue` section containing scenes, choices, and per-choice axis tags.
Scenes reference a `variant_id` but may also carry a `career_type` tag
that allows scene reuse across variants of the same career within the
funnel's allegiance structure.

The character funnel (Timeline → Allegiance → Variant) is a Campaign Studio
and frontend concern. The Game Engine receives the final variant in the
campaign spine JSON and does not need to know the funnel path that produced
it. However, the campaign spine format should include the `allegiance` field
on each variant for context package assembly and NPC disposition calibration.

This is backlog work — not V1. But the character model, the campaign spine
format, and the context package should not contain assumptions that preclude
it.

---

## 6. Session Resume Experience

### The Problem

The Implementation Document handles session persistence — the database
survives process restarts, the session is recoverable. But it does not
address the *player's* recall. When a player returns after three days, they
need to re-enter the story. A wall of prose from their last turn is
disorienting. A blank screen with "continue?" is worse.

### The Design

When a player resumes a saved session, the UI presents a **"Previously..."
passage** — a brief, 80-150 word summary of where the story stands, written
in the same second-person present-tense voice as the game itself. This is
not a mechanical state dump. It is a narrative re-entry point.

*Example:*

> Previously...
>
> You landed on Nar Shaddaa with hot cargo and a missing contact. A bluffed
> customs scan got you through — but the officer remembered your face. Doss's
> last known location led you to a data broker's shop in the Red Sector, its
> door forced open with carbon scoring still warm on the frame. You are
> standing across the street, watching, deciding whether to go in.

This passage is generated by the cloud model from the session's compressed
memory and the most recent uncompressed turns. It is a single cloud call
that runs when the session is loaded, before the player makes their next
choice. The last line of the summary should describe the player's current
situation and end at the decision point — reconnecting them to the moment
where they left off.

After the summary, the UI displays the most recent set of choices (from the
last turn the player completed). The player re-enters the game by making
their next choice. If they want to re-read the full last passage, it is
available via a "show last passage" control.

### Implementation Notes

The resume summary is generated by a call to the cloud model with a dedicated
prompt template (`gm/prompts/resume_summary.txt`). The prompt receives: act
summaries, recent turns, and the last set of choices. The response is
validated for word count (80-150 words) and cached in the session table so
it does not require a new cloud call on subsequent loads of the same state.

The resume experience is a Phase 6 (frontend) concern for the UI, but the
summary generation is a Phase 3 addition to `cloud_gm.py`. The endpoint is
a Phase 5 addition.

---

## 7. Player Onboarding and the Invisible Mechanics Problem

### The Problem

The Vision Document commits to fully invisible mechanics — the player never
sees "Deception check" or "Success with Threat" in the prose. This is the
right aesthetic choice. But it creates a potential frustration loop: a player
who does not know skill checks are occurring cannot develop intuition about
risk. They may perceive repeated failure as a broken AI rather than an honest
dice system. They may never discover the dice panel exists.

### The Design

**First-check teaching moment:** The first time a skill check occurs in a
session (typically Turn 1 or 2), the dice panel auto-expands after the
narration renders. A brief, one-time tooltip appears: "Your choices sometimes
involve skill checks resolved by dice behind the scenes. Expand this panel
anytime to see what happened." The tooltip is dismissible and never appears
again.

**Subtle risk signaling in choice text:** Choices that trigger skill checks
include a subtle textual cue — not a skill name, but a signal of uncertainty
in the character's interiority. Compare:

*No check:* "Head back to the ship and lock down the cargo hold."
(Certain outcome — the player is doing something straightforward.)

*Check involved:* "Try to talk your way past the checkpoint — the uniform
might not hold up to a second look, but confidence has gotten you through
worse."
(Uncertain outcome — the character's own doubt signals that this might not
work.)

This is not a mechanical tag. It is a writing convention in the choice text
that the GM prompt enforces: choices requiring checks are written with
language that conveys risk, while choices without checks are written with
language that conveys certainty. The player develops an intuition for risk
without ever seeing a skill name.

**Post-check prose reflection:** After a check resolves, the narration
includes at least one sentence that implicitly communicates the outcome
quadrant's texture. Not "you succeeded but something went wrong" — that is
mechanical language. Instead: "The officer waves you through, but his eyes
follow you three steps longer than they should." The player learns to read
the outcome space through repeated exposure to the narrative pattern.

### Implementation Notes

The first-check tooltip is a Phase 6 frontend feature — a one-time UI
element triggered by the first turn response that includes dice data.

The risk signaling convention is an addition to the GM narration prompt:
"When generating choices, write choices that require a check with language
that conveys uncertainty or risk from the character's perspective. Write
choices that do not require a check with language that conveys confidence
or certainty."

---

## 8. Replayability

### The Problem

The Vision Document does not discuss replayability, and for V1 (a single
pre-built character on a single campaign) it does not need to. But the long
vision — era campaigns, the psychometric prologue, career diversity — assumes
players will replay. The question is whether the authored spine allows
genuinely different experiences or whether replays feel like the same story
with different flavor text.

### The Design

Replayability in Storyteller V3 comes from four sources, layered from
highest to lowest impact:

**Source 1: Funnel-driven divergence.** The character funnel (Timeline →
Allegiance → Variant) means the same campaign spine supports fundamentally
different protagonist types. A player who enters The Nar Shaddaa Job as a
Criminal-aligned smuggler and one who enters as an Empire-aligned defector
experience structurally different stories despite sharing the same thematic
spine. The protagonist integration layer — the part of the campaign that
adapts to who the player is — reshapes entry points, NPC relationships,
starting situations, and personal stakes. This is the highest-impact
replayability source because it produces the most visible differences from
the first moment of play.

**Source 2: Character-driven divergence.** The same authored anchor beat
plays out differently based on who the character is. The Act 2 anchor
"obligation_triggered" in The Nar Shaddaa Job is the same structural beat —
Vossk's people arrive — but a character whose prologue established them as
Trusting + Principled faces a fundamentally different scene than one
established as Guarded + Pragmatic. The NPC's approach changes. The available
choices change. The player's own instincts produce different decisions. The
spine is the same; the flesh is different.

**Source 3: Dice-driven variation.** The FFG dice system produces genuinely
different outcomes on the same choices. A player who makes identical decisions
across two playthroughs will get different dice results, which produce
different narrative outcomes, which change NPC states and available
information, which alter the choice landscape for subsequent turns. By
mid-Act 2, even identical choices have diverged significantly.

**Source 4: Authored variation points.** Specific moments in the campaign
spine include **branch seeds** — points where the campaign data provides 2-3
possible versions of a scene or NPC state that are selected based on player
behavior patterns. The Vision Document already describes one: Doss's fate is
randomly determined from three options (arrested, sold out, in hiding). This
principle extends to other key moments: the identity of the mysterious comm
voice, the contents of the cargo, which faction makes the first aggressive
move in Act 3. These are not branching paths in the traditional sense — the
anchors remain the same. They are variation in the *texture* of the path
between anchors.

**What this means for campaign design:** Campaign spines should be designed
with replayability as a constraint. The fixed thematic spine needs anchor
beats robust enough to work with multiple allegiance entries and character
archetypes. The protagonist integration layer needs enough depth that
different funnel paths produce genuinely different experiences, not cosmetic
reskins. Key NPCs need motivations that produce different interactions based
on player allegiance, behavior, and character type. At least 2-3 authored
variation points per campaign provide additional texture differences across
replays.

### Implementation Notes

Source 1 is handled by the protagonist integration layer in the campaign
spine — different allegiance entries produce different variant frameworks,
starting situations, and NPC relationship configurations. This is Campaign
Studio authoring work.

Source 2 is handled by the existing architecture — character state and NPC
state cards already shape the GM's output.

Source 3 is inherent to the dice system.

Source 4 requires an extension to the campaign spine format: `variation_points`
that specify conditions and alternative scene/NPC configurations. These are
selected during session creation or at the relevant turn, based on a
combination of random selection and player behavior pattern matching.

This is post-V1 design work. The V1 campaign spine should include at least
the Doss fate variation to validate the mechanism.

---

## 9. Obligation, Duty, and Morality — Mechanical Operation

### The Problem

The Vision Document describes the three motivation tracks eloquently but
narratively. This section specifies how they actually work as game systems —
the hidden rolls, the trigger conditions, the mechanical effects, and how the
GM prompt uses them.

### The Design

**Obligation (Edge of the Empire)**

At the start of each act, the system generates a random number between 1 and
100. If the number falls at or below the character's current Obligation value,
that Obligation activates for the act.

When activated:
- The character's strain threshold is reduced by 2 for the duration of the act
- The arc state includes `obligation_active: true` and `obligation_type: "Debt"`
  (or whichever type applies)
- The GM prompt receives: "The character's Obligation ({type}) is active this
  act. Weave pressure related to {type} into the narrative — not as a direct
  confrontation, but as environmental tightening. The character feels it before
  they understand its source."

When not activated:
- The GM prompt receives nothing about Obligation. It exists as background
  pressure only, mentioned if narratively relevant but not mechanically imposed.

Obligation decreases when the player takes actions that address it. The
amount of decrease is determined by the significance of the action: small
steps (acknowledging the debt, making a partial payment) reduce by 1-2;
major confrontations (directly negotiating with the creditor, taking a job
specifically to pay it off) reduce by 3-5. These reductions are tagged by
the GM or by the campaign spine at specific anchor beats.

**Duty (Age of Rebellion)**

Same d100 roll at act start. When the number falls at or below the Duty
value, the character's Duty activates.

When activated:
- The character's wound threshold *increases* by 1 for the act (representing
  heightened resolve)
- The arc state includes `duty_active: true` and `duty_type: "Intelligence"`
- The GM prompt receives: "The character's Duty ({type}) is active. Present
  an opportunity aligned with {type} that competes with the character's
  current objective. The opportunity is real and meaningful — but pursuing it
  costs something."

Duty increases when fulfilled — the amount determined by significance,
mirroring Obligation's decrease scale.

**Morality (Force and Destiny)**

Morality does not activate per-act. It accumulates and resolves per-act.

During the act, the system tracks **Conflict** — a hidden value incremented
when the player makes choices tagged as morally costly. Tagging is done by
the campaign spine at variation points and by the local model during check
decisions (a new field: `moral_weight: 0-3` where 0 = no moral dimension,
1 = minor, 2 = significant, 3 = severe).

At the end of each act:
- The system rolls 1d10
- If Conflict > roll: Morality decreases by (Conflict - roll)
- If Conflict ≤ roll: Morality increases by (roll - Conflict)
- Morality is clamped between 0 and 100

The GM prompt always receives the current Morality value and a label:
- 71-100: "Light side dominant — moments of calm, instinctive compassion,
  the Force responds gently"
- 41-70: "Grey — conflicted, the Force is present but uncertain, both
  impulses are real"
- 0-40: "Dark side dominant — anger is efficient, the Force responds to
  demand, compassion feels like weakness"

### Implementation Notes

Obligation and Duty activation rolls are generated at session creation (for
Act 1) and at act transitions. Results are stored in the session table.

Conflict tracking is a new field on the turn record: `conflict_earned: int`.
The local model's check decision response schema adds `moral_weight: int`
(0-3). The act summary includes total Conflict and the Morality resolution
roll.

The Morality label is injected into the GM prompt as a tone modifier — not
a directive to write the character as evil or good, but a signal about the
character's internal relationship with the Force.

---

## 10. Scene Type Classification and Pacing

### The Problem

The GM needs to adjust prose pacing based on what kind of scene is occurring.
A combat scene, a social encounter, an exploration sequence, and a quiet
character moment all require different sentence rhythms, paragraph lengths,
and information densities. The current architecture does not provide the GM
with this signal.

### The Design

The local model's check decision is extended to include a **scene type
classification** — a lightweight tag that the GM prompt uses to calibrate
pacing:

- **`combat`** — Short sentences, compressed paragraphs, visceral interiority.
  Passage length trends toward 250-350 words. Choices are immediate and
  action-oriented.
- **`chase`** — Similar to combat in pacing but with a movement/escape focus.
  The prose conveys speed and spatial awareness. 250-400 words.
- **`social`** — Dialogue-forward, NPC voice prominent, subtext matters more
  than action. 350-500 words. Choices involve what to say, what to reveal,
  what to withhold.
- **`exploration`** — Worldbuilding breathes. Environmental detail is rich.
  The character observes and interprets. 400-600 words. Choices involve where
  to go, what to examine, how to approach.
- **`introspection`** — Rare. Used for moments of character reflection,
  typically at act boundaries or after major events. The character's
  interiority dominates. No check occurs. 300-500 words. Choices involve
  internal resolution rather than external action.

The scene type is not a mode switch — it is a pacing signal. The GM blends
types naturally. A social scene that escalates into combat shifts pacing
mid-passage. An exploration scene that reveals something threatening
compresses toward the end.

### Implementation Notes

Scene type is classified by the local model as part of the check decision
response. The JSON schema adds: `"scene_type": {"type": "string", "enum":
["combat", "chase", "infiltration", "social", "exploration", "introspection"]}`.

The GM narration prompt receives the scene type in the context package and
includes pacing guidance per type in the `YOUR TASK` section.

### Scene-Type-Aware Context Package Assembly

The scene type tag controls more than prose pacing — it also modulates
which context package fields are emphasized in the cloud model's prompt.
This is a prompt assembly routing decision, not a change to the
`ContextPackage` class or the NPC state cards. All fields remain populated
regardless of scene type. The change is in `_build_prompt`.

**The finding that motivates this:** Research on KG-assisted LLM story
generation (Pan et al., IJHCI 2025; N=15 user study with Llama 3.1 8B)
demonstrates a statistically significant divergence in how structured state
representations affect narrative quality. Structured state significantly
improves kinetic narratives (p=0.039) — characters, pace, structure, and
coherence all benefit from dense entity-relationship data. But structured
state trends negatively for introspective narratives (p=0.07) — participants
report prose becomes "too literal," pacing becomes "repetitive and
structurally rigid," subtext is rendered as explicit statements, and
ambiguity collapses into declarative entries. The explanation: externally-
driven narratives map cleanly onto structured representations, while
internally-driven narratives degrade when the model treats structured data
as literal constraints rather than atmospheric context.

This maps directly onto the existing scene type system.

**Kinetic scenes (`combat`, `chase`, `infiltration`) — foreground mechanical
state:**

- Full weight: NPC mechanical state (disposition numeric, knowledge lists,
  motivation, last seen turn), spatial/location detail, equipment and injury
  status, dice result block, active sequence state
- Standard weight: recent turns, story summary, arc state, open threads
- Reduced weight: character voice notes, throughline question elaboration

**Transitional scenes (`exploration`) — balanced emphasis:**

- Full weight: location detail, galactic context layer, NPC knowledge states
  (information asymmetry drives exploration), open threads
- Standard weight: all other fields at normal inclusion

**Reflective scenes (`social`, `introspection`) — foreground motivational
and relational context:**

- Full weight: NPC voice/speech notes, NPC motivation, character voice notes,
  throughline question, morality drift state (if Force-sensitive), prose
  diagnostic (when implemented — especially Dimensions 2 and 3)
- Standard weight: recent turns, story summary, arc state, open threads
- Reduced weight: NPC mechanical disposition (single word — "hostile,"
  "wary," "neutral" — not numeric), NPC knowledge lists (condensed to single
  most relevant item per NPC), equipment/injury status (only if narratively
  relevant), spatial detail (minimal unless thematically significant)

**Implementation:** `_build_prompt` accepts `scene_type: str` (already
available from the local model's check decision) and selects a prompt
assembly profile: `kinetic` for combat/chase/infiltration, `balanced` for
exploration, `reflective` for social/introspection. Each profile controls
which NPC fields are included in `build_npc_block()`, whether character
voice notes are prominent or abbreviated, whether the throughline question
gets its own section or is folded into the arc state line, and how much
spatial/equipment detail is rendered. The simplest implementation is a
conditional in `_build_prompt` that selects between two or three prompt
template variants, or a single template with conditional sections.

**Token budget rationale:** The goal is not to reduce total tokens (though
that may be a side effect for reflective scenes). The goal is to shift the
signal-to-noise ratio. For kinetic scenes, mechanical state IS signal. For
reflective scenes, mechanical state is noise that competes with the voice
notes and motivational context the prose model needs for good interiority.

**What this does NOT change:** The `ContextPackage` class (all fields remain
populated), the NPC state cards (always track full mechanical state), the
local model's check decision (scene type classification logic unchanged),
the prose diagnostic (runs identically regardless of scene type), the
distillation data (`context_json` stores the full package regardless of what
was sent to the cloud model).

**Priority:** Late-V1 or early post-V1 refinement. The scene type tag
infrastructure and ContextPackage class already exist. This is a routing
decision in context assembly, not a new system.

---

## 11. Multi-Session Campaign Continuity

### The Problem

The Vision Document describes campaigns spanning dozens of sessions across
weeks or months of real time. The Implementation Document handles within-
session persistence, but campaign continuity across sessions — where the
player returns after days or weeks — requires specific design for: state
integrity, narrative coherence, and the player's evolving relationship with
their character.

### The Design

**Between-session state is frozen at the last completed turn.** The session
table stores the full arc state, character state, and NPC states as of the
last turn. When the player returns, the state is exactly as they left it.
No time passes in the fiction between sessions unless the player was at an
act boundary.

**Act boundaries are natural save points.** The game encourages (but does
not require) ending a session at an act boundary. When the player reaches
an act boundary, the UI presents a natural stopping point: "End of Act 1 —
The Approach. Continue?" If the player stops here, the between-act processing
runs: Obligation/Duty check for the next act, strain recovery, Morality
resolution. When they return, the "Previously..." summary covers the
completed act and the next act begins fresh.

**Mid-act saves are fully supported.** The player can stop at any turn. The
resume experience (Section 6) handles re-entry. Between-act processing does
not run until the act boundary is actually reached.

**Character state drift is tracked.** Each act summary includes a one-sentence
note on how the character's behavioral patterns have shifted (or not) during
that act. This provides the GM with a character development arc that persists
even after individual turns are compressed. Example: "Act 1: Keth prioritized
finding Doss over managing his Obligation. Pattern emerging: loyalty to
individuals over institutional pressures."

### Implementation Notes

Act boundary detection is handled by the arc state's `act_progress` field.
When progress reaches 1.0 (determined by the campaign spine's anchor
completion logic), the system triggers between-act processing.

Character drift notes are generated by the compression system (Phase 4,
`state/memory.py`) — an addition to the compression prompt that asks for
a behavioral pattern observation alongside the event summary.

---

## 12. Design Decisions Deferred to Post-V1

The following design questions are acknowledged but explicitly not resolved
in this document.

**Multiplayer.** The Vision Document describes a single-player experience.
Multiplayer (shared universe, cooperative play, or competitive play) is a
fundamentally different design problem. Deferred entirely.

**The psychometric prologue.** Design is documented in Section 5 of this
document. Character variant design and prologue scene authoring are documented
in the Campaign Studio Design Document (Sections 2.5–2.6). Implementation is
deferred. V1 uses a pre-built character.

**Campaign generation.** Authoring new campaign spines — either manually or
with LLM assistance — is documented in the Campaign Studio Design Document,
including automation modes, validation systems, and the campaign spine JSON
format specification.

**Campaign Studio validation systems.** NPC coherence validation, relationship
network validation, Mode 1 minimum viable input specification, campaign spine
validation audit, and campaign spine schema contract are all documented in
the Campaign Studio Design Document (Sections 5.1–5.4).

**Items now fully designed in this document:**

The following items were previously deferred and are now resolved in
Sections 14–22:

- Character advancement and XP (Section 14)
- Talent trees (Section 15)
- Force mechanics (Section 16)
- Vehicle and starship encounters (Section 17)
- Equipment and inventory (Section 18)
- Time skip mechanics (Section 19)
- Cross-era character progression (Section 20)
- Large-scale NPC management (Section 21)
- Canon character voice fidelity (Section 22)
- Destiny Point pool (Section 23)
- Semantic memory and choice extraction (Section 24)
- NPC emotional state (Section 25)
- Post-turn state reconciliation and narrative pacing (Section 26)

---

## 13. Prose Diagnostic Signal

### The Problem

Long AI-generated sessions exhibit a structural risk: prose staleness. The
Vision Document identifies this implicitly — the page-turner pull requires
variety in sensory detail, paragraph rhythm, and emotional register. The
LLM Evaluation Document identifies it explicitly as a quality concern for
the distillation pipeline. But the current architecture provides no
mechanism for the system to detect when the cloud model's output is
trending toward repetitive patterns, nor does it detect when NPC behavior
in the prose drifts from their mechanical state.

Three empirical findings from external research converge on this problem:

1. MiniMax's production RP system uses a periodic quality auditor that
   scans for surface errors, deep logic failures, and repetition, then
   intervenes. Their approach rewrites previous passages — inapplicable
   here because the player already read them. But the *detection* component
   is transferable.

2. Narrative logic research (Zhang & Long, COLING 2025) demonstrates that
   tracking per-character action-emotion chains and flagging discontinuities
   significantly improves coherence. When a character's described actions
   are inconsistent with their emotional state, the narrative has a logic
   gap.

3. Large-scale network analysis of LLM-generated stories (Nonaka & Perry,
   NeurIPS 2025) proves a statistically significant positivity bias:
   LLMs consistently generate more positive, less conflict-driven character
   dynamics than human authors. This bias is structural, not prompt-
   dependent — it manifests across all four LLMs tested.

### The Design

A lightweight local-model call runs once per turn, scanning the last 3–4
uncompressed passages and the current NPC state cards. It produces a
structured JSON diagnostic that is injected into the cloud model's context
package as an anti-staleness and anti-drift signal.

**The diagnostic checks three dimensions:**

**Dimension 1 — Prose pattern detection.** Which sensory channels (visual,
auditory, tactile, olfactory) dominated recent passages. Whether paragraph
rhythm has been repetitive (e.g., three consecutive long-short-long
patterns). Whether passage openings have been similar. Output example:
"Last 3 passages led with visual. No auditory detail in 4 turns. Paragraph
rhythm uniform."

**Dimension 2 — NPC action-emotion coherence.** Whether the most recent
passage described an NPC behaving inconsistently with their mechanical
state. If an NPC's disposition is hostile (< 0.3) but the prose described
cooperative behavior, or if an NPC's motivation should drive resistance
but the prose showed compliance — the diagnostic flags it. Output example:
"[NPC name] described as helpful in last passage. Disposition: 0.25
(hostile). Flag: action-emotion inconsistency."

**Dimension 3 — Relationship polarity tracking.** Whether the last several
passages have been uniformly positive in NPC interactions despite the
presence of hostile or conflicted NPC states. Output example: "Last 4 NPC
interactions: all positive tone. 2 of 4 NPCs have disposition < 0.5.
Flag: positivity drift."

The cloud model's narration prompt receives this diagnostic in the context
package and is instructed: "The prose diagnostic below identifies patterns
in recent passages. Vary your approach to address any flagged issues. Do
not mention the diagnostic — use it to inform your creative choices."

**What the diagnostic does NOT do:** It does not rewrite previous passages.
It does not generate prose. It does not override the cloud model's creative
output. It only provides awareness of patterns the cloud model should
vary from.

### Implementation Notes

The prose diagnostic is a second local model call per turn. The prompt is
short — it receives the last 3–4 passages (already available in the
uncompressed turns) and the NPC state cards (already in the context
package). It returns structured JSON matching a defined schema.

The call runs in parallel with the check decision call (also a local
model call). On RTX 4070 with Qwen3.5:9B, this adds ~1–2 seconds if
sequential, ~0 additional latency if parallelized with the check decision.

The context package schema includes a `prose_diagnostic` field. In V1,
this field is null — the diagnostic system is not built in V1. But the
schema reservation ensures the addition is not a structural change later.

**JSON schema for the diagnostic output:**

```json
{
  "sensory_channels_recent": ["visual", "visual", "visual"],
  "rhythm_note": "uniform long-short-long",
  "opener_similarity": "3 of 4 passages opened with location description",
  "npc_coherence_flags": [
    {
      "npc": "Vossk",
      "described_behavior": "cooperative",
      "mechanical_disposition": 0.25,
      "flag": "action-emotion inconsistency"
    }
  ],
  "polarity_note": "4 consecutive positive NPC interactions, 2 NPCs below 0.5 disposition"
}
```

**Dual use:** The same diagnostic prompt doubles as the curation filter for
the narration distillation pipeline (LLM Evaluation Document Section 8.4).
Passages flagged by the diagnostic during normal play are excluded from
the training dataset for local model fine-tuning. This is a zero-cost
two-for-one — the diagnostic serves runtime quality and dataset quality
simultaneously.

---

## 14. Character Advancement and Experience

### The Problem

The Vision Document describes campaigns spanning dozens of sessions,
with characters who grow from street-level survival into galaxy-shaping
capability. The FFG system provides a well-defined advancement framework:
XP earned per session, spent on skill ranks, talent tree nodes, new
specializations, and (rarely) characteristic increases. At the tabletop,
this is one of the most satisfying parts of play — players agonize over
advancement choices, plan talent tree paths, and feel genuine ownership
over who their character is becoming.

But the tabletop advancement interface — staring at a talent tree grid,
doing XP arithmetic, comparing skill costs — is exactly the kind of
mechanical UI that the Vision Document says the player should never see.
The player never reads a stat block. They never encounter the word
"roll." By the same principle, they should never encounter the words
"spend 10 XP on Deception rank 3."

The design must satisfy two competing requirements: preserve the *agency*
of choosing your own growth direction, and eliminate the *interface* of
spreadsheet-style stat management. The character must feel like they are
growing from their experiences — the way characters grow in novels —
while the player retains meaningful influence over the direction of that
growth.

This problem has an additional dimension for multi-era sagas. A character
who begins as a street kid running with smugglers and ends as a Jedi
Knight in the New Jedi Order era undergoes a fundamental identity
transformation across campaigns. The advancement system must support not
just incremental skill growth but transformative career transitions,
Force awakening, and the mechanical evolution that accompanies a
character aging 15-20 years across multiple campaign spines.

### The Design

The advancement system operates on two layers: **behavioral inference**
for incremental growth (skill ranks), and **milestone reflections** for
transformative growth (talents, specializations, characteristics, Force
awakening). The first layer runs silently, producing the experience of a
character who learns from what they do. The second layer surfaces at
pivotal moments as narrative choices, producing the experience of a
character who decides who they are becoming.

Both layers are invisible mechanically. The player never sees XP totals,
skill rank numbers, or talent tree grids. They experience growth through
changes in what their character can do — checks that once failed now
succeed, options that once were unavailable now appear, prose that
reflects a character whose competence and identity have shifted.

#### 14.1 XP Earning

XP is awarded at act boundaries, during the between-act processing
pipeline that already handles Obligation/Duty checks, strain recovery,
and Morality resolution. The player never sees the XP award — it is
tracked in the character state (`total_xp`, `available_xp`) and consumed
by the inference and milestone systems.

**Base award:** Each act in the campaign spine specifies a base XP value.
The recommended range is 15-25 XP per act, calibrated to the campaign's
intended progression speed. A campaign about a kid growing rapidly
through formative years can award 25 XP per act. A campaign about an
established operative on a single mission might award 15.

**Performance bonuses:** The campaign spine defines 2-4 bonus conditions
per act, each worth 5 XP. Conditions are evaluated programmatically from
the turn log at the act boundary. The types of conditions available:

- **Anchor beat engagement:** The player reached and meaningfully engaged
  with the act's anchor beat (not just passed through it). Evaluated by
  checking that the anchor beat turn exists and the player made an active
  choice rather than a default/passive option.

- **Motivation track interaction:** The player took at least one action
  that moved their primary motivation track — addressed Obligation,
  fulfilled Duty, or confronted a Morality-weighted choice (moral_weight
  ≥ 2). Evaluated from the turn log's obligation/duty/conflict fields.

- **Skill breadth:** The player used checks across at least 3 different
  skill categories during the act (e.g., social + combat + knowledge,
  not three different social skills). Evaluated from check_skill fields
  in the turn log. Rewards versatility over specialization.

- **Failure engagement:** The player continued pursuing a goal after
  failing a check related to it, rather than abandoning the approach.
  Evaluated by checking for a failed check followed by a related choice
  in the next 1-2 turns. Rewards persistence and produces better stories.

- **Spine-authored conditions:** Custom conditions specific to the
  campaign. "Discovered the identity of the mysterious comm voice."
  "Maintained Doss's trust through Act 2." These are authored as
  named flags in the campaign spine, set by anchor beat completion or
  variation point resolution.

**Typical act yield:** 20-35 XP. Over a 4-act campaign: 80-140 XP total.
This is consistent with FFG tabletop progression for a campaign spanning
4-8 sessions. Campaigns designed for rapid character transformation (the
smuggler kid saga) should use the upper range. Campaigns about a single
focused mission should use the lower range.

#### 14.2 Behavioral Inference — Skill Rank Advancement

The behavioral inference engine runs at act boundaries after XP is
awarded. It analyzes the player's behavior across the completed act and
automatically allocates available XP to **skill rank increases only.**

Skills are the domain of behavioral inference because skill ranks
represent *competence gained through practice.* A character who spends
an act talking their way through problems gets better at talking. A
character who spends an act running, climbing, and fighting gets more
physically capable. This is how growth works in novels — characters
become competent at what they do, without stopping to decide to become
competent.

Everything else — talents, specializations, characteristic increases,
Force Rating — is gated behind milestone reflections (Section 14.3).
These represent *identity choices* that should be conscious, not
automatic.

**The three input signals:**

The inference engine weighs three behavioral signals from the act's turn
log, ordered by weight to prevent the feedback loop where the system
rewards what is already strong:

**Signal 1 — Choice aspiration (highest weight, ~50%).** Every turn, the
player selects from 2-4 choices. Each choice carries a skill tag
(assigned by the GM, stripped before player display). The skill tags on
*selected* choices represent what the player *reaches for* — their
aspiration, independent of their current capability. A player with
Deception 2 who keeps selecting Perception-tagged choices is aspiring
toward awareness. Choice aspiration is the primary signal because it
captures player intent without requiring the player to articulate it.

Specifically: the engine counts the frequency of each skill tag across
all choices made in the act. Skills that appear in ≥ 30% of selected
choices receive full aspiration weight. Skills that appear in 15-29%
receive half weight. Skills below 15% receive no aspiration signal.

**Signal 2 — Failure learning (significant weight, ~35%).** Skills that
were checked and *failed* during the act receive strong advancement
weight. Struggle is how people grow. A player who failed Discipline
checks twice is a character wrestling with composure — and that struggle
should produce growth faster than effortless success.

Failed checks receive full failure-learning weight. Checks that
succeeded with threat (success but at a cost) receive half weight —
the character succeeded but was pushed. Clean successes receive minimal
weight (see Signal 3).

**Signal 3 — Practiced competence (lowest weight, ~15%).** Skills that
were checked and succeeded cleanly contribute a small amount to
advancement. This prevents the absurd case where a character uses
Deception 50 times successfully and never improves, but the low weight
ensures that repeating what is already easy does not dominate growth.

**XP cost calculation:** FFG skill rank costs are: 5 × new rank value
for career skills, 5 × new rank value + 5 for non-career skills. The
inference engine respects this distinction. A career skill increase from
rank 1 to rank 2 costs 10 XP. A non-career skill from 0 to 1 costs 10
XP.

**Allocation logic:** After computing weighted scores for each skill,
the engine sorts candidates by score and attempts to purchase the
highest-scoring skill rank increase that the available XP can afford. If
the top candidate costs more than available XP, the engine checks the
next candidate. Unspent XP carries forward to the next act — it is never
lost.

**Constraints:**

- The engine will not increase any skill by more than 1 rank per act.
  Characters grow incrementally, not in bursts.

- The engine will not increase a skill above rank 3 through behavioral
  inference alone. Ranks 4 and 5 represent elite mastery and require a
  milestone reflection (the player must consciously choose to pursue
  mastery). This prevents the system from producing hyper-specialized
  characters without player intent.

- The engine will not spend XP if the highest-scoring candidate has a
  weighted score below a minimum threshold (configurable, default 0.15).
  If the player's behavior was too diffuse to produce a clear signal,
  XP banks rather than being spent on a weak match. This prevents
  advancement that feels arbitrary.

- Career skill priority: when two skills have similar weighted scores
  (within 10% of each other), the engine prefers the career skill. This
  produces characters who grow naturally within their professional
  identity while still allowing cross-career growth when the behavioral
  signal is strong enough.

**XP reservation for milestones:** The engine reserves a configurable
portion of earned XP for milestone reflections rather than spending it
all on skill ranks. The default reservation is 40% of each act's XP
award. This ensures that when a milestone reflection fires, there is
XP available to fund the talent, specialization, or characteristic
increase the player selects. Reserved XP is tracked separately
(`reserved_xp`) and is only spent by milestone reflections. If no
milestone fires for 2+ acts, the reservation cap prevents excessive
banking — once reserved XP exceeds 60 XP (enough for most single
milestone purchases), additional XP flows to the behavioral inference
pool instead.

#### 14.3 Milestone Reflections — Transformative Growth

Milestone reflections are narrative moments that surface at specific
trigger points, presenting the player with 2-3 choices that each map
to a different mechanical advancement. The player makes a *character*
decision. The system translates it into XP spending.

Reflections are not menus. They are prose passages — interiority,
dialogue, or situational framing — that present a crossroads in terms
the character would understand. The player never sees what mechanical
effect their choice produces. They discover it through changes in what
their character can do in subsequent sessions.

**Five milestone categories:**

**Category 1 — Talent acquisition.**

*Trigger:* Reserved XP is sufficient to purchase a talent from the
character's current specialization tree(s), AND the behavioral inference
signal suggests a tree direction (the weighted skill scores align with
one branch of the tree more than others).

*Presentation:* A brief reflection passage (2-4 paragraphs) at the act
boundary, after the "Previously..." summary and before the next act
begins. Offers 2-3 choices, each mapping to a different talent. The
choices describe what the character has *become*, not what they are
*buying.*

*Example (Smuggler/Scoundrel tree):*

> The past weeks had changed something in Keth — not the big things,
> not the shape of his life, but the small machinery underneath. The
> way he processed a room. The way he handled pressure.

> *He'd learned to read the gap between what people said and what they
> meant. The pause that lasted a beat too long. The smile that didn't
> reach the eyes. He wasn't just lying better — he was understanding
> truth better, which made the lies surgical.*
> → Maps to: Convincing Demeanor (use Deception in place of other
> social skills)

> *He'd learned to move. Not the desperate scrambling of Nar Shaddaa's
> maintenance corridors but something cleaner — an instinct for where
> the next shot would go and a body that listened when the instinct
> spoke.*
> → Maps to: Dodge (spend strain to upgrade difficulty of incoming
> attack)

> *He'd learned to take a hit. Not just physically — though there was
> that too — but the kind of hit that comes when a deal falls apart or
> a contact burns you or the galaxy reminds you that your plans were
> always provisional. He got back up faster now. The recovery time was
> shrinking.*
> → Maps to: Grit (increase strain threshold by 1)

*Frequency:* Roughly every 2-3 acts, depending on XP flow and tree
depth. The campaign spine can author specific talent milestone windows
to control pacing.

**Category 2 — New specialization.**

*Trigger:* Reserved XP is sufficient for the specialization purchase
cost (new specializations cost 10 × number of specialization trees the
character will have after purchase, for in-career; out-of-career adds
+10), AND a narrative condition authored in the campaign spine has been
met. Narrative conditions might include: "character has interacted with
Force-sensitive NPCs in 3+ scenes," "character has been offered a
leadership role," or "character has operated outside their career
context for 2+ acts."

*Presentation:* A longer reflection passage (4-6 paragraphs) at an act
boundary. This is a character identity crossroads — the most significant
type of milestone after Force awakening. Offers 2-3 specialization
options, each presented as a direction the character's life could take.

*Example (Smuggler adding a second specialization):*

> Three roads had opened in front of Keth and he could feel the weight
> of them. The jobs had changed. The people had changed. He had changed.
> The question was which version of himself he was going to bet on.

> *The version who understood systems — not people-systems but actual
> systems, the mechanical logic of a ship's nervous system, the way a
> door's access panel thought about authorization. He'd been watching
> the mechanics work for months and somewhere along the way he'd
> started understanding what they were doing.*
> → Maps to: Technician (new specialization tree)

> *The version who understood fights. Not the brawling he'd survived
> on Nar Shaddaa but the real thing — tactical thinking, suppressive
> fire, the geometry of a room when weapons come out. He'd been in
> enough firefights now that the panic had been replaced by something
> colder and more useful.*
> → Maps to: Gunslinger (new specialization tree)

> *The version who understood people — not the way a con artist reads
> a mark, but the way a leader reads a crew. Who needs what. Who can
> handle what. How to put the right person in the right place at the
> right time and trust them to do the thing.*
> → Maps to: Squadron Leader or similar leadership specialization

*Frequency:* Once per campaign, occasionally twice in a long campaign
(5+ acts). This is a major character evolution event.

**Category 3 — Characteristic increase.**

*Trigger:* The character has reached the Dedication talent in one of
their specialization trees (Dedication is the only FFG mechanism for
increasing a base characteristic). This is gated by talent tree
progression — the player must have acquired the prerequisite talents
leading to Dedication through prior Category 1 milestones.

*Presentation:* A reflection passage framing a fundamental shift in who
the character is. Offers a choice between 2-3 characteristics, each
described in terms of what kind of person the character has become.

*Example:*

> Something had shifted at a level deeper than skill. Not what Keth
> could do, but what he *was.* The raw material underneath the training.

> *He was faster than he used to be. Not just reflexes — the whole
> system. Hand-eye coordination that had been adequate was now precise.
> Movement that had been functional was now fluid.*
> → Agility increase

> *He was sharper than he used to be. Problems that would have taken
> him an hour to reason through resolved in minutes. He saw connections
> between systems — mechanical, social, strategic — that used to be
> invisible.*
> → Intellect increase

> *He was harder to rattle. The voice inside his head that used to
> scream during firefights and whisper during negotiations had been
> replaced by something steadier. Not calm, exactly. Resolved.*
> → Willpower increase

*Frequency:* Rare. Once per campaign at most, often zero. Dedication
sits deep in the talent tree and requires significant prior investment.

**Category 4 — Force awakening.** (See Section 14.4 for full design.)

*Trigger:* `latent_force_sensitive` is `true`, the campaign spine's
discovery window has been reached, and a narrative trigger condition
has been met.

*Presentation:* The most significant milestone in a Force-sensitive
saga. Presented as a moment of recognition and choice — pursue this
new awareness, or let it pass.

*Frequency:* Once ever per character. If rejected, the latent flag
persists through the cross-era import interface for potential re-offer
in a future campaign (see Section 14.4).

**Category 5 — Career transition.**

*Trigger:* Cross-era import boundary. The character is entering a new
campaign spine whose era, allegiance structure, or narrative context
represents a fundamental shift in the character's life circumstances.

*Presentation:* A reflection passage bridging two eras. "Who are you
becoming in this new world?" Offers specialization and motivation track
adjustments appropriate to the new campaign context.

*Example (smuggler kid → Jedi Academy student):*

> The Academy was nothing like the streets. The hallways were clean.
> The food appeared on schedule. Nobody was running a con at breakfast.
> For the first time in his life, the systems around him were designed
> to help rather than to extract.

> It was disorienting. And underneath the disorientation, a question:
> what kind of student was he going to be?

> *The disciplined kind. Structure was new but not unwelcome. There
> was something almost peaceful about having a schedule, a teacher, a
> path that someone else had thought through.*
> → Maps to: Guardian or Consular specialization (structured Force
> training emphasis)

> *The restless kind. He sat through the lectures but his mind was
> already three steps ahead, looking for the angle, the shortcut, the
> way to learn faster by doing rather than by listening. Old habits,
> repurposed.*
> → Maps to: Sentinel or Seeker specialization (independent, applied
> Force training emphasis)

> *The reluctant kind. He was here because the Force had made itself
> impossible to ignore. That didn't mean he had to like it. He'd learn
> what he needed to learn and keep the rest of himself — the parts that
> had kept him alive on the streets — intact.*
> → Maps to: keeping primary non-Force specialization active, adding
> Force specialization as secondary (hybrid identity)

*Frequency:* Between campaigns only, at import boundaries. Represents
the character's adaptation to a new phase of life.

#### 14.4 Force Sensitivity Discovery System

The character funnel (Campaign Studio) presents three postures toward
the Force. The player's choice determines which Force path the Game
Engine activates.

**Posture 1 — Explicit Force path.**

The player selects a Force-aligned allegiance in the funnel and a
Force-sensitive variant. The character begins with Force Rating 1,
Morality as their primary motivation track, and a Force-sensitive
starting specialization. There is no discovery — the character knows
what they are from the first scene. This is Luke walking into the Jedi
Academy, Ezra meeting Kanan, Cal Kestis reconnecting with the Force.

**Posture 2 — Explicit non-Force path.**

The player selects a non-Force allegiance. `latent_force_sensitive` is
set to `false` in the character data. The Force is never offered as a
personal capability. The character may encounter Force users, witness
Force events, and exist in a galaxy where the Force is real — but it is
not their story. This is Han Solo's path, and the system treats it as
complete and equal. No Force interiority is ever generated. No discovery
milestone ever fires.

**Posture 3 — "Let the Force decide."**

The player selects a non-Force allegiance but enables a hidden random
determination. The character data includes `latent_force_sensitive: null`
at funnel selection, which the system resolves to `true` or `false` at
session creation using a probability defined by the campaign spine.

**Probability calibration:** The campaign spine specifies
`force_discovery_probability` as a float between 0.0 and 1.0. Guidance
for campaign authors:

- Jedi Academy era (11-14 ABY), Luke actively seeking students: 0.40-0.50
- Galactic Civil War era, Force users hunted: 0.15-0.25
- New Republic peacetime, Force users rare but not persecuted: 0.25-0.35
- New Jedi Order era, established Jedi Order: 0.30-0.40
- Old Republic era, Jedi Order at peak: 0.20-0.30 (more Force users
  exist but most are already identified)
- Imperial era Dark Times: 0.10-0.20

These are recommendations, not constraints. The campaign author controls
the probability. A campaign specifically designed around a Force
discovery narrative might use 0.70+. A campaign where Force sensitivity
would be a genuine shock might use 0.10.

**Resolution:** At session creation, when `latent_force_sensitive` is
`null`, the system generates a random float between 0.0 and 1.0. If the
value falls at or below `force_discovery_probability`, the field is set
to `true`. Otherwise, `false`. The result is stored in the character
state and never revealed to the player directly.

**When latent is true — the discovery arc:**

The GM prompt receives a context injection that evolves across three
phases, controlled by the campaign spine's **discovery window** — an
act range (e.g., "Acts 2-3") during which the awakening can occur.

**Phase 1 — Pre-window (before the discovery window opens).**
The GM prompt receives no Force-related context. The character plays
as a completely normal non-Force character. The system provides no
hints. This phase establishes the character's baseline identity so
that the Force discovery feels like a disruption of something real,
not a game feature revealing itself.

**Phase 2 — Discovery window open.**
The GM prompt receives a new context injection in the aspiration echo
block (see Section 14.5):

"LATENT FORCE SENSITIVITY — ACTIVE. The character has latent Force
sensitivity that is beginning to manifest. Weave *occasional* moments
of unexplained sensory awareness into the character's interiority — not
every turn, not as a plot point, but as texture. Moments where the
character knows something they shouldn't: a blaster bolt's trajectory
before the trigger is pulled, a stranger's hostile intent felt as
physical pressure, a door that feels wrong before it opens. These
moments should be ambiguous — explainable as instinct, luck, or
heightened awareness. The character does not understand what is
happening. Do not use the word 'Force.' Frequency: no more than 1 in
every 3-4 turns."

This phase can run for an entire act or more, building a pattern the
player notices even though the character doesn't understand it.

**Phase 3 — Discovery trigger.**
The campaign spine defines a trigger condition within the discovery
window — a specific narrative event (proximity to a Force vergence,
contact with a Force-sensitive NPC, extreme emotional stress, mortal
danger) that catalyzes the awakening. When the trigger condition is
met, the Force awakening milestone fires (Category 4).

The milestone presents the discovery as a moment of undeniable
recognition and offers a choice:

> *The moment lasted less than a second. The crate was falling —
> three hundred kilos of durasteel dropping toward Reeska's head —
> and then it wasn't. It hung in the air like gravity had forgotten
> its job. Reeska scrambled clear. The crate dropped.*
>
> *Nobody else saw it. Or if they did, they decided not to.*
>
> *But Keth felt it. Felt the effort of it in his chest, in his
> fingertips, in the space behind his eyes where something new had
> been building for weeks. He knew what it was. He'd heard the
> stories. He'd seen the holovids. He knew the word.*
>
> *The question was what to do with it.*

> *Pursue it. Find someone who understands. Learn what this is and
> what it means and what it can do.*
> → Accept awakening. Force Rating set to 1. Morality track activates
> as secondary motivation. Force-sensitive specialization becomes
> available at the next specialization milestone.

> *Bury it. This is not who he is. This is not the life he chose.
> Whatever this feeling is, it does not get to rewrite the story he
> is already living.*
> → Reject awakening. `force_rejected_count` incremented by 1.
> `latent_force_sensitive` remains `true`. Phase 2 interiority ceases
> for the remainder of this campaign. The import interface carries
> both the latent flag and the rejection count forward.

**When latent is true and rejected — the persistent offer:**

The `latent_force_sensitive: true` flag and the `force_rejected_count`
persist through the cross-era import interface into subsequent
campaigns. When a new campaign begins and the character still carries
the latent flag, the discovery arc restarts from Phase 2 — but with
modified GM context that reflects the character's history with this
feeling:

"LATENT FORCE SENSITIVITY — RECURRING (previously rejected ×{count}).
The character has experienced Force sensitivity before and consciously
suppressed it. The manifestations this time are *stronger* and *harder
to dismiss.* The character's interiority should reflect someone who
recognizes what is happening and is actively resisting it — not
discovering something new, but confronting something they tried to
leave behind. Frequency: no more than 1 in every 2-3 turns (increased
from the base rate)."

The discovery trigger fires again, with a reflection passage that
acknowledges the character's history:

> *He knew what this was. He'd felt it before — on Nar Shaddaa,
> years ago, when the crate stopped falling. He'd buried it then.
> Told himself it was adrenaline, instinct, coincidence. He'd been
> very convincing. He was a professional liar, after all.*
>
> *But the feeling hadn't buried. It had waited.*

There is no hard limit on rejections. A character can reject the Force
in every campaign and play an entire multi-era saga as a non-Force
character who happens to be latently sensitive. The system respects
the player's choice every time. But each subsequent offer
acknowledges the history and increases the narrative intensity of the
manifestations, creating a thread that the player carries across their
entire saga — whether they ultimately accept it or not.

**When latent is false:**

Nothing. No Phase 2 interiority. No discovery trigger. No milestone.
The player who chose "Let the Force decide" plays through the campaign
without ever knowing whether the possibility was real. The ambiguity
is part of the experience they opted into.

#### 14.5 Aspiration Echo Infrastructure

Aspiration echoes are brief moments of character interiority, woven into
the GM's narration, that reflect the character's growth trajectory. They
serve two functions: in the current system (Hybrid 2), they provide the
latent Force sensitivity hints described in Section 14.4. In the future
(Hybrid 3 upgrade), they expand to cover all advancement directions,
potentially replacing some milestone reflections with a fully seamless
narrative experience.

The infrastructure is built now to serve both purposes.

**GM prompt addition — the aspiration echo block:**

A new section in the context package, injected into the GM narration
prompt between the character state and the NPC state cards:

```
ASPIRATION ECHOES (interiority guidance):
{aspiration_echo_instructions}
```

The content of `aspiration_echo_instructions` is assembled by the
context pipeline based on the character's current state:

**Force sensitivity echoes (active now):** When `latent_force_sensitive`
is `true` and the discovery window is open, the Force interiority
instructions from Section 14.4 Phase 2 are injected here. When the
latent flag is `false` or the window is not open, this slot is empty.

**Skill growth echoes (Hybrid 3 future):** Reserved. When implemented,
this slot will contain instructions based on the behavioral inference
engine's current weighted scores: "The character has been gravitating
toward [awareness/technical competence/physical capability]. Weave
*occasional* moments of interiority where the character notices this
growth in themselves — not as announcement, but as texture. Frequency:
no more than 1 in every 4-5 turns."

**Advancement direction echoes (Hybrid 3 future):** Reserved. When
implemented, this slot will reflect the available talent or
specialization options, describing them as internal tendencies the
character is beginning to feel. The player's engagement with these
themes in their subsequent choices becomes the aspiration signal that
steers the inference engine.

**Frequency management:** The aspiration echo block includes a frequency
cap to prevent interiority overload. The combined frequency of all echo
types should not exceed 1 echo per 2-3 turns. When multiple echo types
are active (e.g., Force sensitivity + skill growth in a Hybrid 3 future),
the system prioritizes the most plot-relevant echo and suppresses others.
The GM prompt includes: "Do not include aspiration echo interiority in
every passage. These moments should feel organic and occasional, not
systematic. When you include one, make it brief — a sentence or two of
interiority, not a paragraph of self-reflection."

**Context assembly integration:** The aspiration echo block is
classified as **reflective context** for scene-type-aware context
assembly (Game Mechanics Section 10). It is foregrounded in
introspection and social scenes, backgrounded in combat and chase
scenes, and omitted entirely during multi-beat action sequences where
pacing cannot accommodate interiority.

#### 14.6 Advancement Notification Through Prose

When the behavioral inference engine purchases a skill rank increase,
or when a milestone reflection results in a talent or specialization
acquisition, the player is not told directly. They discover their
growth through the GM's narration in subsequent turns.

**Skill rank increases** are reflected through changed outcomes. A
Perception check that would have failed at rank 1 succeeds at rank 2.
The prose does not say "you are better at noticing things now." It
shows the character noticing something that matters and succeeding
where they might previously have failed. The player infers growth from
results.

**Talent acquisitions** are reflected through new capabilities appearing
in the prose and choices. A character who acquired Convincing Demeanor
finds that social choices now frame Deception-based approaches in
contexts where previously only Charm or Negotiation options appeared.
A character who acquired Dodge finds that combat passages include
moments where they evade attacks that would have connected before. The
player experiences the talent as "my character can do something new"
without ever seeing the talent name.

**The advancement summary:** At each act boundary, after the
"Previously..." summary and before the next act (or a milestone
reflection if one triggers), the system generates a brief **growth
passage** — 2-3 sentences of interiority that acknowledges how the
character has changed during the completed act. This is not a stat
readout. It is a narrative beat.

*Example:*

> *Something had shifted in the weeks since Nar Shaddaa. Keth read
> rooms faster now — not just the exits and the threats but the
> subtler architecture of who wanted what from whom. And when he
> reached for a lie, it came easier. Cleaner. Like a tool he'd finally
> learned to hold properly.*

This passage tells the player: your Perception and Deception have
improved. But it tells them as a story about their character, not as a
mechanical update. The growth passage is generated by the cloud GM with
a prompt that includes the specific skill changes and frames them as
character development.

### Implementation Notes

**Character state additions:**

- `available_xp: int` — already exists in the Character model. Used by
  both the behavioral inference engine and milestone reflections.
- `reserved_xp: int` — new field. XP earmarked for milestone
  reflections. Default 0. Capped at 60 (configurable).
- `latent_force_sensitive: Optional[bool]` — new field. `None` = "Let
  the Force decide" (resolved at session creation), `True` = latent
  positive, `False` = no Force sensitivity.
- `force_rejected_count: int` — new field. Default 0. Tracks how many
  times the player has rejected Force awakening across campaigns.
- `force_discovery_phase: str` — new field. One of: `"inactive"`,
  `"pre_window"`, `"window_open"`, `"triggered"`, `"accepted"`,
  `"rejected"`. Controls aspiration echo content for Force sensitivity.
- `advancement_log: list[dict]` — new field. Records each advancement
  event with type (skill/talent/specialization/characteristic/force),
  the specific change, the act it occurred in, and the behavioral signal
  that prompted it. Used by the growth passage generator and for
  debugging.

**Campaign spine additions:**

- `xp_base: int` per act — base XP award for the act.
- `xp_bonus_conditions: list[BonusCondition]` per act — each containing
  a condition type, parameters, and XP value.
- `force_discovery_probability: float` — probability of latent Force
  sensitivity resolving to true. Only relevant when the character's
  `latent_force_sensitive` is `null` at session creation.
- `force_discovery_window: [int, int]` — act range (inclusive) during
  which the Force awakening can trigger. E.g., `[2, 3]` means Acts 2
  and 3.
- `force_discovery_trigger: str` — narrative condition description for
  the discovery event. Evaluated by the engine against turn log state.
- `milestone_windows: list[MilestoneWindow]` — optional authored windows
  for talent and specialization milestones, allowing the campaign spine
  to control pacing.

**Between-act processing pipeline (updated order):**

1. Act summary compression (existing)
2. XP award — base + bonus condition evaluation (new)
3. XP reservation — 40% of award to `reserved_xp`, remainder to
   `available_xp`, respecting the 60 XP cap (new)
4. Behavioral inference — skill rank allocation from `available_xp` (new)
5. Milestone check — evaluate triggers for all five categories (new)
6. Obligation/Duty activation roll for next act (existing)
7. Strain recovery (existing)
8. Morality resolution — Conflict vs d10 (existing)
9. Growth passage generation (new)
10. Milestone reflection presentation, if triggered (new)

Steps 9-10 are player-facing. Steps 1-8 are invisible.

**Aspiration echo assembly:**

The context pipeline adds an `aspiration_echo_instructions` field to the
`ContextPackage`. The field is assembled from:

1. Force sensitivity echo (if `latent_force_sensitive` is `true` and
   `force_discovery_phase` is `"window_open"`)
2. Skill growth echo (Hybrid 3 future — empty string for now)
3. Advancement direction echo (Hybrid 3 future — empty string for now)

The echo block is injected into the GM narration prompt. When all slots
are empty, the block is omitted entirely — the GM prompt is not
cluttered with unused sections.

**Behavioral inference engine module:**

New file: `engine/advancement.py`. Contains:

- `compute_behavioral_weights(turns: list[TurnRecord]) -> dict[str, float]`
  — analyzes the act's turn log and produces weighted skill scores
- `select_skill_advancement(weights: dict, character: Character, available_xp: int) -> Optional[SkillAdvancement]`
  — selects the best skill rank purchase given weights and budget
- `evaluate_bonus_conditions(turns: list[TurnRecord], conditions: list[BonusCondition]) -> int`
  — evaluates spine-authored bonus conditions against the turn log
- `check_milestone_triggers(character: Character, spine: CampaignSpine, act: int, reserved_xp: int) -> Optional[MilestoneTrigger]`
  — evaluates all five milestone categories and returns the highest-priority triggered milestone

**Milestone reflection generation:**

Milestone reflection passages are generated by the cloud GM using a
dedicated prompt (separate from the narration prompt). The prompt
receives: the character's current state, the specific milestone type,
the mechanical options available, and the act summary. It produces a
prose passage with 2-3 choices, each tagged with the mechanical effect
it maps to. The player sees only the prose and choices. The tags are
stripped before display (same mechanism as skill tags on regular choices).

**Cross-era import additions:**

The import interface (Campaign Studio Section 6.1) carries forward:
`latent_force_sensitive`, `force_rejected_count`, `advancement_log`,
`total_xp`, `available_xp`, `reserved_xp`, and all skill/talent/
specialization state. The receiving campaign spine's import mapping
specifies how existing advancement state integrates with the new
campaign's milestone windows and Force discovery configuration.

---
## 15. Talent Trees — Mechanical Integration

### The Problem

FFG specialization talent trees are the primary mechanism through which
characters differentiate mechanically. Two Smuggler/Pilots with the same
skill ranks play very differently depending on which talents they have
acquired: one might be an evasion specialist who is nearly impossible to
hit, another might be a smooth-talking con artist who uses Deception in
place of every social skill.

In tabletop, talent trees are 4×5 grids. Players buy talents row by row,
moving along connected paths. Each row costs more XP (5/10/15/20/25 per
tier). The player stares at the grid, plans a path, and makes explicit
purchases. This is engaging at the table but fundamentally incompatible
with the invisible mechanics principle.

The design must solve three problems:

First, **data representation.** Talent effects need to be machine-
readable so the engine can apply them automatically, the local model can
account for them when deciding checks, and the cloud GM can narrate
them. A freetext talent description is not enough — the system must know
that Dodge upgrades difficulty, costs 2 strain, and triggers in combat
scenes.

Second, **mechanical integration.** Different talent types interact with
different layers of the system — some modify dice pools silently, some
change which skills are valid, some create entirely new narrative
possibilities. A unified "talent system" that treats all talents the
same will either be too rigid for narrative talents or too loose for
mechanical ones.

Third, **invisible navigation.** The player acquires talents through
Section 14's milestone reflections, not by clicking on tree nodes. But
the tree still has prerequisites and paths. The milestone system needs
to know which talents are *available* at each reflection point, and the
narrative choices need to map to tree positions without exposing the
grid structure.

### The Design

#### 15.1 Talent Taxonomy

Every FFG talent maps to one of five types based on how it integrates
with the game engine. This taxonomy is the bridge between the FFG
rulebook's freetext talent descriptions and the structured data the
engine needs.

**Type 1 — Passive modifiers.** Always-on effects applied automatically
by the engine. The player never knows these exist as mechanics — they
experience them as their character being better at certain things.

Integration point: `engine/checks.py` — pool construction.

Examples:
- Grit (ranked): +1 strain threshold per rank. Applied directly to
  character state on acquisition. The prose reflects greater endurance
  without naming it.
- Toughened (ranked): +1 wound threshold per rank. Same application.
- Skilled Jockey: Remove 1 setback die from Piloting checks. The pool
  construction step strips the setback before the roll. The character
  simply handles the ship cleanly in conditions that would rattle
  others.
- Forager: Remove 1 setback from Survival checks for food and water.
- Stalker (ranked): Add 1 boost die per rank to Stealth and
  Coordination checks. Pool construction adds the boost.
- Resolve (ranked): Suffer 1 less strain per rank from strain-
  inflicting effects. Applied during strain calculation.

Data schema:
```json
{
  "type": "passive",
  "effect": "modify_pool",
  "target_skills": ["piloting_space", "piloting_planetary"],
  "modifier": {"setback": -1},
  "ranked": false,
  "condition": null
}
```

For threshold modifiers:
```json
{
  "type": "passive",
  "effect": "modify_threshold",
  "target": "strain_threshold",
  "modifier": 1,
  "ranked": true
}
```

**Type 2 — Conditional modifiers.** Dice pool modifications that apply
only when specific situational conditions are met. The engine evaluates
the condition automatically, applies the modifier, and charges any
strain cost. The cloud GM narrates the effect.

Integration point: `engine/checks.py` — post-pool construction
modifier pass; `engine/character.py` — strain application.

The key design decision: conditional modifiers trigger **automatically**
when their conditions are met, rather than requiring the player to
choose to activate them. In tabletop, a player might choose not to use
Dodge to conserve strain. In our system, that tactical strain management
is invisible — the character dodges because dodging is who they are.
The engine applies the effect and charges the strain if the character
can afford it (current strain < strain threshold minus cost). If the
character cannot afford the strain cost, the talent does not trigger.

This is the correct abstraction for the prose-first format. "Do I
spend strain to dodge?" is a mechanical question. "The bolt missed
because Keth moved before he knew he was moving" is a narrative moment
that happened because the engine decided the character could afford it.

Examples:
- Dodge (ranked): When targeted by a combat check, upgrade the
  difficulty by 1 per rank. Costs 1 strain per rank used. Trigger:
  scene type is combat or chase, the check represents an incoming
  attack. In encounter-level combat, this translates to: the enemy's
  effective difficulty is higher, which means the player's defensive
  check is easier or the narrative describes evasion.
- Sidestep (ranked): Same as Dodge but specifically for ranged attacks.
- Quick Strike: Add 1 boost die when the character acts before the
  opponent (first turn of a combat sequence). Trigger: combat scene,
  sequence beat 1 or non-sequence combat turn.
- Defensive Stance (ranked): Upgrade difficulty of incoming melee
  attacks. Costs strain. Trigger: combat scene, melee context.

Data schema:
```json
{
  "type": "conditional",
  "effect": "modify_pool",
  "modifier": {"upgrade_difficulty": 1},
  "condition": {
    "scene_types": ["combat", "chase"],
    "context": "incoming_attack",
    "position": "any"
  },
  "strain_cost": 1,
  "ranked": true
}
```

**Encounter-level translation for conditional modifiers:**

In tabletop, Dodge triggers per-round against individual attacks. In
our encounter-level combat, where a single check resolves an entire
engagement phase, conditional defensive talents translate as follows:

The check decision step determines whether the encounter context
matches the talent's trigger condition. If it does, the engine applies
the modifier to the *player's* check as either a boost (for offensive
conditional talents like Quick Strike) or to the check's effective
difficulty (for defensive talents like Dodge — reducing the effective
difficulty the player faces, because in encounter-level resolution a
defensive talent that makes the enemy's attack harder is mechanically
equivalent to making the player's check easier).

The strain cost is charged once per encounter turn, not once per
attack. This prevents multi-beat action sequences from draining all
strain through a single talent. A 3-beat chase sequence with Dodge
active charges 1 strain per beat, not per hypothetical attack within
each beat.

**Type 3 — Skill substitutions.** These talents change which skills
are valid for a situation, expanding the player's tactical vocabulary.
The local model must know about them to correctly decide checks.

Integration point: Check decision prompt (local model).

Examples:
- Convincing Demeanor: May use Deception in place of Charm,
  Leadership, or Negotiation checks. The local model, when evaluating
  a social situation, can select Deception even when the natural skill
  would be Charm — because this character has developed the ability to
  lie so well that it functions as genuine rapport.
- Outdoorsman: Remove 1 setback from Athletics and Survival checks,
  and decrease overland travel time by 50%. The setback removal is a
  Type 1 passive; the travel time is a narrative enabler (Type 4).
- Researcher: Remove 1 setback from Knowledge checks and decrease
  research time by 50%.

Data schema:
```json
{
  "type": "substitution",
  "original_skills": ["charm", "leadership", "negotiation"],
  "substitute_skill": "deception",
  "condition": null,
  "ranked": false
}
```

**Prompt injection:** The check decision prompt includes a
`TALENT EFFECTS` section listing active Type 3 talents:

```
TALENT EFFECTS (skill substitutions):
- Convincing Demeanor: This character may use Deception in place of
  Charm, Leadership, or Negotiation. When the natural skill for a
  social situation would be Charm/Leadership/Negotiation, you may
  select Deception instead if the character's approach involves
  misdirection, manipulation, or performed sincerity.
```

This is injected between the character summary and the decision rules.
The local model uses it when evaluating which skill fits the player's
action. The engine validates that the selected skill is either the
natural skill for the situation or a valid substitution per active
Type 3 talents.

**Type 4 — Narrative enablers.** These talents create new possibilities
in the fiction — things the character can do or access that would not
exist without the talent. They do not modify dice pools. They change
what the GM offers.

Integration point: Cloud GM narration prompt.

Examples:
- Black Market Contacts: When looking for illegal or restricted goods,
  the character has a reliable source. The GM can offer choices
  involving restricted equipment acquisition where a character without
  this talent would not have that option.
- Speaks Binary: The character can communicate fluently with droids.
  Droid NPCs respond differently. Choices involving droid interaction
  are richer and more productive.
- Animal Bond: The character has a deep connection to a companion
  creature. The companion appears in the prose as a meaningful presence
  and can contribute to scenes.
- Shortcut: The character can find faster routes. In chase sequences,
  the GM can offer "take a shortcut" choices that other characters
  would not have access to.
- Bypass Security: Reduce difficulty of checks to bypass security
  devices. This is mechanically a passive modifier (Type 1) but also a
  narrative enabler — the GM should offer choices involving security
  systems more readily because the character has the tools and knowledge
  to engage with them.

Data schema:
```json
{
  "type": "narrative_enabler",
  "capability": "acquire_restricted_goods",
  "description": "Has reliable black market contacts for acquiring
    illegal or restricted equipment. GM should offer acquisition
    choices when contextually appropriate.",
  "ranked": false
}
```

**Prompt injection:** The narration prompt includes a `CHARACTER
CAPABILITIES` section listing active Type 4 talents:

```
CHARACTER CAPABILITIES (narrative enablers):
- Black Market Contacts: This character has reliable sources for
  restricted goods. When the story involves equipment needs, you may
  offer choices that involve acquiring restricted items through
  contacts — an option a character without this talent would not have.
- Speaks Binary: This character communicates fluently with droids.
  Droid NPCs are more forthcoming and cooperative. Droid-related
  choices should reflect this fluency.
```

This is injected between the NPC state cards and the aspiration echo
block. The cloud GM uses it to expand the choice landscape for
characters whose talents open new narrative doors.

**Type 5 — Intervention talents.** Powerful one-shot abilities that
fire *after* a dice result is known but *before* narration is
generated. These are the talents that let the player push back against
an outcome — rerolling a check, negating a hit, turning a failure into
a partial success.

Integration point: A **new step** in the turn flow between dice
resolution and narration generation.

Examples:
- Natural Charmer: Once per session, reroll any Charm or Deception
  check.
- Natural Pilot: Once per session, reroll any Piloting check.
- Brilliant Evasion: Once per session, ignore all damage from one hit.
- Second Chances (ranked): Once per encounter, reroll a failed check.
  Per rank purchased, can be used an additional time.
- Dedication: Increase one characteristic by 1. This is not truly an
  intervention talent — it is a permanent change applied on acquisition
  through a Category 3 milestone reflection (Section 14.3). Included
  here for completeness as it sits at the bottom of every talent tree.

**The talent intervention step:**

After the dice are rolled and the result is computed but before the
result is sent to the cloud GM, the engine checks whether any Type 5
talents are applicable and available (not already used this session/
encounter). If one or more interventions are available, the engine
presents a **pre-narration choice** to the player.

This choice is presented in narrative terms, not mechanical terms:

> *The negotiation had gone sideways. Keth could feel it in the
> silence that followed his last offer — the kind of silence that
> meant the next words out of anyone's mouth were going to be hostile.
> He'd read the room wrong. Or had he?*
>
> *There was a beat — half a second, maybe less — where he could
> still recover. Shift the frame. Reread the angles. Say the thing he
> should have said the first time.*
>
> **Accept the outcome** — The deal falls apart. Move forward from
> the failure.
>
> **Push through** — Keth reaches for something sharper. *(This will
> cost him — he can feel the strain of it already.)*

If the player chooses "Push through," the engine:
1. Charges the strain cost (typically 1-2 strain)
2. Rerolls the check (or applies the intervention effect)
3. Uses the new result for narration
4. Marks the talent as used for the session/encounter

If the player accepts the outcome, the original result stands and the
talent remains available for future use.

**The physics-before-imagination invariant is preserved** because the
final dice result — whether original or rerolled — is fully resolved
before the cloud GM receives it. The pre-narration choice is a
mechanical decision point, not a narrative one. The player decides
whether to use a resource. The prose that follows honors whatever the
final result is.

**Once-per tracking:** Type 5 talents track their usage via a new field
on the session state: `talent_uses: dict[str, int]` mapping talent
names to the number of times they have been used this session. The
session state resets the counter at act boundaries (translating FFG's
"once per session" to "once per act" for our longer sessions).
Encounter-scoped talents (Second Chances) reset at the end of each
multi-beat sequence or at each turn boundary for non-sequence turns.

Data schema:
```json
{
  "type": "intervention",
  "trigger": "failed_check",
  "applicable_skills": ["charm", "deception"],
  "effect": "reroll",
  "strain_cost": 1,
  "scope": "session",
  "ranked": false,
  "narrative_prompt": "A moment of recovery — the character finds the
    right angle just when everything seemed lost."
}
```

#### 15.2 Talent Tree Data Representation

Each specialization's talent tree is stored as a structured JSON file
in `data/talent_trees/`. The engine loads the tree for each of the
character's active specializations and uses it for: pool modification,
check decision prompt injection, narration prompt injection, and
milestone reflection generation.

**Tree structure:**

```json
{
  "specialization": "scoundrel",
  "career": "smuggler",
  "game_line": "edge_of_empire",
  "talents": [
    {
      "id": "scoundrel_t1_left",
      "name": "Convincing Demeanor",
      "tier": 1,
      "position": 0,
      "xp_cost": 5,
      "prerequisites": [],
      "talent_type": "substitution",
      "ranked": false,
      "effect": {
        "type": "substitution",
        "original_skills": ["charm", "leadership", "negotiation"],
        "substitute_skill": "deception"
      },
      "narrative_identity": "The character's lies function as social
        tools — not crude deception but performed sincerity, tactical
        empathy, the ability to become whoever the situation requires.",
      "prose_tags": ["manipulation", "social_fluency", "masks"]
    },
    {
      "id": "scoundrel_t2_left",
      "name": "Dodge",
      "tier": 2,
      "position": 0,
      "xp_cost": 10,
      "prerequisites": ["scoundrel_t1_left"],
      "talent_type": "conditional",
      "ranked": true,
      "max_rank": 3,
      "effect": {
        "type": "conditional",
        "effect": "modify_pool",
        "modifier": {"upgrade_difficulty": 1},
        "condition": {
          "scene_types": ["combat", "chase"],
          "context": "incoming_attack"
        },
        "strain_cost": 1
      },
      "narrative_identity": "The character moves before they think.
        Instinct sharpened by years of being shot at.",
      "prose_tags": ["evasion", "reflexes", "survival_instinct"]
    },
    {
      "id": "scoundrel_t5_center",
      "name": "Dedication",
      "tier": 5,
      "position": 2,
      "xp_cost": 25,
      "prerequisites": ["scoundrel_t4_center"],
      "talent_type": "passive",
      "ranked": false,
      "effect": {
        "type": "modify_characteristic",
        "target": "player_choice",
        "modifier": 1
      },
      "narrative_identity": "A fundamental shift in who the character is.
        Not what they can do, but what they are made of.",
      "prose_tags": ["transformation", "core_identity"]
    }
  ],
  "tree_paths": {
    "left_branch": {
      "theme": "social_manipulation",
      "description": "The path of the con artist. Lies as tools,
        deception as art, and the ability to become anyone.",
      "talent_ids": ["scoundrel_t1_left", "scoundrel_t2_left",
        "scoundrel_t3_left", "scoundrel_t4_left"]
    },
    "center_branch": {
      "theme": "resilience",
      "description": "The path of the survivor. Taking hits and
        getting back up. Strain and wound management.",
      "talent_ids": ["scoundrel_t1_center", "scoundrel_t2_center",
        "scoundrel_t3_center", "scoundrel_t4_center"]
    },
    "right_branch": {
      "theme": "evasion_and_speed",
      "description": "The path of the quick draw. Reflexes, initiative,
        and the ability to act before anyone else.",
      "talent_ids": ["scoundrel_t1_right", "scoundrel_t2_right",
        "scoundrel_t3_right", "scoundrel_t4_right"]
    }
  }
}
```

**Key fields:**

`narrative_identity` — A prose description of what this talent *means*
for the character, used by the milestone reflection generator to craft
the narrative choice that maps to this talent. This is the bridge
between the mechanical talent and the narrative experience. Convincing
Demeanor is not "use Deception instead of Charm." It is "your lies have
become so refined that they function as genuine connection."

`prose_tags` — Keywords the cloud GM can use to flavor narration when
the talent activates or when its effects are relevant. A character with
Dodge and prose tags ["evasion", "reflexes", "survival_instinct"] gets
narration where near-misses feel instinctive and physical, not lucky.

`tree_paths` — Named branches within the tree. These are the units that
milestone reflections operate on. When a talent milestone fires, the
reflection choices map to branches, not individual nodes. "Lean into
the con artist path" selects the next available talent on the left
branch. "Lean into survival" selects from the center branch. The
player navigates the tree through thematic choices without seeing the
grid.

#### 15.3 Pool Modification Pipeline

The current `build_pool()` function constructs a dice pool from
character stats and check parameters. Talent integration extends this
into a three-stage pipeline:

**Stage 1 — Base pool construction (existing).** The standard FFG
formula: max(characteristic, skill_rank) ability dice, upgrade
min(characteristic, skill_rank) to proficiency, add difficulty,
situational boost/setback from the check decision.

**Stage 2 — Passive modifier pass (new).** The engine iterates over
the character's acquired talents and applies all Type 1 passive
modifiers whose target skills include the current check's skill. Grit
and Toughened are applied at acquisition time (they modify thresholds,
not pools), but pool-modifying passives like Skilled Jockey and Stalker
are applied here.

For ranked talents, the modifier is multiplied by the character's rank.
Stalker rank 2 adds 2 boost dice to Stealth checks.

**Stage 3 — Conditional modifier pass (new).** The engine evaluates
Type 2 conditional talents against the current scene context:

- Does the scene type match the talent's trigger condition?
- Does the check context (offensive vs defensive, melee vs ranged,
  first-turn vs ongoing) match?
- Can the character afford the strain cost?

If all conditions are met, the modifier is applied and the strain cost
is charged. The talent's activation is logged in `talent_activations`
on the turn record for the cloud GM to reference when narrating.

The order matters: passives first, then conditionals. This ensures that
passive setback removal happens before conditional modifiers are
evaluated — a character with both Skilled Jockey (remove setback from
piloting) and a conditional talent that triggers when setback dice are
present will have the passives applied first.

**The modified `build_pool` signature:**

```python
def build_pool(
    character: Character,
    check: CheckRequest,
    scene_context: SceneContext,  # new: scene_type, sequence_beat, etc.
) -> tuple[DicePool, list[TalentActivation]]:
```

The function returns both the modified pool and a list of talent
activations (which talents fired and what they did). The activations
list is included in the turn record and injected into the cloud GM's
context so it knows to narrate the effects.

#### 15.4 Check Decision Talent Awareness

The local model's check decision prompt needs to know about two
categories of talents: Type 3 skill substitutions (which change what
skills are valid) and certain Type 4 narrative enablers (which change
what actions are *possible*).

The check decision prompt gains a new `TALENT EFFECTS` section, injected
between the character summary and the decision rules:

```
TALENT EFFECTS:
{talent_effects_for_check_decision}
```

This section is assembled from the character's acquired talents:

- Type 3 substitutions are listed as skill equivalences: "May use
  Deception in place of Charm, Leadership, or Negotiation."
- Type 4 enablers that affect check validity are listed as capability
  notes: "Speaks Binary — treat droid interaction as a standard social
  encounter with full skill access, not a Computers check."

The section is omitted entirely when the character has no relevant
Type 3 or Type 4 talents — the prompt is not cluttered with an empty
block.

**Important constraint:** The check decision prompt remains concise.
Type 1 and Type 2 talents are NOT listed in the check decision prompt
because the engine handles them automatically in the pool modification
pipeline. The local model should not try to account for Dodge or Grit
— it decides the base check, and the engine layers talent effects on
top. This separation keeps the local model's task simple (decide skill
and difficulty) and the engine's task deterministic (apply talent
rules).

#### 15.5 Narration Talent Awareness

The cloud GM needs to know about talent activations to narrate them
effectively. A character who Dodges an attack should *feel* like they
dodged it in the prose — not just succeed at a check.

The narration prompt gains two talent-related sections:

**Section 1 — Character capabilities (persistent).**

Listed in the character state block. Contains Type 4 narrative enablers
and any Type 3 substitutions that affect how the character approaches
social or problem-solving situations. This is persistent context — the
GM always knows what the character is capable of.

```
CHARACTER CAPABILITIES:
- Convincing Demeanor: The character's deception functions as social
  fluency. When this character lies, it should read as effortless
  rapport, not crude manipulation.
- Black Market Contacts: The character has access to restricted goods
  through a network of suppliers. Acquisition scenes should reflect
  this — not wandering shops but making calls, visiting back rooms,
  knowing which docking bay to visit.
```

**Section 2 — Talent activations (per-turn).**

Injected into the context for the current turn, listing which talents
fired during pool modification and any intervention talents used. This
tells the GM *what happened mechanically* so it can be narrated.

```
TALENT ACTIVATIONS THIS TURN:
- Dodge (rank 1): Activated during combat. The character evaded an
  incoming attack through instinct, costing strain. Narrate the
  near-miss as physical, reflexive movement.
- Quick Strike: Activated at sequence beat 1. The character acted
  before the opponent. Narrate the initiative as decisive — the
  character moved first because they read the situation faster.
```

The `narrative_identity` and `prose_tags` from the talent tree data
are available for the GM prompt to reference, providing flavor
guidance beyond the mechanical description.

#### 15.6 Tree Navigation Through Milestone Reflections

Section 14.3 (Category 1 — Talent acquisition) established the
milestone reflection mechanism: when enough XP has accumulated, the
system presents 2-3 narrative choices that map to talents. This section
specifies *how* those choices are generated from the tree data.

**The tree path model:**

Each specialization tree is divided into named branches (Section 15.2,
`tree_paths`). A branch is a thematic grouping of talents that share
a character identity direction — the con artist path, the survivor
path, the quick draw path. Branches are not necessarily linear columns
in the 4×5 grid — they can zigzag across positions where the thematic
grouping makes sense.

When a talent milestone fires, the system:

1. **Identifies available talents.** For each active specialization
   tree, finds all talents where: the character has not yet acquired
   them, all prerequisites are met (the talent's prerequisite IDs
   are all in the character's acquired talent list), and the XP cost
   is affordable from `reserved_xp`.

2. **Groups by branch.** Available talents are grouped by their
   `tree_paths` branch membership. If a branch has no available
   talents (all acquired or prerequisites not met), that branch is
   not offered.

3. **Selects the next talent per branch.** For each branch with
   available talents, selects the lowest-tier unacquired talent. This
   is the next natural step on that branch's path.

4. **Generates reflection choices.** Each available branch becomes a
   narrative choice. The choice text is generated by the cloud GM
   using the branch's `theme`, `description`, and the specific
   talent's `narrative_identity` as input. The mechanical mapping
   (which talent is purchased) is tagged on the choice and stripped
   before display.

**Cross-specialization navigation:**

Characters with multiple specializations may have milestone reflections
that offer talents from different trees. In this case, the reflection
choices are drawn from the available branches across *all* active trees,
with the highest-weighted behavioral signal (from Section 14.2) used to
prioritize which trees' branches are offered. The system offers at most
3 choices regardless of how many branches are available — this keeps the
reflection moment focused.

**Ranked talent progression:**

Ranked talents (Grit, Toughened, Dodge, etc.) can be acquired multiple
times, potentially from different positions in different trees. When a
character acquires rank 2 of a ranked talent, it appears as a milestone
option if: the character already has rank 1, a tree position offering
the next rank has its prerequisites met, and the XP cost is affordable.
The milestone reflection for a ranked talent emphasizes *deepening* an
existing capability: "The instinct sharpened. What had been a flinch
became a controlled slide, a half-step that arrived before conscious
thought."

#### 15.7 Talent Data Scope

Implementing talent trees for the full FFG catalogue is a significant
data entry task. Each of the three game lines contains 6 careers with
3-4 specializations each, and additional universal specializations.
Total: approximately 70+ specialization trees with 20 talents each,
plus shared talents that appear across multiple trees.

**Phased approach:**

Phase 1 (V1+1): Implement the talent engine and data format. Author
talent tree data for the Smuggler career's three specializations
(Pilot, Scoundrel, Thief) to validate the design with Keth Varso's
natural progression paths. This covers all five talent types and
tests cross-tree navigation.

Phase 2 (V2): Extend to all Edge of the Empire careers. This covers
the broadest character variety within the game line that Keth and
similar characters inhabit.

Phase 3 (V2+): Add Force and Destiny specialization trees. These
include Force-specific talents that interact with the Force mechanics
system (Section TBD) and are prerequisite for the Force progression
your saga concept requires.

Phase 4 (V3): Complete catalogue. All three game lines, all
specializations, all universal talent trees. Full cross-career
specialization support for characters who span multiple game lines
across eras.

**Shared talent deduplication:** Many talents appear in multiple
specialization trees (Grit, Toughened, Dodge, Dedication are nearly
universal). The talent data uses a **talent library** — a central
registry of talent definitions keyed by canonical talent name. Each
specialization tree references talents by ID from the library. The
tree data specifies position, tier, and prerequisites; the library
provides the effect, type, narrative identity, and prose tags. This
prevents duplication and ensures consistent behavior across trees.

```
data/talent_trees/
├── talent_library.json     # Canonical talent definitions
├── smuggler_pilot.json     # Specialization tree (references library)
├── smuggler_scoundrel.json
├── smuggler_thief.json
└── ...
```

### Implementation Notes

**Character state additions:**

- `acquired_talents: list[AcquiredTalent]` — new field. Each entry
  contains: talent library ID, specialization tree source, tier,
  position, rank (for ranked talents), and acquisition act number.
  Ordered by acquisition time.

- `talent_uses: dict[str, int]` — new field. Tracks Type 5
  intervention talent usage per session. Reset at act boundaries.

**Turn record additions:**

- `talent_activations: list[TalentActivation]` — new field per turn.
  Records which talents fired during pool modification (Type 1 and 2)
  and any intervention choices made (Type 5). Consumed by the cloud
  GM's narration prompt and stored in the turn log for advancement
  analysis.

**Turn flow modification — the intervention step:**

The current turn flow is:

1. Player selects choice
2. Local model decides check
3. Engine builds pool and rolls dice
4. Cloud GM generates narration from result
5. New choices presented

The talent system inserts step 3.5:

3.5. **Talent intervention check.** Engine evaluates Type 5 talents
against the dice result. If an applicable intervention is available
(talent not yet used this session/encounter, character can afford
strain, trigger condition met), the engine presents a pre-narration
choice to the player. If the player activates the intervention, the
engine applies the effect (reroll, negate, modify) and uses the new
result for step 4. If declined, the original result proceeds.

The intervention step is skipped entirely when the character has no
Type 5 talents or none are applicable. The vast majority of turns
proceed without interruption.

**Context assembly additions:**

The context pipeline (`gm/context.py`) adds two new fields to the
`ContextPackage`:

- `talent_effects_for_check_decision: str` — Type 3 substitutions and
  relevant Type 4 enablers, assembled from the character's acquired
  talent list. Injected into the check decision prompt.

- `talent_capabilities_for_narration: str` — Persistent Type 4
  narrative enablers and Type 3 substitutions formatted for the
  narration prompt. Injected as a character capabilities block.

- `talent_activations_for_narration: str` — Per-turn Type 1, 2, and 5
  activations formatted for the narration prompt. Injected as a turn-
  specific context block.

These fields are assembled by a new function:
`build_talent_context(character: Character, scene: SceneContext,
activations: list[TalentActivation]) -> TalentContext`

**New module:** `engine/talents.py`. Contains:

- `load_talent_library() -> dict[str, TalentDefinition]` — loads the
  central talent library
- `load_specialization_tree(name: str) -> SpecializationTree` — loads
  a specialization tree, resolving talent references from the library
- `get_available_talents(character, trees) -> list[AvailableTalent]` —
  computes which talents are available for purchase given current
  acquisitions and prerequisites
- `apply_passive_modifiers(pool, character, skill) -> DicePool` — Stage
  2 of the pool modification pipeline
- `apply_conditional_modifiers(pool, character, scene_context) ->
  tuple[DicePool, list[TalentActivation]]` — Stage 3 of the pipeline
- `check_interventions(result, character, scene_context) ->
  Optional[InterventionOffer]` — evaluates Type 5 talent eligibility
- `build_milestone_choices(character, trees, reserved_xp) ->
  list[MilestoneChoice]` — generates talent milestone reflection
  options grouped by tree branch

**FFG fidelity note:** Not every FFG talent translates cleanly to the
five-type taxonomy. Some talents have complex conditional effects that
combine multiple types (e.g., a talent that is both a passive modifier
and a narrative enabler). These are represented as multi-effect entries
in the talent library, with each effect processed by its corresponding
integration point. The taxonomy is a routing mechanism, not a
constraint — talents can have effects in multiple categories.

---
## 16. Force Mechanics

### The Problem

The FFG Force and Destiny system adds a parallel mechanical layer for
Force-sensitive characters: white Force dice that generate light and
dark side pips instead of successes and failures, Force powers with
their own upgrade trees, a Force Rating that determines how many Force
dice are rolled, and a temptation mechanic where using dark side pips
costs Conflict (feeding the Morality track) and strain. At the tabletop,
using the Force is an explicit mechanical action — the player announces
"I'm using Move," rolls Force dice, counts pips, decides whether to
flip dark pips, pays strain, and resolves the effect.

This mechanical layer is one of the most narratively powerful elements
in FFG. The moment where a light-side Jedi considers reaching for the
dark side to save someone they love — and the player has to decide,
right now, whether to pay that Morality cost — is exactly the kind of
drama the Vision Document describes. But the *interface* of counting
pips and managing Force power trees is as mechanically exposed as
anything in the FFG system.

The design must preserve three things: the Force should feel mysterious
and powerful rather than like another stat to optimize; the dark side
temptation must be a conscious moral choice the player makes through
narrative framing; and Force powers must expand what the character can
do in the fiction without requiring the player to manage a power tree.

This section depends on:
- Section 9 (Morality — the Conflict accumulation and drift system)
- Section 14 (Character Advancement — Force awakening, milestone
  reflections, behavioral inference)
- Section 15 (Talent Trees — the intervention step pattern, talent
  data representation)

### The Design

#### 16.1 Force Dice in the Engine

The dice engine already supports Force dice — the FORCE_TABLE, the
light/dark pip symbols, and the force field on DicePool and RollResult
are implemented. What is missing is the *interpretation layer* — how
Force pip results translate into mechanical effects and narrative
outcomes.

**When Force dice are rolled:**

Force dice enter a pool in two situations:

**Situation 1 — Force-enhanced skill checks.** The character uses the
Force to augment a normal action. Lifting a heavy blast door
(Athletics enhanced by the Force), reading an adversary's surface
emotions to gain an edge in negotiation (social check enhanced by
Sense), steadying their aim through the Force (Ranged check enhanced
by the Force). The standard skill check pool is constructed normally
(ability, proficiency, difficulty dice per the existing pipeline),
and Force dice equal to the character's Force Rating are added to the
pool. The skill check portion resolves success/failure as usual. The
Force dice resolve separately — their pips determine whether the Force
enhancement works.

**Situation 2 — Pure Force actions.** The character uses the Force as
the primary action — telekinetic manipulation, mind trick, Force
healing, sensing danger. There is no skill check. The character rolls
Force dice equal to their Force Rating, and the pips determine the
result directly. The power's pip requirement (how many pips are needed
for the base effect and any upgrades) is compared against the pips
generated.

**Force pip resolution:**

After a pool containing Force dice is rolled, the engine separates the
Force result from the skill check result:

- `light_pips`: The number of light side pips generated.
- `dark_pips`: The number of dark side pips generated.
- `pips_needed`: The Force power's pip requirement (minimum 1 for any
  Force use).

If `light_pips >= pips_needed`: the Force use succeeds at no additional
cost. The character channeled the light side cleanly. No Conflict, no
strain beyond what the action itself costs.

If `light_pips < pips_needed` but `light_pips + dark_pips >= pips_needed`:
the Force use *can* succeed, but only by drawing on the dark side. This
triggers the **dark side temptation** (Section 16.2).

If `light_pips + dark_pips < pips_needed`: the Force use fails
regardless. The character reached for the Force and it was not enough.
The narration reflects a Force user straining against something that
will not yield. No Conflict is generated because no dark side pips were
used.

**Force-enhanced check interaction:**

When Force dice accompany a skill check, the two results are
independent but narratively intertwined:

- Skill success + Force success: The action succeeded and the Force
  enhancement worked. The best possible outcome. The character lifted
  the door *and* did it with controlled, graceful power.

- Skill success + Force failure: The action succeeded on mundane
  capability alone. The Force did not answer, or the character did not
  need it. The door yielded to brute strength and leverage. The Force
  was silent.

- Skill failure + Force success: The action failed despite the Force
  working. The character felt the Force flowing but could not translate
  it into the physical result. The door shuddered, moved, but their
  grip slipped and it fell back. Narratively potent — the Force is
  present but the character lacks the skill to wield it fully.

- Skill failure + Force failure: Complete failure. Neither the mundane
  nor the mystical was sufficient.

These four combinations replace the standard two-axis (success/
advantage) result for Force-enhanced checks. The GM prompt receives
both the skill result and the Force result, with instructions to
narrate the interplay.

#### 16.2 The Dark Side Temptation

This is the most important interaction pattern for Force-sensitive
characters. It is the mechanical embodiment of the Star Wars moral
question: what are you willing to become to get what you need?

**When it triggers:**

The dark side temptation fires when a Force roll generates insufficient
light pips but sufficient total pips (light + dark) to meet the
power's requirement. The engine detects this condition after dice
resolution and before narration — the same intervention step used by
Type 5 talents (Section 15, step 3.5 in the turn flow).

**How it is presented:**

The temptation is presented as a narrative choice, not a mechanical
menu. The engine generates a pre-narration passage that describes what
the character feels — the Force offering a different path — and
presents two options:

> *The Force was there but it was wrong. Not the gentle current he'd
> learned to feel in meditation — this was something hotter, something
> that lived in the space behind his ribs where anger went when he
> swallowed it. The door needed to move. The Force could move it. But
> the Force that was answering right now was not the one Master Skywalker
> had taught him to listen to.*
>
> *It would work. He could feel that with absolute certainty. It would
> work and it would cost him something he couldn't name yet.*
>
> **Let it go.** The Force isn't answering the way it should. Accept
> the failure.
>
> **Reach deeper.** The door needs to move. Whatever it costs.

If the player chooses to let it go: the Force use fails. The original
pip result stands (insufficient light pips). No Conflict is generated.
The narration describes a Force user who reached for power and
deliberately stopped. This is a light-side-affirming moment.

If the player chooses to reach deeper: the Force use succeeds using
dark side pips. The engine applies two costs:

1. **Conflict.** The player earns Conflict equal to the number of
   dark pips used. This feeds directly into the Morality system
   (Section 9) — at the end of the act, accumulated Conflict vs the
   d10 roll determines whether Morality drifts darker.

2. **Strain.** The character suffers strain equal to the number of
   dark pips used. This represents the physical toll of channeling
   the dark side. For characters already at high strain, this creates
   a risk of incapacitation — using the dark side can knock you out.

Both costs are invisible to the player in numerical terms. The prose
reflects the strain ("something tore behind his eyes") and the
Conflict manifests through the Morality drift at the act boundary
("the calm that used to come after meditation didn't come tonight").

**Dark side dominant characters (Morality 0-40):**

The temptation pattern inverts for dark-siders. The dark side is their
natural channel. For them, *light* side pips are the ones that cost.

When a dark-side-dominant character rolls Force dice:
- Dark pips are used freely — no Conflict, no strain. The dark side
  answers when called by someone who has embraced it.
- Light pips require an active choice to use. Using light pips
  generates no Conflict (it reduces Morality drift by being a light-
  side-affirming action) but costs strain — resisting the dark side
  is physically exhausting for someone who has adapted to its current.

The temptation passage for a dark-sider is tonally inverted:

> *The Force answered immediately — it always did now, eager and sharp,
> like a blade that wanted to be drawn. But underneath the familiar
> surge, something else stirred. Quieter. Cooler. The version of the
> Force that required patience instead of demand.*
>
> *It would be harder. Slower. And it would not feel like power.*
>
> **Take what's offered.** The dark side is faster. It's always faster.
>
> **Reach for the quiet.** There's another way. There always was.

This inversion is mechanically significant: a dark-sider who
consistently reaches for the light is making the same kind of costly
moral choice as a light-sider reaching for the dark, but in reverse.
Both drift Morality. Both cost strain. The system is symmetrical.

**Grey characters (Morality 41-70):**

Grey characters pay the standard costs for dark pip usage (Conflict +
strain) but at reduced rates: strain cost is reduced by 1 (minimum 1),
reflecting that the character has an uneasy accommodation with both
sides. They are neither fully light nor fully dark — using either
extreme is less shocking to their system than it would be for someone
firmly aligned.

#### 16.3 Force Powers

Force powers define what a Force-sensitive character can *do* with
the Force. In FFG, each power has a base effect and an upgrade tree
(range, magnitude, strength, duration, control upgrades). The upgrade
tree is a separate grid from the specialization talent tree — powers
are purchased with XP independently.

**Prose-first translation:**

In the tabletop, a player declares "I use Move to lift that crate" and
manages the mechanical resolution themselves. In our system, the Force
power manifests through the player's choices and the GM's narration.

The key insight: **the player never selects a Force power by name.** They
select a choice that involves using the Force, and the engine determines
which power applies. When the GM presents choices like:

> *Reach out with the Force and stop the crate before it crushes her*

The skill tag on this choice is not `[Athletics]` — it is `[Force:Move]`.
The engine recognizes this as a Force action, rolls Force dice equal to
the character's Force Rating, and resolves pips against the Move power's
requirements. The player chose to *use the Force.* The system determined
that this use maps to the Move power, checked that the character has it,
and resolved accordingly.

If the character does *not* have the Move power, the choice is not
offered. The GM's narration prompt includes the character's active Force
powers in the capability block (Section 15.5). The GM only offers Force-
tagged choices for powers the character actually possesses. This prevents
the player from attempting Force actions their character hasn't developed
— without ever telling them "you don't have that power."

**Power categories:**

Force powers map to four narrative categories that the GM uses to
generate appropriate choices:

**Physical manipulation:** Move (telekinesis), Bind (restraint), Enhance
(physical augmentation). These produce choices about affecting the
physical world — lifting, pushing, holding, jumping, running. Enhance
is unique in that it primarily functions as a Force-enhanced skill check
rather than a pure Force action.

**Mental influence:** Influence (emotion manipulation, mind trick), Misdirect
(illusions), Foresee (premonition). These produce choices about
affecting minds and perceptions — convincing, deceiving, predicting,
sensing intent. Mind tricks are presented as social choices with a Force
tag rather than a Deception or Charm tag.

**Perception and knowledge:** Sense (danger sense, emotion reading, combat
awareness), Seek (tracking, finding hidden things), Foresee (visions).
These produce choices about gaining information — reading emotions,
sensing danger, locating things, glimpsing possible futures. Many of
these enhance other checks (Sense + Vigilance for initiative, Seek +
Perception for finding hidden objects).

**Restoration and harm:** Heal (mending wounds), Harm (inflicting wounds
through the Force), Protect/Unleash (defensive barrier / Force
lightning). Heal/Harm is the most morally loaded power — the same
ability that saves lives can take them, and the dark side temptation
on Harm checks carries heavy Conflict.

**Power data representation:**

Each power the character possesses is stored in the character state as
a structured entry:

```json
{
  "power_id": "move",
  "name": "Move",
  "category": "physical_manipulation",
  "base_pips_required": 1,
  "active_upgrades": ["strength_1", "range_1"],
  "narrative_capability": "Can move objects up to silhouette 1
    within medium range using the Force. With concentration, can
    hurl small objects with enough force to harm.",
  "gm_choice_guidance": "Offer telekinetic choices when physical
    objects could be manipulated at a distance. Lifting, pushing,
    pulling, catching, throwing. Scale to current upgrades — base
    Move cannot shift a starship.",
  "dark_side_flavor": "Dark side Move is violent. Objects don't
    drift — they slam. The Force doesn't suggest motion, it
    demands it."
}
```

The `narrative_capability` field is injected into the GM's character
capabilities block so it knows what this character can do. The
`gm_choice_guidance` field is injected into the narration prompt to
help the GM generate appropriate Force-tagged choices. The
`dark_side_flavor` field is available when dark pips were used, giving
the GM tonal direction for narrating dark-side-fueled Force use.

#### 16.4 Force Power Progression

Force power upgrades use the same milestone reflection system as talent
acquisition (Section 14.3, Category 1), with a separate milestone
category for Force power advancement.

**New milestone category — Force power upgrade.**

*Trigger:* Reserved XP sufficient for a power upgrade purchase, AND
the character has used the relevant Force power at least once in the
current or previous act (behavioral signal), AND the behavioral
inference engine's Force usage patterns suggest a progression
direction.

*Presentation:* A reflection passage themed around deepening the
character's relationship with a specific aspect of the Force:

> *The training sessions had shifted. What Master Skywalker asked of
> him now was not the basic exercises — lift the stone, feel the
> presence, quiet the mind. It was refinement. Precision. Control
> over aspects of the Force that had been blunt instruments.*

> *He could feel the edges of what was possible. Three directions,
> each requiring a different kind of discipline.*

> *Reach further. The stone across the clearing. The tool on the
> far workbench. Distance was a wall, and he could feel it thinning.*
> → Range upgrade: increase effective range of Move by one band

> *Push harder. Not just the stone but the boulder. Not just the
> tool but the workbench it sat on. Mass was resistance, and
> resistance could be overcome.*
> → Strength upgrade: increase silhouette limit of Move by 1

> *Think faster. The stone in mid-air, held and then redirected.
> The tool caught and thrown in a single motion. The Force as
> reflex, not deliberation.*
> → Control upgrade: use Move as a maneuver (in addition to action)

The player navigates the power upgrade tree the same way they navigate
the talent tree — through narrative choices that map to mechanical
branches, without ever seeing the grid.

**XP costs for Force powers:**

Base power: 5-15 XP (varies by power, per FFG). Upgrades: 5-15 XP
each, increasing with depth (same tier pricing as talent trees). These
are drawn from the `reserved_xp` pool, same as talent milestones.

**Force Rating increases:**

Force Rating increases through specific talents deep in Force-sensitive
specialization trees (the Force Rating talent, analogous to Dedication).
When the character reaches a Force Rating talent through their talent
tree progression, a Category 3 milestone fires that presents the
increase as a fundamental deepening:

> *Something shifted. Not a skill learned or a technique mastered —
> something deeper, structural, like a room in his mind he hadn't
> known was there suddenly opening. The Force didn't get louder. It
> got wider. More of it was available. More of it was him.*

Force Rating increases from 1→2 or 2→3 are the most transformative
progression events for a Force user, comparable to a characteristic
increase for a non-Force character. They are rare — once per campaign
at most.

#### 16.5 Committed Force Dice

Some Force powers have ongoing effects — Sense's danger awareness,
Protect's defensive barrier, Enhance's sustained physical augmentation.
In FFG, maintaining these effects requires **committing** Force dice.
A committed Force die is removed from the character's available pool
for as long as the effect is maintained.

**Design:**

The character state tracks `force_committed: int` (already present in
the character model). When a sustained Force effect is active, the
committed dice are subtracted from the available Force Rating for all
subsequent Force rolls.

*Example:* A character with Force Rating 2 commits 1 die to Sense
(ongoing danger awareness). They now roll only 1 Force die on any
Force use. If they commit the second die to Enhance (sustained physical
augmentation), they have 0 available Force dice and cannot perform any
additional Force actions until they release a commitment.

**Committing and releasing in the prose-first format:**

Committing dice happens automatically when the character activates a
sustained Force power — the engine reduces available Force dice and
tracks the commitment. The player does not choose to commit; the
power's nature requires it.

Releasing a commitment requires a narrative transition — the character
consciously stops maintaining the effect. This is handled through
choices: if a character has committed Force dice to Sense and the
situation shifts (entering combat, for instance), the GM may offer
choices that implicitly release the commitment ("Drop your awareness
net and focus everything on the fight" vs "Maintain your danger sense
but with less Force available for active use").

The engine tracks commitments in the character state:

```json
{
  "force_committed": 1,
  "active_commitments": [
    {
      "power": "sense",
      "upgrade": "danger_sense",
      "dice_committed": 1,
      "committed_since_turn": 14,
      "narrative_note": "Ongoing danger awareness — the character
        feels threats before they materialize"
    }
  ]
}
```

The GM prompt receives the active commitments as part of the character
state, allowing it to weave the sustained effect into the prose
("the prickling at the base of his skull that hadn't stopped since
the cantina — it intensified now, focused on the corridor ahead").

#### 16.6 The Dark Side Spiral

The Morality system (Section 9), the dark side temptation (Section
16.2), and the Force power system (Section 16.3) create a feedback
loop that is deliberate and central to the Force user experience.

**The spiral, stated clearly:**

A character under pressure reaches for the dark side to succeed at a
critical moment. This generates Conflict. Conflict drifts Morality
darker. As Morality drops below 40, the dark side becomes the
character's *natural channel* — dark pips are free, light pips cost
strain. This makes it *easier* to use the dark side and *harder* to
use the light. Which generates more Conflict. Which drifts Morality
further. The spiral accelerates.

This is not a bug. This is how the dark side works in Star Wars. It is
fast and easy and it gets faster and easier the more you use it. The
spiral is the mechanic that produces the fiction's most compelling
moral stories — because *pulling out of the spiral* requires the player
to consistently choose the harder, costlier, less effective path. It
requires them to accept failure when success was available, to pay
strain when the dark side was free, to watch their character struggle
when power was right there.

**Anti-spiral safety valve:**

The spiral must not become irreversible within a single campaign. If a
character reaches Morality 0, they are fully dark-side-dominant but
not mechanically locked in. The path back exists — it is just
punishingly expensive in strain and narrative suffering. The campaign
spine can author specific redemption anchor beats (a confrontation with
a loved one, a mirror moment, a choice that forces the player to see
what they have become) that reduce Conflict accumulation temporarily
or grant Morality restoration outside the normal resolution cycle.

These are not automatic. The player must still choose the light-side
action at the redemption beat. The spine creates the opportunity. The
dice determine the outcome. The player's choice determines the moral
direction. All three must align for the spiral to reverse.

**The GM's role in the spiral:**

The GM prompt's Morality label (Section 9) already adjusts tone based
on Morality band. The Force mechanics section adds a specific
instruction for Force-related narration:

For light-dominant characters (71-100): "Force use feels natural,
responsive, warm. The character reaches and the Force meets them. Dark
side temptation passages should emphasize the *wrongness* of the dark
current — it is alien, invasive, a violation of the character's
relationship with the Force."

For grey characters (41-70): "Force use is uncertain, flickering. The
character reaches and sometimes the Force answers clearly, sometimes
it hesitates. Dark side temptation passages should emphasize the
*familiarity* of the dark current — it is known, not alien. The
character has been here before. The question is whether they go back."

For dark-dominant characters (0-40): "Force use feels like command.
The character demands and the Force obeys. Light side temptation
passages should emphasize the *effort* required — reaching for the
light is like swimming upstream, fighting a current the character
has been riding for months or years. It is exhausting and unfamiliar
and the payoff is not obvious."

#### 16.7 Force Use in the Check Decision Flow

The local model must recognize when a player's action involves the
Force and tag the check appropriately. This extends the check decision
schema and prompt.

**Check decision schema additions:**

```json
{
  "requires_check": true,
  "skill": "athletics",
  "difficulty": "hard",
  "force_use": true,
  "force_power": "enhance",
  "force_pips_required": 1,
  "scene_type": "combat",
  "moral_weight": 0,
  "reasoning": "Leaping across the chasm while channeling the Force
    to augment physical ability. Enhance + Athletics."
}
```

New fields:
- `force_use: bool` — whether this action involves the Force
- `force_power: str` — which Force power applies (from the
  character's active powers list)
- `force_pips_required: int` — minimum pips needed for the base
  effect. Defaults to 1. Higher for powerful applications.

**Check decision prompt additions:**

The check decision prompt gains a `FORCE POWERS` section when the
character has Force Rating > 0:

```
FORCE POWERS:
This character is Force-sensitive (Force Rating {force_rating},
{available_force_dice} dice available after commitments).
Active powers: {power_list_with_brief_descriptions}

When the player's action involves using the Force:
- Set force_use to true
- Set force_power to the relevant power name
- Set force_pips_required to the minimum pips needed (usually 1
  for basic applications, 2+ for powerful effects)
- The skill field should be the mundane skill being enhanced, or
  omitted for pure Force actions
- Force dice are added automatically by the engine — do not
  include them in boost_dice

When the player's action does NOT involve the Force, even if the
character is Force-sensitive, set force_use to false. Not every
action by a Jedi involves the Force. Walking, talking, shooting
a blaster — these are mundane actions for everyone.
```

**Pool construction for Force checks:**

When `force_use` is true, `build_pool()` adds Force dice equal to
the character's available Force Rating (total minus committed) to the
pool. For pure Force actions (no mundane skill), the pool contains
only Force dice, boost, and setback — no ability, proficiency,
difficulty, or challenge dice. The "success" of a pure Force action
is determined entirely by pip generation versus requirement.

For Force-enhanced skill checks, the pool contains both the standard
skill dice and the Force dice. The standard dice resolve
success/failure. The Force dice resolve pip generation. Both results
are reported to the cloud GM.

#### 16.8 New Force User Onboarding

When a character first awakens to the Force (Section 14.4) or begins
a campaign as Force-sensitive (Posture 1), they enter the Force system
at a specific starting configuration:

**Awakened characters (Posture 3, accepted):**
- Force Rating: 1
- Force powers: none initially. First power acquired through the
  first Force-related milestone reflection, typically within 1-2 acts
  of awakening. The campaign spine defines which powers are available
  based on the character's context (a Jedi Academy student gets
  offered basic Sense or Move; a self-taught Force user in the
  wilderness might get Enhance or Survival-oriented powers).
- Morality: activates as secondary motivation track. Starting value 50
  (neutral). Conflict accumulation begins immediately from this point
  forward.

**Explicit Force characters (Posture 1):**
- Force Rating: 1 (starting; increases through Force Rating talents
  in specialization trees)
- Force powers: 1-2 starting powers defined by the character variant.
  A Jedi Guardian variant might start with Move and Enhance. A Mystic
  might start with Sense and Foresee. These are authored in the
  campaign spine's character variant data.
- Morality: primary motivation track. Starting value set by the
  variant (typically 50, but the campaign spine can adjust).

**The first Force milestone:**

For awakened characters, the first Force-related milestone reflection
is critical to the experience. It is the moment where the character
goes from "something strange is happening" to "I can do something
with this." The campaign spine should author a milestone window within
1-2 acts of the awakening point, offering 2-3 starting powers that
match the character's context and the behavioral signals from the
awakening act.

> *Master Skywalker had explained it three different ways. The third
> time, something clicked. Not in his mind — in his body. In the
> place behind his sternum where the Force lived.*
>
> *The exercises were simple. Embarrassingly simple. But simple did
> not mean easy.*

> *Feel it. The stone on the table, its weight, its presence in the
> Force. Now move it. Not with your hands.*
> → Move: telekinesis. Begin with small objects at close range.

> *Feel it. The presence of the other students in the room. Their
> emotions like colors you didn't know existed. Anxiety. Boredom.
> Curiosity. The one in the back row — something darker.*
> → Sense: emotion reading and danger awareness.

> *Feel it. Your own body. The Force flows through muscle and bone.
> You have been strong; now learn to be more than strong.*
> → Enhance: physical augmentation through the Force.

### Implementation Notes

**Character state additions:**

- `force_powers: list[ForcePower]` — new field. Each entry contains:
  power ID, name, category, base pip requirement, active upgrades,
  narrative capability, GM choice guidance, and dark side flavor text.
- `active_commitments: list[ForceCommitment]` — new field. Each entry
  tracks: power, upgrade, dice committed, turn committed since, and
  narrative note.
- `force_committed: int` — already exists. Updated when commitments
  change.

**Turn record additions:**

- `force_use: bool` — whether Force dice were rolled this turn.
- `force_power: Optional[str]` — which power was used.
- `force_pips_required: int` — pip requirement for this use.
- `force_result: Optional[ForceResult]` — light pips, dark pips,
  pips used, dark pips used, conflict earned from dark pip usage.
- `dark_side_temptation_offered: bool` — whether the temptation choice
  was presented.
- `dark_side_temptation_accepted: bool` — whether the player chose to
  use dark pips.

**Check decision schema extension:**

The `CHECK_DECISION_SCHEMA` adds three optional fields: `force_use`
(bool), `force_power` (string, from valid power names), and
`force_pips_required` (int, minimum 1). The `CheckDecision` dataclass
gains matching fields with defaults (`force_use=False`,
`force_power=None`, `force_pips_required=0`).

**Turn flow modification — Force resolution:**

The turn flow from Section 15 (with the talent intervention step)
extends:

1. Player selects choice
2. Local model decides check (now including Force fields)
3. Engine builds pool (adding Force dice if force_use is true)
3a. Talent passive/conditional modifier pass
4. Engine rolls dice
4a. **Force pip resolution.** Engine separates Force result from skill
    result. Evaluates pip sufficiency against requirement.
4b. **Dark side temptation check.** If pips insufficient from light
    side alone but sufficient with dark pips, present temptation
    choice. Player decides.
4c. **Talent intervention check** (existing step 3.5, renumbered).
    Type 5 talent interventions evaluated against the final result.
5. Cloud GM generates narration from combined skill + Force result
6. New choices presented (Force-tagged choices included based on
   character capabilities)

Steps 4b and 4c both use the pre-narration choice mechanism. If both
trigger on the same turn (rare — requires a Force check that also has
an applicable Type 5 intervention), the dark side temptation is
presented first. The player resolves the moral question before the
mechanical intervention question.

**GM prompt additions:**

The narration prompt gains:

- A `FORCE STATE` block in the character section:
  ```
  Force Rating: {force_rating} ({available_dice} available)
  Morality: {morality_value} — {morality_label}
  Active commitments: {commitment_descriptions}
  ```

- A `FORCE RESULT` block in the turn-specific section (when Force
  dice were rolled):
  ```
  Force dice result: {light_pips} light, {dark_pips} dark
  Pips required: {pips_required}
  Dark side used: {yes/no, how many pips}
  Force outcome: {success/failure/dark_success}
  {force_narration_guidance based on morality band}
  ```

- Force powers listed in the CHARACTER CAPABILITIES block alongside
  Type 4 narrative enabler talents.

**New module:** `engine/force.py`. Contains:

- `resolve_force_pips(result: RollResult, pips_required: int,
  morality: int) -> ForceResolution` — evaluates pip sufficiency,
  determines whether temptation triggers, and computes costs for
  dark pip usage based on morality band.
- `apply_dark_side_choice(resolution: ForceResolution,
  accepted: bool) -> ForceResult` — finalizes the Force result after
  the player's temptation decision.
- `commit_force_dice(character: Character, power: str, upgrade: str,
  dice: int) -> Character` — applies a Force commitment.
- `release_force_commitment(character: Character,
  commitment_id: str) -> Character` — releases a commitment.
- `get_available_force_dice(character: Character) -> int` — returns
  force_rating minus force_committed.
- `build_force_context(character: Character,
  force_result: Optional[ForceResult]) -> ForceContext` — assembles
  Force-related context for the GM prompt.

**Force power data:**

Stored in `data/force_powers/`. Each power is a JSON file containing:
base pip requirement, upgrade tree (with tier costs and pip
requirement changes per upgrade), narrative capability at each upgrade
level, GM choice guidance, and dark side flavor text. The upgrade tree
structure mirrors the talent tree branch model — named paths (range
path, strength path, control path) that milestone reflections can
target through narrative choices.

```
data/force_powers/
├── move.json
├── sense.json
├── influence.json
├── enhance.json
├── heal_harm.json
├── bind.json
├── misdirect.json
├── seek.json
├── foresee.json
├── protect_unleash.json
└── ...
```

**Phased implementation:**

Phase 1 (with talent tree Phase 3): Implement the Force dice
resolution engine (`engine/force.py`), dark side temptation choice
mechanism, check decision Force fields, and GM prompt Force context
blocks. Use a single Force power (Move) for validation.

Phase 2: Add the core Force power set — Move, Sense, Influence,
Enhance, Heal/Harm. Author power data files and upgrade trees.
Validate the milestone reflection system for Force power progression.

Phase 3: Complete the Force power catalogue. Add committed Force dice
management. Validate the dark side spiral over multi-act campaigns.

Phase 4: Cross-era Force progression — validate the full arc from
Force awakening through Jedi Knight-level capability across multiple
campaign spines. This is the test case for your saga concept.

---
## 17. Vehicle and Starship Encounters

### The Problem

FFG Star Wars has a full vehicle and starship subsystem: hull trauma
(vehicle wounds), system strain (vehicle strain), shields (fore/aft/
port/starboard), speed and handling ratings, silhouette (size class),
component targeting, and a distinct critical hit table for vehicles.
Space combat at the table runs on the same round-by-round structure as
personal combat but with different actions: Pilot Only maneuvers, Gain
the Advantage, Angle Deflector Shields, Fire Linked Weapons. A capital
ship battle might run 15+ rounds.

Section 3 solved the personal combat abstraction by resolving encounters
at the engagement level rather than the round level. Vehicle encounters
need a parallel treatment with different constraints: the player is
typically commanding a ship, not swinging a weapon; the choices are
tactical (reroute power, target engines, evasive pattern) rather than
physical; and the scale difference between personal and vehicle combat
matters — a freighter fighting TIE fighters is a fundamentally
different fiction from a person fighting stormtroopers.

For your saga concept, vehicle encounters span everything from a
smuggler kid's first desperate escape in a stolen shuttle to a Jedi
Knight commanding a starfighter during the Yuuzhan Vong invasion.

### The Design

#### 17.1 The Ship State Card

Every ship the character operates has a state card in the session data,
parallel to NPC state cards. The ship state tracks the narrative and
mechanical status of the vessel:

```json
{
  "ship_id": "miras_luck",
  "name": "Mira's Luck",
  "type": "YT-2000 light freighter",
  "silhouette": 4,
  "speed": 3,
  "handling": -1,
  "hull_threshold": 22,
  "system_strain_threshold": 16,
  "current_hull_trauma": 0,
  "current_system_strain": 0,
  "armor": 3,
  "shields": {"fore": 1, "aft": 1},
  "weapons": [
    {
      "name": "Dorsal laser turret",
      "skill": "gunnery",
      "damage": 6,
      "arc": "all",
      "qualities": ["linked_1"]
    }
  ],
  "active_damage": [],
  "narrative_notes": "Battered but reliable. The hyperdrive has a
    tendency to stutter on cold starts. Keth knows every sound she
    makes and can tell by engine pitch alone when something is wrong."
}
```

The ship state is loaded from the campaign spine's vehicle registry
for ships defined in the campaign, or created when a new ship is
introduced. The state persists across turns and sessions, tracking
damage and system strain the same way the character state tracks wounds
and strain.

**Simplified damage model:** FFG's vehicle damage uses hull trauma
(reduced by armor), system strain (from ion weapons, maneuvers, and
critical hits), and a vehicle critical hit table with specific
mechanical effects (Engine Hit, Weapon Damaged, Hull Breach, etc.).

In Storyteller V3, vehicle damage is abstracted to three levels:

**Operational** — Hull trauma below 50% of threshold, system strain
below 50%. The ship is functional. Prose reflects a working vessel.
No mechanical penalties.

**Stressed** — Either hull trauma or system strain at 50-80% of
threshold. The ship is taking punishment. The GM prompt receives:
"The ship is stressed — describe intermittent system failures, sparks,
warning lights, the sounds of a vessel being pushed past comfort." The
check decision prompt adds 1 setback die to all vehicle-related checks
to represent deteriorating performance.

**Critical** — Either threshold above 80%, or a critical hit has been
sustained. The ship is in danger of being lost. The GM prompt receives
specific critical damage descriptions (from the critical hit table,
resolved by the engine when Triumph/Despair occurs on vehicle checks).
The check decision prompt adds 2 setback dice. Certain choices may
become unavailable — "Jump to hyperspace" is not an option if the
hyperdrive is damaged.

This three-tier model replaces the granular hull/strain tracking with a
narrative status that the prose can convey without numbers.

#### 17.2 Encounter Resolution

Vehicle encounters follow the same encounter-level abstraction as
personal combat (Section 3), adapted for the tactical vocabulary of
ship operations.

**The player's role determines the skill:**

In FFG, crew members take different roles: pilot, gunner, mechanic,
comms officer, captain. In our single-character format, the player
occupies whichever role their choice implies:

- Choices about maneuvering, evasion, and pursuit → Piloting (Space)
  or Piloting (Planetary)
- Choices about targeting, firing, and weapon solutions → Gunnery
- Choices about rerouting power, emergency repairs, boosting shields
  → Mechanics
- Choices about coordinating crew, directing NPC actions, tactical
  command → Leadership
- Choices about astrogation, calculating hyperspace routes, finding
  navigational solutions → Astrogation
- Choices about electronic warfare, jamming, sensor use → Computers

The local model selects the skill based on the player's choice, same as
personal combat. The player never selects a "crew role." They pick the
action and the system maps it to the appropriate skill.

**Handling as pool modifier:**

FFG ships have a Handling rating (+2 to -3) that modifies Piloting
checks. Positive handling adds boost dice. Negative handling adds
setback dice. This is a ship-level passive modifier, applied the same
way talent passives are applied in Section 15's pool modification
pipeline — the engine reads the ship's handling rating and adjusts the
pool before rolling.

**Encounter structure:**

Small-scale encounters (dogfight with pirates, evading a patrol, running
a blockade) use 1-3 turns, identical to personal combat's encounter-
level resolution. Each turn resolves one phase of the engagement.

*Example — Running the Nal Hutta blockade:*

Turn 1: The approach. Imperial interdictors have locked down the
system. The player chooses their approach: punch straight through at
full speed (Piloting check, hard difficulty), slip through disguised
as local traffic (Deception or Computers for transponder spoofing), or
find a gap in the patrol pattern (Perception + Astrogation). The check
resolves the first phase.

Turn 2: Complication. Based on Turn 1's result — if they ran and
succeeded with threat, they're through the outer line but the TIEs
have scrambled. New choices: outrun them (Piloting), fight (Gunnery),
or lose them in the asteroid field (Piloting, harder difficulty but
success means clean escape). If Turn 1 failed, they're engaged and
must deal with an active interdiction.

Turn 3 (if needed): Resolution. Escaped, captured, or something in
between. A Triumph might mean the ship took no damage and gained
intelligence on the Imperial patrol patterns. A Despair might mean
escape with a crippled hyperdrive.

Large-scale encounters (fleet battle participation, capital ship
engagement, Yuuzhan Vong invasion battle) use the multi-beat sequence
structure (2-4 turns) with the addition of a **battle context layer**
— a persistent description of the larger battle that changes between
beats, giving the player a sense of the war going on around their
personal encounter.

*Example — Battle of a star system (NJO era):*

Battle context: "The Yuuzhan Vong fleet dropped from hyperspace in three
waves. The New Republic defense line is holding but stretched thin.
Coralskippers are swarming the starfighter screen."

Beat 1: The player's squadron engages a coralskipper formation. Choices
about tactical approach. Gunnery or Piloting check resolves the
engagement phase.

Battle context update: "The second wave has punched through the
picket line. A Yuuzhan Vong frigate analog is targeting the medical
frigate."

Beat 2: New situation forced by the battle context. The player must
choose between continuing their current engagement or breaking off to
defend the medical frigate. Different skills, different stakes, the
larger battle shaping personal choices.

Beat 3: Resolution. The battle outcome is determined by the campaign
spine (the galactic context layer decides whether the system falls or
holds), but the player's personal outcome within the battle — survival,
heroism, loss, the state of their ship and crew — is determined by
their choices and dice.

#### 17.3 Ship Damage and Repair

**Hull trauma and system strain** accumulate based on check results.
When a vehicle check produces net threat, the GM decides whether the
threat manifests as system strain (subsystems stressed) or enemy hits
(hull trauma). The engine applies damage to the ship state card. The
three-tier status (operational/stressed/critical) updates automatically.

**Vehicle critical hits** are resolved when a Triumph or Despair occurs
on a vehicle-context check. The engine rolls on a simplified vehicle
critical hit table (10 entries rather than FFG's full table) and applies
the result as a narrative tag on the ship state — identical to how
personal critical injuries work in Section 3.

Simplified vehicle critical table:
1-2: Rattled — cosmetic damage, no mechanical effect
3-4: Shields disrupted — reduce shield in one arc by 1 until repaired
5-6: Engine hit — reduce speed by 1 until repaired
7-8: Weapon damaged — one weapon offline until repaired
9: Navigation systems hit — Astrogation checks +1 difficulty
10: Hull breach — hull trauma threshold reduced by 2 until repaired

**Repair** occurs during narrative downtime — between encounters, during
time skips, at friendly ports. The campaign spine and the GM narrate
repair as story beats, not as mechanical transactions. A Mechanics check
during downtime can restore hull trauma and system strain, with the
result determining how much is repaired and whether the fix holds. Major
damage (critical hits) requires specific narrative conditions — access
to a repair yard, a skilled NPC mechanic, parts acquisition.

### Implementation Notes

**New state model:** `ShipState` — Pydantic model parallel to
`NPCState`, stored in a new `ship_states` table in SQLite. Contains
all fields from the ship state card above. Loaded from the campaign
spine's vehicle registry at session creation.

**Scene type extension:** The scene type enum gains a seventh value:
`space_combat`. This signals the check decision prompt to use vehicle-
appropriate skills and the narration prompt to use space combat prose
pacing. The existing `combat` and `chase` types remain valid for
personal-scale encounters. `space_combat` indicates the vehicle
subsystem is active.

**Check decision prompt addition:** When `scene_type` is `space_combat`,
the prompt includes the ship's current status and capabilities:

```
SHIP STATUS: {ship_name} — {status_tier}
Handling: {handling} | Speed: {speed}
Weapons: {weapon_list}
Active damage: {damage_list}
```

**Context assembly:** The ship state card is injected into the context
package alongside NPC state cards. The GM receives the ship's narrative
notes and current status to weave into prose — the sounds of a damaged
engine, the flicker of shields taking hits, the feel of a ship that
handles differently when stressed.

**Campaign spine additions:** Each campaign spine includes an optional
`vehicle_registry` listing ships available to the character, with full
stat blocks. The test campaign spine (The Nar Shaddaa Job) would include
Mira's Luck as the primary ship.

---

## 18. Equipment and Inventory

### The Problem

FFG has extensive gear lists: weapons with damage and critical ratings,
armor with soak and defense values, slicing gear, medical supplies,
survival equipment, communications gear, droids. At the table, players
track specific items — "I have a heavy blaster pistol, a comlink, two
stimpacks, and a breath mask." Equipment affects dice pools (weapon
damage, armor soak), enables specific actions (you need a medpac to
attempt Medicine checks in the field), and creates narrative texture
(the character's gear says something about who they are).

The prose-first format cannot accommodate traditional inventory
management without creating a menu-based equipment screen that breaks
immersion. But completely ignoring equipment makes the world feel
abstract — a smuggler's tools should matter, a soldier's kit should
affect what they can do.

### The Design

#### 18.1 The Loadout Model

Equipment is managed through a **loadout** — a structured summary of
what the character carries and has access to, tracked in the character
state. The loadout is not an item-by-item inventory list. It is a
curated set of capability categories with narrative descriptions.

```json
{
  "loadout": {
    "weapons": [
      {
        "name": "Modified DL-44 heavy blaster pistol",
        "skill": "ranged_light",
        "damage_bonus": 7,
        "critical_rating": 3,
        "qualities": ["stun_setting"],
        "narrative_note": "Scratched and reblued twice. The grip is
          shaped to Keth's hand from years of use."
      }
    ],
    "armor": {
      "name": "Spacer's leather jacket (armored liner)",
      "soak_bonus": 1,
      "defense": 0,
      "narrative_note": "Looks like a jacket. Is a jacket. The liner
        is a pragmatic addition, not a fashion statement."
    },
    "tools": [
      {
        "category": "slicing",
        "name": "Custom slicing kit",
        "mechanical_effect": "Enables Computers checks on secured
          systems. Removes 1 setback from slicing attempts.",
        "narrative_note": "Hidden in the lining of his bag. Three
          dataspikes, a code cylinder, and a signal scrambler."
      },
      {
        "category": "medical",
        "name": "Two stimpacks",
        "mechanical_effect": "Can heal 5 wounds per stimpack. Two
          uses before resupply needed.",
        "narrative_note": "Standard Alliance surplus. Functional
          but not comfortable."
      }
    ],
    "special_items": [
      {
        "name": "Forged Imperial transit pass",
        "mechanical_effect": "Reduces difficulty of checks to pass
          Imperial customs by 1.",
        "narrative_note": "Good enough to fool a bored checkpoint
          guard. Would not survive an ISB audit."
      }
    ]
  }
}
```

**What the loadout tracks:**

**Weapons** — each entry has a skill association, damage value, critical
rating, and qualities. The engine uses these during combat checks: the
weapon's damage modifies the consequence of success (the GM is told the
effective damage to narrate), and weapon qualities are available for the
GM's advantage-spending narration (Section 3). The check decision prompt
does not need weapon data — it decides skill and difficulty. The weapon
affects the *outcome*, not the *check*.

**Armor** — soak bonus and defense rating. Soak is applied automatically
when the character takes wound damage (wounds reduced by soak + Brawn).
Defense adds setback dice to incoming attacks, applied through the pool
modification pipeline alongside talent effects.

**Tools** — categorized by function (slicing, medical, mechanical,
survival, communications). Tools enable or modify specific check types.
A character without a medpac cannot attempt field medicine. A character
with a slicing kit removes setback from Computers checks on secured
systems. Tool effects are either passive modifiers (handled by the
engine) or capability gates (handled by the check decision prompt,
which knows what tools the character has).

**Special items** — narrative-significant objects that create specific
mechanical effects or story opportunities. The forged transit pass, the
Jedi holocron, the encrypted data chip containing evidence. These are
authored in the campaign spine and updated by gameplay events.

#### 18.2 Acquisition and Loss

The loadout changes through gameplay, not through shopping UI.

**Acquisition** happens through the story: looting after a successful
encounter, purchasing at a market (resolved as a social or Streetwise
check, not a menu), receiving from an NPC, discovering during
exploration, or crafting during downtime. When the GM narrates the
acquisition, the engine adds the item to the loadout. The check
decision prompt and narration prompt handle this organically — the GM
describes finding a weapon, and the turn processing adds it to state.

The campaign spine defines **starting loadout** for each character
variant, appropriate to their career and situation. Keth starts with
his blaster, jacket, slicing kit, and stimpacks. A Jedi Academy
student might start with training clothes and a practice lightsaber.

**Loss** happens through narrative consequences: confiscation at a
checkpoint, damage during a fight (Despair can destroy an item), trade
as payment, voluntary abandonment. The engine removes items based on
narrative events flagged in the turn processing.

**Resupply** for consumable items (stimpacks, ammunition) happens at
narrative transition points — visiting a market, returning to base,
receiving a supply drop. The engine checks consumable counts at act
boundaries and flags low supplies to the GM, which weaves resupply
opportunities into the early turns of the next act.

#### 18.3 Equipment and the Check Decision

The local model needs to know about equipment that gates or modifies
checks. The check decision prompt gains an `EQUIPMENT` section:

```
EQUIPMENT:
{equipment_summary_for_check_decision}
```

This section is assembled from the loadout and lists:

- Tool capabilities: "Has slicing kit — can attempt Computers checks
  on secured systems (1 setback removed)."
- Weapon-skill associations: "Armed with DL-44 heavy blaster — Ranged
  (Light) is the appropriate combat skill."
- Capability gates: "No climbing gear — Athletics checks for vertical
  ascent are +1 difficulty."

The section is concise — only items that affect check decisions are
listed. The GM's narration prompt receives the full loadout with
narrative notes for prose flavor.

#### 18.4 Equipment and the Narration

The cloud GM receives the full loadout in the character state block.
Narrative notes tell the GM *how* the character interacts with their
gear — not just "has a blaster" but "has a blaster shaped to their hand
from years of use." This enables equipment-specific prose that grounds
the character in physical reality.

Weapon qualities surface in advantage-spending narration (Section 3):
when a combat check produces net advantages, the GM selects from the
weapon's qualities to narrate the effect. A blaster with Stun Setting
produces different advantage narration than a vibroblade with Pierce.

Armor and soak surface in damage narration: when a character takes
wounds, the prose reflects what their armor absorbed versus what got
through. "The bolt caught him in the chest. The armored liner took
the worst of it — without it, he'd be on the ground."

#### 18.5 Lightsabers

Lightsabers deserve specific mention because they function differently
from all other weapons in the FFG system and carry unique narrative
weight in Star Wars.

**FFG lightsaber mechanics:** The lightsaber skill uses Brawn as its
governing characteristic by default, but several Force specialization
talents allow substituting a different characteristic (Cunning for a
deceptive fighter, Willpower for a disciplined one, Agility for a
graceful one). Lightsabers have high damage (base 6 + Brawn), low
critical rating (1 — they critical on any advantage), and the Breach 1
quality (ignores 10 points of armor — lightsabers cut through almost
anything).

**Prose-first treatment:** The lightsaber is introduced as a narrative
milestone, not an inventory addition. When a character constructs or
receives their first lightsaber, the campaign spine marks it as a
major story moment — comparable in weight to a talent milestone or
Force awakening. The weapon enters the loadout like any other, but the
prose around its introduction carries ceremony.

The lightsaber's mechanical power (high damage, Breach, low critical
threshold) is reflected in the narration: lightsaber combat is more
decisive than blaster combat. Encounters involving lightsabers resolve
faster (1-2 turns rather than 2-3) because lightsabers are
narratively lethal. Success with advantage doesn't just injure — it
maims or disarms. The GM prompt receives specific guidance when the
character wields a lightsaber: "Lightsaber combat is fast and
decisive. Every exchange carries lethal weight. Near-misses scorch and
scar. Successful strikes have permanent consequences."

The characteristic substitution from talent trees (Section 15) is
handled by a Type 3 skill substitution talent: "Lightsaber skill may
use {characteristic} instead of Brawn." The check decision prompt's
talent effects section carries this information, allowing the local
model to build the pool correctly.

### Implementation Notes

**Character state additions:**

- `loadout: Loadout` — new field. Pydantic model containing weapons,
  armor, tools, and special items as structured lists.

**Campaign spine additions:**

- `starting_loadout` per character variant — the loadout the character
  begins with.
- `vehicle_registry` (from Section 17) — ships available to the
  character.

**Check decision prompt:** Gains `EQUIPMENT` section between character
summary and talent effects, listing capability-relevant gear.

**Narration prompt:** Receives full loadout with narrative notes in the
character state block.

**Context assembly:** The loadout is classified as **kinetic context**
for scene-type-aware assembly (Section 10). Weapon and armor details
are foregrounded in combat scenes, backgrounded in social and
introspection scenes. Tool details are foregrounded when relevant to
the scene type (slicing kit in infiltration, medpac after combat).

**New module:** `engine/equipment.py`. Contains:

- `apply_weapon_damage(result: RollResult, weapon: Weapon, target_soak: int) -> DamageResult` — computes wounds inflicted from a successful combat check
- `apply_armor_soak(incoming: int, armor: Armor, brawn: int) -> int` — reduces incoming wounds by soak
- `check_tool_requirements(skill: str, tools: list[Tool]) -> ToolModifier` — evaluates whether the character has required tools and returns any pool modifiers
- `update_loadout(loadout: Loadout, event: LoadoutEvent) -> Loadout` — processes acquisition, loss, and consumable use events

---
## 19. Time Skip Mechanics

### The Problem

The multi-session continuity system (Section 11) handles the player
returning after real-world days or weeks — the fiction freezes between
sessions. But multi-era campaigns require **narrative time skips** where
months or years pass within the fiction: the smuggler kid ages from 12
to 16 during Jedi Academy training, the Jedi Knight ages from 20 to 25
between the Academy era and the NJO. During these gaps, the character
trains, relationships evolve, the galaxy changes, and the person who
emerges on the other side is different from the one who entered.

Section 11's act boundary system freezes state. Time skips need to
*advance* state — credibly, controllably, and with player input into
the direction of growth.

### The Design

#### 19.1 Two Scales of Time Skip

**Intra-campaign skips** occur between acts within a single campaign
spine. Weeks or months pass. The character trains, recovers, travels.
These are common — a 4-act campaign might have 3-month gaps between
Acts 2 and 3. The campaign spine defines the skip duration and
narrative framing per act transition.

**Inter-campaign skips** occur between campaign spines, at import
boundaries. Years pass. The character's life circumstances change
fundamentally. These are rare and significant — your smuggler kid
entering the Academy, the Academy student graduating into the NJO era.
These are handled by the cross-era progression system (Section 20) and
triggered during Category 5 milestone reflections (Section 14.3).

This section covers intra-campaign skips. Inter-campaign skips are
specified in Section 20.

#### 19.2 What Changes During a Skip

The between-act processing pipeline (Section 14, Implementation Notes)
already runs at act boundaries. Time skips extend this pipeline with
additional steps that simulate the passage of time.

**Skill drift.** During a time skip, skills the character used heavily
in the previous act receive a small passive improvement (1-2 XP worth
of progress, applied through the behavioral inference engine as if the
character "practiced" during the gap). Skills not used at all may decay
by 0.5 ranks — not enough to lose a full rank, but tracked as a
fractional value that delays the next rank increase. This is subtle and
never communicated to the player directly. They experience it as "I'm
a little rustier at this than I expected" or "that came easier than it
used to" in the narration.

Skill decay is **optional and configurable per campaign spine.** Some
campaigns may disable it (short time skips don't warrant decay). The
default is enabled for skips of 3+ months.

**NPC relationship drift.** NPCs the character interacted with
frequently in the previous act maintain or slightly improve their
disposition during the skip — these relationships were active. NPCs
the character did not interact with drift toward a neutral baseline by
a small amount (0.02-0.05 per month of skip). Close relationships
resist this drift — disposition above 0.8 or below 0.2 drifts slower.
The effect is that acquaintances fade while deep relationships persist.

The campaign spine can override drift for specific NPCs with authored
skip events: "During the gap, Doss was arrested and his disposition
toward Keth shifts by -0.1 (Keth wasn't there to help)." These are
injected into NPC state cards before the next act begins.

**Strain and wound recovery.** Full recovery during any skip of 1+ weeks.
Current wounds and current strain reset to 0. Active injuries heal
unless the campaign spine specifies otherwise (major critical injuries
from Section 3 may persist with GM narration noting the scar or
lingering limitation).

**Galactic context advance.** The galactic context layer (Section 4)
updates for the new act. The campaign spine defines the new galactic
state, which may be dramatically different after a multi-month gap.
The "Previously..." summary at session resume bridges the gap.

**Motivation track events.** For longer skips (6+ months), the between-
act processing runs an additional Obligation/Duty roll representing
background pressure during the gap. If Obligation activates, the act
opens with narrative consequences of the Obligation compounding during
the skip ("Three months and the debt hasn't gotten smaller. If
anything, the interest has been accruing in ways Keth hadn't expected").

#### 19.3 The Player Experience of a Time Skip

The player experiences a time skip as a structured sequence of five
elements at the act boundary. The sequence takes 4-6 minutes of reading
and interaction — long enough to feel like the gap was lived, short
enough to maintain momentum into the next act.

**Element 1 — The act summary.** The "Previously..." recap from Section
11's session resume design. Covers what happened in the act just
completed. This exists regardless of whether a time skip follows.

**Element 2 — The opening passage.** A brief impressionistic montage
(2-3 paragraphs) establishing the texture of the gap period. Not a
detailed account — a compression of time into feelings, routines, and
shifts. Generated by the cloud GM from the campaign spine's skip
framing notes and the character's state.

> *Three months passed the way time passes when you stop running:
> slowly at first, then all at once.*
>
> *The Academy had rhythms. Morning meditation before the jungle mist
> burned off. Lightsaber forms on the courtyard stones. Evening meals
> with the other students, where the silences gradually became more
> comfortable than the conversations that filled them.*

This passage is not interactive. The player reads it like a chapter
break in a novel. It sets the temporal and emotional frame for
everything that follows.

**Element 3 — Skip vignettes.** The core of the time skip experience.
Two to three short playable scenes drawn from the gap period, each
one presenting a single passage and a single choice. Vignettes are
not full gameplay turns — there are no dice rolls, no skill checks,
no mechanical resolution. They are narrative moments where the player
makes a character decision that carries real weight.

Each vignette produces concrete mechanical effects: behavioral data
for the inference engine (the choice's skill tag feeds into skill
drift weighting), NPC disposition changes (the player's response to
an NPC shifts the relationship), and aspiration signals (the choice
pattern across vignettes tells the system what the player is reaching
for during this period).

Vignettes are where the player *lives* the time skip rather than
being told about it.

**Element 4 — The closing passage.** A brief passage (1-2 paragraphs)
after the final vignette, bridging from the gap period into the
present moment of the new act. This passage reflects the cumulative
effect of the player's vignette choices — the character who emerges
from the gap is shaped by what the player did within it.

**Element 5 — Milestone reflections.** Any milestones triggered by
the between-act processing (talent acquisition, Force power upgrade,
specialization crossroads) are presented after the closing passage
and before the new act opens. These are separate from the vignette
choices — the vignettes capture how the character lived during the
gap; the milestones capture how the character grew.

#### 19.4 Skip Vignettes — Design

**What a vignette contains:**

Each vignette is a self-contained narrative moment: one passage of 3-5
paragraphs, followed by 2-3 choices. The passage sets a specific scene
within the gap period — a particular day, a particular interaction, a
particular challenge. The choices represent different ways the character
could respond. No choice is wrong. Each produces a different character
signal.

*Example vignette 1 — Training crisis (Academy skip):*

> *The exercise was simple. Embarrassingly simple. Lift the stone.
> Hold it steady. Set it down. Every other student in the courtyard
> could do it. The Barabel in the back row could do it in her sleep.*
>
> *Keth couldn't do it. The stone trembled, rose half a meter, and
> dropped. Three times. Four. The frustration was physical — heat
> behind his eyes, tension across his shoulders, the old familiar
> impulse to walk away from anything that wouldn't yield to instinct
> and cleverness.*
>
> *Master Skywalker watched from the colonnade. He didn't intervene.
> He didn't offer advice. He watched.*

> *Try again. Slower this time. Feel the weight of it not with his
> hands but with the thing behind his sternum that the instructors
> kept calling the Force and he kept thinking of as the hum.*
> → Patience. Discipline. Feeds behavioral signal toward Willpower,
> Force training. Produces small Morality increase (light-affirming).

> *Walk away. Not permanently — he'd be back tomorrow. But right now,
> the stone wins. There's no shame in knowing when you've hit the
> wall for the day.*
> → Self-awareness. Pragmatism. Feeds behavioral signal toward
> Resilience, emotional regulation. Neutral Morality.

> *Get angry. Not at the stone — at himself. At the gap between what
> everyone else could do and what he couldn't. Use that heat. Reach
> for the stone with the hot thing instead of the calm thing.*
> → Intensity. Dark-side-adjacent. Feeds behavioral signal toward
> Willpower, but through anger. Produces Conflict (moral_weight 1).
> The stone rises. Master Skywalker's expression changes.

*Example vignette 2 — NPC relationship (Academy skip):*

> *Jacen found him in the archives after hours. Not looking for him,
> exactly — Jacen seemed to live here when the other students were
> sleeping. He was reading something about Sith philosophy, which
> would have been alarming from anyone else but from Jacen was just
> curiosity.*
>
> *"You're not sleeping either," Jacen said. Not a question.*
>
> *Keth wasn't sleeping because the dreams about Nar Shaddaa had been
> worse this week. He hadn't told anyone. The other students had their
> own problems. He didn't need to add his to the pile.*

> *Tell him. Not everything — not the debts, not Vossk, not the years
> of running. But the dreams. The way the corridors still felt more
> real than the Academy some nights.*
> → Trust. Vulnerability. Jacen disposition increases significantly.
> Social aspiration signal. Feeds behavioral inference toward
> Presence/social skills.

> *Deflect. "Just couldn't sleep. What are you reading?" Turn it
> back to him. The old instinct: never show what's underneath. Gather
> information instead of giving it.*
> → Self-protection. The street kid's instinct. Jacen disposition
> change is smaller but positive (he recognizes the deflection and
> doesn't push). Feeds behavioral inference toward Cunning/Deception.

> *Ask about the Sith text. Change the subject to something
> intellectual — something they can discuss as equals rather than as
> a kid with nightmares and a Jedi's son. Meet Jacen where he lives.*
> → Intellectual engagement. Sidesteps the emotional moment but
> builds a different kind of connection — shared curiosity. Jacen
> disposition increases moderately. Feeds behavioral inference toward
> Knowledge/Lore.

*Example vignette 3 — Solitary reflection (Academy skip):*

> *The roof of the old temple was technically off-limits. Keth had
> found the access route in his second week — an instinct for exits
> and vantage points that the Academy hadn't trained into him and
> probably couldn't train out.*
>
> *From up here, the jungle stretched to the horizon in every
> direction. No buildings. No corridors. No recycled air. Just green
> and birdsong and the vast, disorienting openness of a planet that
> didn't have a ceiling.*
>
> *He came here when the Academy felt too much like a box with nice
> furniture.*

> *Meditate. Master Skywalker's instructions, followed for once
> without resistance. Quiet the mind. Feel the living things. Let
> the Force be a presence rather than a tool.*
> → Force attunement. Discipline. Aspiration signal toward Force
> training. Feeds skill drift toward Discipline and Force powers.

> *Plan. Old habits. Map the terrain, identify resources, think
> through contingencies. The Academy wouldn't last forever. What
> came after? Where would he go? Who would he be?*
> → Strategic thinking. Independence. Aspiration signal toward
> Cunning and self-reliance. Feeds skill drift toward Survival,
> Streetwise.

> *Just... be here. Don't train. Don't plan. Don't analyze. Sit on
> the roof of an ancient Jedi temple on a jungle moon and exist for
> thirty minutes without turning the experience into something useful.*
> → Presence. Letting go. The hardest thing for someone who survived
> by constant vigilance. Aspiration signal toward Willpower and
> emotional growth. Small Morality increase.

**How vignettes are selected:**

The campaign spine defines a **vignette library** per time skip — a
pool of 4-6 authored vignettes, each tagged with:

- `category`: training, relationship, solitary, crisis, discovery,
  mundane
- `npc_focus`: which NPC is central (if any)
- `skill_domain`: which skill categories the choices feed
- `requires`: optional prerequisites (e.g., "latent_force_sensitive
  is true," "disposition with Jacen > 0.5," "previous act contained
  a combat failure")
- `excludes`: conditions that remove this vignette from the pool

The system selects 2-3 vignettes from the library based on:

**Behavioral signal matching.** The player's choice patterns from the
previous act suggest which categories are most relevant. A player who
gravitated toward social interactions gets at least one relationship
vignette. A player who struggled with Force checks gets a training
vignette.

**NPC relationship priority.** Vignettes featuring NPCs the player
has the strongest relationship with (highest or lowest disposition)
are prioritized. The player should encounter the characters they
care about most during the gap.

**Category diversity.** The system ensures the selected vignettes span
at least two different categories. Three training vignettes would feel
monotonous. A training + relationship + solitary combination provides
texture and variety.

**Prerequisite filtering.** Vignettes with unmet prerequisites are
removed from the pool before selection. A vignette requiring Force
sensitivity does not appear for a non-Force character. A vignette
featuring Jacen does not appear if Jacen's disposition is below the
threshold.

**Short skips (1-2 months):** One vignette. The opening passage is
briefer (1-2 paragraphs), the closing passage is a single paragraph,
and the entire skip takes 2-3 minutes.

**Medium skips (3-6 months):** Two vignettes. The standard experience
described above. 4-5 minutes.

**Long skips (6+ months):** Three vignettes. The opening passage is
more substantial (3-4 paragraphs), time-stamp headers separate the
vignettes to convey the span ("Two weeks in" / "The third month" /
"Near the end"), and the closing passage reflects a more significant
transformation. 5-7 minutes.

#### 19.5 Vignette Mechanical Effects

Vignette choices produce three categories of mechanical effect, all
processed during the between-act pipeline:

**Behavioral inference input.** Each vignette choice carries a hidden
skill tag (same system as regular turn choices). The tags across all
vignette choices are fed into the behavioral inference engine alongside
the previous act's turn data, weighted as if the vignette choices
were made during the final 2-3 turns of the act. This means the
player's behavior during the skip directly influences which skills
receive drift XP. A player who chose the patience option in the
training vignette, the trust option with Jacen, and the meditation
option on the roof produces strong Willpower and Discipline signals.
A player who chose anger, deflection, and planning produces Cunning
and Willpower signals — same characteristic, different direction.

**NPC disposition changes.** Vignette choices that involve NPC
interaction produce disposition changes on the relevant NPC state
card. These are defined per choice in the vignette data — each choice
specifies which NPC's disposition it affects and by how much (+0.05
to +0.15 for positive interactions, -0.05 to -0.10 for negative
ones). The changes are applied before the next act begins, so the
NPC's behavior in Act 3 reflects how the player interacted with them
during the skip.

**Morality effects.** Vignette choices can carry moral_weight values
(0-3), same as regular turn choices. The training vignette's anger
option produces Conflict. The meditation option produces a small
Morality boost. These feed into the end-of-act Morality resolution
alongside any Conflict from the previous act's gameplay.

#### 19.6 Authoring Vignettes

Vignettes are authored in the campaign spine alongside anchor beats
and NPC roster entries. They are a Campaign Studio concern — the Game
Engine consumes them as data and presents them, but the creative design
lives in the spine.

**Vignette authoring guidelines for the Campaign Studio:**

Each vignette should be a self-contained moment that could exist in a
novel. The test: if you read this scene in a Star Wars book during a
time-skip chapter, would it feel earned? Would it reveal something
about the character? Would you remember it?

No choice should be obviously "correct." The training vignette's anger
option is not a trap — it produces real mechanical benefits (the stone
rises, the behavioral signal is strong) alongside a real cost
(Conflict). The player who chooses it is playing a character with a
specific relationship to frustration, and the system should respect
that.

Vignettes should reference events from the previous act when possible.
A training vignette that echoes a failure from Act 2 — "the same
feeling he'd had in the corridor on Nar Shaddaa, reaching for
something just out of reach" — connects the skip to the lived
experience and makes the gap feel like continuity rather than a reset.

At least one vignette per skip should feature an NPC relationship.
Time skips are where relationships deepen. A skip with no NPC
interaction wastes the gap's relationship-building potential.

**Vignette data schema:**

```json
{
  "vignette_id": "academy_skip_training_crisis",
  "category": "training",
  "npc_focus": null,
  "skill_domain": ["willpower", "discipline", "force"],
  "requires": {"latent_force_sensitive": true},
  "excludes": {},
  "time_stamp": "The second week",
  "passage": "The exercise was simple. Embarrassingly simple...",
  "choices": [
    {
      "text": "Try again. Slower this time...",
      "skill_tag": "discipline",
      "npc_effects": {},
      "moral_weight": 0,
      "morality_bonus": 1,
      "aspiration_tags": ["patience", "force_attunement", "discipline"],
      "narrative_consequence": "The stone rises. Not far, not
        steady, but it rises. The hum in his chest quiets into
        something that almost feels like the calm the instructors
        keep describing."
    },
    {
      "text": "Walk away. Not permanently...",
      "skill_tag": "resilience",
      "npc_effects": {},
      "moral_weight": 0,
      "morality_bonus": 0,
      "aspiration_tags": ["self_awareness", "pragmatism"],
      "narrative_consequence": "He walks back to the dormitory
        with the sunset on his back. Tomorrow. The stone isn't
        going anywhere."
    },
    {
      "text": "Get angry...",
      "skill_tag": "willpower",
      "npc_effects": {},
      "moral_weight": 1,
      "morality_bonus": 0,
      "aspiration_tags": ["intensity", "dark_side_adjacent", "force_power"],
      "narrative_consequence": "The stone slams upward — not a
        gentle rise but a violent lurch, three meters off the ground
        before he can think to stop it. It hovers, trembling with the
        force of his frustration. Across the courtyard, Master
        Skywalker's expression does something complicated."
    }
  ]
}
```

Each choice includes a `narrative_consequence` — a brief passage (2-4
sentences) that immediately follows the player's selection, showing the
outcome of their choice within the vignette. This is not generated by
the cloud GM. It is authored in the spine alongside the vignette,
ensuring quality and consistency. The vignette is a contained authored
experience, not a generative one.

After the final vignette's consequence passage, the closing passage
(Element 4 from Section 19.3) is generated by the cloud GM, informed
by the full set of vignette choices the player made. This closing
passage is generative — it synthesizes the player's specific pattern of
skip choices into a narrative summary of who the character has become
during the gap.

### Implementation Notes

**Campaign spine additions:**

- `time_skip` per act transition — optional. Contains:
  `duration_months` (int), `narrative_framing` (str, guidance for
  opening and closing passage generation), `skip_events` (list of
  authored events affecting NPC states or world state variables),
  `skill_decay_enabled` (bool), `vignette_library` (list of vignette
  data objects), `vignette_count` (int, 1-3 — overrides the duration-
  based default if the author wants control).

**Between-act processing pipeline extension:**

After existing steps 1-10 (Section 14), when a time skip is defined:

11. Opening passage generation — cloud GM produces the time skip
    opening montage
12. Vignette selection — system selects 2-3 vignettes from the library
    based on behavioral signals, NPC priority, and category diversity
13. Vignette presentation — each vignette is presented sequentially
    (passage → choice → consequence → next vignette)
14. Vignette effect processing — behavioral tags, NPC disposition
    changes, and Morality effects from all vignette choices are
    aggregated
15. Skill drift — apply passive XP based on prior act behavior +
    vignette behavioral signals
16. NPC relationship drift — adjust dispositions based on interaction
    frequency, skip duration, and vignette NPC effects
17. Authored skip events — apply campaign-spine-defined state changes
18. Closing passage generation — cloud GM produces the closing passage
    informed by vignette choice patterns
19. Milestone presentations (if triggered)

---

## 20. Cross-Era Character Progression

### The Problem

The Campaign Studio's import interface (Campaign Studio Section 6.1)
handles the mechanical transfer of a character between campaign spines:
NPC relationships, motivation tracks, world state variables. But the
character *sheet itself* — skills, talents, specializations, Force
Rating, equipment — must transform when moving between eras. A smuggler
kid becoming a Jedi student is not a mechanical transfer. It is a
character metamorphosis.

FFG's multi-specialization rules allow buying into additional
specialization trees at increasing XP cost. This provides the
mechanical foundation. The design question is how the prose-first
format presents, manages, and narratively frames a character whose
identity spans multiple careers and eras.

### The Design

#### 20.1 The Import Package

When a character moves from one campaign spine to the next, the Game
Engine exports an **import package** — a complete snapshot of the
character's state, stripped of campaign-specific data and enriched with
cross-campaign metadata:

**Carried forward (mechanical):**
- Full character sheet: characteristics, skills, all ranks
- Acquired talents (full list with source specializations)
- Force powers and upgrade state
- Force Rating
- Total XP earned and spent (the character's full mechanical history)
- Morality value and Conflict history
- Obligation/Duty values and types
- `latent_force_sensitive` and `force_rejected_count`

**Carried forward (narrative):**
- Advancement log (Section 14) — what the character has become and when
- NPC relationship summaries — compressed one-sentence descriptions of
  significant relationships, keyed by NPC name
- World state variables — the butterfly-effect booleans from prior
  campaigns (Campaign Studio Section 6.3)
- Throughline question history — the prior campaign's throughline and
  how the character's choices answered it (or didn't)
- Character voice notes — how the character speaks, thinks, and
  presents, evolved through play

**Not carried forward:**
- Turn-level history (compressed away; only act summaries survive)
- NPC full state cards (compressed to relationship summaries)
- Campaign-specific arc state
- Session data

#### 20.2 Era Transition Processing

When the receiving campaign spine ingests an import package, the
engine runs a **transition processing** step before the first act:

**Specialization mapping.** The receiving campaign spine's import
interface specifies how the character's existing specializations
interact with the new campaign context. Three outcomes are possible:

*Continuity* — the specialization remains fully active. A Smuggler/
Pilot specialization continues to function in a Jedi Academy campaign.
The character retains all talents and can continue progressing.

*Dormancy* — the specialization becomes inactive but is not lost.
Talents from dormant specializations are not applied to checks and
do not appear in the GM prompt, but the character retains them. If
circumstances change (the former smuggler needs to fly again),
dormancy can be lifted through a narrative trigger authored in the
spine. This handles the transition where a street kid's survival
skills are less relevant during formal Jedi training but might become
critical later.

*Evolution* — the specialization maps to a related specialization in
the new context. A Smuggler/Scoundrel specialization might evolve
into a Sentinel/Shadow specialization when the character enters
the Jedi Order — the social manipulation skills are the same, but
the context and identity have shifted. Evolution preserves acquired
talent progress where the talents overlap and opens new talent
branches where they diverge.

The spine author designs these mappings during campaign creation. The
Game Engine applies them mechanically.

**Motivation track transition.** The primary motivation track may change
at era transitions. A smuggler carrying Obligation who enters the
Rebellion acquires Duty as a secondary track (or primary, if the
campaign spine designates it). A non-Force character who accepts Force
awakening gains Morality. The import interface specifies track
transitions, and the Category 5 milestone reflection (Section 14.3)
presents them as narrative choices.

**XP rebalancing.** Characters entering a new era may have XP totals
that are too low or too high for the new campaign's intended power
level. The campaign spine specifies a `target_xp_range` — a minimum
and maximum total XP for incoming characters. If the character is below
minimum, they receive bonus XP during the inter-campaign time skip
(representing off-screen growth during the years between campaigns).
If above maximum, no XP is removed — the character is simply ahead of
the curve, which the spine's difficulty calibration should accommodate.

**Equipment transition.** The loadout (Section 18) is rebuilt at era
transitions. The campaign spine defines a starting loadout for imported
characters that replaces the prior campaign's gear, reflecting the
character's new circumstances. A smuggler entering the Academy doesn't
bring their blaster (or rather, it's confiscated/stored — the spine
might track it as a dormant special item that returns later). A Jedi
Knight entering the NJO campaign starts with their lightsaber, robes,
and whatever the spine defines.

#### 20.3 The Transition Passage

The inter-campaign time skip is presented as a longer, more reflective
passage than the intra-campaign skip (Section 19). This passage covers
years, not months, and represents a fundamental chapter break in the
character's life:

> *Five years.*
>
> *Five years since the streets. Five years since the jobs and the
> debts and the constant, grinding arithmetic of survival. The Academy
> had taken all of it — the paranoia, the instincts, the ability to
> read a room for threats before anyone else had finished their first
> drink — and reshaped it into something the Jedi Order could use.*
>
> *He was not the kid who had arrived at Yavin 4 with stolen credits
> and a Force sensitivity he still half-wished would go away. But he
> was not entirely someone else, either. The old reflexes surfaced at
> odd moments. The way he automatically mapped exits in every room.
> The way he still thought in terms of angles and leverage before he
> thought in terms of trust.*

The transition passage is followed by the Category 5 milestone
reflection, where the player makes the identity choices that define
their character in the new era.

### Implementation Notes

**Import/export module:** `engine/import_export.py`. Contains:

- `export_character(character, session, campaign) -> ImportPackage` —
  generates the full import package from current state
- `apply_import(package, target_spine) -> Character` — processes the
  import package against the receiving spine's import interface,
  applying specialization mappings, motivation transitions, XP
  rebalancing, and loadout rebuilding
- `generate_transition_passage(package, target_spine) -> str` — prompt
  assembly for the transition passage generation

**Campaign spine additions:**

- `import_interface` (Campaign Studio Section 6.1, now with mechanical
  detail): `compatible_campaigns` (list), `specialization_mappings`
  (dict mapping source specs to continuity/dormancy/evolution),
  `motivation_transition` (dict), `target_xp_range` (tuple),
  `imported_loadout` (Loadout), `transition_framing` (str for passage
  generation)

---

## 21. Large-Scale NPC Management

### The Problem

A character who has played through three campaigns accumulates
relationships with 30+ NPCs — smuggler contacts, Jedi instructors,
fellow students, military commanders, antagonists, canon characters.
The current system gives every NPC a full state card injected into the
GM prompt. This does not scale. At 30+ NPCs, the state cards would
consume a significant fraction of the context window, diluting the
GM's attention on the NPCs who actually matter this scene.

The design needs: relevance routing (which NPCs matter right now?),
state compression (full cards for active NPCs, summaries for
background), and relationship lifecycle management (how NPCs enter,
persist, and fade).

### The Design

#### 21.1 NPC Tiers

Every NPC is assigned to one of three tiers based on recency and
significance. Tier assignment is dynamic — it changes every turn based
on narrative context.

**Tier 1 — Active (full state card).** NPCs who are present in the
current scene, referenced in the current act's anchor beats, or whose
relationship with the character is narratively relevant right now.
Maximum 4-6 Tier 1 NPCs per turn. Full state cards injected into the
GM prompt: knowledge, disposition, motivation, voice notes, behavioral
envelope.

**Tier 2 — Relevant (compressed summary).** NPCs who are not in the
scene but have been referenced recently (within the current act),
whose relationship to the character is significant (disposition above
0.8 or below 0.2), or who are connected to the current narrative
thread. Maximum 6-10 Tier 2 NPCs. Injected as one-sentence summaries:
"Doss (former contact, disposition 0.3 — strained trust after Nar
Shaddaa)."

**Tier 3 — Background (not injected).** All other NPCs. State cards
are preserved in the database but not included in the GM prompt. These
NPCs can be promoted to Tier 2 or Tier 1 when narrative context
brings them back into relevance.

#### 21.2 Relevance Scoring

Tier assignment is computed by a relevance scoring function that runs
at the start of each turn, before context assembly. The function
evaluates each NPC against five signals:

**Scene presence (highest weight).** Is this NPC named in the current
scene description, the previous turn's narration, or the player's
selected choice? Direct mentions guarantee Tier 1.

**Anchor beat connection.** Is this NPC referenced in the current act's
anchor beat definition or the next upcoming anchor? If so, Tier 1 or
high Tier 2 — the NPC is approaching narrative significance even if
they haven't appeared yet.

**Recency.** How recently was this NPC's state card updated? NPCs
interacted with in the last 3 turns score high. NPCs not seen for
10+ turns score low. NPCs from previous campaigns score lowest.

**Relationship intensity.** Extreme dispositions (very loyal or very
hostile) score higher than neutral. The characters who love you and
the characters who hate you are more narratively relevant than
acquaintances.

**Narrative thread connection.** Does this NPC connect to any of the
current act's open threads? The thread tracking system already
maintains a list of unresolved narrative questions. NPCs connected to
active threads score higher.

The scoring function produces a ranked list. The top 4-6 become Tier 1,
the next 6-10 become Tier 2, and the rest remain Tier 3.

#### 21.3 State Compression for Cross-Campaign NPCs

When a character's import package (Section 20) carries NPC relationships
into a new campaign, the full state cards are compressed to
**relationship summaries** — one-paragraph distillations of the
relationship's history, current state, and emotional significance:

```json
{
  "npc_name": "Jacen Solo",
  "relationship_summary": "Trained alongside Jacen at the Academy for
    three years. Started as mutual wariness — Jacen's thoughtfulness
    clashed with Keth's instinct-first approach. Gradually developed
    into genuine respect. Last interaction: Jacen helped Keth understand
    a difficult Force meditation technique. Disposition: 0.72 (warm,
    with underlying philosophical tension).",
  "era": "jedi_academy",
  "last_campaign": "yavin_training",
  "disposition_at_export": 0.72
}
```

When the receiving campaign spine reintroduces a previously known NPC
(Jacen Solo appearing in the NJO campaign), the import interface
**rehydrates** the relationship summary into a full state card. The
summary provides the disposition baseline and relationship history.
The new campaign spine provides the updated NPC profile — Jacen's
current motivation, knowledge state, voice notes appropriate to the
new era. The combined result is an NPC who remembers the shared history
while existing in the present.

NPCs from prior campaigns who are not reintroduced in the new campaign
remain as compressed summaries in the character's relationship history.
They can surface in reputation echoes ("A name from the Academy —
someone who remembered Keth from the old days") or through authored
spine events, but they do not occupy context window space unless
promoted.

#### 21.4 The Reputation Network

As the NPC roster grows across campaigns, the reputation echo system
(Section 1) needs to draw from a larger pool. The reputation log
tracks notable player actions across all campaigns, and imported
reputation entries persist through era transitions.

The reputation echo injection selects from the 3-5 most relevant
reputation entries per turn — relevance scored by: connection to the
current scene's location or faction, recency, and narrative impact.
A reputation entry from the Academy era might surface in the NJO
campaign when the character encounters someone who knew them during
that period: "The Barabel pilot studied him for a long moment. 'You
were at the Academy. Solusar's cohort. I remember your name.'"

### Implementation Notes

**NPC state table extension:** Add `tier: int` (1-3) and
`relevance_score: float` columns to the `npc_states` table. Updated
per turn by the relevance scoring function.

**Context assembly modification:** The NPC injection step in the
context pipeline reads tier assignments and injects accordingly:
Tier 1 as full state cards, Tier 2 as one-sentence summaries, Tier 3
omitted. The total NPC context is capped at a configurable token
budget (default: 1500 tokens, roughly 10% of a typical context
window allocation for NPCs).

**New module:** `engine/npc_relevance.py`. Contains:

- `score_npc_relevance(npc, scene, act, turn_history) -> float` —
  computes relevance score for a single NPC
- `assign_tiers(npcs, scene, act, turn_history) -> dict[str, int]` —
  ranks all NPCs and assigns tiers
- `compress_npc_for_export(npc_state, turn_history) -> RelationshipSummary` — generates cross-campaign summary
- `rehydrate_npc(summary, spine_npc_profile) -> NPCState` — combines
  imported summary with new campaign's NPC profile

**Import package additions:** `npc_summaries: list[RelationshipSummary]`
— compressed NPC relationships from prior campaigns.

---

## 22. Canon Character Voice Fidelity

### The Problem

When the GM writes Jacen Solo, Luke Skywalker, Jaina Solo, or any
other established Legends character, the prose must feel like *that
person* — not a generic NPC with their name. Star Wars readers know
these characters intimately. A Jacen Solo who talks like a generic
Jedi teenager will break immersion for any player who has read the
Young Jedi Knights or NJO novels.

The existing NPC system provides voice notes and behavioral envelopes,
which work for original characters. Canon characters need deeper
profiling — their speech patterns, thinking styles, relationship
dynamics, and hard red lines are established by decades of published
fiction. The LLM has this information in its training data but needs
structured prompting to access it consistently rather than collapsing
to stereotypes (a known risk per Research Catalogue Source 11).

### The Design

#### 22.1 Canon Character Profiles

Canon characters receive an **extended NPC profile** — a structured
document that goes beyond the standard state card fields to capture
the character's established identity. This profile lives in the
campaign spine as part of the NPC roster entry.

```json
{
  "name": "Jacen Solo",
  "canon": true,
  "era_profile": "njo_early",
  "role": "Fellow Jedi Knight — philosophical counterweight",

  "voice": {
    "speech_patterns": "Thoughtful. Pauses before speaking. Asks
      questions that reframe the problem. Dry humor inherited from
      Han but delivered with Leia's precision. Uses metaphors from
      nature and the Force, not from technology or combat.",
    "thinking_style": "Seeks understanding before action. Sees
      connections between living systems. Questions the Jedi Order's
      assumptions from within, not as rebellion but as genuine inquiry.
      His intelligence is philosophical, not tactical.",
    "emotional_register": "Warm but contained. Empathy is his
      default mode — he feels what others feel and this is both
      his strength and his vulnerability. Anger is rare and
      frightening when it surfaces because it is so unlike him."
  },

  "behavioral_envelope": [
    "Never acts without thinking first — impulsive action is
      fundamentally out of character",
    "Never dismisses another person's perspective, even an enemy's",
    "Never brags about his family — the Solo/Skywalker legacy is
      a weight he carries, not a credential he deploys",
    "Does not use the Force casually or showily — his relationship
      with the Force is reverent and personal"
  ],

  "relationship_dynamics": {
    "with_player": "Initially cautious — Jacen reads people carefully
      and a former street kid registers as an unknown variable. Warms
      through demonstrated thoughtfulness, not through competence or
      aggression. A player who asks why before acting earns Jacen's
      respect faster than one who acts effectively.",
    "with_jaina": "Twin bond that operates on a level neither fully
      understands. Jaina is action where Jacen is thought. They
      complement but also frustrate each other. Their disagreements
      are never petty.",
    "with_anakin_solo": "Older-brother protectiveness layered over
      genuine admiration for Anakin's directness. Jacen overthinks;
      Anakin acts. Jacen sometimes envies this and sometimes fears it."
  },

  "era_specific_notes": "Pre-capture Jacen. The philosophical
    questions are genuine curiosity, not the darker searching that
    comes later. His faith in the Force is whole. His doubts are
    about the Order's methods, not about the Force itself. He has
    not yet been broken and remade.",

  "anti_stereotype_notes": "Do NOT write Jacen as: a generic wise
    Jedi, a brooding philosopher, a Han Solo clone with Force powers,
    or a simple pacifist. He is specific: a young man who thinks
    deeply and feels deeply, whose intelligence is emotional and
    philosophical rather than strategic, who would rather understand
    a problem than solve it quickly."
}
```

#### 22.2 Profile Sections Explained

**Voice** gives the GM specific direction for dialogue and interiority
when writing this character. Speech patterns, thinking style, and
emotional register are the three dimensions that make a character feel
like themselves on the page.

**Behavioral envelope** defines hard constraints — things this
character would never do regardless of narrative pressure. The envelope
is the same field used by standard NPCs (Section 15.5) but is more
detailed for canon characters because the stakes of getting them wrong
are higher. The LLM needs explicit "never" constraints because its
default is to make NPCs cooperative with whatever the narrative needs.

**Relationship dynamics** are specific to canon characters because
their relationships with each other are as established as their
individual identities. Jacen and Jaina's twin dynamic, Jacen and
Anakin Solo's brother dynamic, Luke's teaching relationship with his
students — these need to be authored rather than inferred because the
LLM will default to generic relationship templates otherwise.

The `with_player` entry is particularly important: it tells the GM how
this canon character would respond to the specific protagonist the
player is playing. This is authored per campaign spine with awareness
of the character variants — a former street kid gets a different
reception from Jacen than a disciplined military brat would.

**Era-specific notes** ground the character in a specific point in
their timeline. Jacen Solo in the Academy era is fundamentally
different from Jacen Solo during the NJO, who is different from Jacen
Solo during the Dark Nest Crisis. The canon profile must be era-locked
to prevent the GM from writing a character who exhibits traits from a
future or past version of themselves.

**Anti-stereotype notes** directly address the LLM archetype collapse
documented in Research Catalogue Source 11. Without explicit
counterpressure, LLMs trained on Star Wars fiction will default Jacen
to a "wise Jedi" archetype, Jaina to a "tough female pilot" archetype,
and Luke to a "benevolent master" archetype. These are reductive. The
anti-stereotype section tells the GM what this character is NOT, pushing
the output into more specific territory.

#### 22.3 Canon Profile Integration

Canon profiles are injected into the GM narration prompt when the
character is Tier 1 (present in the scene). The profile replaces the
standard NPC state card's voice notes and behavioral envelope with the
extended format.

The prompt injection is structured as:

```
NPC — JACEN SOLO (canon character):
Disposition: {current_disposition}
Knowledge: {what_jacen_knows}
{voice section}
{behavioral_envelope}
{era_specific_notes}
{anti_stereotype_notes}
Relationship with {player_character}: {relationship_dynamics.with_player}
```

**Token budget consideration:** Canon profiles are longer than standard
NPC state cards (~300 tokens vs ~80 tokens). The NPC tier system
(Section 21) accommodates this by limiting Tier 1 to 4-6 NPCs. In
scenes with multiple canon characters, the token budget for NPCs may
need to increase. The context assembly pipeline's NPC token cap should
be treated as a soft limit that can flex upward for canon-heavy scenes.

#### 22.4 Canon Character Progression Across Eras

When a campaign spine spans a period where a canon character is known
to change (Jacen Solo's arc from idealistic student to Dark Lord of
the Sith), the canon profile must evolve across acts.

The campaign spine defines **per-act canon profile overrides** for
characters whose arc requires it:

```json
{
  "name": "Jacen Solo",
  "base_profile": "jacen_solo_njo_early",
  "act_overrides": {
    "act_3": {
      "era_specific_notes": "Post-capture Jacen. The Yuuzhan Vong
        broke something and rebuilt it differently. His philosophy
        has shifted from curiosity to conviction. He is sure of
        things he used to question. This certainty is new and
        unsettling to those who knew him before.",
      "voice": {
        "emotional_register": "Calmer than before, but the calm
          is different. Not peaceful — resolved. The empathy is
          still there but filtered through something harder."
      }
    }
  }
}
```

The engine merges act overrides onto the base profile at the start of
each act. Fields not overridden retain their base values. This allows
the campaign author to evolve a canon character across the campaign's
timeline while maintaining consistency in fields that don't change.

**Player-influenced canon character state:**

The player's relationship with a canon character creates state that
diverges from the published canon. If the player built a deep
friendship with Jacen during the Academy era, NJO-era Jacen's
`with_player` relationship dynamics are richer than the default. The
import interface carries this relationship forward.

The key design constraint: **canon events happen regardless of the
player's relationship.** Jacen's capture by the Yuuzhan Vong occurs
in the galactic context layer. His philosophical transformation
occurs in the era-specific notes. The player cannot prevent these
events. What the player *can* affect is how the canon character
relates to *them* within these fixed events — a Jacen who considers
the player a close friend processes his captivity differently in
scenes with the player than a Jacen who barely knows them.

### Implementation Notes

**Campaign spine NPC roster extension:** Canon NPCs include all
standard NPC fields plus: `canon: true`, `era_profile` (string
referencing a profile version), `voice` (extended three-field
structure), `relationship_dynamics` (dict), `era_specific_notes`
(string), `anti_stereotype_notes` (string), `act_overrides` (dict).

**Profile data storage:** Canon character profiles can be stored
centrally in `data/canon_profiles/` and referenced by campaign
spines, allowing reuse across campaigns set in the same era. A
campaign set during the Academy era and a different campaign set
during the same period can share Jacen's base profile while
authoring different `with_player` relationship dynamics.

```
data/canon_profiles/
├── luke_skywalker_academy.json
├── jacen_solo_academy.json
├── jacen_solo_njo_early.json
├── jacen_solo_njo_post_capture.json
├── jaina_solo_academy.json
├── jaina_solo_njo.json
├── anakin_solo_njo.json
└── ...
```

**Context assembly:** Canon profiles use the same injection point as
standard NPC state cards but with the extended format. The NPC
relevance scoring function (Section 21) treats canon and original
NPCs identically for tier assignment — a canon character who is not
in the scene is Tier 2 or Tier 3 regardless of their fame. Narrative
relevance, not canon status, determines context window priority.

---
## 23. Destiny Point Pool

### The Problem

FFG's Destiny Pool is a shared resource between players and the GM. At
session start, each player generates a Light or Dark side token based on
a Force die roll. Players spend Light Side points to upgrade an ability
die to proficiency (better odds) or to trigger certain abilities. The GM
spends Dark Side points to upgrade difficulty dice to challenge (worse
odds) or to introduce complications. When a point is spent, it flips to
the other side — Light becomes Dark, Dark becomes Light. The pool
creates a push-and-pull rhythm: the more the players invest, the more
ammunition the GM has.

In our system, V1 tracks `destiny_light` and `destiny_dark` in the
session table but spending is deferred (Rule 8). The design challenge
has three dimensions:

First, the invisible mechanics principle. In tabletop, "I spend a
Destiny Point" is an explicit tactical declaration. In our system, the
player should never say or think those words. They should feel the
effect — a moment where the odds shifted in their favor, or a scene
where everything went wrong in ways that felt like fate — without seeing
the resource.

Second, the GM side. In tabletop, the human GM decides when to spend
Dark Side points against the players. Our GM is an LLM. It does not
manage resources or make adversarial decisions. The Dark Side spending
needs to be engine-driven, triggered by narrative conditions.

Third, the pool modification pipeline. Section 15 defines three stages
for pool construction: base pool → passive talents → conditional
talents. Destiny Point upgrades modify the pool (upgrading dice), which
means they need a defined position in that pipeline. Building the
pipeline without a Destiny slot means retrofitting it later.

### The Design

#### 23.1 Pool Initialization and Reset

At session creation, the engine generates the starting Destiny Pool
by rolling one Force die per player character. In our single-player
format, this is one Force die roll. The light and dark pips from the
roll set the starting `destiny_light` and `destiny_dark` values.

Typical result: 1-2 light pips and 0-1 dark pips, or 1-2 dark pips
and 0-1 light pips. The Force die's distribution (6 dark faces, 2
single-light faces, 4 double-light faces) means the average starting
pool leans slightly toward light — 1.75 light pips vs 1.58 dark pips
on average per die.

**Reset timing:** The pool resets at act boundaries (our session-
equivalent). A new Force die is rolled at the start of each act. This
prevents pool starvation over long acts and creates a fresh rhythm
each session.

**Pool state:** `destiny_light: int` and `destiny_dark: int` in the
session table. Already exist in V1 schema.

#### 23.2 Light Side Spending — Player Favor

When the engine spends a Light Side Destiny Point, it upgrades one
ability die (green d8) to a proficiency die (yellow d12) in the
player's pool. This is a meaningful boost — proficiency dice have more
success faces, double-success faces, and the Triumph face.

**Trigger model — system-managed with narrative surfacing:**

The engine evaluates each check against a **destiny threshold** to
determine whether the moment warrants a Destiny Point investment. The
threshold considers three factors:

**Narrative stakes.** The scene type and act position determine base
stakes. Climax scenes (tension: "climax") have higher base stakes than
rising scenes. Anchor beat proximity increases stakes — a check that
occurs within 1-2 turns of an anchor beat carries more narrative weight.

**Mechanical impact.** The engine computes the probability delta — how
much the upgrade changes the odds. Upgrading an ability die to
proficiency on a check with 4 ability dice is less impactful (one of
many) than upgrading on a check with 1 ability die (dramatic
difference). Higher probability deltas increase the destiny score.

**Player investment.** Checks where the player's choice expressed
strong directional intent — choosing a risky option over a safe one,
pursuing a goal they've been building toward — score higher. The
choice's skill tag is compared against the behavioral inference
engine's aspiration signal. Checks aligned with what the player has
been reaching for are more "destiny-worthy."

If the combined destiny score exceeds the threshold AND a Light Side
point is available, the engine spends it. The upgrade is applied at
**Stage 4 of the pool modification pipeline** (new stage, after
passive and conditional talent modifiers, before dice are rolled).

After spending, the point flips: `destiny_light -= 1`,
`destiny_dark += 1`.

**The player's experience:**

The player never knows a Destiny Point was spent. They experience it
as: this check went better than expected. The prose reflects the shift.
The GM prompt receives a flag: `destiny_spent: true` with a narrative
note: "This check was touched by fate. The character experienced a
moment of preternatural luck, perfect timing, or an instinct that
arrived exactly when needed. Weave this into the narration as fortune,
not as skill."

The player reads: "The bolt should have missed. Every calculation said
it would miss — the angle was wrong, the range was absurd, the target
was moving. But Keth's hand adjusted before his brain caught up, a
correction so small he wouldn't be able to explain it afterward, and
the bolt caught the junction box dead center."

That's a Destiny Point. The player felt lucky. They were.

#### 23.3 Dark Side Spending — The Galaxy Pushes Back

When the engine spends a Dark Side Destiny Point, it upgrades one
difficulty die (purple d8) to a challenge die (red d12) in the check's
opposition pool. Challenge dice have the Despair face — a catastrophic
negative outcome — making the check meaningfully more dangerous.

**Trigger model — condition-driven:**

The engine evaluates Dark Side spending based on narrative conditions
rather than a continuous threshold. Dark Side points spend when specific
authored or systemic triggers are active:

**Obligation active.** When the character's Obligation has triggered
for the current act (Section 9), one Dark Side point is spent on the
first check of each scene where the Obligation's source is narratively
relevant. The debt makes the world harder. The narration reflects
pressure from the Obligation manifesting as circumstances that fight
the character.

**Antagonist engagement.** When the check involves direct opposition
from a significant NPC (disposition below 0.3), a Dark Side point may
be spent. The antagonist's competence and malice are felt mechanically,
not just narratively.

**Spine-authored triggers.** The campaign spine can mark specific
anchor beats or scenes with `destiny_dark_trigger: true`, forcing a
Dark Side spend on the first check within that scene. This is the
campaign author's tool for creating moments that feel fateful — the
climactic check of Act 3 should carry maximum weight.

**Escalation pacing.** The engine tracks Light Side spends. If the
player has received 2+ Light Side spends in the current act without a
Dark Side spend, the threshold for Dark Side spending lowers. The pool
seeks equilibrium — good luck invites bad luck. This creates the
push-pull rhythm that FFG's tabletop design intended.

After spending, the point flips: `destiny_dark -= 1`,
`destiny_light += 1`.

**The player's experience:**

The player doesn't know a Dark Side point was spent. They experience
it as: this went worse than it should have. The Despair face on the
challenge die may have fired, producing a catastrophic complication.
Even without Despair, the additional threat and failure symbols from
the challenge die make the check harder. The GM prompt receives:
`destiny_dark_spent: true` with: "Fate worked against the character
this time. The situation was harder than it should have been — bad
timing, unexpected complications, the galaxy's indifference to good
intentions. Narrate the difficulty as environmental or circumstantial,
not as character incompetence."

The player reads: "The security sweep should have missed them. It was
random — wrong corridor, wrong time. But the officer leading it was
the same one from the spaceport, the one whose face Keth had studied
and then deliberately forgotten. Recognition flickered in the officer's
eyes half a second before Keth's hand moved toward the comlink."

That's a Dark Side point. The player felt unlucky. The world pushed
back.

#### 23.4 The Seize-the-Moment Choice (Optional)

For the most critical checks in a campaign — the climactic moment of
an act, the decisive roll at an anchor beat — the system can offer
the player a **pre-roll narrative choice** that corresponds to spending
a Destiny Point. This is optional, controlled by the campaign spine,
and should occur no more than once or twice per campaign.

The choice is not "spend a Destiny Point." It is a narrative moment
that expresses committing everything to this moment:

> *This was the moment. Keth could feel it — the way the corridor
> narrowed to a single point, the way time seemed to stretch, the way
> every decision he had made since arriving on Nar Shaddaa compressed
> into the weight of what happened next.*
>
> *He could play it safe. Stay with what he knew. Let the dice fall
> where they would.*
>
> **Trust the moment.** Everything on this one.
>
> **Stay steady.** No need to overcommit.

"Trust the moment" spends a Light Side Destiny Point — the pool
upgrade is applied, and the narration reflects the investment. "Stay
steady" makes the check normally. This preserves the invisible
mechanics principle because the player is making a *narrative* choice
about commitment, not a *mechanical* choice about resource spending.

**Trigger:** The campaign spine marks specific moments with
`seize_the_moment: true`. These are authored, not systemic. They
should correspond to the campaign's highest-stakes moments — the
act climax, the confrontation with the antagonist, the moment the
throughline question is under maximum pressure.

**Availability:** The choice only appears if a Light Side point is
available. If the pool is empty, the moment plays as a normal check
with no choice offered.

#### 23.5 Pool Modification Pipeline — Final Order

With Destiny Points integrated, the full pool modification pipeline
is:

**Stage 1 — Base pool construction.** Standard FFG formula:
max(characteristic, skill_rank) ability dice, upgrade
min(characteristic, skill_rank) to proficiency. Add difficulty dice.
Situational boost/setback from check decision.

**Stage 2 — Passive talent modifiers.** Type 1 talents (Skilled Jockey,
Stalker, etc.) add/remove boost/setback.

**Stage 3 — Conditional talent modifiers.** Type 2 talents (Dodge,
Quick Strike) evaluated against scene context. Strain charged if
triggered.

**Stage 4 — Destiny Point modification.** Engine evaluates Light Side
and Dark Side spending conditions. If Light Side triggers: upgrade one
ability → proficiency. If Dark Side triggers: upgrade one difficulty →
challenge. Both can fire on the same check (the moment is both lucky
and dangerous). Pool flip applied.

**Stage 5 — Force dice addition.** If `force_use` is true, add Force
dice equal to available Force Rating.

**Stage 6 — Roll.** All dice rolled. Result computed.

**Stage 7 — Post-roll decisions.** Force pip resolution → dark side
temptation (if applicable) → Type 5 intervention talents (if
applicable). These are sequential decision points between dice and
narration.

### Implementation Notes

**Session state:** `destiny_light` and `destiny_dark` already exist.
Add: `destiny_light_spent_this_act: int` and
`destiny_dark_spent_this_act: int` for escalation pacing tracking.
Reset at act boundaries alongside pool regeneration.

**Turn record additions:**

- `destiny_light_spent: bool` — whether a Light Side point was spent
  on this turn's check
- `destiny_dark_spent: bool` — whether a Dark Side point was spent
- `seize_the_moment_offered: bool` — whether the pre-roll choice was
  presented
- `seize_the_moment_accepted: bool` — whether the player committed

**Campaign spine additions:**

- `destiny_dark_trigger: bool` per anchor beat or scene marker
- `seize_the_moment: bool` per anchor beat (controls the optional
  pre-roll choice)

**Pool modification pipeline extension:**

`engine/checks.py`'s `build_pool()` gains Stage 4 — a call to
`engine/destiny.py`'s `evaluate_destiny_spend()` which returns the
pool modifications (if any) and flips the pool. The function signature:

```python
def evaluate_destiny_spend(
    pool: DicePool,
    character: Character,
    scene_context: SceneContext,
    arc_state: ArcState,
    destiny_light: int,
    destiny_dark: int,
    act_spend_counts: tuple[int, int],
) -> DestinyResult:
```

Returns: modified pool, whether light/dark were spent, narrative notes
for GM prompt injection.

**New module:** `engine/destiny.py`. Contains the evaluation logic,
threshold computation, and seize-the-moment choice generation.

---

## 24. Semantic Memory and Meaningful Choice Extraction

### The Problem

The turn log records *what happened* — the player selected choice B,
a Deception check was rolled, it succeeded with threat. It does not
record *what it meant* — the player chose to protect someone through
deception at personal cost, revealing a pattern of prioritizing
relationships over self-preservation.

This distinction matters because the systems that depend on behavioral
understanding — character drift notes (Section 11), the aspiration
echo system (Section 14.5), throughline question evolution, and cross-
campaign character identity (Section 20) — need the *meaning*, not
just the facts. The behavioral inference engine (Section 14.2) uses
skill tags as a proxy signal, but skill tags capture the *method* of
a choice, not its *significance*.

Without semantic extraction, a player who chose Deception to protect a
friend and a player who chose Deception to scam a merchant produce
identical behavioral signals. The system cannot distinguish kindness
expressed through lies from selfishness expressed through lies. Over
time, this flattens the character model — the system sees "this player
uses Deception a lot" when it should see "this player protects people
through deception" or "this player exploits people through deception."

The retrofitting risk is data loss. If the semantic memory system later
needs a `choice_implications` field on turn records, and we don't
reserve it, we lose the contextual data needed to retroactively extract
meaning from past turns. The alternatives that were available, the
stakes that were present, the NPC relationships at play — that context
is compressed away after a few turns.

### The Design

#### 24.1 Per-Turn Choice Annotation

After the player makes a choice and before the check decision runs,
the engine generates a **choice annotation** — a structured record of
what the choice meant in context. This annotation is produced by the
local model through a lightweight call that runs in parallel with the
check decision (zero additional latency if parallelized).

The annotation prompt receives: the player's selected choice text, the
other available choices that were *not* selected, the current scene
description, the active NPC state summaries, and the character's recent
behavioral pattern (from the last 3-5 turns).

The annotation produces structured JSON:

```json
{
  "choice_target": "protect_doss",
  "choice_method": "deception",
  "sacrifice": "personal_risk",
  "priority_revealed": "relationship_over_safety",
  "npc_impact": {
    "doss": "trust_invested",
    "customs_officer": "antagonized"
  },
  "throughline_relevance": "high",
  "throughline_direction": "becoming_someone_worth_following",
  "behavioral_tags": [
    "protective", "deceptive", "risk_taking", "loyalty"
  ]
}
```

**Key fields:**

`choice_target` — what the player was trying to accomplish with this
choice. Not the skill, but the intent.

`choice_method` — how they tried to accomplish it. This overlaps with
the skill tag but is expressed in narrative terms.

`sacrifice` — what the player gave up or risked by making this choice
instead of the alternatives. This is only meaningful in context of the
unchosen options.

`priority_revealed` — what this choice, in the context of the
alternatives, reveals about the player's values. This is the most
important field. "Relationship over safety," "mission over compassion,"
"truth over advantage," "efficiency over principle."

`npc_impact` — how this choice affects the player's relationships,
expressed as relational verbs rather than disposition numbers.

`throughline_relevance` — how directly this choice pressures the
campaign's throughline question. High/medium/low.

`throughline_direction` — which direction this choice pushes the
throughline answer, in the throughline question's own terms.

`behavioral_tags` — free-form tags that characterize the choice across
multiple dimensions. These accumulate across turns and acts to form a
behavioral fingerprint.

#### 24.2 How Annotations Feed Other Systems

**Behavioral inference (Section 14.2).** The `priority_revealed` and
`behavioral_tags` fields enrich the inference engine's signal beyond
skill tags. A player whose annotations consistently show
"relationship_over_safety" receives growth in social and protective
skills even when their skill tag frequency is mixed. The annotations
provide the *why* behind the choices.

**Character drift notes (Section 11).** At act boundaries, the
compression system summarizes the act's annotations into a character
drift statement: "Act 2: Keth consistently prioritized protecting
individuals over completing objectives. Emerging pattern: loyalty to
specific people overriding institutional or transactional obligations."
This is richer than the current drift notes, which can only observe
skill usage patterns.

**Aspiration echoes (Section 14.5).** The `throughline_direction`
field tells the aspiration echo system which direction the character
is leaning. Echoes that match the player's throughline trajectory feel
organic; echoes that counter it feel like narrative tension. Both are
useful.

**Throughline question evolution (Section 20).** When the character
is exported for cross-campaign import, the accumulated annotation data
produces a throughline answer summary: "Across Campaign 1, the player's
choices consistently answered 'Can a man who has only ever looked out
for himself become someone worth following?' with: Yes, but only for
specific people, not for institutions or ideals." This summary travels
with the import package and informs the next campaign's throughline
design.

**Milestone reflections (Section 14.3).** The annotations help the
milestone system generate more specific reflection passages. Instead of
generic "you've been using Deception a lot" directions, the system can
offer: "He'd realized something about the way he lied. It wasn't about
getting away with things anymore. Every lie he told lately was a wall
built around someone he wasn't ready to lose."

#### 24.3 Annotation Quality and Failure Modes

The local model produces these annotations. They will not always be
accurate. The design must be robust to annotation noise.

**Redundancy.** No single annotation drives a mechanical outcome.
Annotations accumulate over many turns. A misannotated choice is
diluted by correctly annotated ones. The behavioral inference engine
uses annotations as one signal among several — skill tags and check
results are still tracked independently.

**Validation.** The annotation schema is validated structurally (JSON
schema compliance, enum values for fields like throughline_relevance).
Invalid annotations are logged and discarded, not surfaced or acted on.

**Graceful degradation.** If the annotation call fails (local model
timeout, malformed output after retries), the turn proceeds without
an annotation. The turn record's `choice_implications` field is null.
Systems that consume annotations handle null entries by falling back
to skill-tag-only signal. The annotation system is an enhancement, not
a dependency — the game works without it, just with a less nuanced
character model.

### Implementation Notes

**Turn record addition:**

- `choice_implications: Optional[str]` — JSON string containing the
  structured annotation. Null when annotation fails or is unavailable.
  Stored as text in the `turns` table.

**New prompt:** `gm/prompts/choice_annotation.txt` — The prompt for the
local model's annotation call. Receives: selected choice, rejected
choices, scene description, active NPC summaries, recent behavioral
pattern. Returns structured JSON.

**Parallelization:** The annotation call runs in parallel with the
check decision call. Both use the local model (Ollama). If Ollama
supports concurrent requests, latency is zero. If not, the annotation
runs as a background task after the check decision completes, and the
result is stored asynchronously — it does not block the turn flow.

**Compression integration:** The compression system (`state/memory.py`)
receives annotations alongside turn data. Act summaries include an
aggregated behavioral fingerprint derived from the act's annotations:
the top 5 most frequent `priority_revealed` values, the top 10
behavioral tags, and the dominant throughline direction.

**Module addition to `engine/advancement.py`:** The behavioral inference
engine's `compute_behavioral_weights()` function gains an optional
`annotations: list[dict]` parameter. When annotations are available,
the engine uses `priority_revealed` and `behavioral_tags` to refine
weighted scores. When unavailable, the engine falls back to skill-tag-
only computation (the current design).

#### 24.4 Conditional Choice Availability from Behavioral Patterns

The semantic memory system produces behavioral annotations per turn and
aggregated behavioral fingerprints per act. This data enables a system
the Vision Document describes (§7): some choices are only available
because of who the character has become through their choices.

**The behavioral availability signal.** At each act boundary, the
compression system aggregates annotations into a signal:

```json
{
  "dominant_priorities": [
    "relationship_over_safety",
    "truth_over_advantage",
    "patience_over_speed"
  ],
  "dominant_tags": [
    "protective", "loyal", "cautious", "observant",
    "honest_with_allies", "deceptive_with_strangers"
  ],
  "throughline_lean": "becoming_someone_worth_following",
  "pattern_strength": 0.72
}
```

`dominant_priorities` — the 3 most frequent `priority_revealed` values
across all annotated turns in the campaign. `dominant_tags` — the 6
most frequent `behavioral_tags`. `throughline_lean` — the dominant
`throughline_direction` from high-relevance annotations.
`pattern_strength` — concentration ratio of top priorities vs. total
annotated turns (0-1). Below 0.4, signal is too weak and the
availability system is inactive.

**Prompt injection.** The signal is injected into the narration prompt's
choice generation rules as a BEHAVIORAL CONTEXT block:

```
BEHAVIORAL CONTEXT FOR CHOICES:
This character has established the following patterns:
{behavioral_signal}

Use this to shape which choices you offer:
- If the character has shown [trust/loyalty/protectiveness], include at
  least one choice that ASSUMES earned trust — an option only someone
  who has built trust would be offered.
- If the character has shown [self-interest/pragmatism/deception], do
  NOT offer choices that assume deep NPC trust unless the NPC's
  disposition explicitly warrants it.
- If the character has NOT established a clear pattern
  (pattern_strength < 0.4), do not constrain choices.
- NEVER announce availability constraints. The choices simply reflect
  the world's response to the player's behavioral history.
```

The system does NOT use mechanical lock/unlock lists. The cloud GM
receives a behavioral portrait and generates choices that naturally
reflect the world's response to that portrait. Availability emerges
from the GM's understanding of how people respond to patterns.

**NPC-specific availability.** NPC dispositions create hard
constraints independently: NPCs with disposition below 0.3 will not
offer help, share information voluntarily, or extend trust. NPCs who
don't know something cannot reveal it. This is state-based, not
pattern-based, and works from Phase 7 onward.

**Authored availability gates.** Campaign spines can include explicit
`availability_gates` on anchor beats:

```json
{
  "choice_gate": {
    "description": "Offer the option to call for NPC help",
    "requires": {
      "npc_disposition_min": {"doss": 0.5},
      "behavioral_tag_present": ["loyal"],
      "npc_alive": "doss"
    }
  }
}
```

When conditions are met, gated options appear in the situation
description. When not met, they're absent. NPC disposition gates work
in V1 spines. Behavioral tag gates require Phase 13.

**Mixed patterns.** When behavioral tags show contradictions
(e.g., "protective" and "ruthless"), the GM reflects ambivalence —
choices that pull in different directions, because contradictory
characters are interesting.

**Pattern evolution.** The signal updates at act boundaries, not
per-turn. A dramatic mid-act reversal won't change the choice
landscape until the next act. Behavioral patterns should be
slow-moving, reflecting accumulated identity rather than momentary
impulse.

**Graceful degradation.** Before Phase 13 (no annotations), the
behavioral signal block is omitted entirely and choices are
unconstrained by behavioral patterns. The system falls back to NPC
state and disposition constraints only.

---

## 25. NPC Emotional State

### The Problem

The NPC state card tracks disposition — a long-term relationship axis
from hostile to loyal. But disposition is a slow-moving average. It
does not capture what an NPC is feeling *right now.*

An NPC with disposition 0.7 (friendly) toward the player can still be
angry — the player just delivered bad news, or broke a promise, or
showed up at the worst possible time. The anger is transient. It will
fade. But right now, this NPC is angry-and-friendly simultaneously, and
that combination produces richer scenes than either state alone. A
friendly NPC who is angry makes different choices and speaks differently
than a friendly NPC who is calm. The GM needs both signals.

Without an emotional state field, the GM writes every NPC as if they are
in their default emotional mode for their disposition level. Friendly
NPCs are consistently pleasant. Hostile NPCs are consistently cold. The
result is emotional flatness — NPCs feel like mood-labeled automatons
rather than people whose emotional state fluctuates in response to
events.

The retrofitting risk is modest — adding the field to NPCState is
trivial. But if we build the NPC context injection and the narration
prompt structure without accounting for emotional state, we have to
modify both when we add it. Designing it now means the field exists
from the start, the prompt injection handles it, and the system is
ready for the emotional dynamics the Vision Document describes.

### The Design

#### 25.1 Emotional State as Transient Overlay

Each NPC carries an `emotional_state` that overlays their baseline
disposition. The emotional state describes what the NPC is feeling
*right now* as a result of recent events. It is set by game events and
decays toward neutral over time.

```json
{
  "emotional_state": {
    "mood": "angry",
    "intensity": 0.7,
    "source": "Player revealed that Doss was arrested",
    "set_at_turn": 14,
    "decay_rate": 0.15
  }
}
```

**Mood vocabulary.** A constrained set of emotional states that the GM
can reliably distinguish and portray:

- `calm` — the default. NPC behaves according to their disposition
  baseline. No emotional overlay.
- `angry` — provoked, irritated, or furious (intensity determines
  degree). NPC is shorter, more confrontational, less willing to
  cooperate regardless of disposition.
- `afraid` — threatened, anxious, or panicked. NPC is evasive,
  cautious, may act irrationally to protect themselves.
- `grieving` — processing loss. NPC is withdrawn, distracted, may be
  more emotionally vulnerable or more hardened depending on personality.
- `suspicious` — doubting the player's motives or truthfulness. NPC
  questions more, reveals less, watches more carefully.
- `grateful` — the player just did something meaningful for them. NPC
  is warmer, more forthcoming, more willing to extend trust temporarily.
- `desperate` — backed into a corner. NPC may take actions outside
  their normal behavioral envelope (with GM prompt warning that
  desperate behavior should feel extreme and motivated, not casual).
- `amused` — finding something genuinely funny or absurd about the
  situation. Lightens tone, may lower guard, creates space for
  unexpected connection.
- `conflicted` — torn between two impulses (loyalty vs self-
  preservation, duty vs personal desire). NPC behavior is inconsistent,
  reveals internal tension.

**Intensity** (0.0 to 1.0) scales the emotional effect. At 0.3, the
mood is a subtle undertone — the NPC is slightly irritated but
functioning normally. At 0.8, the mood dominates their behavior — the
NPC is visibly angry and it shapes every interaction.

**Source** tracks what caused the emotional state, so the GM can
reference it in dialogue and behavior. "Vossk's intermediary is angry
because the delivery is late" produces different anger than "angry
because the player lied to them."

#### 25.2 Setting Emotional State

Emotional states are set by three mechanisms:

**Dice result consequences.** When a social check produces a failure
or significant threat, the target NPC's emotional state may shift. A
failed Deception check on a neutral NPC might set `suspicious` at
intensity 0.5. A failed Coercion check might set `angry` at intensity
0.6. The check decision's outcome quadrant and the NPC's current
disposition determine which emotion and what intensity. This is handled
by a post-check processing step that evaluates social-scene outcomes
against the NPC context.

**Narrative events.** The campaign spine and the GM's narration can set
emotional states through authored triggers. "When the player reveals
Doss's arrest to Reeska, set Reeska's emotional_state to
`grieving/0.6`." These are authored in anchor beats and variation
points. The engine applies them when the trigger condition is met.

**GM-inferred state.** The cloud GM's narration may describe an NPC
reacting emotionally to events. A post-narration processing step
(local model call, parallel with other between-turn processing) can
extract emotional state changes from the narration: "The GM described
Vossk's intermediary as 'speaking through clenched teeth' — infer
emotional state: angry, intensity 0.5." This is a lightweight
extraction, not a complex inference — the local model reads the
narration and identifies explicit emotional cues.

#### 25.3 Decay

Emotional states decay toward `calm` over turns. Each state has a
`decay_rate` (intensity reduction per turn). Typical decay rates:

- `angry`: 0.15 per turn (fades in 4-5 turns from high intensity)
- `afraid`: 0.10 per turn (persists longer — fear lingers)
- `grieving`: 0.05 per turn (very slow decay — grief doesn't fade
  quickly)
- `suspicious`: 0.08 per turn (suspicion lingers but can be overcome)
- `grateful`: 0.20 per turn (gratitude fades fastest — it is given,
  not owed)
- `desperate`: 0.12 per turn (resolves as the situation changes)
- `amused`: 0.25 per turn (amusement is the most transient state)
- `conflicted`: 0.05 per turn (internal conflict persists until
  resolved by events, not by time)

When intensity drops below 0.1, the emotional state resets to `calm`.

**Decay is paused when the source is still active.** If the NPC is
afraid because an antagonist is in the scene, the fear doesn't decay
until the antagonist leaves. The engine checks whether the source
condition is still true each turn before applying decay.

**Events can override decay.** A new emotional trigger replaces the
current state rather than competing with it. If a grateful NPC
(intensity 0.3, decaying) receives new cause for anger (intensity 0.6),
the anger replaces the gratitude. The strongest current emotion wins.

#### 25.4 Emotional State in the GM Prompt

The NPC's emotional state is injected into their state card (or
summary for Tier 2 NPCs) in the GM prompt:

**Tier 1 (full state card):**
```
Doss:
  Disposition: neutral (0.48)
  Currently: afraid (intensity 0.6) — suspects Vossk's people
    are looking for him
  Knows: Player is carrying sealed cargo; Keth mentioned the comm warning
  Doesn't know: What's in the cargo; that Vossk's patience has run out
  Voice: Half-sentences, nervous deflections, trails off mid-thought
  Wants: To survive the next 48 hours
  Never: Confronts directly; always seeks escape routes first
```

The `Currently:` line tells the GM what Doss is feeling right now and
why. This produces narration where Doss's fear is visible: the way he
checks the door, the way his voice drops, the things he says and
doesn't say. Without the emotional state, the GM would write Doss as
generically neutral (disposition 0.48). With it, the GM writes Doss as
neutral-toward-Keth but afraid-of-the-situation — a much richer
characterization.

**Tier 2 (one-sentence summary):**
```
Doss (contact, disposition 0.48, currently afraid — suspects pursuit)
```

Even in compressed form, the emotional state flag gives the GM enough
to avoid writing a calm Doss when Doss should be frightened.

#### 25.5 Emotional State and Disposition Interaction

Emotional state is *not* disposition. A grateful NPC does not
permanently become friendlier. A suspicious NPC does not permanently
become more hostile. Emotional states decay; disposition persists.

However, sustained emotional states nudge disposition over time. If an
NPC is angry at the player for 5+ consecutive turns (anger keeps being
re-triggered), their disposition decreases slightly (0.02-0.05). If an
NPC is grateful for an extended period, disposition increases by a
similar amount. This is the mechanism by which emotional interactions
crystallize into relationship changes — a single angry moment fades,
but a pattern of provoking anger erodes the relationship.

The disposition nudge is applied during between-turn NPC state
processing, not in real-time. The engine checks: has this NPC been in
a non-calm emotional state for 3+ consecutive turns? If yes, nudge
disposition in the direction indicated by the emotion (negative for
angry/suspicious/afraid, positive for grateful, neutral for amused/
conflicted/desperate).

### Implementation Notes

**NPCState additions:**

```python
@dataclass
class EmotionalState:
    mood: str = "calm"
    intensity: float = 0.0
    source: str = ""
    set_at_turn: int = 0
    decay_rate: float = 0.15

@dataclass
class NPCState:
    # ... existing fields ...
    emotional_state: EmotionalState = field(
        default_factory=EmotionalState
    )
```

**`to_prompt_block()` extension:** The existing `to_prompt_block()`
method on NPCState gains a `Currently:` line when the emotional state
is not calm (intensity > 0.1). The line includes the mood, a
qualitative intensity descriptor (slight/moderate/intense based on
thresholds), and the source.

**Turn processing addition:** Between-turn NPC processing gains two
new steps:
1. **Emotional decay.** For each NPC with a non-calm emotional state,
   reduce intensity by decay_rate (unless source is still active).
   Reset to calm if intensity drops below 0.1.
2. **Disposition nudge.** For NPCs in sustained non-calm states (3+
   turns), apply disposition adjustment.

**Post-check emotional inference:** After a social check resolves, the
engine evaluates whether the result should set an emotional state on
the target NPC. Mapping:

- Failed Deception/Charm → `suspicious` (intensity proportional to
  net failure)
- Failed Coercion → `angry` (intensity proportional to net failure)
- Successful Charm with Triumph → `grateful` (intensity 0.5)
- Successful Coercion with threat → `afraid` (intensity proportional
  to net threat)

**Campaign spine additions:** Anchor beats and variation points gain
an optional `npc_emotional_triggers` field — a list of NPC name →
emotional state mappings that fire when the trigger condition is met.

---
## 26. Post-Turn State Reconciliation and Narrative Pacing

### The Problem

The turn flow as specified is: player chooses → check decision → dice
roll → talent/Force/Destiny modification → cloud GM narrates → log
turn → background compression. Every step in this chain is designed.
But between "GM narrates" and "log turn," there is a critical gap:
**nothing updates the world state based on what just happened.**

After the GM writes that Keth lied to Doss about the cargo, Doss's
state card should update — he now believes something false. After the
GM writes that Keth fought off two thugs in the maintenance corridor,
the story should be closer to the next anchor beat. After three turns
of exploration, the act's progress should have advanced enough that
the GM starts building toward the anchor.

Without this system, the world is static between turns. NPCs know the
same things they knew at session start. The story never progresses
toward its structural beats. Act transitions never fire. The game loop
works mechanically but the campaign doesn't *go anywhere.*

This is not a single feature — it is the connective tissue between the
turn loop and every state system in the engine: NPC state cards
(knowledge, disposition), story progression (act_progress, anchor
detection), act transitions (between-act processing), and the narrative
pacing that guides the GM toward structural coherence.

### The Design

#### 26.1 The Reconciliation Step

After the cloud GM produces its narration and before the turn is logged
to the database, the engine runs a **reconciliation step** — a local
model call that analyzes what just happened and produces structured
state updates.

**Position in the turn flow:**

```
1.  Player selects choice
2.  Check decision (local model)
3.  Pool construction → talent/destiny modification
4.  Dice roll
5.  Post-roll decisions (Force temptation, interventions)
6.  Cloud GM narrates
7.  ── RECONCILIATION STEP (local model) ──
8.  Apply state updates
9.  Log turn (with updated state)
10. Background compression
```

The reconciliation step runs *after* narration because it needs to
analyze what the GM wrote — the narration contains information about
what happened that isn't captured by the dice result alone. The GM
decided that Doss revealed a piece of information, or that the
environment changed, or that an NPC reacted emotionally. These
narrative events need to be captured as state changes.

**The reconciliation prompt:**

The local model receives:

- The player's selected choice
- The check result (if any)
- The GM's narration (the full passage that was just generated)
- The current NPC state cards for all NPCs present in the scene
- The current act's anchor beat name and description
- The current `act_progress` value
- The number of turns played in this act so far

It returns structured JSON:

```json
{
  "npc_updates": [
    {
      "npc_name": "Doss",
      "knowledge_gained": ["Keth claims the cargo is replacement parts"],
      "knowledge_lost": [],
      "disposition_shift": 0.0,
      "emotional_state_change": null
    }
  ],
  "thread_updates": {
    "threads_advanced": ["What happened to Doss?"],
    "threads_resolved": [],
    "threads_opened": []
  },
  "story_progress": {
    "anchor_proximity": "approaching",
    "progress_delta": 0.08,
    "reasoning": "Player is actively investigating Doss's location,
      which is the setup for the contact_discovered anchor."
  },
  "reputation_event": null,
  "notable_action": "Lied to protect Doss's reputation with Vossk's
    intermediary"
}
```

#### 26.2 NPC State Updates

**Knowledge changes** are the most important NPC update. When the GM
narrates information exchange — the player tells an NPC something,
an NPC reveals something, the player's actions demonstrate something
the NPC can observe — the reconciliation step captures what each
NPC now knows that they didn't before, and what (if anything) they
previously believed that has been contradicted.

`knowledge_gained` adds entries to the NPC's `knows` list.
`knowledge_lost` removes entries from `knows` and optionally adds
them to `doesnt_know` (representing a belief that was corrected or
revealed as false).

**Disposition shifts** from gameplay events are small per-turn
adjustments based on how the player treated the NPC during the
narration. A successful Charm check doesn't automatically change
disposition — the reconciliation step evaluates whether the
*interaction* (not just the check result) warrants a shift.

Disposition shift guidelines for the reconciliation prompt:

- Most turns: 0.0 (no shift). Disposition is sticky. A single
  interaction rarely changes a relationship.
- Positive interaction (helped, protected, showed respect): +0.03
  to +0.08
- Negative interaction (lied and caught, threatened, betrayed):
  -0.05 to -0.15
- Significant betrayal or sacrifice: -0.2 to +0.2 (these are
  rare and require the narrative to explicitly describe a
  relationship-changing moment)

The reconciliation prompt includes these guidelines so the local
model's disposition shifts stay calibrated. The engine clamps all
disposition values to 0.0-1.0 after applying shifts.

**Emotional state changes** follow the same mechanism as Section 25
(NPC Emotional State). The reconciliation step can set or modify an
NPC's transient emotional state based on what happened in the
narration. If the GM wrote Doss as panicked, the reconciliation
captures `emotional_state_change: {"mood": "afraid", "intensity": 0.6,
"source": "Learned that Vossk's enforcers are searching for him"}`.

**NPCs not in the scene** are not updated. The reconciliation step
only processes NPCs listed in the current scene's active NPC set.
Off-screen NPC updates happen through authored spine events and the
NPC information propagation system (when built).

#### 26.3 Story Progression and Anchor Pacing

This is the system that makes the story *go somewhere* — advancing
through the campaign spine's authored structure while preserving the
player's agency over how they get there.

**The `act_progress` model:**

Each act has a progress value from 0.0 (act just started) to 1.0
(anchor beat reached, act complete). Progress advances incrementally
each turn based on the reconciliation step's `progress_delta` value.

The reconciliation prompt evaluates progress against two signals:

**Turn count pacing.** The spine's `expected_turns` field for the
current act provides a baseline. If the act expects "8-12 turns" and
the player is on turn 6, the expected progress is roughly 0.5-0.75.
The reconciliation step uses this to calibrate progress_delta — if
the player is behind pace, deltas are slightly larger. If ahead,
slightly smaller. This prevents both rushing (reaching the anchor in
3 turns when 10 were expected) and stalling (turn 15 with no anchor
in sight).

**Narrative proximity.** The reconciliation step evaluates how close
the current narrative situation is to the conditions needed for the
next anchor beat. The anchor name and the spine's anchor description
(from `opening_situation` of the next act, which implies what the
anchor transition looks like) provide the target. The
`anchor_proximity` field is one of: `"distant"` (the player is doing
something unrelated to the anchor's setup), `"approaching"` (the
player's actions are moving toward the anchor's conditions),
`"imminent"` (the anchor could fire in the next 1-2 turns), or
`"reached"` (the anchor conditions are met in this turn's narration).

**Progress delta guidelines:**

- `distant`: 0.03-0.05 per turn (the story advances even when the
  player explores, but slowly)
- `approaching`: 0.06-0.10 per turn (the player is moving toward
  the story's structural spine)
- `imminent`: 0.10-0.15 per turn (convergence — the anchor is close)
- `reached`: set progress to 1.0 (anchor detected)

These ranges are modulated by the turn-count pacing signal. If the
player is on turn 3 of an expected 10-turn act and the anchor is
`imminent`, the delta is reduced — it's too early. If the player is
on turn 14 of expected 10, the delta is increased — it's time.

#### 26.4 Anchor Beat Detection and Triggering

When `act_progress` reaches 1.0 (or when `anchor_proximity` is
`"reached"`), the engine triggers the anchor beat transition.

**What triggers means:**

The engine does not generate the anchor beat itself — the anchor is a
*situation*, not a *passage* (per Campaign Studio Design §2.2). The
engine signals the cloud GM that the anchor should occur on the next
turn by modifying the context package:

1. The `situation` field in the context package is updated to the next
   act's `opening_situation` (which describes the post-anchor state).
2. The narration prompt receives an **anchor instruction**: "This is
   an anchor beat — a major story moment. The situation has shifted
   irreversibly. [anchor description]. Write the transition into this
   new reality. The player should feel that they have crossed a
   threshold."
3. The `tension_level` updates to the next act's tension.
4. Open threads from the completed act are carried forward (unless
   resolved).

The anchor beat passage is generated by the cloud GM on the *next
turn after* progress hits 1.0, not on the same turn. This means the
turn that completes the act feels like a culmination, and the first
turn of the next act feels like a new beginning. The act boundary
falls *between* these two turns.

#### 26.5 Act Transition Processing

When an anchor beat fires and the act boundary is crossed, the
between-act processing pipeline runs. This is the pipeline specified
in Section 14 (Implementation Notes), now with the full sequence:

**The complete between-act pipeline:**

1. Act summary compression — compress the completed act's turns into
   a summary stored in `act_summaries`
2. Character drift note — behavioral pattern observation for the act
3. XP award — base + bonus condition evaluation (Section 14.1)
4. XP reservation — 40% to reserved_xp, 60% to available_xp
5. Behavioral inference — skill rank allocation (Section 14.2)
6. Choice annotation aggregation — behavioral fingerprint from
   semantic memory (Section 24)
7. Milestone check — evaluate all milestone categories (Section 14.3)
8. Obligation/Duty activation roll for next act (Section 9)
9. Strain and wound recovery (partial — not full, unless a time skip
   follows)
10. Morality resolution — Conflict vs d10 (Section 9)
11. NPC relationship drift — minor disposition adjustments for NPCs
    not seen during the act
12. Destiny Pool regeneration — new Force die roll (Section 23)
13. Growth passage generation — cloud GM produces the advancement
    narrative
14. Milestone reflection presentation (if triggered)
15. Time skip sequence (if `time_skip_after` is defined for this act
    — Section 19: opening passage → vignettes → closing passage)
16. Load next act — update arc state with new act's galactic context,
    anchor, tension, open threads

Steps 1-12 are invisible. Steps 13-16 are player-facing.

#### 26.6 GM Pacing Guidance

The GM needs to know where the story is in relation to its structure
so it can pace its narration appropriately. Without guidance, the GM
writes in an eternal present — every turn has the same urgency, the
same scope, the same sense of where things are heading. This produces
narratively flat campaigns.

**Pacing context in the narration prompt:**

A new `PACING` block is added to the context package, injected between
the story context and the NPC section:

```
PACING:
Act progress: {act_progress_percentage}%
Turns in act: {turns_this_act} of ~{expected_turns}
Next structural beat: {next_anchor_description}
Proximity: {anchor_proximity}
{pacing_instruction}
```

The `pacing_instruction` varies by act progress:

**Early act (0-30%):** "This is early in the act. Establish the
situation, introduce complications, let the player explore. Do not
rush toward the anchor. There is time for character moments, world
detail, and setup."

**Mid act (30-70%):** "The act is developing. Threads should be
converging. Complications are mounting. The player should feel
increasing pressure from the situation, but the anchor is not
imminent. Maintain tension without premature resolution."

**Late act (70-90%):** "The act is approaching its anchor beat.
Begin converging threads. Increase urgency. The choices should narrow
toward the conditions that will trigger the anchor. The player should
sense that something is about to change."

**Anchor imminent (90%+):** "The anchor beat is imminent. The next
1-2 turns should bring the current threads to a convergence point.
The choices should be consequential — the player is making the
decisions that determine how they enter the anchor situation."

**Anchor reached (100%):** The anchor instruction from Section 26.4
replaces the pacing block entirely.

The GM uses this guidance to modulate prose pacing, choice design, and
narrative scope. Early-act turns can be expansive and exploratory.
Late-act turns should be compressed and focused. The player feels the
story's rhythm without seeing the progress bar.

#### 26.7 Thread Management

Open threads are tracked in the arc state and updated by the
reconciliation step. The three thread operations:

**Threads advanced.** A thread that received new information or
development during this turn. "What happened to Doss?" advances when
the player finds a clue about Doss's whereabouts. Advanced threads
are weighted higher in the GM's open threads block, signaling the GM
to continue developing them.

**Threads resolved.** A thread whose question has been answered by
the narration. "What is actually in the cargo?" resolves when the
player opens the container or learns its contents from an NPC.
Resolved threads are moved from `open_threads` to `closed_threads`
in the arc state. The GM no longer references them as open questions.

**Threads opened.** New questions raised by the narration that weren't
in the original thread list. The GM's narration might introduce a new
complication or mystery that becomes a new thread. The reconciliation
step identifies these and adds them to `open_threads`.

Threads provide the GM with narrative continuity between turns. The
open threads block in the narration prompt tells the GM what questions
are still live, preventing it from forgetting about established
mysteries or prematurely resolving them.

### Implementation Notes

**New module:** `engine/reconciliation.py`. Contains:

- `reconcile_turn(narration, choice, check_result, active_npcs,
  arc_state, spine_act) -> ReconciliationResult` — orchestrates the
  local model call and parses the structured JSON response
- `apply_npc_updates(updates, npc_states) -> list[NPCState]` —
  applies knowledge changes, disposition shifts, and emotional state
  changes to NPC state cards
- `apply_story_progress(progress_result, arc_state) -> ArcState` —
  updates act_progress and anchor_proximity
- `apply_thread_updates(thread_result, arc_state) -> ArcState` —
  manages open/closed thread lists
- `detect_act_boundary(arc_state) -> bool` — returns True when
  act_progress >= 1.0
- `run_between_act_pipeline(session, character, spine, act_number)
  -> BetweenActResult` — the full 16-step pipeline from Section 26.5

**New prompt:** `gm/prompts/reconciliation.txt` — the local model
prompt for the reconciliation step. Structured to produce valid JSON
matching the schema from Section 26.1.

**Turn flow modification:**

The turn flow becomes:

```
1.  Player selects choice
2.  Choice annotation (local model, parallel with step 3)
3.  Check decision (local model)
4.  Pool construction → talent/destiny modification
5.  Dice roll
6.  Post-roll decisions (Force temptation, interventions)
7.  Cloud GM narrates
8.  Reconciliation (local model)
9.  Apply state updates (NPC, progress, threads)
10. Check act boundary → if reached, queue between-act processing
11. Log turn
12. Background compression
13. Between-act processing (if queued in step 10)
```

Steps 2 and 3 run in parallel (both are local model calls).
Step 8 runs sequentially after narration (it needs the narration text).
Step 13 only runs when an act boundary is detected.

**Latency consideration:** The reconciliation step adds one local
model call per turn. On the dev machine (Qwen3.5:9B on RTX 4070),
this should return in 1-2 seconds — comparable to the check decision.
Total per-turn local model time: ~2-4 seconds (check decision +
reconciliation, sequential), plus cloud GM time. This is acceptable
for a prose-first reading experience where the player spends 30-60
seconds reading the passage before making their next choice.

If latency becomes a concern, the reconciliation step can be
parallelized with the turn logging — apply NPC updates optimistically
while the reconciliation runs, then reconcile any differences. But
the simpler sequential approach should work given the hardware spec.

**Context assembly additions:**

The `ContextPackage` gains:

- `pacing_block: str` — assembled from act_progress, turns_this_act,
  expected_turns, anchor_proximity, and the pacing instruction
  appropriate to the current progress band
- `anchor_instruction: Optional[str]` — set when act_progress >= 1.0,
  providing the anchor beat guidance to the cloud GM

**Reconciliation JSON schema:**

```json
{
  "type": "object",
  "properties": {
    "npc_updates": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "npc_name": {"type": "string"},
          "knowledge_gained": {"type": "array", "items": {"type": "string"}},
          "knowledge_lost": {"type": "array", "items": {"type": "string"}},
          "disposition_shift": {"type": "number", "minimum": -0.2, "maximum": 0.2},
          "emotional_state_change": {
            "type": ["object", "null"],
            "properties": {
              "mood": {"type": "string"},
              "intensity": {"type": "number"},
              "source": {"type": "string"}
            }
          }
        },
        "required": ["npc_name"]
      }
    },
    "thread_updates": {
      "type": "object",
      "properties": {
        "threads_advanced": {"type": "array", "items": {"type": "string"}},
        "threads_resolved": {"type": "array", "items": {"type": "string"}},
        "threads_opened": {"type": "array", "items": {"type": "string"}}
      }
    },
    "story_progress": {
      "type": "object",
      "properties": {
        "anchor_proximity": {
          "type": "string",
          "enum": ["distant", "approaching", "imminent", "reached"]
        },
        "progress_delta": {"type": "number", "minimum": 0.0, "maximum": 0.25},
        "reasoning": {"type": "string"}
      },
      "required": ["anchor_proximity", "progress_delta"]
    },
    "reputation_event": {"type": ["string", "null"]},
    "notable_action": {"type": ["string", "null"]}
  },
  "required": ["npc_updates", "thread_updates", "story_progress"]
}
```

**Campaign spine additions:**

- `anchor_description: str` per act — a brief description of what the
  anchor beat looks like narratively, used by the reconciliation prompt
  to judge anchor proximity and by the narration prompt for the anchor
  instruction. Distinct from `opening_situation` (which describes the
  state *after* the anchor).

**ArcState additions:**

- `turns_this_act: int` — incremented each turn, reset at act
  boundary
- `anchor_proximity: str` — updated by the reconciliation step each
  turn
- `pacing_instruction: str` — derived from act_progress band

**Build Roadmap integration:**

This system is partially needed in V1 (the reconciliation step should
exist even if only for basic NPC knowledge updates during the 5-turn
test) and fully needed for Milestone 1. The recommended approach:

**V1:** Implement a minimal reconciliation step that handles NPC
knowledge updates and basic thread tracking. Story progression and
act transitions are not needed (V1 stays within Act 1). The
reconciliation module and prompt exist but the progress/anchor
logic can return fixed values.

**Milestone 1, Phase 7 (before motivation wiring):** Implement the
full reconciliation step including story progression, anchor
detection, and act transition processing. This is prerequisite for
all of Milestone 1 because playing Acts 1-4 requires act transitions
to work.

---
## 27. Revision History

**v1.8 — Deferral design completion (March 2026)**

1. **Section 1.1 added: Reputation Echo Delivery Mechanism.** Complete
   pipeline from reconciliation capture through reputation log population,
   relevance scoring, surfacing frequency control with 3-turn cooldown,
   narration prompt injection block, and cross-campaign persistence.
   Completes the design that §1 and §21.4 partially specified.

2. **Section 24.4 added: Conditional Choice Availability from Behavioral
   Patterns.** Behavioral availability signal structure (dominant
   priorities, tags, throughline lean, pattern strength). Prompt injection
   mechanism that gives the cloud GM a behavioral portrait rather than
   lock/unlock lists. NPC-specific availability from disposition. Authored
   availability gates for campaign spines. Pattern strength threshold
   (0.4 minimum), mixed pattern handling, and graceful degradation before
   Phase 13.

3. **Section 26 subsection numbering fixed.** Internal subsections
   corrected from 27.x to 26.x.

**v1.7 — Post-turn state reconciliation (March 2026)**

1. **Section 26: Post-Turn State Reconciliation and Narrative Pacing.**
   The connective system between the turn loop and world state. Local
   model reconciliation step after each narration: updates NPC knowledge
   and disposition, tracks story progression via act_progress, detects
   anchor beat proximity, triggers act transitions, and manages open
   narrative threads. GM pacing guidance via progress-band-aware prompt
   instructions. Full 16-step between-act processing pipeline defined.
   Complete turn flow specified: 13 steps from choice selection through
   between-act processing. Minimal reconciliation in V1 (NPC knowledge
   only); full system for Milestone 1.

**v1.6 — Retrofit-risk closure (March 2026)**

Three additional sections closing all identified retrofitting risks
before V1 build:

1. **Section 23: Destiny Point Pool.** System-managed Light/Dark side
   spending integrated as Stage 4 of the pool modification pipeline.
   Light Side spending triggered by narrative stakes, mechanical
   impact, and player investment — experienced as luck or fate.
   Dark Side spending triggered by Obligation activation, antagonist
   engagement, spine-authored triggers, and escalation pacing —
   experienced as the galaxy pushing back. Optional seize-the-moment
   pre-roll choice for campaign climaxes. Full pipeline order
   defined: base → passives → conditionals → destiny → Force dice →
   roll → post-roll decisions.

2. **Section 24: Semantic Memory and Meaningful Choice Extraction.**
   Per-turn choice annotation via local model: extracts behavioral
   meaning (intent, sacrifice, priority revealed, NPC impact,
   throughline relevance) alongside the existing skill tag signal.
   Feeds enriched data to behavioral inference, character drift notes,
   aspiration echoes, throughline evolution, and milestone reflections.
   Graceful degradation — annotation failure falls back to skill-tag-
   only processing.

3. **Section 25: NPC Emotional State.** Transient mood overlay on
   long-term disposition. Nine-mood vocabulary with intensity and
   decay. Set by dice result consequences, spine-authored triggers,
   and GM-inferred cues. Emotional state injected into NPC prompt
   blocks. Sustained emotions nudge disposition over time. Decay
   paused when source is still active.

**v1.5 — Full mechanical design (March 2026)**

Nine new sections (14–22) completing the mechanical design for the
finished product. Previously deferred items now fully specified:

1. **Section 14: Character Advancement and Experience.** Behavioral
   inference engine for automatic skill rank advancement based on
   player choice patterns and failure learning. Milestone reflection
   system for transformative growth (talents, specializations,
   characteristics, Force awakening). XP earning via base-plus-
   performance at act boundaries. Force sensitivity discovery system
   with three postures (explicit Force, explicit non-Force, randomized
   "Let the Force decide"). Aspiration echo infrastructure in the GM
   prompt for latent Force hints and future Hybrid 3 advancement.

2. **Section 15: Talent Trees.** Five-type talent taxonomy (passive,
   conditional, substitution, narrative enabler, intervention). Pool
   modification pipeline with three stages. Pre-narration intervention
   step for reroll/negate talents. Branch-based tree navigation through
   milestone reflections. Talent library with shared definitions and
   per-specialization tree data. Check decision and narration prompt
   injection for talent awareness.

3. **Section 16: Force Mechanics.** Force dice resolution for enhanced
   skill checks and pure Force actions. Dark side temptation as
   conscious pre-narration moral choice. Morality inversion for dark-
   dominant characters (dark pips free, light pips cost strain). Force
   powers through narrative-tagged choices. Power upgrade trees via
   milestone reflections. Committed Force dice for sustained effects.
   Dark side spiral dynamics and anti-spiral safety valve.

4. **Section 17: Vehicle and Starship Encounters.** Ship state cards
   parallel to NPC state cards. Three-tier damage model (operational/
   stressed/critical). Encounter-level resolution paralleling Section 3.
   Role-determines-skill mapping for crew positions. Battle context
   layer for large-scale engagements.

5. **Section 18: Equipment and Inventory.** Loadout model replacing
   item-by-item inventory. Weapons, armor, tools, and special items
   as structured categories. Acquisition and loss through narrative.
   Equipment effects on check decisions and narration. Lightsaber
   special treatment.

6. **Section 19: Time Skip Mechanics.** Skip vignettes as core player
   experience — 2-3 authored playable scenes within each time gap,
   each producing behavioral inference data, NPC disposition changes,
   and Morality effects. Vignette library authored in campaign spine.
   Selection based on behavioral signals and NPC relationship priority.
   Skill drift and NPC relationship drift during gaps.

7. **Section 20: Cross-Era Character Progression.** Import package
   specification for character transfer between campaign spines.
   Specialization continuity/dormancy/evolution mappings. Era
   transition processing including motivation track transitions and
   XP rebalancing. Transition passage generation.

8. **Section 21: Large-Scale NPC Management.** Three-tier relevance
   routing (active/relevant/background). Five-signal relevance scoring.
   State compression for cross-campaign NPCs. Relationship summary
   rehydration at import boundaries. Reputation network scaling.

9. **Section 22: Canon Character Voice Fidelity.** Extended canon
   character profiles with voice, behavioral envelope, relationship
   dynamics, era-specific notes, and anti-stereotype notes. Per-act
   profile evolution for characters whose arc changes during the
   campaign. Player-influenced canon character state through import.

10. **Section 12 updated.** Deferred items list reduced to: multiplayer,
    psychometric prologue implementation, Campaign Studio systems.
    All mechanical design items now resolved in Sections 14–22.

**v1.4 — Character funnel pivot (March 2026)**

1. **Section 5 updated:** Psychometric Prologue problem statement and design
   updated to reflect the character funnel (Timeline → Allegiance → Variant).
   Prologue scenes may now be drawn from a career- and allegiance-scoped
   library rather than authored per specific named variant. Layer 2 mapping
   tables scoped by career type rather than specific variant, enabling
   scalability as the funnel's combinatorial space grows. Implementation
   notes updated to include `allegiance` field on variants, `career_type`
   tag on prologue scenes, and note that the funnel is a Campaign Studio /
   frontend concern — the Game Engine receives the final variant unchanged.

2. **Section 8 expanded:** Replayability gains Source 1 (funnel-driven
   divergence) as the highest-impact replayability mechanism. Different
   allegiance entries into the same campaign produce structurally different
   protagonist experiences through the protagonist integration layer.
   Previous Sources 1-3 renumbered to 2-4. Campaign design guidance updated
   to reflect that the fixed thematic spine must support multiple allegiance
   entries.

**v1.3 — Campaign Studio material migrated (March 2026)**

6. **Section 12 consolidated:** Five Campaign Studio deferred items (NPC
   coherence validation, relationship network validation, Mode 1 minimum
   viable input, campaign spine validation audit, campaign spine schema
   contract) migrated to the new Campaign Studio Design Document v1.0
   (Sections 5.1–5.4 and Section 3). Section 12 now contains brief
   references to the Campaign Studio Document for these items. Game Engine
   deferred items (multiplayer, character advancement, talent trees, vehicle
   encounters, crafting, psychometric prologue) remain in this document.

**v1.2 — Scene-type-aware context assembly (March 2026)**

5. **Section 10 expanded with scene-type-aware context assembly:** The cloud
   model's prompt assembly now modulates which context package fields are
   emphasized based on the scene type tag. Kinetic scenes (combat, chase,
   infiltration) foreground dense mechanical state — NPC dispositions,
   knowledge lists, spatial detail, equipment status. Reflective scenes
   (social, introspection) foreground motivational and relational context —
   NPC voice notes, character voice, throughline question, morality drift —
   while abbreviating mechanical state to avoid the "too literal" failure
   mode documented in KG-assisted storytelling research (Pan et al., IJHCI
   2025). Exploration scenes use balanced emphasis. No changes to the
   ContextPackage class, NPC state cards, or scene type classification logic.
   This is a prompt assembly routing decision, not a new system.

**v1.1 — Research integration (March 2026)**

1. **New Section 13 added:** "Prose Diagnostic Signal" — a lightweight
   local-model quality check running once per turn, scanning for prose
   pattern repetition, NPC action-emotion coherence drift, and relationship
   positivity bias. Produces structured JSON injected into the cloud model's
   context package. Deferred to post-V1 but schema reservation (`prose_
   diagnostic` field) added to context package spec. Dual-use as curation
   filter for the distillation pipeline. Informed by MiniMax's production
   quality auditing, MLD-EA's action-emotion coherence research (COLING
   2025), and Nonaka & Perry's network analysis of LLM positivity bias
   (NeurIPS 2025).

2. **Section 1 expanded:** Anti-positivity-bias prompt instruction added to
   implementation notes. Empirical data from 1,200+ story network analysis
   demonstrates LLMs systematically generate more positive, less conflict-
   driven character dynamics than human authors. Explicit prompt instruction
   added to counteract this in NPC interactions.

3. **Section 12 expanded with five Campaign Studio deferred items:**
   Campaign spine NPC coherence validation (per-NPC action-emotion chain
   tracing across acts), NPC relationship network validation (signed edge
   weight and clustering checks against LLM positivity norms), Mode 1
   minimum viable input specification (negative archetype requirements),
   campaign spine validation audit (multi-pass narrative/mechanical/variety
   checks), and campaign spine schema contract (typed validation on Studio
   output as interface contract with Game Engine). *Note: These items
   migrated to Campaign Studio Design Document v1.0 in v1.3.*

4. **Cross-references established:** Section 13 connects to LLM Evaluation
   Document v1.5 (distillation curation spec) and Implementation Document
   v1.5 (context package schema). Section 12 Campaign Studio items connect
   to the Campaign Studio Design Document v1.0 (migrated from Research
   Scoping Document v1.0).

**v1.0 — Initial document**

Created from design review session identifying gaps between the Vision
Document and the Implementation Document. Covers: core engagement loop,
failure recovery, combat abstraction, galactic context layer, psychometric
prologue design, session resume, onboarding, replayability, motivation track
mechanics, scene type pacing, and multi-session continuity.

---

*Storyteller V3 — Game Mechanics Design Document v1.7*
*The bridge between creative intent and code architecture.*
