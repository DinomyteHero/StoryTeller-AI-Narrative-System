# Storyteller V3
## Game Vision & Design Document

---

## Executive Summary

Storyteller V3 is an AI-powered narrative RPG engine that delivers a
prose-first, book-like gaming experience using the FFG Star Wars tabletop
roleplaying system as its mechanical foundation. It is not a video game.
It is not a chatbot. It sits at the intersection of three things that have
never been cleanly combined: the literary reading experience of Choice of
Games interactive fiction, the mechanical richness and dramatic texture of
Fantasy Flight Games' narrative dice system, and the generative intelligence
of modern large language models acting as a persistent, context-aware Game Master.

The result is something genuinely new — a game that reads like a Star Wars
novel, plays like a tabletop session, and remembers who your character is
becoming.

The prose voice blends the visceral interiority of Matthew Stover with the
lived-in political worldbuilding of James Luceno. The player experiences
the game in chapter-length sessions of 45 to 90 minutes, each structured
with its own internal arc and designed to produce a page-turner pull that
makes stopping mid-chapter feel like putting down a novel at the wrong moment.
The mechanical layer is invisible — the player never sees a number, never
reads a stat block, never encounters the word "roll." They feel the stakes
rise. They make a choice. The story tells them what happened.

---

## 1. The Problem We Are Solving

Every existing approach to AI-driven narrative gaming has failed in one of
two directions.

The first failure is **mechanical shallowness.** Products like AI Dungeon
demonstrated that LLMs could generate compelling prose but produced narratives
that drifted, contradicted themselves, and carried no meaningful consequence.
Dice were cosmetic. Character sheets were decorations. The story forgot what
happened three turns ago. The experience felt like a dream — vivid in the
moment, incoherent in aggregate.

The second failure is **narrative shallowness.** Traditional TTRPG video game
adaptations — Knights of the Old Republic, Baldur's Gate, the Pathfinder
games — built mechanically rigorous systems but delivered pre-authored,
finite narrative spaces. The story was written by humans before you played.
Your choices navigated a tree that existed before you arrived. The world did
not respond to you specifically. It responded to whichever branch you were on.

Storyteller V3 refuses both failures. The mechanical layer is real and
consequential. The narrative layer is genuinely generative and specific to you.
The two layers are not separate — the dice do not pause the story, they
generate it.

---

## 2. The Format — Choice of Games, Taken Seriously

Choice of Games is an interactive fiction publisher whose games are beloved
for one reason: they make you feel like the protagonist of a novel rather than
a player navigating a system. Their format is prose-first. You read a passage
of 250 to 600 words that places you in a specific moment with specific sensory
detail and genuine literary care. Then you make a choice. The choice leads to
another passage. The story accumulates.

This format is the right delivery mechanism for what we are building. It is
not a dialogue wheel. It is not a conversation box. It is not a menu of
actions. It is reading. The primary activity is reading, and everything else
serves that activity.

What makes CoG's choices work — and what most imitators miss — is that the
choices are not generic action types. They are not Attack/Defend/Talk/Retreat.
They are specific to this character, in this moment, with these stakes. Each
option represents a genuinely different way of being in the world. The choice
you make says something about who you are, not just what you do.

Our system generates choices this way. They emerge from the scene. They are
mechanically tagged where appropriate — this one requires a Deception check,
that one costs resources but needs no roll. Some are only available because of
who your character has revealed themselves to be. None of them are generic.

---

## 3. The Prose Voice — Stover Meets Luceno

The single most important creative decision in Storyteller V3 is the prose
voice. Everything the player experiences is filtered through it. If the voice
is wrong, nothing else matters.

The target is a specific blend of two Star Wars Legends authors who represent
complementary strengths.

**From Matthew Stover: interiority.** Stover's defining gift is that he writes
from inside his characters' bodies. You do not observe a Stover protagonist —
you inhabit them. You feel the adrenaline spike before the conscious thought
catches up. You experience decisions as they form, messy and contradictory and
real, before they become action. His prose is present-tense in spirit even
when it is past-tense in grammar. It is immediate. It is visceral. When a
Stover character is afraid, the reader's pulse changes. When a Stover character
makes a terrible decision, you understand exactly why it felt like the right
one in the moment.

This is what the GM must achieve on every turn. The player should feel what
their character feels. Not be told about it. Not observe it from outside. Feel
the heat of a bad situation closing in. Feel the specific quality of relief
when a desperate gamble pays off. Feel the sickening drop when a trusted contact
turns out to have been compromised. The prose must live inside the character's
nervous system.

**From James Luceno: worldbuilding that breathes.** Luceno's galaxy feels
inhabited in a way that few other Star Wars authors achieve. His settings are
not backdrops — they are ecosystems. A Luceno spaceport has specific customs
procedures, specific economic pressures, specific political tensions simmering
beneath the surface. His characters do not move through empty corridors between
plot points. They move through a galaxy where other things are happening
simultaneously, where systems of power have histories, where the environment
itself tells a story about who controls this place and why.

This is what gives the game its texture. When Keth lands on Nar Shaddaa, the
prose should convey not just a neon-lit vertical city but a specific economy —
who runs this landing pad, what jurisdiction it falls under, why the customs
droid is scanning for particular signatures and not others, what the Hutt
Council's current territorial arrangements mean for a Bothan with hot cargo.
The player should feel like they have arrived somewhere real, somewhere that
existed before they got here and will continue to exist after they leave.
The galaxy is not a stage set. It is a living system.

**What the blend produces:** Prose that places you inside a character who
exists inside a world. The interiority makes you care. The worldbuilding makes
the stakes feel real. When combined, they produce the specific quality that
the best Star Wars fiction achieves: the sense that your personal story is
happening against a canvas that is vastly larger than you, that the galaxy
has its own momentum, and that the choices you make ripple outward into
systems you can only partly see.

**What the voice does not default to.** It does not default to Zahn's military
precision — the prose should feel warmer and more internal than clinical
detachment. It does not default to Karpyshyn's game-paced efficiency — the
prose should linger on moments that matter, not rush through them. It does not
default to Aaron Allston's comedy of character — humor is not the baseline
register. And it is never, under any circumstances, the house style of
AI-generated fiction: no "tapestry," no "delve," no "testament to," no
"couldn't help but notice." The prose must sound like a human author with a
specific voice, not like a language model performing "literary."

**Voice modulation.** The Stover-Luceno blend is the center of gravity — it is
what the prose sounds like when you are not sure what it should sound like. But
a 45-90 minute session that holds a single register at full intensity becomes
exhausting. The voice modulates by scene type and character state.

When the character is relaxed — a cantina conversation, a quiet moment between
crises, banter with a trusted contact — the prose warms up and lets humor
breathe. This is the Allston register: character-driven warmth, dry wit, the
small human moments that earn the reader's investment before the story takes
those moments away. When the character enters tactical mode — calculating odds,
reading a room, planning an approach — the prose tightens and gets precise. This
is the Zahn register: efficient, controlled, the interiority of someone who
thinks in operational terms. When the character is in over their head — a plan
falling apart, a betrayal landing, a moment of genuine danger — the prose goes
full Stover: visceral, immediate, present-tense in spirit, the character's
nervous system on the page.

The Luceno worldbuilding layer is always present as texture but varies in
density. Exploration scenes get rich environmental detail — the political
economy of a docking bay, the specific customs procedures of a frontier
station. Combat scenes get almost none — the world compresses to the immediate
situation. Social scenes fall between, with setting details that reveal
information about the NPCs and the power dynamics in the room.

The modulation is not random. It follows the emotional and tactical arc of the
scene. A scene that begins in Allston warmth and ends in Stover intensity
tells a specific story about a situation that escalated. A scene that begins
in Zahn precision and shifts to Stover interiority tells a story about a plan
that stopped being abstract and became personal. The transitions between
registers are themselves a narrative tool.

The one absolute prohibition remains: the AI-generated house style. No
register of the prose — warm, precise, visceral, or atmospheric — should ever
sound like a language model. Every register must sound like a specific human
author writing in a specific mode.

---

## 4. The Setting — FFG Star Wars

The game launches in the Star Wars universe using all three lines of Fantasy
Flight Games' narrative TTRPG system: Edge of the Empire, Age of Rebellion,
and Force and Destiny.

These three books were published between 2013 and 2015 and represent the
most thoughtfully designed Star Wars tabletop experience ever produced.
They share a unified mechanical core while offering distinct thematic lenses:

**Edge of the Empire** places characters on the fringes of galactic civilization —
smugglers, bounty hunters, scoundrels, mechanics, and colonists trying to
survive in a galaxy controlled by the Empire and carved up by criminal
organizations. The central mechanical tension is Obligation: a debt, a
betrayal, a family, a criminal record that intrudes on your story at the
worst possible moments and demands to be paid.

**Age of Rebellion** places characters inside the conflict between the Galactic
Empire and the Alliance to Restore the Republic. Soldiers, pilots, commanders,
spies, diplomats. The central mechanical tension is Duty: a personal commitment
to the Rebellion that earns recognition and resources when fulfilled, and
weighs on your conscience when neglected.

**Force and Destiny** places characters in the position of Force sensitives
navigating a galaxy where the Jedi are extinct and the dark side has consumed
their order's successor. Seekers, consulars, guardians, mystics. The central
mechanical tension is Morality: a drift between the light and dark sides
measured through the actual choices you make under pressure, not through
abstract alignment declarations.

A character in Storyteller V3 may span all three lines simultaneously, which
is how the books always intended the system to work. A Force-sensitive smuggler
who gets drawn into the Rebellion's military conflict carries all three
motivation tracks. The story presses all three simultaneously.

### Game Lines as Lenses, Not Era Locks

The three FFG game lines provide mechanical vocabulary — Obligation, Duty, and
Morality — not era restrictions. Although each was published with Galactic
Civil War framing, the experiences they describe exist in every era of the
Star Wars timeline.

Obligation is the experience of operating under personal pressure — debts,
betrayals, criminal records, family complications. A Clone Wars-era mercenary
running supplies through Separatist blockades carries Obligation just as much
as a GCW-era smuggler. A post-Vong War freelancer rebuilding from nothing
carries it in a different form.

Duty is the experience of commitment to something larger — a cause, an
institution, a mission. A Republic officer in the Clone Wars carries Duty to
a government that may not deserve it. A Galactic Alliance intelligence
operative in the Legacy era carries Duty to a fractured state.

Morality is the experience of moral drift under pressure — the slow
accumulation of compromises. A Jedi padawan in any era carries Morality.
So does a non-Force-using soldier who has to decide what the mission is
worth.

Campaign spines specify which motivation tracks are active and how they
manifest for a given character in a given era. The first campaign (The Nar
Shaddaa Job) is Edge-flavored because Keth is a smuggler with Obligation:
Debt. A Clone Wars campaign could emphasize Duty for a Republic officer,
Obligation for a war profiteer, or Morality for a Jedi — or all three for
a character caught between institutional loyalty, personal debts, and moral
compromises. The era provides the setting context. The game lines provide the
mechanical framework. The two are orthogonal.

---

## 5. The Mechanical Heart — FFG Symbol Dice

Fantasy Flight Games created something genuinely unusual for Star Wars: a
resolution system that produces dramatic situations rather than binary outcomes.

Most tabletop systems resolve checks with a binary result. You succeed or you
fail. FFG's symbol dice produce four possible outcome states:

**Succeed with Advantage** — you got what you wanted, and something additional
went your way. Information, position, time, goodwill. Yes, and.

**Succeed with Threat** — you got what you wanted, but something went wrong or
a cost was incurred. A new problem emerged from your success. Yes, but.

**Fail with Advantage** — you didn't get what you wanted, but something useful
emerged from the attempt. An unexpected opportunity, information you couldn't
have gotten otherwise, a changed situation that opens new doors. No, but.

**Fail with Threat** — you didn't get what you wanted, and the situation is now
actively worse. The most dangerous outcome. No, and.

On top of these four quadrants sit Triumphs and Despairs: uncancellable
critical results that layer a significant positive or negative consequence onto
whatever the base outcome was. A Triumph on a failed roll means something
critically good happened even though you missed your target. A Despair on a
successful roll means something critically bad happened even though you got
what you asked for.

These four outcome states are not a game mechanic grafted onto a story.
They are a narrative grammar. They map precisely onto the improv framework
that professional storytellers use. The dice do not pause the story. The dice
write the next sentence.

This is why the FFG system was chosen above all others. D&D reduces to binary.
Pathfinder 2e has degrees of success but lacks the advantage/threat separation.
Only FFG's system produces the full four-quadrant outcome space that makes
every roll dramatically interesting regardless of whether the character succeeds.

### How the Dice Feel to the Player

The player never sees the dice. They never see the numbers. They never encounter
the word "roll" or "check" or "pool" or "difficulty" anywhere in the prose or
the choices. The mechanical layer is invisible.

What the player feels is tension.

A choice that involves a skill check reads exactly like any other choice. The
player does not know in advance which choices will trigger the dice and which
will not. What they experience is this: they make a choice, and the prose that
follows either goes their way or it does not, and the way it goes or doesn't
has a specific texture — a success that costs something, a failure that reveals
something — that they could not have predicted but that feels exactly right
for the moment.

The dice panel exists. It is hidden by default, collapsed beneath the prose
passage. A player who wants to see the mechanical resolution — the pool
composition, the symbols rolled, the net result — can expand it. Think of it
as the appendix at the back of a novel: there if you want it, invisible if
you don't. Some players will never open it. Their experience will be purely
literary. Other players will check it every turn, watching their character's
mechanical profile interact with the world. Both experiences are valid. Both
are designed for. But the default — the experience a new player has on their
first turn — is the invisible one. The story tells you what happened. The
how is behind the curtain.

This invisibility is what allows the FFG system's four-quadrant outcome
space to do its best work. When the player reads "you talked your way past
the checkpoint, but the officer's eyes lingered on your cargo manifest a
beat too long," they do not think "success with threat." They think "that
went well but something is wrong now." The dramatic experience is pure. The
mechanical precision that produced it is completely hidden.

---

## 6. The AI Game Master

The AI Game Master is the game. Everything else serves it.

The GM is not a chatbot. It does not respond to free-text conversation.
It does not answer questions about lore or rules. It does one thing:
it receives a complete briefing about the current state of the story and
produces the next passage of that story, along with the choices that define
the player's next decision.

The briefing the GM receives every turn contains everything it needs and
nothing it doesn't:

**Who the character is** — characteristics, skills, wounds and strain,
Obligation or Duty or Morality score, the character's narrative voice,
their established behavioral patterns.

**Where the story is** — which act, what the tension level is, what has
been established and what remains unresolved, what the character's central
throughline question is.

**What has happened** — recent turns in full detail, earlier turns as
compressed meaningful summaries. Not a transcript. A briefing. The GM
doesn't need to remember every word spoken. It needs to know what mattered
and what it implied.

**Who is present** — NPC state cards tracking what each character knows,
what they want, how they speak, and what their disposition toward the player
currently is.

**What the dice said** — if a check occurred, the exact result injected in
plain English: "The roll SUCCEEDED with 2 net advantages and a Triumph."
The GM's job is to make that result feel like a story. It never overrides
the dice. It never softens a failure or diminishes a triumph. The dice are
the truth of what happened in this moment.

The AI GM is powered by a cloud language model selected for prose quality
and creative intelligence. The mechanical layer — dice construction, pool
resolution, check decisions — runs on a fast local model that costs nothing
to operate. This hybrid architecture keeps costs low while ensuring the prose
the player actually reads is of genuine literary quality.

---

## 7. The Art of the Choice

If the prose is the body of the game, the choices are its skeleton. Every
passage ends with 2 to 4 options. These choices are the only way the player
acts in the world. They must bear the entire weight of player agency, character
expression, and strategic thinking simultaneously.

### The Design Principle: Character Through Tactics

The best choices in Storyteller V3 are the ones where the tactical decision
and the identity decision are the same thing. The player is not choosing
between "the smart option" and "the moral option" — they are choosing between
different ways of being effective, each of which reveals something different
about who they are.

Consider a moment where Keth needs to get past a locked door in a Nar Shaddaa
warehouse. A bad choice set looks like this:

> 1. Pick the lock (Skulduggery)
> 2. Force the door open (Athletics)
> 3. Try to talk someone into opening it (Charm)

These are generic action types wearing scene-specific clothes. They test what
the player does, not who they are. Any smuggler in any warehouse on any planet
could face these options. They reveal nothing.

A good choice set for the same moment looks like this:

> 1. Work the lock yourself — you have done this a hundred times, and patience
>    is cheaper than favors. (Skulduggery)
> 2. Signal Doss's emergency frequency one more time. If he is in there, he
>    will hear it. If someone else hears it first, that tells you something too.
> 3. Walk around the block, buy a drink at the cantina next door, and watch who
>    goes in and out. The door will still be there in an hour. (Streetwise)
> 4. Pull the fire suppression trigger on the adjacent unit. When the building
>    evacuates, walk in with the crowd.

Every option here accomplishes the same tactical goal — getting through the
door. But each one says something specific about Keth. The first says he is
self-reliant and patient. The second says he is still invested in his missing
contact even when the smart move is to walk away. The third says he is
cautious and reads situations before acting. The fourth says he is creative,
willing to cause collateral disruption, and comfortable improvising on the
fly. The player is revealing their Keth through the tactic they choose.

### Choice Design Rules

**No generic action types.** Choices never reduce to attack/defend/talk/flee.
Each choice is a specific action that only this character would consider in
this specific moment. The language of the choice reflects the character's
voice and worldview.

**Risk gradient.** Every choice set includes at least one lower-risk option
and at least one higher-risk option. The player always has a cautious path
available. They also always have a bold path that might produce a spectacular
result or a spectacular disaster. The interesting space is the middle — choices
where the risk is ambiguous, where the player cannot be sure whether they
are being cautious or reckless.

**Mechanical tagging is invisible to the player by default.** The skill that
a choice requires is tagged in the system (the local model needs it to build
the dice pool) but never appears in the choice text the player reads. The
player does not see "(Skulduggery)" after an option. They see a description
of an action and they decide whether it feels right for their character. If
they have spent ten turns establishing Keth as someone who reads people rather
than situations, they will gravitate toward the choice that reads people —
not because they calculated which skill is highest, but because it is who
their Keth is.

**Conditional availability.** Some choices are only available because of who
the character has become. A choice that requires trusting an NPC might only
appear if the player has established a pattern of trust in prior turns. A
choice that involves calling on a contact might only appear if that contact
is alive and favorably disposed. A reckless option might disappear if the
character is wounded. The choice set the player sees is curated by their own
history.

**Consequences are unpredictable.** The player should never be able to
reliably guess which choice leads to the "best" outcome. The cautious option
sometimes costs more than the bold one. The clever option sometimes outsmarts
itself. The straightforward option sometimes works perfectly because the
situation was simpler than it appeared. The unpredictability is not randomness —
it is the interaction between the player's choice, the dice result, and the
narrative context. The system does not punish or reward particular approaches.
It reveals what happens when this person makes this decision in this moment.

### Dialogue Choices

The choice design rules above apply to every kind of choice — but the
examples so far have been weighted toward action: head to the Red Sector,
duck into the cantina, pull the fire suppression trigger. Some of the most
important moments in the game are conversations, and in a conversation the
most natural choice is not something you do — it is something you say, or
how you choose to conduct the exchange.

Dialogue choices follow the same principles as action choices: no generic
types, risk gradient, character-specific, consequences unpredictable. The
difference is that the "action" is what you say or how you steer the
conversation. The dice system integrates naturally — a Deception check on a
bluff, a Cool check on maintaining composure, a Negotiation check on
finding the right leverage. The player never sees the skill tag. They feel
the uncertainty of whether their words will land.

Dialogue choices take two forms that can coexist in the same choice set:

**Direct lines.** The player reads exactly what their character would say.
Choosing it means saying it. This works when the specific words are the
interesting decision — when the line itself carries weight, risk, or
revelation.

> 1. "You sound like Vergere. She nearly destroyed you — and now you're
>    quoting her?"

That line is the choice. Saying it means invoking a specific shared history.
The player who selects it has decided that this reference is worth the
reaction it will produce.

**Conversational approaches.** The player chooses a tactic — press for
specifics, share a personal story, deflect, stay silent — and the GM
narrates how that approach plays out in the conversation. This works when
the interesting decision is the strategy, not the exact phrasing.

> 2. Press him on the specifics. What exactly does he think the Order should
>    be doing differently? Make him commit to something concrete instead of
>    philosophy.
> 3. Tell him about the settlement on Ryloth — the one the Order failed to
>    protect while they debated jurisdiction. He is not wrong. That is what
>    makes this dangerous.
> 4. Say nothing. Let the silence do the work. He is testing you, and you
>    want to see what he says when you do not give him what he expects.

Each approach reveals something different about the character: choice 2 is
analytical and confrontational; choice 3 concedes ground deliberately to
build trust; choice 4 is controlled and observational. All three are
tactical decisions and identity decisions simultaneously. The Character
Through Tactics principle holds — it simply operates through social tactics
rather than physical ones.

A conversation choice set can mix direct lines, conversational approaches,
and actions (walk away, signal someone, change the subject by doing
something physical). The variety prevents conversations from feeling like
dialogue trees and ensures that the player always has options that feel
natural to their character.

**What dialogue choices are not:** They are not Bioware dialogue wheels.
The player is not choosing a tone (polite / aggressive / sarcastic) and
watching the character deliver a pre-written line. They are choosing what
to say or how to conduct the conversation, and the outcome depends on the
dice, the NPC's state, and the accumulated context of the relationship.
The conversation is a live scene, not a branching script.

### Introspection Choices

Character Through Tactics is the primary mode — most choices are
simultaneously tactical decisions and identity decisions. But not every
moment in a story is about action. At key narrative junctures — act
boundaries, after major events, during natural downtime — the game presents
**introspection choices**: moments where the player processes what has
happened and decides what it means to them.

Introspection choices do not involve dice checks. They are purely about
internal resolution. "Do you dwell on what happened at the dock, or push it
down and focus on what comes next?" "When you close your eyes, is it the
face of the person you helped or the person you left behind?" These choices
do not change the tactical situation. They shape the character's internal
landscape — their voice notes, their throughline trajectory, their
relationship with their own decisions.

The purpose is pacing. A story that is all external pressure and tactical
decision-making becomes exhausting. The introspection moments give the
player space to breathe, to reflect, and to feel ownership over who their
character is becoming — not just what their character is doing. They also
provide the system with direct signal about the player's internal priorities,
which is harder to infer from tactical choices alone.

---

## 8. Character — Emergent, Not Constructed

Most games ask you to build your character before you play. You pick a class,
assign statistics, write a backstory, choose an alignment. You arrive at the
game with a fully formed person and then inhabit them.

Storyteller V3 inverts this — partially. You do not build a character from a
stat screen. But you are not dropped into a story with no anchor either.

### The Character Funnel — Narrowing Into Identity

A tabletop GM does not hand you a list of pre-approved characters. They ask
"who do you want to play?" and reshape the adventure around the answer. The
adventure's structure survives — but the specific scenes, NPC relationships,
entry points, and narrative hooks all flex to accommodate the player's fantasy.

Storyteller V3 replicates this through a **character funnel** — a guided
sequence of identity decisions that narrows the galaxy-wide possibility space
into a specific protagonist, one meaningful step at a time.

**Step 1 — Choose Your Timeline.** The player selects the era of their story.
The Clone Wars. The Galactic Civil War. The New Jedi Order. Each era carries
its own moral landscape, political tensions, and thematic texture. This is the
broadest stroke — the player is choosing the *kind* of galaxy they want to
inhabit.

**Step 2 — Choose Your Allegiance.** Within the selected timeline, the player
chooses a starting faction alignment. Empire, Rebellion, Criminal Underworld,
Independent, Jedi Order — the available allegiances depend on the era and the
campaign. This is where the player's fantasy takes shape. Someone who wants to
be an Imperial TIE pilot starts here. Someone who wants to be a Bothan spy
starts here. The allegiance determines which side of the story the player
enters from.

**Step 3 — Choose Your Variant.** Within the selected allegiance, the player
sees **character variants** — not stat blocks, not class descriptions, but
narrative pitches. A sentence or two that captures who this person is and what
kind of story they carry:

*"A TIE pilot at the academy who is starting to notice things that don't add
up."*
*"A Bothan intelligence operative whose last handler went dark three weeks
ago."*
*"A smuggler running from a debt that is catching up to him."*
*"A student who followed the wrong person to the wrong place and can't go
home."*

The player reads these pitches and selects the one that speaks to them. This is
a narrative choice, not a mechanical one — the player is choosing the shape of
their story, not optimizing a build. Each variant comes with a pre-authored
framework: a career, a primary motivation track, a starting situation, and a
set of prologue scenes designed to refine that specific variant.

The funnel gives the player agency at every layer. They chose the era. They
chose the faction. They chose the character. What they do not yet know is
*what kind* of that character they are. Cautious or bold? Trusting or guarded?
Principled or pragmatic? That is what the prologue discovers.

### Why a Funnel, Not a Flat List

The funnel solves two problems that a flat variant list cannot.

The first is **fantasy fulfillment.** Star Wars players arrive with specific
fantasies — an Imperial pilot, a Rebel spy, a criminal who got in too deep, a
student caught up in something bigger than themselves. A flat list of 4-6
variants per campaign cannot cover the breadth of what players want to be. The
funnel makes faction and era first-class player choices, which means the most
common fantasies — faction-specific ones — always have a path.

The second is **perceived agency.** A flat list of four pitches feels thin even
when the downstream variation is substantial. The funnel converts a single
selection into a sequence of meaningful identity decisions. Each step narrows
the space while giving the player a choice that reflects their fantasy. By the
time they reach the variant pitch, the character already feels partially
theirs — because they built the context for it.

The funnel also preserves the core design advantage of constrained selection.
Pure inference from a blank slate — where the system tries to determine career,
motivation, and personality entirely from behavioral choices — is technically
ambitious but fragile. If the inference misfires, the player feels like they
got the wrong character, and that mismatch poisons the entire experience. The
funnel narrows the possibility space through player choices before the system
does any inference at all. By the time the prologue begins, the inference
problem is tractable: the system is not determining *who you are* from scratch,
it is determining *what kind of this person* you are within a well-defined
space.

### The Campaign as Adaptive Structure

The funnel changes the relationship between character and campaign. Instead of
the campaign containing a fixed set of character variants, the campaign has a
**fixed thematic spine** and a **flexible protagonist integration layer.**

The fixed spine is the campaign's core: the setting, the era, the central
conflict, the act structure, the dramatic arc, the anchor beats. "A story
about survival and loyalty in the Nar Shaddaa underworld during the Imperial
era" is a fixed spine. It does not change based on who the protagonist is.

The protagonist integration layer is what adapts. *Why* the protagonist is on
Nar Shaddaa. *Who* is threatening them. *What* they stand to lose. *Which*
NPCs are allies and which are obstacles. An Imperial defector is on Nar Shaddaa
because they are running. A criminal is there because it is home. A student is
there because they followed someone they should not have. Same setting, same
central conflict, different entry point and different personal stakes.

This mirrors what a tabletop GM does instinctively. The adventure has a
structure — the players will discover the conspiracy, confront the antagonist,
make the hard choice. But the GM reshapes every scene around who the players
actually are. The NPCs react differently to a soldier than to a smuggler. The
entry points shift. The personal stakes change. The structure holds; the flesh
adapts.

The Campaign Studio (Section 2.5, 2.8) is responsible for authoring both
layers: the fixed spine and the integration layer that connects different
protagonist types to that spine. The Game Engine consumes the result — a
campaign spine JSON with a specific character variant already selected — and
does not need to know that the variant was produced through a funnel.

### The Psychometric Prologue — Refining the Variant

Once the player selects a character variant, the prologue begins — 3-5 scenes
experienced as the opening chapter of a novel. The player does not know they
are being measured. They are simply making choices under pressure.

Each prologue scene presents 3-4 choices. Each choice is pre-tagged by the
campaign designer (invisible to the player) with behavioral dimensions:

**Approach:** Direct (confronts problems head-on) or Indirect (maneuvers
around problems).
**Social:** Trusting (extends goodwill, builds relationships) or Guarded
(self-reliant, information-conservative).
**Risk:** Bold (accepts uncertainty for potential gain) or Cautious (minimizes
exposure, preserves options).
**Moral:** Principled (acts on values even at cost) or Pragmatic (acts on
outcomes regardless of method).

Three scenes with 3-4 choices each produce enough signal to identify the
player's behavioral cluster within the variant space. The system does not need
perfect resolution. A player who is 60% Direct / 40% Indirect gets a character
who leans direct but has moments of subtlety. That ambiguity is a feature, not
a limitation.

The prologue adapts. If three scenes produce clear signal — all four behavioral
axes show a strong majority direction — the prologue ends. If any axis remains
ambiguous, one or two additional targeted scenes appear. The maximum is five
scenes. If signal remains ambiguous after five, the system selects the best-fit
profile and begins. Characters do not need to be perfectly classified to be
well-written.

From the player's behavioral cluster, the system produces:

**A mechanical profile** — characteristics and skills mapped through a
hand-authored table, not generated by the AI. Two players who both selected the
smuggler variant but showed different behavioral patterns get different stat
distributions — one emphasizes Cunning and social skills, the other emphasizes
Agility and piloting.

**A refined motivation track** — the track type is set by the variant
(Obligation for a smuggler, Duty for a soldier), but the specific form emerges
from the prologue. A trusting, principled smuggler might carry Obligation:
Family. A guarded, pragmatic smuggler might carry Obligation: Criminal Record.

**A throughline question** — inferred by the cloud model from the full set of
prologue choices. Not declared by the player. Discovered. The question emerges
from how the player navigated the prologue's pressures and what their choices
implied about what they care about.

**A narrative voice** — 2-3 sentences of voice notes that calibrate every
passage of prose that follows. Inferred from the texture of the player's
choices and the variant's authored baseline.

What the player experiences is the opening pages of a novel. The character
who emerges at the end feels like someone they recognize — not because they
designed that person on a spreadsheet, but because they chose a story that
interested them and then discovered the specific person living inside it.

---

## 9. Force Sensitivity and Career Diversity

One of the most important design decisions in Storyteller V3 is the treatment
of Force users.

Star Wars games consistently make the same mistake: Force users become the
default. Every system, every adaptation, every fan project tilts toward Jedi
as the most interesting and capable option. The result is Jedi inflation.
The Force loses its mythic quality. Non-Force-using careers feel like lesser
versions of the real game.

This is wrong for Star Wars as a setting and wrong for the game we are building.

Consider what makes Han Solo compelling. He never touches the Force. His
heroism costs him something real because he has no supernatural safety net.
Every clever solution he finds is specific to him — his skills, his improvisation,
his willingness to be in a terrible position with no fallback. That specificity
is what makes his moments feel earned.

Our game treats Force sensitivity as a **player choice, surfaced through the
character funnel.** The allegiance step may include a Force-aligned option
(Jedi Order, Force Tradition) when the era supports it, and Force-sensitive
variants appear within those allegiances. A player who wants to play a Jedi
selects a Force-aligned allegiance and then a Force-sensitive variant. A player
who wants to play a smuggler selects a Criminal or Independent allegiance and
a variant without Force powers. Neither path is presented as the default or
the superior option. The player's funnel choices make their intent explicit
before the system does any work.

This respects the player's agency. If someone sits down wanting to explore a
Jedi's story, telling them "your choices didn't indicate Force sensitivity"
is not a page-turner moment — it is a reason to stop playing. Equally, a
player who chose a smuggler should never feel like they are playing the lesser
version of the game.

The rarity principle applies at the **campaign design level**, not the character
selection level. Not every campaign needs a Force-sensitive allegiance path.
Campaign spines designed for non-Force characters should be equally compelling —
equally rich in moral complexity, equally demanding in their choices, equally
capable of producing a story the player feels ownership over. Force sensitivity
is one kind of story, not the best kind. The Campaign Studio's job is to ensure
that career diversity is a genuine design priority, not a concession.

Every career is designed to feel like the protagonist of its own story.

The Smuggler's campaign is about the gap between who you have to be to survive
and who you might become if survival stopped being the only priority.

The Bounty Hunter's campaign is about the contracts you take and the person
those contracts are making you, and the job you'll eventually refuse regardless
of the credits.

The Soldier's campaign is about what a war asks of the people who fight it
and whether what you sacrifice to win was worth the victory.

The Politico's campaign is about power — how to get it, what it costs, and
what you do with it when you have it.

The Medic's campaign is about triage in every sense of the word. Who gets saved.
What it costs to keep saving people when the war doesn't end.

None of these require Force powers. Some of them are better without them.

---

## 10. Motivation Mechanics — Obligation, Duty, and Morality

The three motivation tracks are not passive flavor. They are engines that
generate narrative pressure. Each one intrudes on the story in different ways
and demands different things from the player.

### How Motivation Tracks Are Assigned

The primary motivation track is set by the character variant the player
selects at the end of the funnel. A smuggler variant carries Obligation. A
soldier variant carries Duty. A Force-sensitive variant carries Morality. The
player knows this from the variant's narrative pitch — "a smuggler running from
a debt" clearly signals Obligation, even though the mechanical label is never
shown. The allegiance step in the funnel also provides signal — an Empire-
aligned variant is more likely to carry Duty, while a Criminal-aligned variant
is more likely to carry Obligation — but the specific track is set by the
variant, not the allegiance.

The specific **type** of the motivation track — whether Obligation is Debt,
Betrayal, Family, or Criminal Record — is refined by the prologue. A
trusting, relationship-oriented smuggler might emerge with Obligation: Family.
A guarded, self-reliant smuggler might emerge with Obligation: Criminal Record.
The player chose the broad strokes; the prologue filled in the specifics
based on who the player actually is under pressure.

Characters can carry secondary motivation tracks when narratively appropriate.
A Force-sensitive smuggler drawn into the Rebellion's cause carries Morality
as primary but can accumulate Obligation and Duty as the campaign presses new
commitments onto them. The campaign spine specifies when secondary tracks
activate and what triggers their introduction into the story.

### Obligation (Edge of the Empire)

Obligation is a weight. It has a numerical value and a type — Debt, Betrayal,
Criminal Record, Family, Addiction, Oath. At the start of each chapter, the
system makes a hidden roll against the party's total Obligation. If the roll
falls within Keth's personal range, his Obligation activates for that chapter.

When Obligation activates, it does not announce itself with a notification or
a game mechanic. The story simply tightens. Vossk's people appear in the
background of a scene. A customs officer mentions a name Keth was hoping
nobody here knew. A contact asks, casually, whether Keth is still running
jobs for the Hutts — and the question is not casual at all. The player feels
the pressure before they understand its source. The Obligation makes itself
known through the world closing in.

Mechanically, activated Obligation reduces the character's strain threshold
for the chapter. The player is operating at diminished capacity — more
vulnerable to panic, exhaustion, poor decisions under pressure. This manifests
in the prose as a subtle shift in tone. The character's interiority becomes
more strained. Thoughts come faster. The usual dry humor has an edge to it.
The player may not consciously register why the character feels more
pressured this chapter, but the writing conveys it.

Obligation decreases when the player takes actions that address it directly.
Paying down the debt. Confronting the betrayal. Dealing with the family
complication. These are never presented as "pay off your Obligation" menu
items. They emerge as choices within the story that happen to address the
underlying pressure — and they always cost something else.

### Duty (Age of Rebellion)

Duty is a pull. Where Obligation pushes by making the personal situation
worse, Duty pulls by offering something the character cares about — but at a
price. A character with Combat Victory duty feels the pull when a battle
presents itself. A character with Intelligence duty feels it when information
is available but obtaining it means risk. A character with Personnel duty
feels it when subordinates need protection at the expense of the mission
objective.

When Duty activates (same hidden roll mechanism), the story presents an
opportunity aligned with the character's Duty type. The opportunity is real —
acting on it genuinely advances the character's standing within the Rebellion
and earns mechanical benefits. But it always competes with something else.
The intelligence is available, but pursuing it means abandoning the smuggler
who helped you get this far. The battle can be won, but only by sacrificing
a position you spent three chapters securing.

Duty increases when fulfilled and the story acknowledges it — a superior
contacts the character with recognition, resources become available, the
character's reputation within the Alliance shifts. This is not a reward screen.
It is a scene. A brief encrypted message from Rebel Command. A whispered
conversation in a safehouse. The acknowledgment is woven into the narrative,
and it carries weight because the player earned it through a genuine sacrifice.

### Morality (Force and Destiny)

Morality is a drift. It is the most subtle and the most dangerous of the
three tracks. It does not activate in chapters the way Obligation and Duty
do. It accumulates.

Every significant choice the player makes under pressure is tagged with a
Conflict value. The tagging is invisible to the player. They do not see
"+2 Conflict" after a choice. They simply make the choice. But the choice
was noted: using the Force aggressively when a passive solution existed.
Lying to protect yourself when the truth would have protected someone else.
Choosing efficiency over compassion. Choosing power over patience.

At the end of each chapter, the system resolves Morality: Conflict earned
minus a die roll. If the player accumulated more Conflict than they rolled,
their Morality drops. If they accumulated less, it rises. The drift is slow
but relentless. A character who consistently makes pragmatic, self-serving
decisions under pressure will drift dark. A character who consistently
chooses the harder path that protects others will drift light. A character
who does both — the most interesting case — will oscillate.

The story reflects the drift. A light-side-drifting Force user begins to
notice things — moments of calm in chaos, an instinct that arrives before
the rational thought, a sense of connection to living things that defies
explanation. A dark-side-drifting Force user begins to notice different
things — how easy anger makes everything, how much faster the Force responds
when you stop asking and start demanding, how convenient it is that the
person who stood in your way had an accident.

Neither direction is presented as good or bad by the narrator. The prose
simply shows what is happening to this person. The player decides whether
they are comfortable with it.

---

## 11. The NPC System — People, Not Props

NPCs in Storyteller V3 are not quest dispensers. They are not dialogue trees.
They are people with their own knowledge, their own agendas, and their own
memory of what the player has done.

### State Cards

Every NPC the player interacts with has a persistent state card that tracks:

**What they know.** Specifically: what they know about the player character,
what they know about the current situation, and what they know that the player
does not. Knowledge updates after every interaction. If Keth lies to an NPC
and the lie succeeds, the NPC's state card records the false belief. If the
lie later unravels — through events, through other NPCs, through the player's
own actions — the NPC's state card updates to reflect the betrayal, and their
disposition shifts accordingly.

**What they don't know.** Equally important. An NPC who does not know about
the cargo in Keth's hold behaves differently from one who does. The GM
receives both sides — what the NPC knows and what they are ignorant of — so
it can write interactions where the information asymmetry creates dramatic
tension. The player knows something the NPC doesn't, or the NPC knows
something the player doesn't, and the scene derives its energy from the gap.

**What they want.** Every significant NPC has a motivation that exists
independently of the player. Vossk wants his investment returned with
interest. Doss wants to survive a situation that has become more dangerous
than he anticipated. The mysterious voice on the comm wants something the
player does not yet understand. These motivations drive NPC behavior regardless
of the player's choices. NPCs act in their own interest. Sometimes those
interests align with the player's. Sometimes they do not. Often they align
in some ways and conflict in others, which is where the most interesting
scenes emerge.

**How they speak.** Voice notes that capture the NPC's speech patterns,
vocabulary level, emotional register, and habitual expressions. Vossk's
intermediaries speak with formal indirection — they never threaten, they
observe possibilities. Doss speaks in half-sentences and nervous deflections.
An Imperial officer speaks in bureaucratic precision designed to make cruelty
sound administrative. The GM uses these voice notes to make every NPC sound
like a specific person rather than a generic dialogue function.

**Their disposition toward the player.** A single axis from hostile to
loyal, updated by every interaction. Disposition is not binary like or
dislike. It is a continuous measure that shifts in response to the player's
behavior. An NPC can be simultaneously impressed by the player's competence
and angry about a prior betrayal. Disposition influences what choices are
available — a hostile NPC does not offer the same options as a neutral one,
and a loyal NPC might offer options no one else would.

### NPC Memory

NPCs remember. Not everything — they have human-scale recall, not omniscient
databases. But they remember what mattered. If Keth promised Doss something
in Act 1 and broke that promise in Act 2, Doss remembers the broken promise
in Act 3. If Keth was generous to a dockworker in a scene that seemed trivial,
that dockworker remembers the generosity if they reappear later. The
persistence layer stores these memories. The context package delivers them
to the GM. The prose reflects them.

This creates a world where actions have social consequences. Not just plot
consequences — those are handled by the story structure. Social consequences:
the way people treat you changes based on what you have actually done, and
that change is specific and earned and remembered.

### Where the NPC System Grows

The state card foundation — knowledge, disposition, motivation, voice, memory —
is the V1 system. Beyond V1, the NPC system deepens in four directions:

**Relationship triangles.** NPCs should have dispositions toward each other,
not just toward the player. Vossk's intermediary and Doss might have their own
history — a grudge, a debt, a shared past — that affects how they behave when
the player is navigating between them. NPC-NPC relationships create social
dynamics the player must read and navigate, producing richer scenes than a hub
model where every NPC relates only to the protagonist.

**Emotional state.** Disposition is a long-term relationship axis. But NPCs
also have in-the-moment emotional states that affect behavior within a scene.
An NPC with high disposition toward the player can still be angry, frightened,
distracted, or grieving right now. A transient emotional state — set by recent
events, decaying over turns — gives the GM more to work with than disposition
alone and prevents NPCs from feeling emotionally flat across interactions.

**Behavioral envelopes.** Hard constraints on what an NPC would never do,
regardless of circumstances. Vossk would never appear in person. Doss would
never betray someone face-to-face. An Imperial officer would never break
protocol in front of subordinates. These constraints prevent the LLM from
generating out-of-character NPC behavior under narrative pressure, preserving
the consistency that makes NPCs feel like real people rather than plot
functions.

**Information propagation.** Information should travel between NPCs offscreen.
If the player does something notable in front of one NPC, another NPC who
knows the first might learn about it by their next appearance — not through
omniscient awareness, but through the social networks that exist in the world.
This connects to the reputation echo system and makes the world feel like a
place where actions have reach beyond the scene where they occurred.

---

## 12. Story Structure — The Authored Spine

Pure generative narrative — letting the AI produce everything dynamically from
nothing — produces interesting moments that don't connect to anything. The model
drifts. It contradicts what was established. The story feels like twenty loosely
related short stories rather than one coherent arc.

We solve this with a structure borrowed from professional TTRPG module design:
the authored spine.

Every campaign has a skeleton of 4-5 scene anchors — specific narrative beats
that will occur regardless of player choice. What changes is everything between
those anchors: how the player arrives at each one, in what condition, with
what allies and enemies, having made what sacrifices. The anchors provide
coherence. The generative space between them provides genuine agency.

This is how skilled human Game Masters actually run tabletop sessions. They
prepare a skeleton and improvise the flesh around player actions, but they have
anchor points that keep the story from collapsing. The AI GM operates on the
same principle.

The authored spine for our vertical slice — The Nar Shaddaa Job — looks like this:

**Act 1 — The Approach:** Keth Varso arrives above Nar Shaddaa with hot cargo
and a contact who has gone dark. An unknown voice warns him off the original
drop coordinates. The act ends when the nature of his contact's disappearance
is discovered.

**Act 2 — The Complication:** What is actually in the cargo becomes clear.
The Obligation triggers — Vossk's people arrive with their own agenda. The
player must choose between competing interests for the first time.

**Act 3 — The Squeeze:** Keth is caught between at least two factions who
both want the cargo. The choices made in Acts 1 and 2 determine which options
are available. Some doors are closed. Others opened unexpectedly.

**Act 4 — The Resolution:** The payoff of everything that came before. The
dice and the choices determine not just what happens but who Keth is at the
end of it. The throughline question receives its answer — not necessarily the
one the player expected.

### Spine Shapes Beyond Linear

The Nar Shaddaa Job uses a linear spine: Act 1 → Act 2 → Act 3 → Act 4,
with anchors in sequence. This is the right V1 structure — simplest to author,
simplest to validate, cleanest to test.

But linear is not the only shape the spine can take. Future campaigns can use
alternative structures that the engine supports without architectural changes:

**Hub-and-spoke** — a central location (a space station, a city, a ship) with
multiple available story threads the player can pursue in any order, converging
on a final act. This gives the player more agency over pacing and sequencing.
The authored anchors still exist, but their order is partially player-determined.

**Parallel tracks** — two simultaneous story threads that the player switches
between. The cargo problem AND the missing contact problem, rather than one
leading to the other. This creates natural tension through competing demands
on the player's time and resources, and the moment the tracks converge
becomes a powerful anchor beat.

These are campaign authoring concerns, not engine concerns. The engine
processes turns based on the current arc state and the campaign spine data.
Whether the spine is linear, hub-and-spoke, or parallel-tracked changes what
the Campaign Studio produces, not how the Game Engine consumes it.

---

## 13. Pacing and Chapter Structure

### The Unit of Play: The Chapter

Storyteller V3 is designed around chapter-length play sessions of 45 to 90
minutes. Each act of a campaign functions as a chapter — a self-contained
narrative unit with its own internal arc that begins at a specific point,
builds through a series of turns, and ends at a natural resting point that
is also, deliberately, a point of maximum narrative tension.

This is the novel-chapter structure. A chapter in a well-paced novel does not
end at a resolution. It ends at a question. It ends when the character has
just learned something that changes everything. It ends when the door has
just opened onto something the character was not expecting. It ends at the
moment that makes you turn the page even though you told yourself you would
stop at the end of the chapter.

Each act is structured to produce this effect:

**The hook** — the opening turn of the act establishes the immediate situation,
the available information, and the first choice. It does this quickly. The
player should be making a decision within 60 seconds of starting a new chapter.

**The rising middle** — the majority of turns occur here. Each turn raises
the stakes, reveals new information, complicates the situation, or forces a
choice that narrows future options. The pace accelerates. Early turns in the
middle can be exploratory — gathering information, talking to NPCs, assessing
the situation. Later turns in the middle compress: time pressure increases,
competing demands multiply, and the player begins to feel that they cannot
address everything.

**The turn** — a single moment near the end of the act where the situation
changes fundamentally. A revelation. A betrayal. An arrival. A consequence.
This is the anchor beat — the authored spine ensures it happens. How it
happens, what it means, and how it feels are shaped by everything the player
did to get here.

**The cliffhanger** — the final turn of the act presents the new reality
and ends. It does not resolve. It opens. The player is left with a question
that demands an answer, and the only way to answer it is to start the next
chapter.

### The Page-Turner Pull

The pacing within each chapter is designed to produce the specific sensation
of being unable to stop reading. This is not accidental — it is an engineered
quality of the prose, the choice structure, and the information flow.

The primary mechanism is **incomplete information cascading forward.** Every
turn answers something and asks something new. The player never reaches a
point where all questions are resolved. There is always one more thread to
pull, one more unknown to resolve, one more consequence to discover. The
threads multiply faster than they resolve. By the midpoint of an act, the
player is juggling three or four open questions simultaneously, and each
turn either answers one (creating satisfaction) or reveals that two of them
are connected in a way the player did not anticipate (creating the "just one
more turn" compulsion).

The secondary mechanism is **escalating consequence density.** Early turns
in a chapter are relatively low-stakes — the player is gathering information,
establishing position, making preliminary moves. As the chapter progresses,
each choice carries more weight because it interacts with more established
context. By the final third of a chapter, every choice feels significant
because the player can see the web of consequences that preceded it and can
sense that the web is about to resolve into something irreversible.

### Turn Length and Rhythm

Individual turns vary in passage length between 250 and 600 words. This is
not arbitrary — it is calibrated to the reading rhythm.

Quiet turns — exploration, conversation, observation — tend toward the longer
end. The prose takes its time. The worldbuilding breathes. The character
notices details. These passages establish texture and earn the player's
investment in the setting.

High-tension turns — confrontations, chase sequences, moments of crisis —
tend toward the shorter end. Sentences shorten. Paragraphs compress. The
prose accelerates to match the pace of the situation. A 280-word passage
during a desperate escape through Nar Shaddaa's maintenance corridors should
feel faster to read than a 500-word passage in a cantina, even though the
reading speed is the same. The density of action per sentence creates the
perception of pace.

---

## 14. The Reading Experience

### The Screen

The player's screen is a reading surface. It is not a dashboard. It is not a
HUD. It is a page.

The design philosophy is atmospheric but functional: the interface should
carry a subtle sense of the Star Wars universe without ever becoming
cosplay. It is not a datapad prop. It is not a holographic display. It is
a beautifully designed reading environment that happens to feel like it
belongs in the same galaxy as the story it delivers.

Dark background, warm light text. Maximum prose width of 650 pixels — wide
enough to feel like a page, narrow enough that the eye does not lose its
place crossing a line. Typography that is readable for extended sessions.
Generous line height. Comfortable margins. The prose should feel spacious
on the screen, not cramped.

Nothing on the screen competes with the text for attention. No avatars. No
maps. No character sheets in V1. No animated backgrounds. No particle
effects. No sound. The text is the world. Everything else is subordinate.

The choices appear below the passage as full-width buttons. They are large
enough to be comfortable touch targets on mobile (minimum 44 pixels). They
are styled to feel like part of the reading experience — not game UI buttons,
but continuation points of the narrative. Each choice reads as a sentence,
not a label.

### Atmospheric Details

The subtle Star Wars flavor comes from small, consistent design choices rather
than overt theming:

The color palette draws from the specific visual language of the Outer Rim —
not the clean whites and blues of the Republic, but the amber, rust, and
deep charcoal of frontier stations and smuggler haunts. The aesthetic is
closer to the interior of the Millennium Falcon than the bridge of a Star
Destroyer.

Transitions between passages are unhurried. When a new passage appears, it
does not pop in — it materializes, word by word if streaming is enabled, as
if being written in real time. The player watches the story arrive. This
pacing transforms the 5-10 second latency of the cloud model from a
technical limitation into an atmospheric feature — the story is not loading,
it is being told.

The dice panel, when expanded, uses the visual language of the FFG system:
green for ability dice, yellow for proficiency, purple for difficulty, red
for challenge. These colors carry meaning for players who know the system.
For players who do not, they are simply part of the aesthetic. The panel
feels like a hidden mechanism glimpsed behind the narrative curtain —
interesting to examine, never required.

---

## 15. Memory and Continuity

A game that forgets what happened is not a game. It is a series of disconnected
prompts wearing a story's clothes.

Every turn in Storyteller V3 writes to a persistent database. Every meaningful
choice is tagged with what it implied about the character. Every NPC interaction
updates the NPC's state card — what they now know, how their disposition has
shifted, what they remember about you.

The AI GM receives a carefully assembled context package every turn rather than
raw conversation history. This package contains the story so far in compressed
form: recent turns at full detail, earlier turns as meaningful summaries focused
on consequences rather than events. The GM doesn't need to remember that in
turn 7 Keth described the weather on Nar Shaddaa. It needs to know that in turn
7 Keth chose to trust a Rebel Intelligence contact despite every professional
instinct saying not to, and that this choice implied something specific about
who he is.

Those meaningful implications accumulate. By turn 20 the GM is writing prose
about a character it knows — not from a character sheet, but from twenty
decisions made under pressure. The prose feels like it has been paying
attention to you specifically. Because it has.

---

## 16. A Worked Example — One Complete Turn

The following is a complete worked example of a single turn in The Nar Shaddaa
Job. It shows the prose passage the player reads, the choices they receive,
the hidden mechanical layer, and what the system infers about the character
based on their decision. This is what the game actually feels like.

### Context

This is Turn 4 of Act 1. Keth has landed on Nar Shaddaa at alternate
coordinates provided by the mysterious comm voice. He has spent the previous
three turns navigating the landing process — bluffing past a customs scan
(Deception check: success with threat — the scan passed but the officer
remembered his face), finding a docking berth in a bay controlled by a
mid-level Hutt intermediary named Tosk, and picking up a rumor from a
dockworker that Doss was seen in the company of humans who "looked like
they were not from around here." Keth is now heading to Doss's last known
location — a data broker's shop in the Red Sector.

The player chose on the previous turn to go to the data broker's shop
directly rather than contacting Vossk's local representative first. This
was tagged as a meaningful choice: "Prioritized finding Doss over managing
Obligation. Pattern: loyalty to individuals over institutional pressures."

### The Dice Check

The player's previous choice — "Head to the Red Sector on foot, keeping to
the mid-levels where the crowds are thickest" — triggered a Streetwise check.
The local model decided: Average difficulty, 1 setback die for unfamiliar
district.

Pool: 1 Proficiency (yellow) + 3 Ability (green) vs 2 Difficulty (purple)
+ 1 Setback (black).

Result: **2 net successes, 1 net threat.** Outcome quadrant:
**success_threat.** Yes, but.

### What the Player Reads

> The Red Sector earns its name from the light. Every surface here reflects
> some shade of it — the landing indicators on cargo lifts that never stop
> running, the advertisement holos cycling through products you cannot buy
> legally on any Core world, the bioluminescent mold that colonizes the
> duracrete where the environmental scrubbers gave up decades ago.
>
> You know how to walk in a place like this. Shoulders level, pace unhurried,
> eyes moving without your head following. A Bothan who looks lost in the Red
> Sector has a life expectancy measured in city blocks. A Bothan who looks
> like he has been here before — that is just another body in the current.
>
> The data broker's shop is where the dockworker said it would be: wedged
> between a droid repair stall and a cantina whose music bleeds through the
> walls in bass frequencies you feel in your teeth. The sign above the door
> reads VERIFIED INQUIRIES in Aurebesh, which is the most optimistic use of
> the word "verified" you have encountered on this moon.
>
> You find the shop. That is the good news.
>
> The bad news is the door. It is open. Not unlocked — open. The magnetic
> seal has been physically overridden, the housing pried apart with something
> that left carbon scoring along the frame. This was not a break-in by
> someone who cared about being subtle. Inside, the lights are still on. The
> terminal screens are cycling through standard screensavers. Whoever did
> this did not bother to shut anything down.
>
> There is no sound from inside. The cantina bass fills the silence where a
> data broker's voice should be.

> ---CHOICES---
>
> 1. Step inside and assess the damage. Whatever happened here, it happened
>    recently — the carbon scoring is still warm. If there is something to
>    find, it will not be here long.
> 2. Do not go in. Take up a position across the street where you can see
>    the door, and wait. Whoever did this may still be close, and you would
>    rather see them before they see you.
> 3. Reach for your comm and send a burst-encrypted message to Doss's
>    personal frequency. If he is alive and anywhere within range, he will
>    hear the three-tone signal you agreed on years ago.
> 4. Duck into the cantina next door. The bartender has been watching this
>    street all day. Buy a drink and find out what they saw.

### What the System Sees

The dice result — success with threat — produced a passage where Keth
successfully navigated the Red Sector and found the shop (success), but
the situation he found is worse than expected (threat). The open door with
carbon scoring is the threat manifesting. He got where he wanted to go,
but what he found there has raised the stakes.

### What the System Infers from the Player's Choice

If the player selects **Choice 1** (go inside): The system tags this as
risk-tolerant, information-seeking, action-oriented. Pattern contribution:
"Moves toward danger when information is at stake."

If the player selects **Choice 2** (observe from outside): The system tags
this as cautious, tactically patient, self-preserving. Pattern contribution:
"Prioritizes situational awareness over speed."

If the player selects **Choice 3** (contact Doss): The system tags this as
loyalty-driven, relationship-prioritizing, potentially impulsive. Pattern
contribution: "Reaches for personal connections under pressure, even when
it risks revealing position."

If the player selects **Choice 4** (cantina bartender): The system tags this
as socially oriented, information-gathering through people rather than
environments, comfortable in social spaces. Pattern contribution: "Reads
people before reading rooms."

No choice is correct. No choice is optimal. Each one leads to a different
version of the next scene, a different dice check (or no dice check), and
a different accumulation of information about who Keth is becoming.

---

## 17. The Long Vision — Era Campaigns

What we are building in the vertical slice is the foundation for something
much larger. The following is not planned for the first version. All of it
is designed for. The architecture supports it. The narrative principles
extend to it. The mechanical foundation carries it.

The character funnel (Section 8) makes era selection a first-class player
choice — the very first step in constructing their identity. The eras below
are not just setting backdrops for campaign authors. They are the entry point
for players who arrive with a specific period of the galaxy in mind.

### Complete Career Arcs

A character who begins as a small-time smuggler on the fringes of the Outer
Rim and over dozens of sessions pays off their Obligation, earns a reputation,
gets drawn into something larger than themselves, and arrives somewhere
unrecognizable from where they started. The mechanical progression — XP, new
specializations, rising characteristics — maps onto a narrative arc. The
numbers go up because the story demands it, not the other way around.

### Character Continuity Across Real Time

The game should remember who Keth was. Not just mechanically. The throughline
question he was answering five years ago should still be visible in the choices
he makes today, if you return to him. The story should age with its player.

### Era Spanning

The game is designed to support play across the full Star Wars Legends
timeline. Each era provides a setting context — the political situation, the
faction landscape, the active threats, the available technology, the specific
moral pressures of the moment. What each era does **not** provide is a genre
lock.

Any era can support multiple genres of story. The Clone Wars is not only
political thrillers. The New Jedi Order is not only survival horror. Legacy
of the Force is not only stories about betrayal. Each era has a dominant
thematic texture — the thing that makes it feel different from other eras —
but within that texture, smuggler stories, military stories, spy stories,
mystery stories, and adventure stories all exist. The era determines the
backdrop. The campaign spine determines the genre.

What follows are concrete examples of era-specific campaigns — not finished
designs, but demonstrations of how the architecture adapts to fundamentally
different kinds of Star Wars stories. Each era includes its primary example
plus alternative story shapes to demonstrate genre flexibility.

---

### 17.1 Clone Wars / Republic Era

**The Moral Landscape:** The Republic is dying from the inside out, and almost
nobody can see it. The Jedi serve a government that is already compromised.
The clone army is an ethical catastrophe that no one has time to examine. The
Separatists have legitimate grievances wrapped in illegitimate methods. Nothing
is clean. The player operates in a galaxy where every institution they might
trust has already begun to rot.

**What Makes It Different:** This era inverts the Rebellion-era dynamic. In
the Galactic Civil War, the moral lines are relatively clear — the Empire is
oppressive, the Rebellion is justified. In the Clone Wars, the moral lines
are deliberately blurred. A soldier following Republic orders may be
committing atrocities. A Jedi following the Council's directives may be
enabling authoritarianism. A Separatist sympathizer may be the most ethical
person in the room. The story presses the player to question institutions
rather than individuals.

**Campaign Spine Example — "The Ryloth Corridor":**

A Republic military advisor — career: Commander or Diplomat — is assigned to
coordinate the defense of a Twi'lek settlement corridor that both the Republic
and the Separatists need for strategic logistics reasons. The Republic claims
to be protecting the Twi'leks. The Separatists claim to be liberating them.
Neither claim survives contact with the ground truth.

Act 1 — Arrival. The player discovers the Republic garrison has been
requisitioning Twi'lek supplies without compensation under emergency war
powers. The clone troopers are following orders. The orders are wrong.

Act 2 — The Separatist Offer. A Separatist envoy makes contact through
back channels. Their offer is genuine: they will leave the corridor neutral
if the Republic does the same. The catch is that accepting means betraying
the Republic's strategic plan, and the envoy is not authorized to guarantee
that the Separatist fleet will honor the agreement.

Act 3 — The Squeeze. The Republic learns about the contact. The player is
suspected of treason. The Twi'lek settlement leaders are caught in the
middle and want the player to guarantee their safety — a guarantee the player
cannot make regardless of which side they choose.

Act 4 — The Choice. The player must decide what this corridor is worth and
to whom, and their decision will cost something real regardless of the
direction.

**Throughline Question:** "What do you owe the people who trust you when the
institution you serve does not deserve that trust?"

**Motivation Track Emphasis:** Duty is central. The question of what Duty
means when the cause may not be just is the beating heart of Clone Wars
narratives.

**Other stories in this era:** A smuggler running weapons through Separatist
blockades (Obligation-driven, action-adventure). A Jedi padawan sent on a
solo mission who discovers their master's orders were fabricated (mystery,
Morality-driven). A bounty hunter working both sides of the war who discovers
the war itself is manufactured (thriller, Obligation-driven). A clone trooper
struggling with emerging individuality while following orders that feel wrong
(military drama, Duty and Morality intertwined).

---

### 17.2 New Jedi Order Era (Yuuzhan Vong War)

**The Moral Landscape:** The galaxy is being invaded by an extragalactic
species that exists outside the Force, that uses biotechnology instead of
machines, and that worships pain as a sacrament. The Yuuzhan Vong are not
evil in the way the Empire is evil — they are alien in a way that nothing
in the Star Wars galaxy has ever been. The Force does not detect them. The
Jedi cannot sense them. Everything the galaxy relied on for four thousand
years no longer works.

**What Makes It Different:** This era is about loss on a civilizational
scale. Entire worlds fall. The New Republic government collapses under the
weight of refugee crises and military defeats. The Jedi Order is fractured
over whether to fight, to retreat, or to seek understanding. Characters
who defined themselves by their competence — their skills, their
connections, their place in the galactic order — discover that all of it
can be taken. The story asks what remains when everything external is
stripped away.

**Campaign Spine Example — "The Refugee Run":**

A smuggler or freighter captain — career: Smuggler or Explorer — runs
evacuations from worlds in the invasion corridor. Not military operations.
Not combat missions. Evacuations: getting civilians off planets before the
Yuuzhan Vong worldshaping begins.

Act 1 — The First Run. The player evacuates a settlement on a Mid Rim
world. The process is orderly. The ship has capacity. Everyone who needs
to leave can leave. This act exists to establish what normal looks like
before the story takes it away.

Act 2 — Triage. The next evacuation has twice the civilians and half the
time. The player must decide who boards and who does not. The choice is not
abstract — the NPCs the player interacts with have names, have children,
have reasons they cannot wait for the next ship. There is no next ship.

Act 3 — The Offer. A Yuuzhan Vong collaborator — a human who has accepted
the invaders' terms — offers the player a deal: safe passage through the
occupied corridor in exchange for delivering a specific passenger to
Yuuzhan Vong custody. The passenger is a Jedi in hiding. The deal is
genuine. The passage is safe. The cost is one life.

Act 4 — The Run. Whatever the player decided in Act 3, the final act is the
last evacuation. The Yuuzhan Vong are performing worldshaping — transforming
the planet's biosphere into something alien. The player has limited time,
limited capacity, and the accumulated weight of every choice made in the
prior three acts pressing down on what kind of person they are when the
galaxy is ending.

**Throughline Question:** "When there is not enough room for everyone, how
do you decide who matters?"

**Motivation Track Emphasis:** Obligation transforms here. The debt is not
financial — it is moral. The player owes something to every person they
could not save, and that weight accumulates.

**Other stories in this era:** A Jedi Knight on the front lines struggling
with whether to fight the Vong or seek understanding (Morality-driven, war
drama). A New Republic intelligence operative tracking Yuuzhan Vong
infiltrators on Coruscant (spy thriller, Duty-driven). An arms dealer
profiting from the chaos who starts to see the human cost (Obligation-driven,
moral reckoning). A xenobiologist studying captured Vong biotechnology who
discovers something that could change the war — if it does not change her
first (science thriller, Morality-driven).

---

### 17.3 Legacy of the Force Era

**The Moral Landscape:** The galaxy that rebuilt after the Yuuzhan Vong war
is tearing itself apart from the inside. Jacen Solo — the hero who helped
end the invasion — is becoming a Sith Lord, and the tragedy is that he
believes he is saving the galaxy. Corellia wants independence. The Galactic
Alliance wants control. Luke Skywalker's Jedi Order is caught between a
government sliding toward authoritarianism and a former student sliding
toward the dark side. Everyone has a reason. No one is entirely wrong.
That is what makes it devastating.

**What Makes It Different:** This era is about the people you trust becoming
the people you fight. The enemy is not alien. The enemy is family. The
political conflicts are between people who share a history, a language, a
culture, and a genuine disagreement about what the galaxy should become. It
is a civil war in every sense — including the personal one.

**Campaign Spine Example — "Divided Loyalty":**

A Galactic Alliance Intelligence officer — career: Spy — is tasked with
infiltrating the Corellian independence movement to assess whether they
pose a genuine military threat or a political one.

Act 1 — The Assignment. Standard intelligence work. The player establishes
a cover identity and begins building contacts within the Corellian
expatriate community on a neutral world. The Corellians are passionate,
articulate, and not wrong about the Alliance's overreach. The player begins
to understand their position.

Act 2 — The Source. A Corellian contact offers to provide military
intelligence about Alliance fleet positions — information the Corellians
would use to defend their system, but that would also cost Alliance lives
if a battle occurs. The contact trusts the player. The trust is earned.
Betraying it accomplishes the mission. Honoring it compromises it.

Act 3 — The Order. GAG (Galactic Alliance Guard, Jacen Solo's secret
police) contacts the player with a new directive: identify Force-sensitive
individuals within the Corellian community for "protective custody." The
player understands what protective custody means. The order comes from the
top. Refusing it is treason.

Act 4 — The Break. The player must decide where they stand. Not
theoretically. Specifically: which person do they protect, which person do
they betray, and what does that make them?

**Throughline Question:** "When every side is partially right and every
loyalty costs you another loyalty, who do you actually serve?"

**Motivation Track Emphasis:** Morality is central even for non-Force users.
The moral drift here is not about the Force — it is about what you are
willing to do for a cause you are no longer sure is just.

**Other stories in this era:** A smuggler caught between Corellian
independence fighters and Galactic Alliance blockade enforcement, with
contacts on both sides (action-adventure, Obligation-driven). A Jedi Knight
who trained alongside Jacen Solo and now must decide what that friendship
means as he changes (personal drama, Morality-driven). A war correspondent
documenting the conflict who discovers classified information about GAG
operations (investigative thriller, Duty-driven). A Mandalorian mercenary
hired by both sides who discovers the war is being manipulated (conspiracy
thriller, Obligation-driven).

---

### 17.4 Fate of the Jedi Era

**The Moral Landscape:** Something is wrong with the Force. Former students
of Luke Skywalker's academy are going insane — experiencing a psychosis that
grants them enormous power and absolute conviction that they are the only
ones who see reality clearly. Behind this psychosis is Abeloth, a being of
cosmic horror that predates the Jedi and the Sith, that exists in the spaces
between the Force's light and dark aspects, and that hungers for connection
with an appetite that consumes civilizations.

**What Makes It Different:** This is Star Wars as cosmic horror. The threat
is not military, not political, not personal. It is ontological. The Force
itself — the metaphysical foundation of the entire setting — may be
fundamentally different from what anyone believed. The Jedi and the Sith
are both wrong, not about tactics or philosophy but about the nature of
reality. Players in this era confront the possibility that the universe
operates on principles that their training, their intuition, and their
experience cannot prepare them for.

**Campaign Spine Example — "The Maw Expedition":**

A Jedi scholar or Force-sensitive archaeologist — career: Seeker or Mystic —
is dispatched to investigate a Jedi outpost in the Maw Cluster that has
gone silent. The outpost was researching pre-Republic Force traditions.

Act 1 — The Approach. The journey through the Maw Cluster's black hole
cluster is mechanically demanding — navigation checks against extreme
difficulty. The Force behaves strangely here. Meditation produces visions
that feel more like memories. The character begins to sense something vast
at the edge of perception.

Act 2 — The Outpost. The outpost is intact. The researchers are present.
They are not insane in any obvious way. But their research has led them to
a conclusion that they deliver calmly, with evidence, and that terrifies
the player: the Force is not a natural phenomenon. It is a system. And
systems have administrators.

Act 3 — Contact. Abeloth does not appear as a monster. She appears as a
presence — a sense of being observed by something that is simultaneously
ancient, lonely, and unspeakably dangerous. She does not attack. She offers
understanding. She offers the answer to the question the player's character
has been carrying since the prologue. The answer is true. The cost of
accepting it is not immediately apparent.

Act 4 — The Choice. The player must decide what to do with what they have
learned. The outpost researchers want to continue. The Jedi Council wants a
report. Abeloth wants the player to stay. The Force itself seems uncertain.
The player chooses, and the choice reverberates through a story structure
that understands cosmic horror is not about tentacles — it is about the
moment you realize the universe is larger than your ability to comprehend it.

**Throughline Question:** "What do you do when the truth is bigger than your
ability to hold it?"

**Motivation Track Emphasis:** Morality is paramount but operates differently
here. The Conflict is not between light and dark in the traditional sense —
it is between human-scale understanding and something that transcends the
framework entirely. The drift is not toward evil. It is toward something
that has no name yet.

**Other stories in this era:** A GA intelligence officer tracking the
political maneuvering between Chief of State Daala and the Jedi Order
(political thriller, Duty-driven). A bounty hunter hired to track down
psychotic Jedi who discovers sympathy for the afflicted and resistance to
the people giving orders (moral action, Obligation and Morality intertwined).
A journalist or scholar investigating the Lost Tribe of the Sith's
infiltration of galactic society (conspiracy thriller, Duty-driven). A
smuggler running supplies to Jedi in exile as the government turns against
the Order (adventure, Obligation-driven — echoing the GCW dynamic but in a
profoundly different political context).

---

### 17.5 Cross-Era Campaign Continuity

The most compelling stories in the Star Wars Legends timeline are the ones
that span eras — where a character's choices in one period reverberate through
the next. Storyteller V3 is designed to support this.

**The principle:** A character who completes a campaign in one era can persist
into a campaign set in a later era, carrying their full state — mechanical
profile, NPC relationships, motivation tracks, behavioral patterns, throughline
question, and voice notes — forward. The character who emerges from twenty
hours of play in the New Jedi Order is a specific person. When they enter a
Legacy of the Force campaign, they arrive as that person, not a fresh start
with backstory text.

**Canon as environmental constraint.** Canon events — Jacen Solo's fall, the
Second Galactic Civil War, Abeloth's emergence — are galactic-scale events
driven by forces larger than the player. They function as **environmental
anchors**: they happen, and the player's story exists within and around them.
The player does not prevent Jacen from becoming Caedus any more than a single
person stops a real political collapse. But the player's *relationship* to
those events is entirely shaped by their history.

A player who befriended Jacen during the Vong War and built genuine trust
through play — not backstory, but actual shared moments under fire — faces his
fall as a personal tragedy, not a plot point. The GM has their NPC state card
for Jacen: high disposition, specific shared memories, earned trust. The prose
puts that history on the page. The player can argue, plead, fight alongside
him, or stand against him. The dice determine whether their words land. But
the canon anchor — Jacen crosses the line — holds. What the player owns is
their response to it and the consequences that follow.

**The butterfly effect — personal scale.** Player actions do not rewrite the
galactic timeline. But they create ripples that the narrative acknowledges.
Because you helped the Corellians in Act 2, a Corellian senator remembers your
name during the secession crisis. Because you saved a specific family during
the Vong War, their grandchild appears in the Legacy era with a debt they
intend to repay. The world remembers the player at the scale the player
operated — personal, social, local — and those memories compound across eras
into something that feels like a life lived inside a galaxy that was always
larger than you.

**Campaign import interface.** Cross-era continuity requires campaign spines
that can intake a character's prior state. A Legacy of the Force spine needs to
know: does this character have a pre-existing relationship with Jacen Solo?
What is the disposition? What is the shared history? If the player is starting
fresh, Jacen is an authored NPC with a default state card. If the player has
prior history, the state card is a hybrid of the authored Legacy starting point
and the imported relationship data. This is a Campaign Studio design concern —
the engine processes the state card regardless of its origin.

---

### Setting Extensibility

The Star Wars FFG system is the first implementation. The architecture is
designed so that the rules layer is specific to FFG while the narrative and
memory layers are setting-agnostic. Other settings — original science fiction,
supernatural drama, espionage, historical fiction — become possible once the
foundation is proven.

### Original Worldbuilding

The generative systems that populate Nar Shaddaa's docking bays with specific
dockworkers and specific nervous contacts can populate any setting. New planets,
new factions, new species, new Force traditions — all generated from
designer-provided seeds that capture the creative intent and then filled with
texture the AI produces and the persistence layer locks in place.

---

## 18. The Vertical Slice

Before any of the above. Before era packs, before campaign generation, before
extensibility, before anything:

One complete working turn. Keth Varso, Bothan Smuggler, arriving above Nar
Shaddaa with a problem. A choice. A dice check that matters. A passage of prose
that honors what the dice said. Two more choices.

If that loop feels like a story worth reading, everything else becomes
an engineering problem. If it doesn't, nothing else matters.

That is where we start.

---

## 19. What This Is Not

This document would be incomplete without being explicit about what Storyteller
V3 is not, because the failure modes are obvious and we have fallen into some
of them before.

It is not a platform. We are not building infrastructure for all possible
narrative games. We are building one specific game with one specific mechanical
system in one specific setting.

It is not a chatbot with RPG flavoring. The player does not type free text to
a GM character. They read prose and make choices from a curated set of options.

It is not a real-time game. Nothing happens fast. The experience is reading,
thinking, and choosing. Latency of 5-10 seconds for a narrative passage is
acceptable. The pace is deliberate.

It is not a companion experience. The AI GM is a narrator and a mechanical
judge. It is not a friend, a therapist, or a conversational partner. Players
who want to talk to an AI should use a different product.

It is not a complete Star Wars encyclopedia. The game does not attempt to
represent every species, every planet, every canon event, every EU novel.
It represents the specific characters and situations of the campaigns it
contains, with the depth those situations require.

It is not finished until one complete turn feels like a story worth reading.
Everything added before that moment is premature. Everything added after that
moment is expansion of something proven.

---

---

## Revision History

**v3.1 — Character funnel pivot (March 2026)**

1. **Section 8 rewritten:** Character creation revised from flat variant
   selection to a three-step funnel: Timeline → Allegiance → Variant. The
   funnel converts a single selection into a sequence of meaningful identity
   decisions, solving both fantasy fulfillment (faction-specific player
   fantasies always have a path) and perceived agency (each step narrows
   while giving the player a choice that reflects their intent). New
   subsections: "The Character Funnel — Narrowing Into Identity," "Why a
   Funnel, Not a Flat List," "The Campaign as Adaptive Structure." The
   psychometric prologue (Section 8 continued) is unchanged — behavioral
   axes, adaptive depth, and three-layer inference all still apply.
   Introduces the fixed thematic spine / flexible protagonist integration
   layer split, which is the architectural enabler for the funnel. The
   Campaign Studio authors both layers. The Game Engine consumes the result
   — a specific character variant in a campaign spine JSON — unchanged.

2. **Section 9 revised:** Force sensitivity now surfaces through the funnel's
   allegiance step. Force-aligned allegiances (Jedi Order, Force Tradition)
   are available when the era supports them. The rarity principle is
   unchanged — applied at campaign design level, not character selection.

3. **Section 10 updated:** Motivation track assignment language updated to
   reference the funnel. Primary track still set by variant. Allegiance
   provides signal but does not determine the track.

4. **Section 17 updated:** Era campaigns now explicitly noted as the first
   step in the character funnel, not just setting backdrops for campaign
   authors.

**v3.0 — Design refinement pass (March 2026)**

1. **Section 3 revised:** Prose voice modulation added. Stover-Luceno remains
   the center of gravity but the voice now explicitly modulates by scene type
   and character state — Allston warmth for lighter moments, Zahn precision
   for tactical scenes. Anti-targets revised from absolute exclusions to
   non-default registers. AI-generated house style prohibition remains
   absolute.

2. **Section 4 expanded:** Game lines as lenses clarification. Obligation,
   Duty, and Morality are mechanical vocabulary, not era restrictions. Campaign
   spines specify which tracks are active. Era provides setting context; game
   lines provide mechanical framework. The two are orthogonal.

3. **Section 7 expanded:** Dialogue choices added — direct lines and
   conversational approaches as a mode within the choice system, with worked
   examples. Integrates naturally with the dice system (social skill checks)
   and the Character Through Tactics principle (social tactics as identity
   decisions). Introspection choices also added as complement to Character
   Through Tactics — pure identity choices at key narrative junctures (act
   boundaries, after major events, downtime) with no dice check. Provides
   pacing relief and direct signal about player's internal priorities.

4. **Section 8 rewritten:** Character creation revised from pure open-ended
   inference to constrained selection with prologue refinement. Player selects
   from 4-6 pre-designed character variants (narrative pitches, not stat
   blocks), then the psychometric prologue refines the variant along four
   behavioral axes. Aligns with Game Mechanics Document v1.2 Section 5.

5. **Section 9 revised:** Force sensitivity changed from random emergence
   (1-in-10) to player choice via character variant selection. Rarity principle
   preserved at campaign design level — not every campaign needs Force
   protagonists, and non-Force careers must be equally compelling.

6. **Section 10 expanded:** Motivation track assignment at character creation
   documented. Primary track set by character variant. Specific type refined
   by prologue. Secondary tracks introduced by campaign spine when narratively
   appropriate.

7. **Section 11 expanded:** NPC system growth direction documented. Four
   post-V1 expansion areas: relationship triangles (NPC-NPC dispositions),
   emotional state (transient in-scene mood), behavioral envelopes (hard
   constraints on NPC behavior), information propagation (offscreen NPC-to-NPC
   knowledge transfer).

8. **Section 12 expanded:** Non-linear spine structures acknowledged.
   Hub-and-spoke and parallel track alternatives documented as campaign
   authoring concerns (not engine concerns) for post-V1.

9. **Section 17 expanded:** Genre alternatives added to all four era examples
   (2-4 per era). New Section 17.5 added: Cross-Era Campaign Continuity —
   character persistence across campaigns, canon as environmental constraint,
   butterfly effect at personal scale, campaign import interface.

**v2.0 — Initial expansion**

Expanded to 19 sections. Considered stable.

---

*Storyteller V3 — Vision Document v3.1*
*The game that reads like a novel, plays like a session, and remembers who
your character is becoming.*
