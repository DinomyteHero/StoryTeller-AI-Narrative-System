"""Augment a campaign spine with Phase 25 runtime experience content.

Idempotent — running multiple times produces the same content. Any
authored Phase 25 fields already in the spine are preserved.

Usage:
    python scripts/add_phase25_content.py [PATH]

Default PATH is data/campaigns/shadows_of_the_custodian.json.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = REPO_ROOT / "data" / "campaigns" / "shadows_of_the_custodian.json"


# ── Codex entries (Phase 25 §2.1) ──────────────────────────────────


CODEX_ENTRIES = [
    {
        "entry_id": "shaala_praxeum",
        "title": "Shaala Praxeum",
        "tag": "(History Lesson)",
        "body": (
            "The Shaala Praxeum is the New Republic's working-Jedi training "
            "facility — neither the secret refuge of the Resistance era nor "
            "the High Republic's radiant academies. It teaches by doing. "
            "Students walk patrol with their masters, mediate disputes in "
            "outer rim settlements, and stand the long watch with the "
            "Custodians of Records. The senior council includes Master "
            "Ailith Cor, whose patience is a pedagogical instrument, and "
            "Master Ren Voq, whose impatience is the same. The temple's "
            "stone is volcanic, imported from Mustafar at someone's quiet "
            "expense before the war ended. No one has ever explained why."
        ),
        "surface_when": {"requires_act_minimum": 1},
    },
    {
        "entry_id": "imperial_remnant_fragments",
        "title": "What Survived the Surrender",
        "tag": "(Reality)",
        "body": (
            "The official version of the Imperial collapse is that command "
            "structures dissolved when Coruscant fell. The reality is that "
            "they fragmented — into warlord enclaves, smuggling cartels, "
            "deniable wet-work cells, and at least three intelligence "
            "services that still file reports under names that no longer "
            "officially exist. The New Republic's Reintegration Office "
            "knows this. Its public position is that anyone willing to "
            "swear loyalty in front of a recording droid is a citizen. "
            "Its private position is more complicated."
        ),
        "surface_when": {"requires_act_minimum": 1},
    },
    {
        "entry_id": "imperial_remnant_official",
        "title": "Loyalty and Reintegration",
        "tag": "(Imperial Doctrine)",
        "body": (
            "The Reintegration Office maintains that loyalty oaths heal "
            "civic wounds. A former officer who swears the oath is a "
            "former officer. A former informer who swears the oath is "
            "a citizen. The doctrine refuses the language of crime, "
            "preferring the language of return. There are no Imperial "
            "fugitives in the New Republic — only citizens who have not "
            "yet been heard from. The doctrine survives because the "
            "alternative would require trials no one has the appetite for."
        ),
        "surface_when": {"requires_act_minimum": 1},
    },
    {
        "entry_id": "joran_veska",
        "title": "Joran Veska",
        "tag": "(Reputation)",
        "body": (
            "Among the senior students, Joran is the one who finishes other "
            "people's sentences without making them feel small. He is from "
            "Rann Veska's family — an older brother in the way that older "
            "brothers can be — and his presence at the Praxeum has the "
            "feel of a story everyone agreed not to tell yet. Masters "
            "approve of him. Other students orbit him. There is something "
            "in his attention that makes you want to be the version of "
            "yourself he seems to see."
        ),
        "surface_when": {"requires_act_minimum": 1},
    },
    {
        "entry_id": "tarsh_voll",
        "title": "Tarsh Voll",
        "tag": "(Crew Roster)",
        "body": (
            "Tarsh keeps an open seat at meals. She does not save it for "
            "anyone in particular; the seat is the point. She came in late "
            "to the Praxeum from a labor cooperative on Horizon Station — "
            "a place that values usefulness and treats sentiment as "
            "self-indulgence — and she left because she discovered she "
            "wanted to belong somewhere that could accommodate both. "
            "She has never asked you what you used to do. This is on "
            "purpose."
        ),
        "surface_when": {"requires_act_minimum": 1},
    },
    {
        "entry_id": "rann_veska",
        "title": "Rann Veska",
        "tag": "(Crew Roster)",
        "body": (
            "Rann is six standard years younger than her brother and treats "
            "this as a problem to be solved rather than a fact to be "
            "carried. She is a literalist — she will repeat what someone "
            "actually said back to them, without commentary, and watch what "
            "happens. Her training partner of choice is whoever is most "
            "willing to be wrong out loud. She is unsentimental about the "
            "Veska name, but she will put herself in front of it when it "
            "matters."
        ),
        "surface_when": {"requires_act_minimum": 1},
    },
    {
        "entry_id": "the_long_watch",
        "title": "The Long Watch",
        "tag": "(Holocron Fragment)",
        "body": (
            "The senior Custodian quoted Master Ailith on this once, and the "
            "students wrote it down: 'The long watch is not a vigil. A "
            "vigil ends when the dawn comes. The long watch is the form of "
            "attention that does not end — that is the work of staying "
            "with what is still becoming.' Whether the saying is properly "
            "Master Ailith's or whether she was repeating something older "
            "is a debate the masters seem disinclined to settle."
        ),
        "surface_when": {"requires_act_minimum": 2},
    },
    {
        "entry_id": "horizon_station",
        "title": "Horizon Station",
        "tag": "(History Lesson)",
        "body": (
            "Horizon Station is one of the larger stable cooperatives in "
            "the outer rim — a habitat assembled from three decommissioned "
            "Imperial dropships, lashed together over years by people who "
            "needed somewhere to be. It runs on a labor-credit economy and "
            "a council that rotates whether or not anyone particularly "
            "wants the seat. The Praxeum has a long-standing protocol of "
            "asking the council before sending students through. The "
            "council has a long-standing protocol of saying yes."
        ),
        "surface_when": {"requires_act_minimum": 1},
    },
    {
        "entry_id": "custodians_records",
        "title": "Custodians of Records",
        "tag": "(History Lesson)",
        "body": (
            "The Custodians of Records are an order older than the war. "
            "They were not Jedi exactly — though the line was always "
            "blurry — and they kept the kind of archives the Empire would "
            "have burned if it had thought to look for them. The senior "
            "Custodian at Shaala is one of perhaps twelve still living, "
            "and she does not advertise this. The records they keep are "
            "in part the reason the Praxeum exists where it does."
        ),
        "surface_when": {"requires_act_minimum": 2},
    },
    {
        "entry_id": "hux_shadow_cell",
        "title": "What the Office Won't Say",
        "tag": "(Whispers)",
        "body": (
            "There are people who say the Reintegration Office knows about "
            "a particular shadow cell — Imperial Intelligence holdovers, "
            "operating with deniable funding from at least two reputable "
            "members of the Senate — and that the Office's policy is to "
            "let it run. The argument is that watching is more useful than "
            "scattering. The counter-argument is that watching is what you "
            "tell yourself when you cannot bring yourself to act. Neither "
            "argument shows up in any official transcript."
        ),
        "surface_when": {"requires_act_minimum": 2},
    },
    {
        "entry_id": "drel_and_sona",
        "title": "Drel and Sona",
        "tag": "(Dossier)",
        "body": (
            "Field operatives. Drel: ex-Stormtrooper, defected during the "
            "Endor week, never officially registered as a defector, "
            "currently moves between three identities. Sona: human, "
            "mid-thirties, trained at the Imperial Academy on Carida, "
            "spent the surrender on a station nobody can find on any "
            "current map. They work together. They were close once. "
            "Whether they still are is a question even people who know "
            "them cannot quite answer."
        ),
        "surface_when": {"requires_act_minimum": 3},
    },
    {
        "entry_id": "what_belonging_costs",
        "title": "What Belonging Costs",
        "tag": "(Holocron Fragment)",
        "body": (
            "Quoted in a holocron fragment recovered from a temple ruined "
            "long before the Empire: 'To belong is to be claimed by what "
            "you have not yet earned, and to live in such a way that the "
            "claim becomes warranted. The work of belonging is the work "
            "of becoming someone the place can hold without strain.' The "
            "fragment is unattributed. Master Ailith uses it in her first "
            "lesson with new students."
        ),
        "surface_when": {"requires_act_minimum": 1},
    },
]


# ── Glossary entries (Phase 25 §3.6) ───────────────────────────────


GLOSSARY_ENTRIES = [
    {"term": "Praxeum", "short_definition": "Working-Jedi training facility — the New Republic-era model.",
     "long_definition": "A Praxeum trains by doing rather than by lecture. Students walk patrol, mediate disputes, and learn the discipline of attention from senior Jedi and Custodians."},
    {"term": "Custodian", "short_definition": "Member of the Custodians of Records — a pre-war archival order.",
     "long_definition": "Older than the Jedi-Sith conflict in its current form. Custodians kept records the Empire would have burned. The order survived in fragments."},
    {"term": "Holocron", "short_definition": "Crystal storage device for Force-related teachings.",
     "long_definition": "Holocrons can hold Jedi or Sith knowledge. Some respond only to specific users; some hold fragments rather than complete works."},
    {"term": "Custodians of Records", "short_definition": "An archival order older than the Republic-era Jedi.",
     "long_definition": "Their records are kept in repositories scattered across the galaxy. The Shaala Praxeum hosts one such repository in its lower levels."},
    {"term": "Reintegration Office", "short_definition": "New Republic body that processes former Imperials.",
     "long_definition": "The Reintegration Office's official position is that loyalty oaths heal civic wounds. Its private practice is more selective."},
    {"term": "Hutt", "short_definition": "A long-lived sentient species notorious for criminal enterprise.",
     "long_definition": ""},
    {"term": "Twi'lek", "short_definition": "Humanoid species native to Ryloth, recognizable by head-tails (lekku).",
     "long_definition": ""},
    {"term": "Bothan", "short_definition": "Mammalian species known for intelligence networks across the galaxy.",
     "long_definition": ""},
    {"term": "Devaronian", "short_definition": "Horned humanoid species; many serve in mercantile and labor trades.",
     "long_definition": ""},
    {"term": "Triumph", "short_definition": "A critical positive effect on a dice roll, on top of base success.",
     "long_definition": ""},
    {"term": "Despair", "short_definition": "A critical negative effect on a dice roll, on top of base failure.",
     "long_definition": ""},
    {"term": "Strain", "short_definition": "Mental and emotional fatigue. Overflowing strain incapacitates.",
     "long_definition": ""},
    {"term": "Soak", "short_definition": "Damage reduction from Brawn and armor.",
     "long_definition": ""},
    {"term": "Force commit", "short_definition": "Force dice held in reserve to power ongoing effects.",
     "long_definition": "Committed Force dice cannot be rolled. Committing a Force die reduces the protagonist's effective Force rating until released."},
    {"term": "Morality", "short_definition": "Light/Dark side alignment. 0 = full Dark. 100 = full Light.",
     "long_definition": ""},
    {"term": "Obligation", "short_definition": "Past debts the protagonist owes someone.",
     "long_definition": "When obligation activates, it pulls the protagonist back into the world they came from. High obligation lowers strain threshold."},
    {"term": "Duty", "short_definition": "Cause the protagonist owes themselves to.",
     "long_definition": ""},
    {"term": "Drel", "short_definition": "Ex-Stormtrooper field operative; defected during Endor week.",
     "long_definition": ""},
    {"term": "Sona", "short_definition": "Field operative; trained at the Imperial Academy on Carida.",
     "long_definition": ""},
    {"term": "Joran Veska", "short_definition": "Senior student at the Shaala Praxeum.",
     "long_definition": "Older brother of Rann Veska. Joran's mission and his warmth are equally real, which is part of the difficulty."},
    {"term": "Rann Veska", "short_definition": "Younger sister of Joran. A literalist by temperament.",
     "long_definition": ""},
    {"term": "Tarsh Voll", "short_definition": "Senior student. Came to the Praxeum from Horizon Station.",
     "long_definition": ""},
    {"term": "Brann Riako", "short_definition": "Senior student. Former Imperial pattern-reader, now using those habits to protect.",
     "long_definition": ""},
    {"term": "Lirah Tann", "short_definition": "Senior student. Field medic in training.",
     "long_definition": ""},
    {"term": "Cassen Vell", "short_definition": "Senior student. Inheritor of an Imperial-era family fortune.",
     "long_definition": ""},
    {"term": "Inya Vorn", "short_definition": "Senior student. Lightsaber and discipline focus.",
     "long_definition": ""},
    {"term": "Master Ailith Cor", "short_definition": "Senior Jedi at the Shaala Praxeum.",
     "long_definition": ""},
    {"term": "Master Ren Voq", "short_definition": "Senior Jedi at the Shaala Praxeum.",
     "long_definition": ""},
    {"term": "Horizon Station", "short_definition": "Outer-rim labor cooperative.",
     "long_definition": "An assembled habitat from decommissioned Imperial dropships, run on labor-credit economy."},
]


# ── Set-piece declarations (Phase 25 §2.8) ─────────────────────────


SET_PIECES = [
    {
        "anchor_id": "arrivals",
        "scene_title": "The Stone of the Praxeum",
        "word_budget_multiplier": 1.5,
        "visual_treatment": "title_card",
        "choice_count_recommendation": 4,
    },
    {
        "anchor_id": "long_watch",
        "scene_title": "The Long Watch",
        "word_budget_multiplier": 1.6,
        "visual_treatment": "scene_break",
        "choice_count_recommendation": 4,
    },
    {
        "anchor_id": "two_brothers",
        "scene_title": "Two Brothers",
        "word_budget_multiplier": 1.7,
        "visual_treatment": "title_card",
        "choice_count_recommendation": 5,
    },
    {
        "anchor_id": "custodians_hand",
        "scene_title": "The Custodian's Hand",
        "word_budget_multiplier": 1.7,
        "visual_treatment": "scene_break",
        "choice_count_recommendation": 5,
    },
    {
        "anchor_id": "what_remains",
        "scene_title": "What Remains",
        "word_budget_multiplier": 2.0,
        "visual_treatment": "title_card",
        "choice_count_recommendation": 5,
    },
]


# ── Personality lock moments (Phase 25 §2.5) ───────────────────────


PERSONALITY_LOCK_MOMENTS = [
    {
        "anchor_id": "long_watch",
        "prompt_text": (
            "The Custodian has asked you to take the long watch with her, "
            "alone in the lower archives, while everyone else sleeps. The "
            "things she will show you are not for the senior students. They "
            "are not for the masters either, exactly. Going forward, you "
            "carry this with you:"
        ),
        "belief_options": [
            {
                "belief_text": (
                    "I keep what is given to me. The Custodian chose me; I "
                    "honor that by holding the line of who knows."
                ),
                "axis_effects": {
                    "lone_wolf_crew_loyalist": +5,
                    "showy_quiet": -5,
                    "lawful_lawless": +5,
                },
                "voice_tag": "keeper",
            },
            {
                "belief_text": (
                    "I share what I learn with the people who matter. "
                    "Knowledge that cannot be carried by the people I love "
                    "is knowledge that does not protect them."
                ),
                "axis_effects": {
                    "lone_wolf_crew_loyalist": -8,
                    "direct_subtle": +5,
                },
                "voice_tag": "open",
            },
            {
                "belief_text": (
                    "I trust my own judgment about what to share, and when. "
                    "The Custodian is teaching me the discipline of choosing."
                ),
                "axis_effects": {
                    "reckless_cautious": -5,
                    "direct_subtle": -3,
                    "lawful_lawless": -3,
                },
                "voice_tag": "discerning",
            },
        ],
    },
    {
        "anchor_id": "two_brothers",
        "prompt_text": (
            "Joran has confessed everything. The mission, the names, the "
            "people on Coruscant who told him you were the leverage. He is "
            "asking you to choose. Going forward, you carry this with you:"
        ),
        "belief_options": [
            {
                "belief_text": (
                    "Joran's life is worth the cost of what he tried to take "
                    "from me. I will fight for him because I refuse to let "
                    "the people who used him be the ones who decide his end."
                ),
                "axis_effects": {
                    "lone_wolf_crew_loyalist": -10,
                    "reckless_cautious": +5,
                    "showy_quiet": +5,
                },
                "voice_tag": "redemptive",
            },
            {
                "belief_text": (
                    "Joran chose his side knowing the cost. I will report "
                    "him because the people who trusted me to be honest "
                    "deserve honesty, even when it hurts."
                ),
                "axis_effects": {
                    "lawful_lawless": +10,
                    "direct_subtle": +5,
                },
                "voice_tag": "lawful",
            },
            {
                "belief_text": (
                    "There is a third path. I can find a way that costs less "
                    "than either of the obvious answers — even if the price "
                    "of inventing it is mine to pay."
                ),
                "axis_effects": {
                    "direct_subtle": -8,
                    "reckless_cautious": -3,
                    "lone_wolf_crew_loyalist": +3,
                },
                "voice_tag": "third_path",
            },
        ],
    },
    {
        "anchor_id": "custodians_hand",
        "prompt_text": (
            "The Custodian is dying, and her last instruction is for you "
            "alone. The senior masters are scattered. Drel and Sona will be "
            "at the gate within the hour. Going forward, you carry this "
            "with you:"
        ),
        "belief_options": [
            {
                "belief_text": (
                    "I do what the Custodian asked, exactly. Her trust is "
                    "the form my obedience takes."
                ),
                "axis_effects": {
                    "lawful_lawless": +5,
                    "direct_subtle": +3,
                    "showy_quiet": -3,
                },
                "voice_tag": "faithful",
            },
            {
                "belief_text": (
                    "I do what she would have asked if she had known what "
                    "I know. The instruction was the form. The intent is the "
                    "thing I have to keep."
                ),
                "axis_effects": {
                    "lawful_lawless": -3,
                    "direct_subtle": -5,
                    "lone_wolf_crew_loyalist": +3,
                },
                "voice_tag": "interpretive",
            },
            {
                "belief_text": (
                    "I do what protects the people in this temple, even if "
                    "neither the Custodian nor the masters would have asked "
                    "me to. The temple is not the records. The people are."
                ),
                "axis_effects": {
                    "lone_wolf_crew_loyalist": -5,
                    "lawful_lawless": -8,
                    "reckless_cautious": +3,
                },
                "voice_tag": "people_first",
            },
        ],
    },
]


# ── Achievements (Phase 25 §2.7) ───────────────────────────────────


ACHIEVEMENTS = [
    {
        "achievement_id": "ach_arrivals_complete",
        "title": "Initiate of Shaala",
        "description": "Survived the first month at the Praxeum with your name and your name alone.",
        "visibility": "always_visible",
        "earn_condition": {"condition_type": "spine_anchor", "parameters": {"anchor_id": "arrivals"}},
    },
    {
        "achievement_id": "ach_long_watch",
        "title": "The Long Watch",
        "description": "Stood the long watch with the Custodian.",
        "visibility": "always_visible",
        "earn_condition": {"condition_type": "spine_anchor", "parameters": {"anchor_id": "long_watch"}},
    },
    {
        "achievement_id": "ach_two_brothers",
        "title": "Two Brothers",
        "description": "Faced what Joran chose, and chose in return.",
        "visibility": "always_visible",
        "earn_condition": {"condition_type": "spine_anchor", "parameters": {"anchor_id": "two_brothers"}},
    },
    {
        "achievement_id": "ach_custodians_hand",
        "title": "The Custodian's Hand",
        "description": "Honored the Custodian's last instruction, in your own way.",
        "visibility": "always_visible",
        "earn_condition": {"condition_type": "spine_anchor", "parameters": {"anchor_id": "custodians_hand"}},
    },
    {
        "achievement_id": "ach_what_remains",
        "title": "What Remains",
        "description": "Lived through the day after.",
        "visibility": "always_visible",
        "earn_condition": {"condition_type": "spine_anchor", "parameters": {"anchor_id": "what_remains"}},
    },
    {
        "achievement_id": "ach_codex_history",
        "title": "Student of the Real",
        "description": "Read every (History Lesson) page.",
        "visibility": "progress_visible",
        "earn_condition": {"condition_type": "codex", "parameters": {"tag": "(History Lesson)", "required_count": 3}},
    },
    {
        "achievement_id": "ach_codex_doctrine_vs_reality",
        "title": "The Discipline of Doubt",
        "description": "Read the matched (Imperial Doctrine) and (Reality) pages.",
        "visibility": "hidden_until_earned",
        "earn_condition": {"condition_type": "pattern", "parameters": {"achievement_id": "ach_codex_doctrine_vs_reality", "count": 2}},
    },
    {
        "achievement_id": "ach_joran_close",
        "title": "Brother in Practice",
        "description": "Earned Joran's deep trust before the unraveling.",
        "visibility": "progress_visible",
        "earn_condition": {"condition_type": "relationship", "parameters": {"npc_name": "Joran Veska", "disposition_minimum": 0.85}},
    },
    {
        "achievement_id": "ach_rann_close",
        "title": "Sister in Truth",
        "description": "Earned Rann's confidence — including the difficult kind.",
        "visibility": "progress_visible",
        "earn_condition": {"condition_type": "relationship", "parameters": {"npc_name": "Rann Veska", "disposition_minimum": 0.85}},
    },
    {
        "achievement_id": "ach_tarsh_close",
        "title": "Easy Belonging",
        "description": "Belonged at the Praxeum the way Tarsh wanted you to.",
        "visibility": "progress_visible",
        "earn_condition": {"condition_type": "relationship", "parameters": {"npc_name": "Tarsh Voll", "disposition_minimum": 0.85}},
    },
    {
        "achievement_id": "ach_force_sense_milestone",
        "title": "Reading the Room",
        "description": "Acquired Force Sense — the discipline of noticing.",
        "visibility": "hidden_until_earned",
        "earn_condition": {"condition_type": "force_power_milestone", "parameters": {"power_id": "sense"}},
    },
    {
        "achievement_id": "ach_force_move_milestone",
        "title": "Hand of the Force",
        "description": "Acquired Force Move.",
        "visibility": "hidden_until_earned",
        "earn_condition": {"condition_type": "force_power_milestone", "parameters": {"power_id": "move"}},
    },
    {
        "achievement_id": "ach_force_influence_milestone",
        "title": "Voice of the Force",
        "description": "Acquired Force Influence.",
        "visibility": "hidden_until_earned",
        "earn_condition": {"condition_type": "force_power_milestone", "parameters": {"power_id": "influence"}},
    },
    {
        "achievement_id": "ach_lock_long_watch",
        "title": "First Belief",
        "description": "Locked your first belief — the long watch decided who you become.",
        "visibility": "hidden_until_earned",
        "earn_condition": {"condition_type": "pattern", "parameters": {"achievement_id": "ach_lock_long_watch", "count": 1}},
    },
    {
        "achievement_id": "ach_pacifist_combat",
        "title": "The Restraint",
        "description": "Won three combat scenes without killing.",
        "visibility": "hidden_until_earned",
        "earn_condition": {"condition_type": "pattern", "parameters": {"achievement_id": "ach_pacifist_combat", "count": 3}},
    },
]


# ── Foreshadowing plants per act (Phase 25 §2.9) ────────────────────


# Indexed by act_number, list of {plant_act, payoff_act, plant_concept, payoff_concept}.
ACT_FORESHADOWING = {
    1: [
        {
            "plant_act": 1, "payoff_act": 3,
            "plant_concept": "Joran's small habit of finishing other people's sentences — read by the player as warmth, but in retrospect a tell of someone listening for what to say next.",
            "payoff_concept": "When Joran admits the mission, the gesture surfaces again — the same reflex, no longer warm.",
        },
        {
            "plant_act": 1, "payoff_act": 2,
            "plant_concept": "The volcanic stone of the Praxeum — imported from Mustafar, no one explains why. Briefly noticed in passing.",
            "payoff_concept": "The Custodian shows the protagonist that the volcanic stone is not decorative. It anchors a Custodian repository beneath the temple.",
        },
    ],
    2: [
        {
            "plant_act": 2, "payoff_act": 4,
            "plant_concept": "An unexplained line in the Custodian's archive: 'the hand that stays' — touched without comment.",
            "payoff_concept": "The Custodian's last instruction includes that phrase. The protagonist now knows what it means.",
        },
    ],
    3: [
        {
            "plant_act": 3, "payoff_act": 5,
            "plant_concept": "Drel says, almost casually, that his name was given to him by an officer he has never met. A throwaway line.",
            "payoff_concept": "In the final act, the protagonist meets that officer — and recognizes the gift as a leash.",
        },
    ],
}


# ── Add title_visible to acts ──────────────────────────────────────


ACT_TITLES = {
    1: "Arrivals",
    2: "The Long Watch",
    3: "Two Brothers",
    4: "The Custodian's Hand",
    5: "What Remains",
}


def merge_phase25_content(spine: dict) -> dict:
    """Augment spine with Phase 25 content; preserves authored entries."""
    # Codex
    existing_codex = {e.get("entry_id") for e in spine.get("codex", [])}
    new_codex = list(spine.get("codex", []))
    for entry in CODEX_ENTRIES:
        if entry["entry_id"] not in existing_codex:
            new_codex.append(entry)
    spine["codex"] = new_codex

    # Glossary
    existing_terms = {(e.get("term") or "").lower() for e in spine.get("glossary", [])}
    new_glossary = list(spine.get("glossary", []))
    for entry in GLOSSARY_ENTRIES:
        if entry["term"].lower() not in existing_terms:
            new_glossary.append(entry)
    spine["glossary"] = new_glossary

    # Set pieces
    existing_set = {sp.get("anchor_id") for sp in spine.get("set_pieces", [])}
    new_set = list(spine.get("set_pieces", []))
    for sp in SET_PIECES:
        if sp["anchor_id"] not in existing_set:
            new_set.append(sp)
    spine["set_pieces"] = new_set

    # Personality lock moments
    existing_locks = {m.get("anchor_id") for m in spine.get("personality_lock_moments", [])}
    new_locks = list(spine.get("personality_lock_moments", []))
    for m in PERSONALITY_LOCK_MOMENTS:
        if m["anchor_id"] not in existing_locks:
            new_locks.append(m)
    spine["personality_lock_moments"] = new_locks

    # Achievements
    existing_ach = {a.get("achievement_id") for a in spine.get("achievements", [])}
    new_ach = list(spine.get("achievements", []))
    for a in ACHIEVEMENTS:
        if a["achievement_id"] not in existing_ach:
            new_ach.append(a)
    spine["achievements"] = new_ach

    # Expected relationship count — protagonist + 7 core party = 8 slots
    if "expected_relationship_count" not in spine:
        spine["expected_relationship_count"] = 8

    # Per-act foreshadowing + title
    acts = spine.get("acts", [])
    for act in acts:
        n = act.get("number", 0)
        # Title
        if not act.get("title_visible"):
            act["title_visible"] = ACT_TITLES.get(n, act.get("name", ""))
        # Foreshadowing
        existing_fs = {
            (e.get("plant_act"), e.get("payoff_act"), e.get("plant_concept", "")[:40])
            for e in act.get("foreshadowing_plants") or []
        }
        new_fs = list(act.get("foreshadowing_plants", []) or [])
        for fs in ACT_FORESHADOWING.get(n, []):
            key = (fs["plant_act"], fs["payoff_act"], fs["plant_concept"][:40])
            if key not in existing_fs:
                new_fs.append(fs)
        act["foreshadowing_plants"] = new_fs

    return spine


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    if not path.exists():
        print(f"Spine not found: {path}", file=sys.stderr)
        sys.exit(2)
    # Read with encoding fallback (file may have legacy windows-1252 bytes)
    try:
        with path.open(encoding="utf-8") as f:
            spine = json.load(f)
    except UnicodeDecodeError:
        with path.open(encoding="cp1252") as f:
            spine = json.load(f)
    spine = merge_phase25_content(spine)
    # Write ASCII-safe so tests that open without explicit encoding (e.g.
    # default cp1252 on Windows) still work — JSON's \\uXXXX escapes
    # preserve all characters lossless-ly.
    with path.open("w", encoding="utf-8") as f:
        json.dump(spine, f, indent=2, ensure_ascii=True)
    print(f"Phase 25 content merged into {path}")
    print(f"  codex entries:           {len(spine.get('codex', []))}")
    print(f"  glossary terms:          {len(spine.get('glossary', []))}")
    print(f"  set pieces:              {len(spine.get('set_pieces', []))}")
    print(f"  personality lock moments:{len(spine.get('personality_lock_moments', []))}")
    print(f"  achievements:            {len(spine.get('achievements', []))}")
    fs_total = sum(
        len(a.get("foreshadowing_plants") or [])
        for a in spine.get("acts", [])
    )
    print(f"  foreshadowing plants:    {fs_total}")


if __name__ == "__main__":
    main()
