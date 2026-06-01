#!/usr/bin/env python3
"""OSHA Fall Protection Quiz Generator.

Reads question data from data/osha_questions.json, renders it into
the Jinja2 template at template/index.html.jinja, and writes the
final HTML to output/index.html.
"""

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "data" / "osha_questions.json"
TEMPLATE_DIR = ROOT / "template"
OUTPUT_DIR = ROOT / "output"
OUTPUT_FILE = OUTPUT_DIR / "index.html"


def load_data(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def render(data: dict) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("index.html.jinja")
    return template.render(**data)


def write_output(html: str, path: Path) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)


def main() -> None:
    data = load_data(DATA_FILE)
    print(f"📄 Loaded {len(data.get('practice_questions', []))} questions from {DATA_FILE.name}")

    html = render(data)
    write_output(html, OUTPUT_FILE)
    print(f"✅ Generated {OUTPUT_FILE}")
    print(f"   Size: {len(html):,} bytes")


if __name__ == "__main__":
    main()
