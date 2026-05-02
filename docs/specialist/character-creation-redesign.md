# Storyteller V3 — Character Creation Redesign

> **SPECIALIST SPEC** — Reframes character creation around the
> Choice-of-Games / Heroes Rise pattern: a biographical background
> selected up front, optional refinement (skip-friendly), behavioral
> identity inferred during play via the existing psychometric
> prologue, and *deferred profession commitment* until a mid-game
> crystallization beat.
>
> **Build phase:** Phase 24 (proposed; sequenced after Phase 18
> psychometric prologue). Some elements may ship earlier as
> independent slices.
> **Core design authority:** Game Mechanics §5 (psychometric prologue),
> §14 (advancement), §15 (talents).
> **This document extends:** `prologue-system.md` (Phase 18 spec).
> **Implementation Status: NOT STARTED**

**Version:** 1.0
**Date:** 2026-05-01
**Originating analysis:** comparative review of *Eternal* (EndMaster,
chooseyourstory.com) and *Heroes Rise: The Prodigy* (Choice of Games)
against Storyteller V3.

---

## 0. Why this exists

Storyteller V3 currently frontloads all character creation: the
player picks species, career, specialization, talents, equipment, and
skill allocations *before any prose runs*. This is a tabletop-RPG
pattern.

Both reference CYOA systems we evaluated do something different.
Heroes Rise distributes customization across the opening hour as
diegetic story beats; the player is already invested when each
customization moment arrives. Eternal does no upfront customization at
all — the protagonist's identity *emerges* from a single character
commitment at Year 5 and crystallizes at Year 12. **Both reference
systems defer commitment until the player is engaged.**

The frontload pattern is also at odds with the reality of how
characters develop in narrative. A first-year Jedi Praxeum student in
16 ABY does not arrive with a chosen specialization. The discipline
they grow into is shaped by what they show their teachers, by what
challenges they face, and by what they choose under pressure.

This redesign aligns the character creation flow with the narrative
fiction of "newly-arrived Praxeum student" *and* with the design
patterns that work in successful CYOA. It does not abandon RPG depth
— skills, talents, Force powers, and equipment all remain real
mechanical objects — but their **commitment** is deferred to
narrative moments that earn them.

---

## 1. Design principles

1. **Defer commitment.** The player should not be asked to commit to
   a profession, lightsaber form, or talent tree before they have
   experienced anything. Commitments crystallize at narrative beats.
2. **Biographical + behavioral.** Identity has two layers: where the
   character came from (background, set up front) and how they
   respond to pressure (behavioral archetype, inferred during play).
   Both feed the eventual mechanical profile.
3. **Diegetic customization.** Every customization moment is a story
   beat. Names get picked when an NPC needs to know who you are.
   Gender gets recorded when a Praxeum admission form needs filling.
   Specialization crystallizes when Master Skywalker calls you aside.
4. **Defaults for fast players, customization for the rest.** Every
   field has a sensible default. The player can skip every
   refinement screen and reach gameplay in under 90 seconds. Players
   who want to customize can spend as long as they like.
5. **Maintain RPG depth.** Skills, talents, Force powers, and
   equipment are real. They affect dice pools and outcomes. The
   redesign changes *when* and *how* they are committed, not whether
   they exist.
6. **Use our advantage, don't fight it.** We can adapt narrative in
   real time; neither reference system can. The deferred-commitment
   model leans into this — it would be impractical for hand-authored
   CYOA to support 6 backgrounds × 4 professions × varied
   archetypes, but it is natural for an LLM-driven engine.

---

## 2. Player flow (end-to-end)

### 2.1 Frontload (target: under 90 seconds)

**Step 1 — Pick background (required, single click).**
Six options. Each is described in 2–3 sentences. Each is mechanically
distinct (skill tilts, pre-filled relationship, unique unlocks).

**Step 2 — Optional refinement.**
A single screen with collapsible sections. Each section shows the
background's default value plus a "Change" affordance.

| Field | Default | Change affordance |
|---|---|---|
| Name | One name auto-selected from the background's 5-option list | Pick another from the list, or type custom |
| Species | Background's primary suggested species (often Human) | Pick from full Star Wars species list |
| Gender / Pronouns | Not assumed; player picks from CoG-style 7-option list including custom vocab | (No skip — but the menu is one click) |
| Skill tilt | Background-optimal allocation | Optional skill builder for power users |
| Equipment | Background-themed loadout | Optional gear swap |
| Appearance flair | Sparse defaults | Optional 2–3 line flavor text |

A single "Begin Prologue" button at the bottom commits everything.
Players who skip every section get sensible defaults; players who
customize can do so in any depth.

### 2.2 Identity Prologue (target: 10–15 minutes of play)

The Phase 18 psychometric prologue runs here, with two extensions:

1. **Background-flavored scene library.** Each prologue scene has
   variants tuned to the player's background — an Imperial Defector
   experiences the same psychometric axis test through Imperial-tinged
   imagery, NPC reactions, and dialogue.
2. **Diegetic customization beats.** Anything the player skipped in
   Step 2 surfaces as an in-fiction moment. Name unset → a Master
   asks. Gender unset → admission form scene. The scene structure is
   identical whether the player customized or skipped — but the
   customization moments only display their menus when needed.

Output of the prologue:
- **Behavioral archetype** (existing Phase 18 system)
- **Initial skill tilt** (background tilt + archetype-driven adjustments)
- **Narrative identity** (motivation, throughline, voice notes — existing Phase 18)
- **One filled relationship slot** (background-pre-filled NPC)
- **Personality-lock commitments** (CoG-style multi-clause beliefs from key prologue moments)
- **No committed profession.** The character is "Jedi Praxeum student, [background], [archetype]" — generic Jedi tools, no specialization.

### 2.3 Acts 1–3 (early game, generic Praxeum student)

The character has skills, basic Force training, and behavioral
archetype-driven temperament. They do *not* have:
- A committed career (they are simply "Jedi student")
- Specialization talents (no Guardian / Sentinel / Consular tree active)
- Lightsaber form commitment
- Force power tree progression

What they do have:
- Force Rating 1
- Knowledge: Lore + Discipline as career skills (Praxeum student baseline)
- A small set of beginner Force powers (Move basics, Sense basics)
- Background-tilted skill ranks (e.g., Refugee → high Resilience and Vigilance; Smuggler → high Streetwise)
- Background-themed starter loadout (training saber, robes, datapad)

Talents and Force powers **unlock through play** (§5 below). The
LLM is told the character is "becoming" — narration should reference
emergent leanings, not committed paths.

### 2.4 Profession Crystallization Beat (Act 3 or 4)

A defined narrative moment where the character commits to a
discipline. Modeled directly on Eternal's Year 12 mentor scene where
the Beg/Die/Struggle commitment determines whether the protagonist
becomes Regular Army, Shadow Guard, or Mistress's apprentice.

- Triggered by the spine at a designated act anchor
- Scene context: Master (default: Skywalker) calls the protagonist
  aside after observing their progress
- 3 default options (Guardian, Consular, Sentinel) plus optionally a
  4th *background-specific* option that emerges if conditions are met
- The choice presented is *suggested* by accumulated play: the LLM
  highlights one option as the "natural" path based on the
  character's established pattern, but does not lock the player out
  of others
- The commitment is *real* — afterward the character has a chosen
  career and the corresponding specialization tree opens up

See §6 for full scene mechanics.

### 2.5 Acts 4+ (late game)

After crystallization, the character plays as a committed
Guardian/Consular/Sentinel with specialization unlocks. Sub-paths
within the chosen discipline can crystallize at later beats (e.g.,
saber form choice for Guardian during Act 5).

---

## 3. The Six Backgrounds

Each background is specified with: story seed, default name list,
default species, default skill tilt, pre-filled relationship,
unique unlocks, prologue tailoring, and profession affinities.

### 3.1 Outer Rim Refugee

**Story seed.** Imperial occupation forced your family from your home
world during the end-of-Empire chaos. You spent your formative years
in a refugee convoy, then a New Republic resettlement camp. A Jedi
recruiter found you when you instinctively shielded younger children
from a collapsing roof.

**Default names.** Sora, Jenn, Mira, Kestrel, Talen.

**Default species.** Human (suggested), Twi'lek, Mirialan also offered.

**Default skill tilt.** +1 Resilience, +1 Vigilance, +1 Survival,
−1 Knowledge (Education).

**Pre-filled relationship.** *Ren Vask* — another refugee student at
the Praxeum, slightly older, became a friend during your first weeks
because they recognized the silence of someone who has lost what you
have lost. Disposition: 65% (warm but cautious).

**Unique unlocks.**
- Refugee NPCs across the galaxy treat you with shared recognition;
  unlocked dialogue tone in social scenes with displaced populations
- Flashback access to your home world (used at major emotional beats)
- Trauma-anchored Force surge moments (when defending children, you
  surge above your trained capacity)

**Prologue tailoring.** Cold-open scene shows you arriving at the
Praxeum still carrying a child's blanket from the convoy. The
behavioral archetype scenes are flavored toward "what you do when
something familiar happens" rather than "what you do under
abstract pressure."

**Profession affinities.**
- **Strong fit:** Consular (your trauma points toward healing and
  diplomacy)
- **Possible fit:** Sentinel (the pattern recognition refugees
  develop)
- **Tense fit:** Guardian (combat-focus risks reopening trauma —
  available, but the prologue will warn against it)

---

### 3.2 Imperial Defector

**Story seed.** Born inside the Empire's middle classes, raised on
its propaganda. You served in some capacity (junior officer cadet,
COMPNOR youth corps, Imperial academy student) before your
Force-sensitivity manifested in a way that put you on the Inquisitor
list. You ran. The New Republic intercepted you. You came to the
Praxeum carrying real guilt and real Imperial training.

**Default names.** Cael, Nyx, Vell, Doran, Ardin.

**Default species.** Human (suggested) — the Empire is Human-supremacist,
making other species rare for this background; if chosen, the
character has a more dramatic story.

**Default skill tilt.** +1 Discipline, +1 Knowledge (Warfare), +1
Computers, −1 Charm.

**Pre-filled relationship.** *Master Tev* — a senior Praxeum
instructor who chose to be your sponsor against the wishes of others.
Watches you carefully. Disposition: 50% (neutral, tested).

**Unique unlocks.**
- Imperial-tech recognition (rolls with bonus when interpreting
  Imperial machinery, doctrine, encrypted comms)
- Old contacts (1–2 NPCs from your past exist in the world; can be
  encountered in later acts — possibly as antagonists)
- **Sith-curious dialogue branches.** Some choices that other
  backgrounds cannot pick because they require Imperial framing
  (e.g., "I have read the propaganda; I know how this rhetoric works")

**Prologue tailoring.** Cold-open scene shows you in your former
uniform on the day you ran. The behavioral archetype scenes are
flavored around "what you do when ideology cracks" — high salience
on the Moral axis, fast inference on Trust.

**Profession affinities.**
- **Strong fit:** Sentinel (pattern recognition and infiltration are
  natural extensions of your training)
- **Possible fit:** Consular (some defectors atone through diplomacy)
- **Tense fit:** Guardian (returning to combat triggers identity
  conflict; the prologue will note this)

---

### 3.3 Rebel Legacy

**Story seed.** Your parents fought in the Rebellion. One of them
may still be alive in the New Republic government or military; the
other may have died at Endor or in the wars after. You grew up on
hero stories and at hero funerals. Your Force sensitivity was
expected. The pressure is heavier than the training.

**Default names.** Riggs, Mara, Jarek, Kyla, Ben.

**Default species.** Human (suggested), Mon Calamari, Sullustan
also offered.

**Default skill tilt.** +1 Ranged (Light), +1 Discipline,
+1 Leadership, −1 Coordination.

**Pre-filled relationship.** *Master Tasha Vren* — a Jedi who fought
alongside one of your parents. Has known you since you were a child.
Disposition: 80% (familial warmth, with weight of expectation).

**Unique unlocks.**
- War-veteran NPCs treat you as kin; unlocked dialogue with Rebellion
  / New Republic veterans across the galaxy
- "Impatient with meditation" flavor — your behavior has a
  characteristic restlessness that the Praxeum tries to address
- Your parents' name carries through; Imperial holdouts who
  recognize you may react with hostility

**Prologue tailoring.** Cold-open scene shows you sparring against
upper-classmen with the saber form your parent used; you are *good*
because you have practiced this since you were six. The behavioral
archetype scenes test what happens when expectations conflict with
instinct.

**Profession affinities.**
- **Strong fit:** Guardian (the family path; the protagonist will be
  pushed toward this by everyone in their life)
- **Possible fit:** Sentinel (a quieter variation that some Rebel
  veterans respect)
- **Tense fit:** Consular (chosen against expectation — a rebellion
  against the Rebellion legacy)

---

### 3.4 Discovered Late

**Story seed.** Your Force-sensitivity emerged when you were already
an adult — twenty-three, twenty-five, even older. You had a life: a
career, possibly a partnership, a sense of who you were. The Force
disrupted that. You arrive at the Praxeum older than every other
first-year student, with adult competencies and adult anxieties.

**Default names.** Margo, Tarn, Kael, Senna, Joren.

**Default species.** Human (suggested), Pantoran, Zabrak also offered.

**Default skill tilt.** +1 Knowledge (Lore), +1 Negotiation, +1 Skulduggery,
−1 Athletics.

**Pre-filled relationship.** *Vesper* — a younger student (16-17) who
looks up to you because you are visibly an adult and treat them with
respect rather than condescension. Disposition: 70% (admiration).

**Unique unlocks.**
- Adult-experience flavor — the LLM is told to write you as someone
  who has had jobs, paid rent, lost relationships
- "Less reverent of tradition" — some choices that read as cynical
  for younger students read as informed-skeptical for you
- Your previous career creates contacts in late-game scenes

**Prologue tailoring.** Cold-open scene shows you packing up your
former life — a tool kit, a uniform, a key turned in. The behavioral
archetype scenes test how an adult mind responds to being a
beginner.

**Profession affinities.**
- **Strong fit:** Consular (the patience of someone who has lived
  longer translates well)
- **Possible fit:** Sentinel (your previous career may have already
  trained you in pattern recognition)
- **Tense fit:** Guardian (combat at your age is harder than it would
  be for younger students; the prologue will note physical limits)

---

### 3.5 Frontier-World Native

**Story seed.** You grew up on a Wild Space or Outer Rim world that
the galaxy barely tracks — small population, no holonet, traditional
livelihoods. The Force showed up as part of how the world worked,
and a Jedi recruiter who happened through your settlement noticed
what you were doing. You had never heard of the Jedi until they
explained themselves to you.

**Default names.** Cova, Den, Brae, Tova, Eli.

**Default species.** Human (suggested), Togruta, Cathar, Ithorian
also offered.

**Default skill tilt.** +1 Survival, +1 Perception, +1 Resilience,
−1 Knowledge (Core Worlds).

**Pre-filled relationship.** *Recruiter Adric* — the Jedi who came
through your settlement and brought you to the Praxeum. Visits
occasionally; checks on you. Disposition: 75% (mentor-like, slightly
distant).

**Unique unlocks.**
- Survival skills (shelter, food, terrain reading) usable in
  exploration scenes for narrative bonuses
- Cultural-stranger flavor — you find the Praxeum's politics
  baffling, and the LLM is told to write some scenes as
  observational rather than participatory
- Your home world becomes a load-bearing late-game location

**Prologue tailoring.** Cold-open scene shows you in your home
world's traditional dress on the day Adric arrives. The behavioral
archetype scenes test your responses to cultural-translation moments
as much as ethical-pressure moments.

**Profession affinities.**
- **Strong fit:** Guardian (the practical, physical training fits how
  you already learn)
- **Possible fit:** Sentinel (your perceptiveness was already there)
- **Tense fit:** Consular (the diplomatic register requires cultural
  vocabulary you do not yet have)

---

### 3.6 Reformed Smuggler

**Story seed.** Your Force-sensitivity developed in the wrong
neighborhood. You ran cargoes you shouldn't have, kept company with
people you shouldn't have, and were pretty good at all of it. A
botched job ended with someone dead and you in a Jedi-adjacent
sanctuary. The Praxeum offered a path. You took it. Most of you.

**Default names.** Kade, Loris, Talia, Jin, Ess.

**Default species.** Human (suggested), Rodian, Kel Dor, Twi'lek
also offered.

**Default skill tilt.** +1 Streetwise, +1 Skulduggery, +1 Piloting (Space),
−1 Discipline.

**Pre-filled relationship.** *Hux* — your old smuggling partner, still
working. Has not been told you are at the Praxeum. Disposition: 60%
(loyal but unaware) — will become important in late-game when paths
cross.

**Unique unlocks.**
- Underworld dialogue across the galaxy
- "Distrust authority" flavor — you flinch at uniforms even when
  they are your own side
- Underground contacts can be invoked in narrative for non-combat
  problem-solving

**Prologue tailoring.** Cold-open scene shows you in a Coruscant
lower-level cantina the morning after the botched job. The
behavioral archetype scenes test what happens when you are asked to
trust a system you have spent your life dodging.

**Profession affinities.**
- **Strong fit:** Sentinel (the discipline that survives gray morality)
- **Possible fit:** Consular (some smugglers find unexpected
  diplomatic gifts)
- **Tense fit:** Guardian (your distrust of authority makes the
  Guardian's defender role uncomfortable)

---

## 4. Refinement screen

### 4.1 Layout

Single screen. Top: background card showing what was picked, with
its story seed and a "Change background?" link.

Below: collapsible sections, each header showing field name + current
default + chevron to expand.

Bottom: large "Begin Prologue" button.

### 4.2 Per-field behavior

**Name.**
- Default: one name from the 5-option list, randomly auto-selected
  per session
- Expansion shows the 5 background names plus "Type a custom name…"
  field
- The chosen name is what the LLM writes in narration; if no choice
  is made by the time the prologue's name-asking beat fires, that
  beat displays the menu

**Species.**
- Default: the background's primary suggestion (typically Human)
- Expansion shows 3–5 background-themed options plus "Show all
  species" expander
- Selected species feeds into [engine/character.py](engine/character.py)
  `Species` enum

**Gender / Pronouns.**
- No default — this field is the one that always asks
- Seven-option list modeled on Heroes Rise's:
  1. Female
  2. Male
  3. Assigned female at birth, identify as male
  4. Assigned male at birth, identify as female
  5. Born intersex
  6. Non-binary
  7. None of these — type my own vocabulary
- Pronoun field auto-populated from gender choice but editable
- The choice surfaces *here* if expanded; *or* in the prologue's
  admission-form beat if skipped

**Skill tilt.**
- Default: background's recommended allocation (e.g., Refugee gets
  +1 Resilience, +1 Vigilance, +1 Survival, −1 Knowledge)
- Expansion shows full skill list with adjustable ranks within a
  total-points budget
- Power users can completely re-allocate; default players never see
  this

**Equipment.**
- Default: background-themed starter loadout
- Expansion shows 2–3 alternate loadout themes plus an item-by-item
  swap interface
- Trainee saber, robes, datapad are constants regardless of swap

**Appearance flair.**
- Optional, default is empty
- Expansion shows a free-text field with 2–3 example prompts ("hair,
  notable scar, way of moving")
- Used by the LLM as flavor when it describes the protagonist

### 4.3 Skip behavior

A "Begin Prologue" click with no expansions taken applies all
defaults and proceeds. Total time: under 90 seconds for a player who
clicks through.

### 4.4 Validation

- Background must be selected (no default — first interaction)
- All other fields can default
- Custom name field has a length cap (32 chars) and rejects all
  whitespace
- Custom pronouns field has a length cap (32 chars per slot) and
  is plain-text only

---

## 5. Identity Prologue integration with Phase 18

### 5.1 Relationship to existing spec

The existing Phase 18 spec ([prologue-system.md](docs/specialist/prologue-system.md))
specifies a 3–5 scene psychometric prologue with four behavioral axes
(Approach, Social, Risk, Moral) and a three-layer inference model
(behavioral archetype → mechanical profile → narrative identity).

This redesign **does not replace** the Phase 18 inference engine. It
extends it with three additions:

1. **Background-flavored scene library.** Each axis-test scene has
   per-background variants. The same Approach axis test (Direct vs.
   Indirect) plays out as a different narrative depending on
   background.
2. **Diegetic customization beats.** Customization moments not
   completed in the refinement screen surface as in-fiction events
   inside the prologue.
3. **Tilt, not commitment.** The Phase 18 Layer 2 mechanical profile
   inference still runs, but its output is now a *tilt vector* applied
   to a generic Praxeum-student baseline rather than a committed
   career. The career commitment happens later (§6).

### 5.2 Scene library shape

A Phase 18 prologue scene is currently expected to have shape:
`(career_type, allegiance, axis-tags)`. Under the redesign:

```python
class PrologueScene(BaseModel):
    scene_id: str
    background_variants: dict[str, BackgroundVariant]  # 6 entries
    axis_tags: list[AxisTag]                            # which axes this scene measures
    diegetic_slot: Optional[DiegeticSlot]               # if set, this scene
                                                         # also surfaces a skipped
                                                         # customization beat
```

`BackgroundVariant` carries the prose, NPC names, and choice text
for one background's version of the scene.

`DiegeticSlot` (when present) is one of:
- `name_pick` — used in scenes where an NPC asks the protagonist's name
- `gender_pick` — used in admission-form-style scenes
- `appearance_flair` — used in mirror-and-self-observation scenes

The studio is responsible for ensuring each diegetic slot has at
least one prologue scene that can host it. The runtime checks
whether the relevant field is unset; if so, the scene displays the
menu inline.

### 5.3 Output contract

The prologue's output, post-redesign:

```python
class PrologueOutput(BaseModel):
    behavioral_archetype: str               # Phase 18, unchanged
    initial_skill_tilt: dict[str, int]      # background tilt + archetype-driven adjustment
    narrative_identity: NarrativeIdentity   # Phase 18, unchanged
    filled_relationships: list[RelationshipState]   # at least one (background-pre-filled)
    personality_lock: list[BeliefCommitment]        # CoG-style multi-clause beliefs from key beats
    profession: None                         # explicitly None — committed later
```

The character entering Act 1 is a *Praxeum student* with the
above-tilted skills and an inferred archetype, not a Guardian or
Consular or Sentinel.

---

## 6. Profession Crystallization Beat

### 6.1 Trigger

The crystallization beat is **spine-authored**, not runtime-emergent.
The campaign spine declares an act anchor as the
`profession_crystallization` anchor. For [Shadows of the Custodian](data/campaigns/shadows_of_the_custodian.json)
this would be at Act 3 or Act 4 (TBD during migration §8).

### 6.2 Scene shape

A standard scene (~400–600 words of narration) in which a senior
Jedi calls the protagonist aside. Default mentor: Master Skywalker.
Background-specific alternatives possible (e.g., for Imperial
Defector, Master Tev who sponsored them).

The scene structure:

1. **Recognition beat** — the mentor narrates what they have
   observed about the protagonist's pattern of choices over the
   prologue and Acts 1–3. The LLM receives the accumulated state
   (behavioral archetype, recent choices, skill use patterns, NPC
   dispositions) and renders this in mentor voice.
2. **Suggestion beat** — the mentor gestures toward one of the
   three paths as the natural-feeling fit. This is determined by:
   - Background's strong-fit profession (§3 above) gets +2 weight
   - Behavioral archetype's compatible profession gets +2 weight
   - Most-used skill set (Top 3 skills) gets +1 weight per match
   - The path with highest weight is the *suggested* path
3. **Choice surface** — three options visible:
   - **Guardian** (combat, defense, direct action)
   - **Consular** (mind-arts, diplomacy, healing)
   - **Sentinel** (investigation, balance, hidden service)
   - Plus an optional 4th *background-specific* path that surfaces
     only if the background's flag is set and the pattern strongly
     supports it (e.g., Imperial Defector with high Sentinel-pattern
     might unlock "Shadow Sentinel" — a sub-discipline)
4. **Commitment beat** — the choice is final for this campaign.
   The character's `career` field is set; specialization tree opens.

### 6.3 Suggested vs. forced

The suggested path is *highlighted* in the choice surface but not
*defaulted*. The player can choose against the grain. If they do, the
narration acknowledges it (Master expresses surprise, sometimes
concern, sometimes respect for the unexpected wisdom).

The against-the-grain path is *real* — the character genuinely
becomes that profession and the spine adapts. But the LLM is told
that the early acts of the profession will feel less natural for
this character than they would for someone whose pattern matched.
This is Eternal-style "character formation as fate" softened into
"character formation as suggestion."

### 6.4 Schema

```python
class ProfessionCrystallization(BaseModel):
    anchor_act: int                              # which act this scene lives in
    mentor_npc: str                              # default "Master Skywalker"
    background_overrides: dict[str, str]         # background → mentor NPC
    paths: list[ProfessionPath]                  # 3 default + optional 4th
    suggestion_algorithm: SuggestionAlgorithm    # weights described §6.2
```

`ProfessionPath` contains the career commitment, the talent tree
that opens, and the prose-flavor cue for the LLM's rendering of the
choice in narration.

### 6.5 Backwards compatibility with current Career enum

The existing `Career` enum at [engine/character.py:26-49](engine/character.py)
includes EotE/AoR/F&D careers. The crystallization paths map to F&D
careers:

- Guardian → `Career.GUARDIAN`
- Consular → `Career.CONSULAR`
- Sentinel → `Career.SENTINEL`

Pre-crystallization, the character's career is set to a new enum
value `Career.PRAXEUM_STUDENT` (or `Career.JEDI_STUDENT`) which
indicates the not-yet-committed state. Downstream code paths that
gate on career must handle this value gracefully — see §9 migration.

---

## 7. Talent / Force power unlock model

### 7.1 Current state

[engine/character.py](engine/character.py) `Character.acquired_talents`
and `Character.force_powers` are populated up front by the character
builder.

### 7.2 Proposed state

Both fields start empty for a Praxeum-student character. They
populate through play via three mechanisms:

**Mechanism 1 — Prologue grant.** The prologue's behavioral
archetype output grants 1–2 starter talents and 1 Force power
upgrade aligned with the archetype. The grant is suggested in the
LLM's narration of the prologue's closing beat ("you find that ___
comes more naturally to you than your peers").

**Mechanism 2 — Crystallization unlock.** When the profession
crystallizes (§6), the corresponding specialization talent tree
opens. The protagonist gets 1–2 free baseline talents from the tree
and the rest become available for XP purchase.

**Mechanism 3 — Earned-through-use.** Some talents and Force power
upgrades unlock when the character demonstrates the relevant pattern
enough times. (Implementation borrows from the existing advancement
system at [engine/advancement.py](engine/advancement.py), Phase 10).
For example, a Consular who has used Influence in 4+ scenes might
unlock the "Hard-Pressed Influence" talent at the next milestone.

### 7.3 Player visibility

Unlocks are surfaced in the dashboard with gentle notifications, not
modal popups. Players who care about builds can watch their talent
tree fill in; players who don't care never need to look at it — the
character keeps narrating coherently regardless.

### 7.4 LLM context impact

The narration prompt at [gm/prompts/narration.txt](gm/prompts/narration.txt)
is told the character's currently-active talents and Force powers
each turn. Pre-crystallization, this list is small and Praxeum-flavored;
post-crystallization, it grows with the chosen specialization.

---

## 8. Migration plan — Shadows of the Custodian

### 8.1 Current state of the canonical campaign

[data/campaigns/shadows_of_the_custodian.json](data/campaigns/shadows_of_the_custodian.json)
currently expects the protagonist to arrive with a committed career.
Two character variants exist:
- [praxeum_student.json](data/characters/praxeum_student.json)
- [praxeum_mechanic.json](data/characters/praxeum_mechanic.json)

These are full-kit pre-built characters.

### 8.2 Refactor scope

**Step 1 — Add background field to spine.**
The spine schema gets a `backgrounds: list[Background]` field. For
Shadows of the Custodian, populate with 6 backgrounds defined in §3.

**Step 2 — Convert character variants to background presets.**
The two existing variants become *initial-tilt presets* within the
background system. Likely mapping:
- `praxeum_student.json` → maps to **Rebel Legacy** or **Frontier-World Native**
- `praxeum_mechanic.json` → maps to **Reformed Smuggler** or **Imperial Defector**

The presets retain their narrative identity but are repackaged as
backgrounds. If any of the 6 §3 backgrounds reads as the natural fit,
collapse the variant into the background; otherwise add a 7th.

**Step 3 — Insert Identity Prologue arc.**
A new act (or expanded Act 0) plays the Identity Prologue. The
existing first-encounter scenes in Shadows of the Custodian become
Act 1 content.

**Step 4 — Designate the crystallization beat.**
Pick the act anchor where the protagonist's profession crystallizes.
Likely candidates: the Master Skywalker meeting after a major
mission, or after a moment of personal danger that exposes the
character's pattern. Author the crystallization scene.

**Step 5 — Adjust early-act content.**
Scenes that currently assume specialization-specific abilities or
dialogue need to be either:
- Generalized (replace specialization-specific lines with student-level lines)
- Gated (only available post-crystallization)
- Adapted (accept multiple variants per profession)

**Step 6 — Adjust late-act content for crystallized variations.**
Scenes after the crystallization beat now have profession-specific
content variants. The studio needs to author Guardian / Consular /
Sentinel variants where appropriate.

### 8.3 Risk areas

- **Existing playthroughs.** Storyteller V3 is pre-V1; we have no
  saved-game contract to maintain. Migration breaks any in-progress
  Shadows of the Custodian playthroughs. Acceptable.
- **Narrative arc Brooks/Weiland validation.** The campaign was
  authored to a specific narrative arc structure. Inserting a
  crystallization beat may disrupt the arc. Validation will need to
  re-run.
- **Dramatic mission classification.** The CS-6 dramatic mission
  system at [engine/dramatic_mission.py](engine/dramatic_mission.py)
  classifies scenes by their dramatic function. Pre-crystallization
  scenes need a new classification ("formation") that doesn't yet
  exist.
- **Time-skip vignettes.** The existing Phase 17 time-skip system at
  [engine/time_skip.py](engine/time_skip.py) needs to handle
  pre-crystallization vignette content that shouldn't reference a
  specialization the character does not yet have.

### 8.4 Validation

- All four spine validation gates (Coherence, Anchor, Throughline,
  Narrative Quality at [studio/validate.py](studio/validate.py))
  must pass on the refactored spine
- Manual playthrough of all 6 backgrounds through the prologue and
  to the crystallization beat
- Manual playthrough of all 6 backgrounds × 3 professions =
  18 trajectories at minimum; sample to spot-check for coherence

---

## 9. Schema changes

### 9.1 New models in studio/schema.py

```python
class Background(BaseModel):
    background_id: str                          # e.g. "outer_rim_refugee"
    display_name: str
    story_seed: str                             # 2-3 sentence summary
    default_names: list[str]                    # 5 background-themed names
    default_species: list[str]                  # 1-3 suggested species
    default_skill_tilt: dict[str, int]          # skill ranks adjustment
    default_loadout: str                        # loadout_id reference
    pre_filled_relationship: RelationshipSeed   # one NPC seeded with disposition
    unique_unlocks: list[UniqueUnlock]
    prologue_tailoring: PrologueTailoring
    profession_affinities: ProfessionAffinities

class RelationshipSeed(BaseModel):
    npc_name: str
    npc_role: str                               # e.g. "fellow refugee student"
    initial_disposition: int                    # 0-100
    relationship_summary: str

class UniqueUnlock(BaseModel):
    unlock_id: str
    description: str
    trigger_type: str                           # "dialogue_tone", "flashback_access",
                                                # "conditional_branch", etc.

class PrologueTailoring(BaseModel):
    cold_open_concept: str                      # 1-2 sentences for the LLM
    archetype_scene_flavor: str                 # how to frame psychometric scenes
    diegetic_slot_preferences: dict[str, str]   # which scenes to host which customization beats

class ProfessionAffinities(BaseModel):
    strong_fit: str                             # career_id of natural path
    possible_fit: list[str]                     # career_ids of other reasonable paths
    tense_fit: list[str]                        # career_ids that work but are noted

class CampaignSpine(BaseModel):
    # ... existing fields ...
    backgrounds: list[Background]                       # 6 backgrounds (or campaign-specific count)
    identity_prologue: IdentityPrologueArc
    profession_crystallization: ProfessionCrystallization

class IdentityPrologueArc(BaseModel):
    scene_library: list[PrologueScene]
    expected_scene_count: int                            # 3-5 (Phase 18)
    diegetic_slots_required: list[str]                   # name_pick, gender_pick, etc.

class ProfessionCrystallization(BaseModel):
    anchor_act: int
    mentor_npc: str
    background_overrides: dict[str, str]
    paths: list[ProfessionPath]
    suggestion_algorithm: SuggestionAlgorithm

class ProfessionPath(BaseModel):
    career_id: str
    talent_tree_id: str
    prose_flavor: str

class SuggestionAlgorithm(BaseModel):
    background_weight: int = 2
    archetype_weight: int = 2
    skill_match_weight: int = 1
```

### 9.2 Updates to engine/character.py

```python
class Career(Enum):
    # ... existing values ...
    PRAXEUM_STUDENT = "praxeum_student"   # NEW: pre-crystallization state
    JEDI_STUDENT    = "jedi_student"      # alias

class Character(BaseModel):
    name:                 Optional[str] = None        # CHANGED: now optional
                                                       # (filled by prologue if unset)
    species:              Optional[Species] = None     # CHANGED: now optional
    career:               Career = Career.PRAXEUM_STUDENT   # CHANGED: defaults to student
    specializations:      list[str] = Field(default_factory=list)  # unchanged, but starts empty
    background:           str = ""                              # repurposed: now is the background_id
    gender:               Optional[str] = None         # NEW: optional
    pronouns:             Optional[Pronouns] = None    # NEW: optional
    appearance_flair:     str = ""                     # NEW: optional flavor text
    behavioral_archetype: Optional[str] = None         # NEW: prologue output
    skill_tilt:           dict[str, int] = Field(default_factory=dict)  # NEW: prologue output
    personality_locks:    list[BeliefCommitment] = Field(default_factory=list)  # NEW: prologue output
    crystallized:         bool = False                  # NEW: True after profession crystallization beat
    # ... existing fields continue ...

class Pronouns(BaseModel):
    subject: str       # "she" / "he" / "they" / custom
    object: str        # "her" / "him" / "them" / custom
    possessive: str    # "her" / "his" / "their" / custom

class BeliefCommitment(BaseModel):
    axis: str                # which behavioral axis
    commitment_text: str     # the player-facing belief statement
    stat_effects: dict[str, int]  # range adjustment going forward
```

### 9.3 Updates to api/game_routes.py

The session creation flow at [api/game_routes.py](api/game_routes.py)
gets a new endpoint:

- `POST /api/game/select_background` — accepts `background_id`,
  returns the refinement screen state for that background
- `POST /api/game/refine_character` — accepts the refinement screen
  fields (any subset), returns the prologue start state
- `POST /api/game/crystallize` — accepts the profession choice from
  the crystallization beat, returns the post-crystallization
  character state

### 9.4 Updates to web/index.html

Three new screens:
- Background selection screen (6 cards with story seeds)
- Refinement screen (collapsible sections, defaults visible)
- Crystallization choice surface (3-4 cards with mentor narration above)

---

## 10. LLM context package changes

The cloud GM at [gm/cloud_gm.py](gm/cloud_gm.py) currently receives a
context package with character state, recent turns, dice results, etc.

After this redesign, the context package gains:

- **`background_id`** and **`background_summary`** — short
  description of the protagonist's biographical frame
- **`behavioral_archetype`** (post-prologue) — the inferred axis
  pattern
- **`personality_locks`** — list of belief commitments that constrain
  voice
- **`skill_tilt`** — pre-crystallization skill leanings
- **`profession_status`** — `"praxeum_student"` (pre-crystallization)
  or the committed career
- **`pre_crystallization_flag`** — boolean; when True, the prompt is
  told to write the protagonist as "becoming," not "being"

The narration prompt at [gm/prompts/narration.txt](gm/prompts/narration.txt)
gains guidance for both states:

```
PRE-CRYSTALLIZATION (character is a Praxeum student):
- The protagonist is a first-year student. They have raw talent and
  a behavioral pattern, but no committed discipline.
- Reference emergent leanings ("you find yourself naturally drawn
  to..."), not committed paths.
- Other students and instructors observe the protagonist and may
  speculate about their direction.
- Choices should sometimes test multiple disciplines simultaneously
  to inform the eventual crystallization.

POST-CRYSTALLIZATION (character has chosen a discipline):
- The protagonist has committed to [career]. Reference this as
  established identity.
- Specialization-flavored ability use is normal and expected.
- The choice may have been against the grain of accumulated
  pattern; the narration may occasionally acknowledge the
  protagonist still feeling new in the role if that was the case.
```

---

## 11. Open questions

These are intentionally unresolved at the time of this v1.0 draft:

1. **6 backgrounds vs. 4 vs. 8.** The §3 list has 6. Six is more
   than CoG typically uses (3–4) and less than Eternal's
   "everything matters." Empirical question: does play-testing show
   six as the right count?
2. **Background selection screen UX.** Cards vs. list vs.
   dialog-style intro? Probably cards, but not specified here.
3. **Crystallization timing per spine.** Act 3 vs. Act 4 vs.
   spine-author-determined. Probably spine-author-determined within
   a recommended window.
4. **Background-specific 4th profession path.** Should this exist?
   (Imperial Defector → Shadow Sentinel.) Adds depth but adds
   authoring burden. Defer to first migration to decide.
5. **Pronouns customization granularity.** The schema allows
   custom subject/object/possessive. UX should not overwhelm.
   Possibly hide the granular fields behind a "more options" link.
6. **Talent unlock pacing.** Mechanism 3 in §7.2 (earned-through-use)
   needs concrete thresholds. Borrow from existing advancement
   system or define new.
7. **What happens if the player wants to switch backgrounds
   mid-prologue?** Probably allow until the first axis-test choice;
   afterward, no.
8. **Saga continuity.** When a Phase 19+ saga character is imported
   to a new campaign, what happens to background, archetype, and
   crystallized profession? They probably carry forward; spec needs
   to be explicit.

---

## 12. Phasing

This redesign is large. Recommended phasing if shipping in slices:

**Phase 24a — Background selection + refinement screen.**
Backgrounds defined, refinement screen built, defaults applied.
Prologue still runs as Phase 18 designed (no integration yet).
Profession still committed up front. Player can pick a background
that flavors prose but does not yet defer profession.

**Phase 24b — Background-flavored prologue scene library.**
Phase 18 prologue scenes get background variants. Diegetic
customization beats added.

**Phase 24c — Deferred profession + crystallization beat.**
Career commitment moves out of frontload and into mid-game.
Crystallization scene authored. Talent unlocks gated on
crystallization.

**Phase 24d — Talent earned-through-use mechanism.**
Pattern-based unlock thresholds added.

**Phase 24e — Shadows of the Custodian migration.**
The canonical campaign refactored to use the new system.

Each phase delivers visible value independently. Phase 24a is
shippable in ~1 week of focused work. Phase 24c is the largest
single piece (~3 weeks).

---

## 13. References

- `docs/specialist/prologue-system.md` — Phase 18 psychometric prologue
- `docs/specs/game-mechanics.md` §5 — psychometric prologue design authority
- `docs/specs/game-mechanics.md` §14 — advancement
- `docs/specs/game-mechanics.md` §15 — talents
- `docs/specs/engine-implementation.md` — engine implementation spec
- `docs/specs/studio-implementation.md` — Campaign Studio implementation spec
- Triangular comparative review (working draft): `C:/tmp/eternal_vs_storyteller_draft.md`

---
