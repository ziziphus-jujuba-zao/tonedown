"""Policies turn probabilities into actions. The engine never decides; the policy does.

A platform maps to pass / review / block. The browser tools use their own slider instead, so the same
verdict can be blocked on one site and merely blurred for one user on another.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from tonedown.schema import Action, Category, stronger, weaker

_BUILTIN_DIR = Path(__file__).with_name("policies")


class Policy(BaseModel):
    name: str
    description: str = ""
    block_level: float = 3.0
    """Expected level at or above which the content is blocked."""
    review_level: float = 2.0
    """Expected level at or above which the content goes to review."""
    min_confidence: float = 0.6
    """Below this confidence a block is downgraded to review; never silently remove what the model is unsure about."""
    category_threshold: float = 0.7
    """A category counts as present when its probability reaches this."""
    category_min_action: dict[Category, Action] = Field(default_factory=dict)
    """At least this action when the category is present (e.g. spam: block)."""
    category_max_action: dict[Category, Action] = Field(default_factory=dict)
    """At most this action when the category is present (e.g. self_harm: review, so cries for help reach a human)."""

    def decide(self, level: float, confidence: float, categories: dict[Category, float]) -> Action:
        action = Action.PASS
        if level >= self.block_level:
            action = Action.BLOCK if confidence >= self.min_confidence else Action.REVIEW
        elif level >= self.review_level:
            action = Action.REVIEW
        present = [cat for cat, p in categories.items() if p >= self.category_threshold]
        for cat in present:
            if cat in self.category_min_action:
                action = stronger(action, self.category_min_action[cat])
        for cat in present:
            if cat in self.category_max_action:
                action = weaker(action, self.category_max_action[cat])
        return action


def builtin_policies() -> list[str]:
    return sorted(p.stem for p in _BUILTIN_DIR.glob("*.yaml"))


def load_policy(spec: str | Path | Policy | dict) -> Policy:
    """Accept a built-in name, a path to a yaml file, a dict, or a Policy."""
    if isinstance(spec, Policy):
        return spec
    if isinstance(spec, dict):
        return Policy.model_validate(spec)
    path = Path(spec)
    if not path.suffix:
        path = _BUILTIN_DIR / f"{spec}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No policy named {spec!r}; built-ins are {builtin_policies()}")
    with path.open(encoding="utf-8") as fh:
        return Policy.model_validate(yaml.safe_load(fh))
