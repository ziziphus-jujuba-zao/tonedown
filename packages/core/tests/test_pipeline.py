import pytest
from tonedown import Guard, Item
from tonedown.schema import Action, Category


def test_grade_applies_policy_and_language(fake_backend):
    guard = Guard(fake_backend, policy="balanced")
    v_ok, v_bad = guard.grade(["这集节奏太好了", "OP is an idiot"])
    assert v_ok.action is Action.PASS and v_ok.lang == "zh"
    assert v_bad.action is Action.REVIEW and v_bad.level_argmax == 2
    assert v_bad.top_category is Category.HARASSMENT and v_bad.lang == "en"


def test_cache_and_dedupe(fake_backend):
    guard = Guard(fake_backend)
    first = guard.grade(["same text", "same  text", "other"])
    assert fake_backend.calls == [["same text", "other"]]  # normalized duplicates are sent once
    assert [v.cached for v in first] == [False, False, False]
    second = guard.grade(["same text"])
    assert second[0].cached is True and second[0].input_tokens == 0
    assert len(fake_backend.calls) == 1


def test_lexicon_floors_level_and_adds_reason(fake_backend):
    guard = Guard(fake_backend, policy="balanced")
    (v,) = guard.grade([Item(id="x", text="楼主nmsl")])
    assert v.level_argmax >= 2
    assert v.categories[Category.HARASSMENT] >= 0.9
    assert any(r.startswith("lexicon:zh:") for r in v.reasons)


@pytest.mark.asyncio
async def test_async_path(fake_backend):
    guard = Guard(fake_backend, policy="strict")
    verdicts = await guard.agrade(["you idiot"])
    assert verdicts[0].action is Action.BLOCK


def _verdict(categories):
    from tonedown.schema import Verdict

    return Verdict(
        id="t",
        text_hash="h",
        lang="en",
        level=3.0,
        level_argmax=3,
        level_probs=[0, 0, 0, 1, 0],
        categories=categories,
        targeted=0.9,
        confidence=0.9,
        backend="fake",
    )


def test_threat_is_labelled_violence_even_when_harassment_is_more_probable():
    v = _verdict({Category.HARASSMENT: 0.97, Category.VIOLENCE: 0.93, Category.SPAM: 0.01})
    assert v.present == [Category.HARASSMENT, Category.VIOLENCE]
    assert v.top_category is Category.VIOLENCE


def test_borderline_secondary_category_does_not_steal_the_label():
    v = _verdict({Category.HARASSMENT: 0.96, Category.SEXUAL: 0.55})
    assert v.top_category is Category.HARASSMENT
