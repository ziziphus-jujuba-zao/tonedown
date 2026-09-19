"""Local backend on Qwen3Guard-Gen (Apache 2.0). EXPERIMENTAL and not yet exercised in this repo.

Qwen3Guard answers with a safety label (Safe / Controversial / Unsafe) and a category list; this maps
them onto tonedown's 0-4 levels with fixed probability profiles, so confidence is a constant.
Install with `pip install "tonedown[local]"` and pass model_id="Qwen/Qwen3Guard-Gen-0.6B".
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from tonedown.backends.base import Backend
from tonedown.schema import Category, RawVerdict

_SAFETY = re.compile(r"Safety:\s*(Safe|Unsafe|Controversial)", re.IGNORECASE)
_CATEGORIES = re.compile(r"Categories:\s*(.+)", re.IGNORECASE)

_LEVEL_PROFILE = {
    "safe": [0.85, 0.10, 0.04, 0.01, 0.00],
    "controversial": [0.10, 0.30, 0.40, 0.15, 0.05],
    "unsafe": [0.00, 0.05, 0.25, 0.50, 0.20],
}
_CATEGORY_MAP = {
    "violent": Category.VIOLENCE,
    "non-violent illegal acts": Category.ILLEGAL,
    "sexual content or sexual acts": Category.SEXUAL,
    "suicide & self-harm": Category.SELF_HARM,
    "unethical acts": Category.HARASSMENT,
}


def parse_output(text: str) -> tuple[str, list[str]]:
    safety = _SAFETY.search(text)
    cats = _CATEGORIES.search(text)
    label = safety.group(1).lower() if safety else "safe"
    names = [c.strip().lower() for c in cats.group(1).split(",")] if cats else []
    return label, [n for n in names if n and n != "none"]


def to_raw(label: str, names: list[str], backend_name: str) -> RawVerdict:
    categories = {cat: 0.05 for cat in Category}
    for name in names:
        mapped = _CATEGORY_MAP.get(name)
        if mapped:
            categories[mapped] = 0.9
    return RawVerdict(
        level_probs=_LEVEL_PROFILE[label],
        categories=categories,
        targeted=0.5 if label != "safe" else 0.05,
        confidence=0.7,
        backend=backend_name,
    )


class Qwen3GuardBackend(Backend):
    def __init__(
        self, model_id: str = "Qwen/Qwen3Guard-Gen-0.6B", device: str | None = None, max_new_tokens: int = 64
    ) -> None:
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as error:  # pragma: no cover - optional dependency
            raise RuntimeError('Qwen3GuardBackend needs `pip install "tonedown[local]"`') from error
        self.name = f"qwen3guard:{model_id.rsplit('/', 1)[-1]}"
        self.max_new_tokens = max_new_tokens
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype="auto")
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)

    def _generate(self, text: str) -> str:
        messages: list[dict[str, Any]] = [{"role": "user", "content": text}]
        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.tokenizer([prompt], return_tensors="pt").to(self.device)
        generated = self.model.generate(**inputs, max_new_tokens=self.max_new_tokens, do_sample=False)
        new_tokens = generated[0][len(inputs.input_ids[0]) :]
        return self.tokenizer.decode(new_tokens, skip_special_tokens=True)

    def grade(self, texts: Sequence[str]) -> list[RawVerdict]:
        return [to_raw(*parse_output(self._generate(t)), self.name) for t in texts]
