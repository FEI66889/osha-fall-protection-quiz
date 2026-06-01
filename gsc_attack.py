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

sys.path.insert(0, str(ROOT))

import config  # noqa
from build_site import get_client, call_claude  # type: ignore  # noqa


def keyword_to_slug_topic(keyword: str) -> tuple[str, str]:
    """纯字符串处理，不调外部 API"""
    # Topic: 首字母大写 + 末尾加 " Quiz"
    topic = keyword.strip().title() + " Quiz"
    # Slug: 小写 + 非字母数字替换为 - + 去重 - + 去首尾 - + max 60 chars
    slug = re.sub(r"[^a-z0-9]+", "-", keyword.strip().lower())
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")[:60]
    return slug, topic


def build_attack_prompt(keyword: str, topic: str, num: int) -> str:
    """构建针对长尾关键词的专用 Prompt"""
    return f"""你是一个拥有12年 OSHA 现场安全检查经验的资深工程师和培训师。

用户搜索了关键词 "{keyword}" 并进入了我们的网站。请围绕这个精确搜索意图，生成 {num} 道高质量单选题。

核心要求：
- 每道题必须结合真实施工场景
- 解析部分必须包含：具体 29 CFR 1926 法规引用 + 真实案例后果 + 常见错误分析
- 语言自然、专业，避免模板化句式
- 干扰项看起来合理但可通过专业知识排除
- SEO 元数据中的 h1 和 description 必须包含关键词 "{keyword}"
- 这是 YMYL (Your Money Your Life) 安全类内容，解析必须详细、准确、有权威性

返回纯 JSON（不要 markdown 代码块，不要额外文字）：

{{
  "seo_metadata": {{
    "unique_h1": "包含 '{keyword}' 的独特点击性标题",
    "meta_description": "150字以内独特描述，包含关键词，吸引点击但不夸张",
    "primary_keywords": ["{keyword}", "关键词2", "关键词3"]
  }},
  "questions": [
    {{
      "question": "基于真实施工场景的题目描述...",
      "options": ["A. 选项文本", "B. 选项文本", "C. 选项文本", "D. 选项文本"],
      "answer": "B",
      "analysis": "详细解析 + 法规引用（如29 CFR 1926.xxx）+ 真实案例后果 + 常见错误分析"
    }}
  ]
}}"""


def api_generate(keyword: str, topic: str, num: int) -> dict | None:
    """调用 Claude API 生成 JSON 数据，失败返回 None"""
    prompt = build_attack_prompt(keyword, topic, num)
    print(f"\n🤖 调用 {config.MODEL} 生成 {num} 道题...")
    data = call_claude(prompt)
    if data is None:
        print("❌ API 调用失败（已重试 3 次）")
        return None
    if "questions" not in data or "seo_metadata" not in data:
        print("❌ API 返回数据缺少必要字段")
        return None
    print(f"   ✅ 生成 {len(data['questions'])} 道题")
    return data


def main():
    parser = argparse.ArgumentParser(description="GSC Long-Tail Attack — 一键长尾词攻击脚本")
    parser.add_argument("keyword", type=str, help="GSC 长尾关键词")
    parser.add_argument("--num", type=int, default=20, help="题量 (10-40, default 20)")
    parser.add_argument("--mode", type=str, default="bonus", choices=["bonus", "chapter"], help="模式 (default bonus)")
    args = parser.parse_args()

    if not (10 <= args.num <= 40):
        print("❌ --num 范围: 10-40")
        sys.exit(1)

    if not config.CLAUDE_API_KEY:
        print("❌ 请在 config.py 中设置 CLAUDE_API_KEY")
        sys.exit(1)

    print(f"   Model: {config.MODEL}")

    slug, topic = keyword_to_slug_topic(args.keyword)
    print(f"📎 Keyword: {args.keyword}")
    print(f"   Slug: {slug}")
    print(f"   Topic: {topic}")
    print(f"   Mode: {args.mode}")
    print(f"   Questions: {args.num}")

    # Step 2: API 调用
    data = api_generate(args.keyword, topic, args.num)
    if data is None:
        sys.exit(1)


if __name__ == "__main__":
    main()
