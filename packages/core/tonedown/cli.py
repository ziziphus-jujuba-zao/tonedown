"""Command line: `tonedown grade "text" ...`, `tonedown policies`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tonedown.env import load_dotenv
from tonedown.pipeline import Guard, default_backend
from tonedown.policy import builtin_policies, load_policy
from tonedown.schema import Item


def _read_inputs(args: argparse.Namespace) -> list[str]:
    texts: list[str] = list(args.text)
    if args.file:
        texts.extend(
            line.rstrip("\n") for line in Path(args.file).read_text(encoding="utf-8").splitlines() if line.strip()
        )
    if args.stdin or (not texts and not sys.stdin.isatty()):
        texts.extend(line.rstrip("\n") for line in sys.stdin if line.strip())
    return texts


def cmd_grade(args: argparse.Namespace) -> int:
    load_dotenv()
    texts = _read_inputs(args)
    if not texts:
        print("Nothing to grade. Pass texts, --file, or pipe lines on stdin.", file=sys.stderr)
        return 2
    backend = None
    if args.backend == "lexicon":
        from tonedown.backends.lexicon import LexiconBackend

        backend = LexiconBackend()
    elif args.backend == "jev":
        from tonedown.backends.jev import JevBackend

        backend = JevBackend()
    guard = Guard(backend or default_backend(), policy=args.policy)
    items = [Item(id=str(i), text=t, lang=args.lang) for i, t in enumerate(texts)]
    verdicts = guard.grade(items)
    if args.json:
        print(json.dumps([v.model_dump(mode="json") for v in verdicts], ensure_ascii=False, indent=2))
        return 0
    print(f"{'level':>5} {'action':7} {'category':11} {'target':>6} {'conf':>5} {'lang':4}  text")
    for v, t in zip(verdicts, texts, strict=True):
        cat = v.top_category.value if v.top_category else "-"
        preview = t if len(t) <= 60 else t[:57] + "..."
        print(
            f"{v.level:5.2f} {v.action or '-':7} {cat:11} {v.targeted:6.2f} {v.confidence:5.2f} {v.lang:4}  {preview}"
        )
    tokens = sum(v.input_tokens for v in verdicts)
    print(
        f"\n{len(verdicts)} items, backend {guard.backend.name}, {tokens:.0f} input tokens, {sum(v.cached for v in verdicts)} cached"  # noqa: E501
    )
    return 0


def cmd_policies(args: argparse.Namespace) -> int:
    for name in builtin_policies():
        p = load_policy(name)
        print(f"{name:10} block>={p.block_level} review>={p.review_level} min_conf={p.min_confidence}  {p.description}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tonedown", description="Grade text from safe (0) to dangerous (4).")
    sub = parser.add_subparsers(dest="command", required=True)
    g = sub.add_parser("grade", help="grade texts")
    g.add_argument("text", nargs="*", help="texts to grade")
    g.add_argument("--file", help="file with one text per line")
    g.add_argument("--stdin", action="store_true", help="read one text per line from stdin")
    g.add_argument("--policy", default="balanced", help="built-in policy name or path to a yaml file")
    g.add_argument("--backend", choices=["auto", "jev", "lexicon"], default="auto")
    g.add_argument("--lang", help="force a language code instead of detecting")
    g.add_argument("--json", action="store_true", help="print full verdicts as JSON")
    g.set_defaults(func=cmd_grade)
    p = sub.add_parser("policies", help="list built-in policies")
    p.set_defaults(func=cmd_policies)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
