"""The grading rubric, written once in English. Content can be in any language.

Jev answers every question in one call, in parallel and in isolation, so each text gets one Score
(the level), one Noul per category (multi-label) and one Noul for "targets a specific person".
Every batch also carries a shared `context` entry saying what kind of text this is.
"""

from __future__ import annotations

from typesafe_sdk import Noul, Question, Score

from tonedown.schema import Category

CONTEXT = (
    "Comments and bullet comments (danmaku) posted under videos. Memes, in-jokes, exaggerated reactions and "
    "repeated characters are normal here. Insults and threats still count when they are phrased casually."
)
"""Shared state entry sent with every batch; the risk question reads each comment in this context."""

LEVELS: list[str] = [
    "Safe: ordinary chat and reactions, laughter or screaming (哈哈哈, 啊啊啊, www, lol, 666), repeated characters, "
    "emoji and symbols, memes, in-jokes and slang used playfully, lyrics, game or product names, and opinions, "
    "complaints or harsh criticism of a work that do not attack a specific person or group",
    "Mild: mild profanity, a rude tone, or mocking someone's opinion (卧槽, tm, damn, wtf, 'this take is dumb'), "
    "without insulting the person",
    "Moderate: insults or harassment aimed at a person, crude sexual remarks, scam or advertising spam",
    "Severe: hate speech or slurs against a group, sexual content involving minors or non-consent, wishing or "
    "glorifying violence, doxxing, offering drugs, weapons or fraud services",
    "Dangerous: credible or implied threats of violence against a person (for example saying you know where they "
    "live), expressing or encouraging suicide or self-harm, instructions that enable serious harm or crimes",
]

CATEGORIES: dict[Category, str] = {
    Category.SPAM: "advertising, scams, referral codes, link farming or repeated promotional text",
    Category.HARASSMENT: "insults, mockery, bullying or intimidation aimed at a specific person",
    Category.HATE: "attacks or slurs against a group defined by ethnicity, nationality, region, religion, "
    "gender, sexuality or disability",
    Category.SEXUAL: "sexually explicit or lewd content, or sexual remarks about a person",
    Category.VIOLENCE: "threats, incitement or glorification of physical violence",
    Category.SELF_HARM: "suicide or self-harm, whether expressed by the author or encouraged towards someone",
    Category.ILLEGAL: "facilitating drugs, weapons, fraud, hacking or other serious crimes",
}


def questions(key: str) -> dict[str, Question]:
    """Questions about the state entry named `key` (for example `c3`)."""
    q: dict[str, Question] = {
        f"{key}_risk": Score(
            instructions=f"How harmful is the comment `{key}`, read in `context`? It may be in any language. "
            "Judge what the comment does to people, not the topic it discusses.",
            criteria=LEVELS,
        ),
        f"{key}_targeted": Noul(
            instructions=f"Does the comment `{key}` attack, threaten or demean a specific person, "
            "such as the author of the post or another commenter?",
        ),
    }
    for cat, desc in CATEGORIES.items():
        q[f"{key}_cat_{cat.value}"] = Noul(instructions=f"Is the comment `{key}` an instance of {cat.value}: {desc}?")
    return q
