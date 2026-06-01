#!/usr/bin/env python3
"""
GSC Long-Tail Attack Script
用法: python3 gsc_attack.py "osha subpart m guardrail height requirements 2026" [--num 20] [--mode bonus]
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def keyword_to_slug_topic(keyword: str) -> tuple[str, str]:
    """纯字符串处理，不调外部 API"""
    # Topic: 首字母大写 + 末尾加 " Quiz"
    topic = keyword.strip().title() + " Quiz"
    # Slug: 小写 + 非字母数字替换为 - + 去重 - + 去首尾 - + max 60 chars
    slug = re.sub(r"[^a-z0-9]+", "-", keyword.strip().lower())
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")[:60]
    return slug, topic


def main():
    parser = argparse.ArgumentParser(description="GSC Long-Tail Attack — 一键长尾词攻击脚本")
    parser.add_argument("keyword", type=str, help="GSC 长尾关键词")
    parser.add_argument("--num", type=int, default=20, help="题量 (10-40, default 20)")
    parser.add_argument("--mode", type=str, default="bonus", choices=["bonus", "chapter"], help="模式 (default bonus)")
    args = parser.parse_args()

    if not (10 <= args.num <= 40):
        print("❌ --num 范围: 10-40")
        sys.exit(1)

    slug, topic = keyword_to_slug_topic(args.keyword)
    print(f"📎 Keyword: {args.keyword}")
    print(f"   Slug: {slug}")
    print(f"   Topic: {topic}")
    print(f"   Mode: {args.mode}")
    print(f"   Questions: {args.num}")


if __name__ == "__main__":
    main()
