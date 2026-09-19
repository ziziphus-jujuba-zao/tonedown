from tonedown.policy import Policy, builtin_policies, load_policy
from tonedown.schema import Action, Category


def test_builtins_load():
    assert {"balanced", "strict", "relaxed"} <= set(builtin_policies())
    assert load_policy("strict").block_level == 2.0


def test_balanced_levels():
    p = load_policy("balanced")
    none = {c: 0.0 for c in Category}
    assert p.decide(0.3, 0.9, none) is Action.PASS
    assert p.decide(2.1, 0.9, none) is Action.REVIEW
    assert p.decide(3.5, 0.9, none) is Action.BLOCK


def test_low_confidence_block_becomes_review():
    p = load_policy("balanced")
    assert p.decide(3.5, 0.4, {c: 0.0 for c in Category}) is Action.REVIEW


def test_category_min_and_max_actions():
    p = Policy(
        name="t",
        category_min_action={Category.SPAM: Action.BLOCK},
        category_max_action={Category.SELF_HARM: Action.REVIEW},
    )
    spam = {c: (0.9 if c is Category.SPAM else 0.0) for c in Category}
    assert p.decide(1.0, 0.9, spam) is Action.BLOCK
    harm = {c: (0.9 if c is Category.SELF_HARM else 0.0) for c in Category}
    assert p.decide(3.9, 0.95, harm) is Action.REVIEW
