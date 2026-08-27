"""Rebrand this template for your own project and domain.

Shows its plan by default; nothing changes without --apply:

    uv run python scripts/init_domain.py \
        --name "Membrane Materials KB" \
        --description "Membrane chemistry and performance for water treatment" \
        --apply

What it does (and all it does):

1. Sets your project name/description in pyproject.toml and in
   domain/domain.yaml (the demo ontology stays in place as a worked
   example for you to edit; see docs/bring-your-own-domain.md).
2. Resets domain/eval_seed_questions.jsonl to a guided blank, so the
   demo's ground truth never masquerades as yours.
3. Prints the checklist of what to edit next.

The Python package stays ``sci_rag`` on purpose (see ADR 0004): keeping
the import path lets you diff against, and pull improvements from, the
upstream template.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

SEED_TEMPLATE = """\
# Ground-truth questions for the evaluation harness (one JSON object per line).
# Write 10 to 20 questions a domain expert can vouch for. Format:
#
# {"id": "unique-slug",
#  "question": "As a user would ask it",
#  "reference_answer": "What a correct answer must say",
#  "reference_titles": ["Exact document title that contains the answer"],
#  "evidence_phrases": ["a distinctive string from the answering passage", "42.7 g/L"],
#  "tags": ["your-label"]}
#
# Include one question the corpus canNOT answer, tagged "unanswerable",
# as an honesty probe. See docs/evaluation.md for advice on writing these.
"""


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "my-sci-rag"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="Your project's human name.")
    parser.add_argument("--description", required=True, help="One sentence about the domain.")
    parser.add_argument("--slug", help="Package/distribution slug (default: derived from name).")
    parser.add_argument("--apply", action="store_true", help="Actually write changes.")
    args = parser.parse_args()

    slug = args.slug or _slugify(args.name)
    changes: list[tuple[Path, str, str]] = []

    pyproject = REPO_ROOT / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    new_text = re.sub(r'(?m)^name = ".*"$', f'name = "{slug}"', text, count=1)
    new_text = re.sub(
        r'(?m)^description = ".*"$', f'description = "{args.description}"', new_text, count=1
    )
    if new_text != text:
        changes.append((pyproject, "project name and description", new_text))

    domain_yaml = REPO_ROOT / "domain" / "domain.yaml"
    dtext = domain_yaml.read_text(encoding="utf-8")
    new_dtext = re.sub(r'(?m)^name: ".*"$', f'name: "{args.name}"', dtext, count=1)
    new_dtext = re.sub(
        r"(?ms)^description: >\n(?:  .*\n)+",
        f"description: >\n  {args.description}\n",
        new_dtext,
        count=1,
    )
    if new_dtext != dtext:
        changes.append((domain_yaml, "domain name and description", new_dtext))

    seeds = REPO_ROOT / "domain" / "eval_seed_questions.jsonl"
    if seeds.read_text(encoding="utf-8") != SEED_TEMPLATE:
        changes.append((seeds, "reset seed questions to a guided blank", SEED_TEMPLATE))

    if not changes:
        print("Nothing to change; already initialized with these values.")
        return 0

    for path, what, _ in changes:
        print(
            f"{'WILL CHANGE' if not args.apply else 'CHANGED'}: {path.relative_to(REPO_ROOT)} ({what})"
        )

    if not args.apply:
        print("\nDry run. Re-run with --apply to write these changes.")
        return 0

    for path, _, content in changes:
        path.write_text(content, encoding="utf-8")

    print(
        f"""
Done. {args.name} is yours. Next, in order:

  1. Edit domain/domain.yaml: your entity types, relation types, and
     query classes (the demo ontology is still there as a worked example).
  2. Skim domain/prompts/ and tune the wording to your field.
  3. Put documents in data/raw/ and write a corpus manifest.
  4. Write your seed questions in domain/eval_seed_questions.jsonl.
  5. Rewrite README.md's opening for your project.

The full walkthrough: docs/bring-your-own-domain.md
"""
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
