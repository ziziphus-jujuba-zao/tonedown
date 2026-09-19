"""Run a backend over the golden set and report per-language quality, latency and cost.

uv run eval/run_eval.py                    # backend from TONEDOWN_BACKEND / TYPESAFE_API_KEY
uv run eval/run_eval.py --backend lexicon  # offline baseline
uv run eval/run_eval.py --langs zh,en --policy strict
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "packages" / "core"))

from tonedown import Guard, Item, MemoryCache, load_policy  # noqa: E402
from tonedown.env import load_dotenv  # noqa: E402
from tonedown.schema import Action, Category  # noqa: E402

GOLDEN = ROOT / "eval" / "golden"
REPORTS = ROOT / "eval" / "reports"


def load_golden(langs: set[str] | None) -> dict[str, list[dict]]:
    data: dict[str, list[dict]] = {}
    for path in sorted(GOLDEN.glob("*.jsonl")):
        if langs and path.stem not in langs:
            continue
        data[path.stem] = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return data


def spearman(a: list[float], b: list[float]) -> float:
    def ranks(xs: list[float]) -> list[float]:
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        r = [0.0] * len(xs)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return r

    if len(a) < 2:
        return float("nan")
    ra, rb = ranks(a), ranks(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb, strict=True))
    va = sum((x - ma) ** 2 for x in ra) ** 0.5
    vb = sum((y - mb) ** 2 for y in rb) ** 0.5
    return cov / (va * vb) if va and vb else float("nan")


def f1(expected: list[bool], predicted: list[bool]) -> float:
    tp = sum(e and p for e, p in zip(expected, predicted, strict=True))
    fp = sum((not e) and p for e, p in zip(expected, predicted, strict=True))
    fn = sum(e and (not p) for e, p in zip(expected, predicted, strict=True))
    return 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else float("nan")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["auto", "jev", "lexicon"], default="auto")
    parser.add_argument("--langs", help="comma separated language codes")
    parser.add_argument("--policy", default="balanced")
    parser.add_argument("--batch", type=int, default=16)
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")

    backend = None
    if args.backend == "lexicon":
        from tonedown.backends.lexicon import LexiconBackend

        backend = LexiconBackend()
    elif args.backend == "jev":
        from tonedown.backends.jev import JevBackend

        backend = JevBackend(batch_size=args.batch)
    guard = Guard(backend, policy=args.policy, cache=MemoryCache())
    policy = load_policy(args.policy)
    golden = load_golden(set(args.langs.split(",")) if args.langs else None)

    rows: list[dict] = []
    mistakes: list[str] = []
    for lang, items in golden.items():
        t0 = time.perf_counter()
        verdicts = guard.grade([Item(id=it["id"], text=it["text"], lang=lang) for it in items])
        elapsed = (time.perf_counter() - t0) * 1000
        exp_levels = [float(it["level"]) for it in items]
        pred_levels = [v.level for v in verdicts]
        exact = sum(v.level_argmax == it["level"] for v, it in zip(verdicts, items, strict=True))
        within1 = sum(abs(v.level_argmax - it["level"]) <= 1 for v, it in zip(verdicts, items, strict=True))
        cat_ok = 0
        for v, it in zip(verdicts, items, strict=True):
            expected = set(it.get("categories", []))
            present = {c.value for c in v.present}
            top = v.top_category.value if v.top_category else None
            cat_ok += (expected <= present) if expected else (not present)
            if abs(v.level_argmax - it["level"]) >= 2:
                mistakes.append(f"{it['id']}: expected {it['level']}, got {v.level:.2f} ({top}) · {it['text'][:60]}")
        targeted_ok = sum(
            (v.targeted >= 0.5) == bool(it.get("targeted")) for v, it in zip(verdicts, items, strict=True)
        )
        exp_actions = [
            policy.decide(float(it["level"]), 1.0, {Category(c): 1.0 for c in it.get("categories", [])}) for it in items
        ]
        false_blocks = sum(
            e is Action.PASS and v.action is Action.BLOCK for e, v in zip(exp_actions, verdicts, strict=True)
        )
        misses = sum(e is Action.BLOCK and v.action is Action.PASS for e, v in zip(exp_actions, verdicts, strict=True))
        rows.append(
            {
                "lang": lang,
                "n": len(items),
                "exact": exact / len(items),
                "within1": within1 / len(items),
                "f1_l2": f1([e >= 2 for e in exp_levels], [p >= 1.5 for p in pred_levels]),
                "spearman": spearman(exp_levels, pred_levels),
                "cat": cat_ok / len(items),
                "targeted": targeted_ok / len(items),
                "false_blocks": false_blocks,
                "misses": misses,
                "ms_per_item": elapsed / len(items),
                "tokens_per_item": sum(v.input_tokens for v in verdicts) / len(items),
            }
        )

    header = "| lang | n | exact | ±1 | F1(level≥2) | Spearman | category | targeted | false blocks | misses | ms/item | tokens/item |"  # noqa: E501
    lines = [
        f"# Eval {date.today()} · backend `{guard.backend.name}` · policy `{policy.name}`",
        "",
        header,
        "|" + "---|" * 12,
    ]
    for r in rows:
        lines.append(
            f"| {r['lang']} | {r['n']} | {r['exact']:.2f} | {r['within1']:.2f} | {r['f1_l2']:.2f} | {r['spearman']:.2f} | {r['cat']:.2f} | "  # noqa: E501
            f"{r['targeted']:.2f} | {r['false_blocks']} | {r['misses']} | {r['ms_per_item']:.0f} | {r['tokens_per_item']:.0f} |"  # noqa: E501
        )
    total = sum(r["n"] for r in rows)
    if total:
        lines.append(
            f"| **all** | {total} | {sum(r['exact'] * r['n'] for r in rows) / total:.2f} | {sum(r['within1'] * r['n'] for r in rows) / total:.2f} | "  # noqa: E501
            f"| | {sum(r['cat'] * r['n'] for r in rows) / total:.2f} | {sum(r['targeted'] * r['n'] for r in rows) / total:.2f} | "  # noqa: E501
            f"{sum(r['false_blocks'] for r in rows)} | {sum(r['misses'] for r in rows)} | | |"
        )
    if mistakes:
        lines += ["", "## Off by two or more", ""] + [f"- {m}" for m in mistakes]
    report = "\n".join(lines)
    print(report)
    REPORTS.mkdir(exist_ok=True)
    out = REPORTS / f"{date.today()}-{guard.backend.name.replace(':', '-')}.md"
    out.write_text(report + "\n", encoding="utf-8")
    print(f"\nwritten to {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
