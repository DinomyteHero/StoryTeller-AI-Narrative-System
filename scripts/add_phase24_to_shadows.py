"""Phase 24: add Character Creation Redesign data to the canonical campaign.

Idempotently injects backgrounds, identity_prologue, and
profession_crystallization fields into
data/campaigns/shadows_of_the_custodian.json. Re-running overwrites
the three keys but leaves everything else untouched.

Run: python -m scripts.add_phase24_to_shadows
"""

import json
from pathlib import Path


SPINE_PATH = Path("data/campaigns/shadows_of_the_custodian.json")


# ── 6 backgrounds, tuned to the 16 ABY Praxeum setting ────────────────


BACKGROUNDS = [
    {
        "background_id": "outer_rim_refugee",
        "display_name": "Outer Rim Refugee",
        "story_seed": (
            "Imperial occupation forced your family from your home world during "
            "the end-of-Empire chaos. You spent your formative years in a refugee "
            "convoy, then a New Republic resettlement camp. A Jedi recruiter found "
            "you when you instinctively shielded younger children from a "
            "collapsing roof."
        ),
        "default_names": ["Sora", "Jenn", "Mira", "Kestrel", "Talen"],
        "default_species": ["human", "twi_lek", "mirialan"],
        "default_skill_tilt": {
            "resilience": 1, "vigilance": 1, "survival": 1, "education": -1,
        },
        "default_loadout": "",
        "pre_filled_relationship": {
            "npc_name": "Ren Vask",
            "npc_role": "fellow refugee student at the Praxeum",
            "initial_disposition": 0.65,
            "relationship_summary": (
                "Slightly older. Recognized the silence of someone who has "
                "lost what you have lost. Friendship took root in those first "
                "weeks because neither of you had to explain why you slept "
                "with the lights on."
            ),
        },
        "unique_unlocks": [
            {
                "unlock_id": "refugee_kinship",
                "description": (
                    "Refugee NPCs across the galaxy treat you with shared "
                    "recognition. Unlocks dialogue tone in social scenes "
                    "with displaced populations."
                ),
                "trigger_type": "dialogue_tone",
            },
            {
                "unlock_id": "homeworld_flashback",
                "description": (
                    "Flashback access to your home world at major emotional "
                    "beats. Surfaces as interiority during quiet moments."
                ),
                "trigger_type": "flashback_access",
            },
            {
                "unlock_id": "trauma_anchored_surge",
                "description": (
                    "When defending children, you surge above your trained "
                    "capacity. +1 boost die when the protected party "
                    "includes minors."
                ),
                "trigger_type": "skill_bonus",
            },
        ],
        "prologue_tailoring": {
            "cold_open_concept": (
                "Arriving at the Praxeum still carrying a child's blanket "
                "from the convoy. The colours are wrong against the "
                "jungle green."
            ),
            "archetype_scene_flavor": (
                "Frame psychometric tests as 'what you do when something "
                "familiar happens' rather than 'what you do under abstract "
                "pressure.' Trauma is recognised, not performed."
            ),
            "diegetic_slot_preferences": {
                "name_pick": "intake_with_tionne",
                "gender_pick": "intake_with_tionne",
                "appearance_flair": "morning_after_first_dinner",
            },
        },
        "profession_affinities": {
            "strong_fit": "consular",
            "possible_fit": ["sentinel"],
            "tense_fit": ["guardian"],
        },
    },
    {
        "background_id": "imperial_defector",
        "display_name": "Imperial Defector",
        "story_seed": (
            "Born inside the Empire's middle classes, raised on its propaganda. "
            "You served as a junior officer cadet (or COMPNOR youth corps, or "
            "Imperial academy student) before your Force-sensitivity manifested "
            "in a way that put you on the Inquisitor list. You ran. The New "
            "Republic intercepted you. You arrived at the Praxeum carrying real "
            "guilt and real Imperial training."
        ),
        "default_names": ["Cael", "Nyx", "Vell", "Doran", "Ardin"],
        "default_species": ["human"],
        "default_skill_tilt": {
            "discipline": 1, "warfare": 1, "computers": 1, "charm": -1,
        },
        "default_loadout": "",
        "pre_filled_relationship": {
            "npc_name": "Master Tev",
            "npc_role": "senior Praxeum instructor who chose to sponsor you",
            "initial_disposition": 0.5,
            "relationship_summary": (
                "Watches you carefully. Took the unpopular position of "
                "vouching for your admission against quiet objections. The "
                "trust is conditional and he has not pretended otherwise."
            ),
        },
        "unique_unlocks": [
            {
                "unlock_id": "imperial_tech_recognition",
                "description": (
                    "Imperial machinery, doctrine, and encrypted comms are "
                    "legible to you. +1 boost die on Computers/Knowledge "
                    "(Warfare) checks targeting Imperial systems."
                ),
                "trigger_type": "skill_bonus",
            },
            {
                "unlock_id": "old_contacts",
                "description": (
                    "One or two NPCs from your past exist in the world and "
                    "may surface in later acts — possibly as antagonists."
                ),
                "trigger_type": "conditional_branch",
            },
            {
                "unlock_id": "sith_curious_dialogue",
                "description": (
                    "Some choices that other backgrounds cannot pick because "
                    "they require Imperial framing become available — 'I've "
                    "read the propaganda; I know how this rhetoric works.'"
                ),
                "trigger_type": "dialogue_tone",
            },
        ],
        "prologue_tailoring": {
            "cold_open_concept": (
                "Standing in your former uniform on the day you ran. The "
                "creases are still pressed; the rank pin is in your hand."
            ),
            "archetype_scene_flavor": (
                "Frame psychometric tests as 'what you do when ideology "
                "cracks.' High salience on the Moral axis; fast inference "
                "on Trust."
            ),
            "diegetic_slot_preferences": {
                "name_pick": "intake_with_tionne",
                "gender_pick": "intake_with_tionne",
                "appearance_flair": "uniform_in_the_drawer",
            },
        },
        "profession_affinities": {
            "strong_fit": "sentinel",
            "possible_fit": ["consular"],
            "tense_fit": ["guardian"],
        },
    },
    {
        "background_id": "rebel_legacy",
        "display_name": "Rebel Legacy",
        "story_seed": (
            "Your parents fought in the Rebellion. One of them may still be "
            "alive in the New Republic government or military; the other may "
            "have died at Endor or in the wars after. You grew up on hero "
            "stories and at hero funerals. Your Force sensitivity was "
            "expected. The pressure is heavier than the training."
        ),
        "default_names": ["Riggs", "Mara", "Jarek", "Kyla", "Ben"],
        "default_species": ["human", "mon_calamari", "sullustan"],
        "default_skill_tilt": {
            "ranged_light": 1, "discipline": 1, "leadership": 1,
            "coordination": -1,
        },
        "default_loadout": "",
        "pre_filled_relationship": {
            "npc_name": "Master Tasha Vren",
            "npc_role": "Jedi who fought alongside one of your parents",
            "initial_disposition": 0.8,
            "relationship_summary": (
                "Has known you since you were a child. The warmth is "
                "familial; the expectation is heavier than either of you "
                "would admit."
            ),
        },
        "unique_unlocks": [
            {
                "unlock_id": "veteran_kinship",
                "description": (
                    "War-veteran NPCs treat you as kin. Unlocked dialogue "
                    "with Rebellion / New Republic veterans across the galaxy."
                ),
                "trigger_type": "dialogue_tone",
            },
            {
                "unlock_id": "restless_meditation",
                "description": (
                    "Your characteristic restlessness shows in the way you "
                    "sit through meditation. The Praxeum tries to address it; "
                    "the LLM should write it as a bodily quality."
                ),
                "trigger_type": "voice_flavor",
            },
            {
                "unlock_id": "imperial_recognition_hostile",
                "description": (
                    "Imperial holdouts who recognize your parents' name may "
                    "react with hostility in later acts."
                ),
                "trigger_type": "conditional_branch",
            },
        ],
        "prologue_tailoring": {
            "cold_open_concept": (
                "Sparring against upper-classmen with the saber form your "
                "parent used. You are good because you have practiced this "
                "since you were six."
            ),
            "archetype_scene_flavor": (
                "Test what happens when expectations conflict with instinct."
            ),
            "diegetic_slot_preferences": {
                "name_pick": "sparring_with_kam",
                "gender_pick": "intake_with_tionne",
                "appearance_flair": "father_or_mothers_calluses",
            },
        },
        "profession_affinities": {
            "strong_fit": "guardian",
            "possible_fit": ["sentinel"],
            "tense_fit": ["consular"],
        },
    },
    {
        "background_id": "discovered_late",
        "display_name": "Discovered Late",
        "story_seed": (
            "Your Force-sensitivity emerged when you were already an adult — "
            "twenty-three, twenty-five, even older. You had a life: a career, "
            "possibly a partnership, a sense of who you were. The Force "
            "disrupted that. You arrived at the Praxeum older than every other "
            "first-year student, with adult competencies and adult anxieties."
        ),
        "default_names": ["Margo", "Tarn", "Kael", "Senna", "Joren"],
        "default_species": ["human", "pantoran", "zabrak"],
        "default_skill_tilt": {
            "lore": 1, "negotiation": 1, "skulduggery": 1,
            "athletics": -1,
        },
        "default_loadout": "",
        "pre_filled_relationship": {
            "npc_name": "Vesper",
            "npc_role": "younger Praxeum student (16-17)",
            "initial_disposition": 0.7,
            "relationship_summary": (
                "Looks up to you because you are visibly an adult and treat "
                "them with respect rather than condescension. Admiration "
                "with a tinge of hero-worship."
            ),
        },
        "unique_unlocks": [
            {
                "unlock_id": "adult_experience",
                "description": (
                    "The narration writes you as someone who has held jobs, "
                    "paid rent, lost relationships. Beats land differently "
                    "than they would for a teenager."
                ),
                "trigger_type": "voice_flavor",
            },
            {
                "unlock_id": "informed_skepticism",
                "description": (
                    "Choices that read as cynical for younger students read "
                    "as informed-skeptical for you."
                ),
                "trigger_type": "dialogue_tone",
            },
            {
                "unlock_id": "previous_career_contacts",
                "description": (
                    "Contacts from your previous career surface in late-game "
                    "scenes when your old field intersects the conspiracy."
                ),
                "trigger_type": "conditional_branch",
            },
        ],
        "prologue_tailoring": {
            "cold_open_concept": (
                "Packing up your former life — a tool kit, a uniform, a "
                "key turned in. The hands move from habit; the mind has "
                "not caught up."
            ),
            "archetype_scene_flavor": (
                "Test how an adult mind responds to being a beginner."
            ),
            "diegetic_slot_preferences": {
                "name_pick": "intake_with_tionne",
                "gender_pick": "intake_with_tionne",
                "appearance_flair": "the_things_you_kept",
            },
        },
        "profession_affinities": {
            "strong_fit": "consular",
            "possible_fit": ["sentinel"],
            "tense_fit": ["guardian"],
        },
    },
    {
        "background_id": "frontier_world_native",
        "display_name": "Frontier-World Native",
        "story_seed": (
            "You grew up on a Wild Space or Outer Rim world that the galaxy "
            "barely tracks — small population, no holonet, traditional "
            "livelihoods. The Force showed up as part of how the world worked, "
            "and a Jedi recruiter who happened through your settlement noticed "
            "what you were doing. You had never heard of the Jedi until they "
            "explained themselves to you."
        ),
        "default_names": ["Cova", "Den", "Brae", "Tova", "Eli"],
        "default_species": ["human", "togruta", "zabrak"],
        "default_skill_tilt": {
            "survival": 1, "perception": 1, "resilience": 1,
            "core_worlds": -1,
        },
        "default_loadout": "",
        "pre_filled_relationship": {
            "npc_name": "Recruiter Adric",
            "npc_role": "the Jedi who came through your settlement",
            "initial_disposition": 0.75,
            "relationship_summary": (
                "Brought you to the Praxeum. Visits occasionally, checks on "
                "you. Mentor-like, slightly distant — a man who knows what "
                "it cost you to leave."
            ),
        },
        "unique_unlocks": [
            {
                "unlock_id": "wilderness_survival",
                "description": (
                    "Shelter, food, and terrain reading are second nature. "
                    "+1 boost die on Survival in unfamiliar environments; "
                    "narrative bonuses in exploration scenes."
                ),
                "trigger_type": "skill_bonus",
            },
            {
                "unlock_id": "cultural_stranger",
                "description": (
                    "The Praxeum's politics are baffling. Some scenes are "
                    "written observationally rather than participatorily — "
                    "you are present without being conscripted."
                ),
                "trigger_type": "voice_flavor",
            },
            {
                "unlock_id": "homeworld_anchor",
                "description": (
                    "Your home world becomes a load-bearing late-game "
                    "location."
                ),
                "trigger_type": "conditional_branch",
            },
        ],
        "prologue_tailoring": {
            "cold_open_concept": (
                "Your home world's traditional dress on the day Adric "
                "arrives. The fabric remembers cold the jungle does not have."
            ),
            "archetype_scene_flavor": (
                "Test responses to cultural-translation moments as much as "
                "ethical-pressure moments."
            ),
            "diegetic_slot_preferences": {
                "name_pick": "asked_in_the_colonnade",
                "gender_pick": "intake_with_tionne",
                "appearance_flair": "what_you_brought",
            },
        },
        "profession_affinities": {
            "strong_fit": "guardian",
            "possible_fit": ["sentinel"],
            "tense_fit": ["consular"],
        },
    },
    {
        "background_id": "reformed_smuggler",
        "display_name": "Reformed Smuggler",
        "story_seed": (
            "Your Force-sensitivity developed in the wrong neighborhood. You "
            "ran cargoes you shouldn't have, kept company with people you "
            "shouldn't have, and were pretty good at all of it. A botched job "
            "ended with someone dead and you in a Jedi-adjacent sanctuary. The "
            "Praxeum offered a path. You took it. Most of you."
        ),
        "default_names": ["Kade", "Loris", "Talia", "Jin", "Ess"],
        "default_species": ["human", "rodian", "twi_lek"],
        "default_skill_tilt": {
            "streetwise": 1, "skulduggery": 1, "piloting_space": 1,
            "discipline": -1,
        },
        "default_loadout": "",
        "pre_filled_relationship": {
            "npc_name": "Hux",
            "npc_role": "your old smuggling partner, still working",
            "initial_disposition": 0.6,
            "relationship_summary": (
                "Has not been told you are at the Praxeum. Believes you "
                "took a quiet retirement after the bad job. Loyal but "
                "unaware — a thread waiting to pull."
            ),
        },
        "unique_unlocks": [
            {
                "unlock_id": "underworld_dialogue",
                "description": (
                    "Underworld dialogue tone unlocked across the galaxy. "
                    "Smugglers, fixers, and fringe contacts read you as one "
                    "of theirs."
                ),
                "trigger_type": "dialogue_tone",
            },
            {
                "unlock_id": "uniform_flinch",
                "description": (
                    "You flinch at uniforms even when they are your own "
                    "side. The narration writes this as a small, recurring "
                    "tell."
                ),
                "trigger_type": "voice_flavor",
            },
            {
                "unlock_id": "underground_contacts",
                "description": (
                    "Underground contacts can be invoked for non-combat "
                    "problem-solving when the Praxeum cannot help."
                ),
                "trigger_type": "conditional_branch",
            },
        ],
        "prologue_tailoring": {
            "cold_open_concept": (
                "A Coruscant lower-level cantina the morning after the "
                "botched job. The lights are too bright for what just "
                "happened."
            ),
            "archetype_scene_flavor": (
                "Test what happens when you are asked to trust a system "
                "you have spent your life dodging."
            ),
            "diegetic_slot_preferences": {
                "name_pick": "asked_in_the_cantina",
                "gender_pick": "intake_with_tionne",
                "appearance_flair": "the_jacket_you_kept",
            },
        },
        "profession_affinities": {
            "strong_fit": "sentinel",
            "possible_fit": ["consular"],
            "tense_fit": ["guardian"],
        },
    },
]


# ── Identity Prologue arc ─────────────────────────────────────────────


IDENTITY_PROLOGUE = {
    "scene_library": [
        {
            "scene_id": "arrival_at_praxeum",
            "situation": (
                "The supply shuttle Horizon descends through Yavin 4's "
                "high atmosphere. The viewport floods green. Cohort members "
                "in the seats around you — names you do not yet know — are "
                "doing what people always do during a long descent: "
                "breathing too carefully, pretending not to count exits, "
                "saying the small things that pass for okay."
            ),
            "background_variants": {
                "outer_rim_refugee": {
                    "prose": (
                        "You still have the child's blanket folded inside "
                        "your kit, the one you would not let the resettlement "
                        "officers take. The fabric does not match anything "
                        "in this jungle. The cohort has not asked. "
                        "They will."
                    ),
                    "npc_names": ["Joran Veska"],
                    "choice_overrides": [],
                },
                "imperial_defector": {
                    "prose": (
                        "There is a seat across the aisle from a young "
                        "woman who keeps glancing at the cut of your "
                        "shoulders. Your bearing has not unlearned the "
                        "uniform. You feel her notice. You feel her "
                        "decide not to mention it."
                    ),
                    "npc_names": ["Joran Veska"],
                    "choice_overrides": [],
                },
                "rebel_legacy": {
                    "prose": (
                        "Two of the older students recognize your "
                        "surname before you have introduced yourself. One "
                        "stands up to greet you the way veterans greet a "
                        "veteran's child. The other looks at the floor."
                    ),
                    "npc_names": ["Joran Veska"],
                    "choice_overrides": [],
                },
                "discovered_late": {
                    "prose": (
                        "You are the oldest body on the shuttle by at "
                        "least four years. You feel your knees in a way "
                        "the eighteen-year-olds will not understand for "
                        "another decade. You also feel, for the first "
                        "time in months, that you are not the only adult "
                        "in the room — and you cannot tell yet whether "
                        "that is comfort or threat."
                    ),
                    "npc_names": ["Joran Veska"],
                    "choice_overrides": [],
                },
                "frontier_world_native": {
                    "prose": (
                        "Your home world had no atmosphere this thick. "
                        "The pressure presses on the ears in a way that "
                        "feels animal, not technological. You watch the "
                        "canopy and try to find a tree shape your village "
                        "elders would have a name for."
                    ),
                    "npc_names": ["Joran Veska"],
                    "choice_overrides": [],
                },
                "reformed_smuggler": {
                    "prose": (
                        "The shuttle's manifest list is too clean. No "
                        "false names, no padding, no cargo masking. Your "
                        "hands keep wanting to look for the irregularity. "
                        "A boy across the aisle smiles at you the way "
                        "civilians smile, and you have to remember how "
                        "that face is supposed to read."
                    ),
                    "npc_names": ["Joran Veska"],
                    "choice_overrides": [],
                },
            },
            "axis_tags": ["approach", "social"],
            "choices": [
                {
                    "text": "Introduce yourself first — name the silence and break it.",
                    "axis_tags": {
                        "approach": "direct",
                        "social": "warm",
                    },
                },
                {
                    "text": "Wait. Watch how they handle the descent, and let the cohort form around you.",
                    "axis_tags": {
                        "approach": "indirect",
                        "social": "guarded",
                    },
                },
                {
                    "text": "Pull out your kit, do something useful with your hands, and let work make the introduction.",
                    "axis_tags": {
                        "approach": "indirect",
                        "social": "warm",
                    },
                },
            ],
            "diegetic_slot": {
                "slot_type": "appearance_flair",
                "prompt": (
                    "What does the cohort see when they see you for the "
                    "first time? (Optional — you can skip and let the "
                    "Praxeum decide.)"
                ),
                "optional": True,
            },
        },
        {
            "scene_id": "intake_with_tionne",
            "situation": (
                "Tionne meets you in the small east room off the colonnade. "
                "Her silver hair is loose; her hands are around a cup of "
                "tea she has not touched. The intake form is on the desk "
                "between you, half-completed, and she is not in a hurry. "
                "She has read your file. She has questions the file did "
                "not answer. She begins with the one you can choose to "
                "answer fully, glancingly, or honestly."
            ),
            "background_variants": {
                "outer_rim_refugee": {
                    "prose": (
                        "She has the convoy manifest from when your family "
                        "was processed. She has not opened it. 'Some of "
                        "this isn't mine to read,' she says. 'Tell me what "
                        "you want me to know.'"
                    ),
                    "npc_names": ["Tionne"],
                    "choice_overrides": [],
                },
                "imperial_defector": {
                    "prose": (
                        "She has your defection record. She has the "
                        "annotations Mon Mothma's office added. She has "
                        "the question: 'What did you do, in your service, "
                        "that you would do again if you knew it would "
                        "save someone?'"
                    ),
                    "npc_names": ["Tionne"],
                    "choice_overrides": [],
                },
                "rebel_legacy": {
                    "prose": (
                        "She knew your parent. She tells you this without "
                        "warmth and without coldness. 'You are not them,' "
                        "she says. 'I will not pretend you are. Tell me "
                        "what you came here for, in your words.'"
                    ),
                    "npc_names": ["Tionne"],
                    "choice_overrides": [],
                },
                "discovered_late": {
                    "prose": (
                        "She has the dossier from your old job. She "
                        "looks tired in a way that says she has read it "
                        "twice. 'You have lived a life,' she says. 'I "
                        "want to ask what you came here looking for. The "
                        "honest version, not the application essay.'"
                    ),
                    "npc_names": ["Tionne"],
                    "choice_overrides": [],
                },
                "frontier_world_native": {
                    "prose": (
                        "She speaks slowly, which you mistake for "
                        "condescension until you realize she is choosing "
                        "vocabulary you would understand. 'Your recruiter "
                        "told me what you were doing on the day he found "
                        "you. I want to hear it from you.'"
                    ),
                    "npc_names": ["Tionne"],
                    "choice_overrides": [],
                },
                "reformed_smuggler": {
                    "prose": (
                        "She knows enough. She does not pretend not to. "
                        "'There is a name on this form,' she says. 'I "
                        "do not know if it is yours. I would like to "
                        "use the one you mean.'"
                    ),
                    "npc_names": ["Tionne"],
                    "choice_overrides": [],
                },
            },
            "axis_tags": ["moral", "social"],
            "choices": [
                {
                    "text": "Tell her the version that is true. The whole shape, even the parts you would rather edit.",
                    "axis_tags": {
                        "moral": "honest",
                        "social": "open",
                    },
                },
                {
                    "text": "Tell her the version that lets you stay. Truth at the level of the form, not the soul.",
                    "axis_tags": {
                        "moral": "guarded",
                        "social": "guarded",
                    },
                },
                {
                    "text": "Ask her, instead, what the Praxeum wants from you. Make her go first.",
                    "axis_tags": {
                        "moral": "neutral",
                        "social": "warm",
                    },
                },
            ],
            "diegetic_slot": {
                "slot_type": "name_pick",
                "prompt": (
                    "Tionne is asking, gently, what name she should put "
                    "on the intake form. (You can pick one of your "
                    "background's names, type your own, or — if you "
                    "already chose during refinement — just confirm.)"
                ),
                "optional": False,
            },
        },
        {
            "scene_id": "first_dinner",
            "situation": (
                "First dinner in the great hall. Long tables, mismatched "
                "bowls, the cohort arranging itself by the small "
                "gravities of who is willing to sit next to whom. Joran "
                "Veska saves you a seat without asking. Across from you, "
                "Rann Veska is eating in silence and watching the room. "
                "Tarsh Voll is louder than the room and louder than "
                "anyone trying to be loud. The food is honest. The "
                "conversation is the test."
            ),
            "background_variants": {
                "outer_rim_refugee": {
                    "prose": (
                        "There is bread in the centre of the table that "
                        "is the same shape as the bread the resettlement "
                        "camp baked. You did not expect that. Joran sees "
                        "the look on your face and says nothing, which "
                        "is how you know he saw."
                    ),
                    "npc_names": ["Joran Veska", "Rann Veska", "Tarsh Voll"],
                    "choice_overrides": [],
                },
                "imperial_defector": {
                    "prose": (
                        "Tarsh — loud, fringe-raised, mouthy — makes a "
                        "joke about Imperial mess halls without knowing "
                        "where you came from. Joran does know, and "
                        "watches you choose your laugh."
                    ),
                    "npc_names": ["Joran Veska", "Rann Veska", "Tarsh Voll"],
                    "choice_overrides": [],
                },
                "rebel_legacy": {
                    "prose": (
                        "Two seats down, an older student tells a story "
                        "about your parent that is half true. The half "
                        "that is wrong is the part that mattered. You "
                        "have heard this story told wrong every year of "
                        "your life. Joran reads your face and waits."
                    ),
                    "npc_names": ["Joran Veska", "Rann Veska", "Tarsh Voll"],
                    "choice_overrides": [],
                },
                "discovered_late": {
                    "prose": (
                        "The cohort is younger than you remembered they "
                        "would be. Rann is the only person in the room "
                        "who looks at you as a peer. Joran is making "
                        "easy room for you, the way confident young "
                        "people sometimes do for adults they have decided "
                        "to be kind to."
                    ),
                    "npc_names": ["Joran Veska", "Rann Veska", "Tarsh Voll"],
                    "choice_overrides": [],
                },
                "frontier_world_native": {
                    "prose": (
                        "The food is unfamiliar. You watch how the cohort "
                        "eats it before you try yourself. Joran notices, "
                        "and shows you with his hands without comment. "
                        "Tarsh laughs at something across the table, and "
                        "the sound makes the room feel survivable."
                    ),
                    "npc_names": ["Joran Veska", "Rann Veska", "Tarsh Voll"],
                    "choice_overrides": [],
                },
                "reformed_smuggler": {
                    "prose": (
                        "You are the only person in the room who knows "
                        "what the cook used to mask the missing protein. "
                        "It is a Glass Wake trick. The recognition is "
                        "automatic. Joran says something kind to you. "
                        "You have to remember to be a person being "
                        "spoken kindly to, not a smuggler reading a mark."
                    ),
                    "npc_names": ["Joran Veska", "Rann Veska", "Tarsh Voll"],
                    "choice_overrides": [],
                },
            },
            "axis_tags": ["social", "risk"],
            "choices": [
                {
                    "text": "Speak. Tell the table something about yourself before the cohort decides who you are.",
                    "axis_tags": {
                        "social": "open",
                        "risk": "bold",
                    },
                },
                {
                    "text": "Listen. Let the loudest voices settle the shape of the room and find your place inside it.",
                    "axis_tags": {
                        "social": "guarded",
                        "risk": "cautious",
                    },
                },
                {
                    "text": "Turn to Joran specifically. Make this one connection real before you address the rest.",
                    "axis_tags": {
                        "social": "warm",
                        "risk": "cautious",
                    },
                },
            ],
            "diegetic_slot": None,
        },
        {
            "scene_id": "the_test_in_the_courtyard",
            "situation": (
                "Two weeks in. Inya Vorn — a senior student with the "
                "saber form your file does not yet account for — stops "
                "you in the colonnade after midday meditation. There is "
                "a junior, smaller than both of you, in tears beside the "
                "fountain. Inya is asking the junior to say what "
                "happened. The junior cannot. Across the courtyard, an "
                "older student — Vesh Karro — is leaning against a "
                "pillar, watching. Vesh did something to the junior. "
                "Inya has not yet decided what to do about it. She "
                "looks at you. The decision becomes partly yours."
            ),
            "background_variants": {
                "outer_rim_refugee": {
                    "prose": (
                        "The junior has the same posture you used to have "
                        "in the resettlement queue. You recognize it before "
                        "you have decided to recognize it. Your hands have "
                        "already moved toward them; you have to choose, in "
                        "this half-second, whether to follow."
                    ),
                    "npc_names": ["Inya Vorn", "Vesh Karro"],
                    "choice_overrides": [],
                },
                "imperial_defector": {
                    "prose": (
                        "You know the kind of thing Vesh did. You know it "
                        "by the way he is standing. You knew people who "
                        "stood like that in the academy, and you know what "
                        "they did to the cadets who admitted weakness. "
                        "Inya is waiting to see if you will name it."
                    ),
                    "npc_names": ["Inya Vorn", "Vesh Karro"],
                    "choice_overrides": [],
                },
                "rebel_legacy": {
                    "prose": (
                        "Your parent's saber form is the one that would "
                        "answer this. You have practiced the opening "
                        "strike since you were six. Your hand wants to. "
                        "The Jedi part of you — the part that brought "
                        "you here — is asking whether your hand is "
                        "wanting the right thing."
                    ),
                    "npc_names": ["Inya Vorn", "Vesh Karro"],
                    "choice_overrides": [],
                },
                "discovered_late": {
                    "prose": (
                        "You have managed people who use power like Vesh "
                        "does. You know the script. You also know, as an "
                        "adult, that the wrong adult intervention can "
                        "make a young person's humiliation worse. You "
                        "have less time to choose than you would like."
                    ),
                    "npc_names": ["Inya Vorn", "Vesh Karro"],
                    "choice_overrides": [],
                },
                "frontier_world_native": {
                    "prose": (
                        "Where you grew up, an elder would not have "
                        "asked you. They would have decided. The fact "
                        "that Inya is including you means something you "
                        "do not yet have the vocabulary for. You feel it "
                        "before you read it."
                    ),
                    "npc_names": ["Inya Vorn", "Vesh Karro"],
                    "choice_overrides": [],
                },
                "reformed_smuggler": {
                    "prose": (
                        "On the Wake, you would have known three different "
                        "ways to handle Vesh, and two of them would have "
                        "ended with him not in a position to do this "
                        "again. The Praxeum is asking for the third way. "
                        "You are not sure you have it."
                    ),
                    "npc_names": ["Inya Vorn", "Vesh Karro"],
                    "choice_overrides": [],
                },
            },
            "axis_tags": ["moral", "risk"],
            "choices": [
                {
                    "text": "Stand between Vesh and the junior. Speak first. Make the cost of cruelty visible to him in front of witnesses.",
                    "axis_tags": {
                        "moral": "principled",
                        "risk": "bold",
                    },
                },
                {
                    "text": "Tend to the junior. Let Inya handle Vesh. Triage the wound, not the wound-maker.",
                    "axis_tags": {
                        "moral": "compassionate",
                        "risk": "cautious",
                    },
                },
                {
                    "text": "Wait. Watch Inya. Learn how the Praxeum chooses to handle this, and follow her lead.",
                    "axis_tags": {
                        "moral": "guarded",
                        "risk": "cautious",
                    },
                },
            ],
            "diegetic_slot": None,
        },
    ],
    "expected_scene_count": 4,
    "diegetic_slots_required": ["name_pick", "appearance_flair"],
    "closing_recognition": (
        "After the courtyard scene, Master Skywalker finds you in the "
        "training annex. He does not interrogate. He recognises what "
        "you have already shown. The Praxeum has read your shape — not "
        "your discipline, not your future, but the way you reach for "
        "what reaches for you. He tells you that, in his own words, "
        "and lets you carry it forward."
    ),
}


# ── Profession Crystallization Beat ───────────────────────────────────


PROFESSION_CRYSTALLIZATION = {
    "anchor_act": 3,
    "mentor_npc": "Luke Skywalker",
    "background_overrides": {
        "imperial_defector": "Master Tev",
    },
    "paths": [
        {
            "career_id": "guardian",
            "talent_tree_id": "guardian_protector",
            "display_name": "Guardian",
            "summary": (
                "The Jedi who steps between. Combat, defense, direct "
                "action. Your saber will be the first to ignite when the "
                "people you protect are in reach of harm."
            ),
            "prose_flavor": (
                "Frame the Guardian path as the discipline of putting your "
                "body in the way. The hand that catches the falling beam. "
                "The one who walks the corridor first."
            ),
            "background_specific_id": "",
        },
        {
            "career_id": "consular",
            "talent_tree_id": "consular_sage",
            "display_name": "Consular",
            "summary": (
                "The Jedi who listens. Mind-arts, diplomacy, healing. "
                "Your strength will not be the loudest in the room; it "
                "will be the one that ends the argument."
            ),
            "prose_flavor": (
                "Frame the Consular path as the discipline of patience and "
                "the long view — sitting with someone's grief, talking the "
                "warlord out of the room before the warlord lights anything."
            ),
            "background_specific_id": "",
        },
        {
            "career_id": "sentinel",
            "talent_tree_id": "sentinel_shadow",
            "display_name": "Sentinel",
            "summary": (
                "The Jedi who watches. Investigation, balance, hidden "
                "service. You will work in the seams the Order does not "
                "always admit it needs."
            ),
            "prose_flavor": (
                "Frame the Sentinel path as the discipline of noticing — "
                "the listener at the edge of the room, the one who reads "
                "the trace and finds the cell before it strikes."
            ),
            "background_specific_id": "",
        },
        {
            "career_id": "sentinel",
            "talent_tree_id": "sentinel_shadow_imperial",
            "display_name": "Shadow Sentinel",
            "summary": (
                "A sub-discipline available only to those with Imperial "
                "training. You learned the empire's grammar before you "
                "learned the Jedi's. The Order has uses for that "
                "knowledge that the Order does not always want to admit."
            ),
            "prose_flavor": (
                "Frame the Shadow Sentinel path as the discipline of "
                "turning Imperial fluency into protection — the one who "
                "reads cell signatures from the inside."
            ),
            "background_specific_id": "imperial_defector",
        },
    ],
    "suggestion_algorithm": {
        "background_weight": 2,
        "archetype_weight": 2,
        "skill_match_weight": 1,
    },
    "scene_seed": (
        "Master Skywalker calls the protagonist aside after the events of "
        "Two Brothers. The room is the small east meditation chamber, the "
        "one the cohort thinks is for senior students only. He has watched "
        "what the protagonist did during the off-world mission, what they "
        "did during the courtyard moment in Act 1, what they have done in "
        "the cohort's politics. He has read the pattern. He names the "
        "leanings he has seen, in his own voice — quiet, specific, without "
        "pressure. Then he asks: 'What do you want to become?' The "
        "protagonist has three (sometimes four) answers visible. Skywalker "
        "will accept any of them. He will not pretend the suggested path "
        "and the chosen path are always the same."
    ),
}


def main() -> None:
    text = SPINE_PATH.read_text(encoding="utf-8")
    spine = json.loads(text)

    spine["backgrounds"] = BACKGROUNDS
    spine["identity_prologue"] = IDENTITY_PROLOGUE
    spine["profession_crystallization"] = PROFESSION_CRYSTALLIZATION

    # ensure_ascii=True so the file remains pure ASCII (em-dashes etc.
    # serialize as \uXXXX escapes). This keeps the file loadable by code
    # that opens it without specifying utf-8 — important for test fixtures
    # and downstream tools that haven't been updated.
    SPINE_PATH.write_text(
        json.dumps(spine, indent=2, ensure_ascii=True), encoding="ascii"
    )
    print(f"Wrote {SPINE_PATH}")


if __name__ == "__main__":
    main()
