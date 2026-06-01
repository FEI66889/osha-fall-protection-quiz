#!/usr/bin/env python3
"""
GSC Long-Tail Attack Script
用法: python3 gsc_attack.py "osha subpart m guardrail height requirements 2026" [--num 20] [--mode bonus]
"""
import argparse
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parent

DATA_DIR = ROOT / "data"
TEMPLATE_DIR = ROOT / "template"
DIST_DIR = ROOT / "dist"
DIST_DIR.mkdir(parents=True, exist_ok=True)

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
        print("❌ API 调用失败")
        return None
    # call_claude 已保证 questions 和 seo_metadata 字段存在，这里是 defence in depth
    questions = data.get("questions")
    if not isinstance(questions, list) or len(questions) == 0:
        print("❌ API 返回的 questions 为空或格式错误")
        return None
    if "seo_metadata" not in data:
        print("❌ API 返回数据缺少 seo_metadata")
        return None
    print(f"   ✅ 生成 {len(questions)} 道题")
    return data


def save_json(slug: str, data: dict, force: bool = False) -> bool:
    """保存 JSON 到 data/{slug}.json，已存在时询问"""
    path = DATA_DIR / f"{slug}.json"
    if path.exists() and not force:
        answer = input(f"   ⚠️ {path.name} 已存在，覆盖？[y/N] ").strip().lower()
        if answer != "y":
            print("   ⏭ 跳过，不覆盖")
            return False
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"   💾 已保存: {path}")
    return True


def render_html(slug: str, topic: str, data: dict, domain: str) -> bool:
    """用 quiz_template.html 渲染单页静态 HTML"""
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    try:
        template = env.get_template("quiz_template.html")
    except Exception as e:
        print(f"❌ 找不到模板 quiz_template.html: {e}")
        return False

    seo = data["seo_metadata"]
    questions = data["questions"]
    total_q = len(questions)
    generated_date = date.today().isoformat()

    # FAQ Schema (前 10 题) — 模板中未使用 faq_schema 变量，
    # 模板已内联 Quiz + BreadcrumbList schema，此处保留以备将来使用
    import json as _json
    schema_entities = []
    for q in questions[:10]:
        schema_entities.append({
            "@type": "Question",
            "name": q["question"],
            "acceptedAnswer": {
                "@type": "Answer",
                "text": f"Correct Answer: {q['answer']}. {q['analysis']}"
            }
        })
    faq_schema = _json.dumps({
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": schema_entities
    }, ensure_ascii=False)

    html = template.render(
        # <title>, <h1>, og:title
        title=seo["unique_h1"],
        # <meta description>, og:description
        description=seo["meta_description"],
        # <meta keywords>
        keywords=",".join(seo.get("primary_keywords", [])),
        # canonical, og:url
        canonical_url=f"{domain}/{slug}.html",
        domain=domain,
        # Schema.org 中的章节名
        chapter_title=topic,
        chapter_slug=slug,
        chapter_num=0,
        # 单页：page_num=1, total_pages=1
        page_num=1,
        total_pages=1,
        total_questions=total_q,
        generated_date=generated_date,
        # 题目列表（每项: question, options, answer, analysis）
        questions=questions,
        # 无分页，无上下章
        prev_page_url=None,
        next_page_url=None,
        prev_chapter_link=None,
        next_chapter_link=None,
        prev_chapter_label="",
        next_chapter_label="",
        # 以下变量模板未使用，传入无副作用
        short_title=seo["unique_h1"][:30],
        faq_schema=faq_schema,
    )

    path = DIST_DIR / f"{slug}.html"
    path.write_text(html, encoding="utf-8")
    print(f"   📄 已渲染: {path}")
    return True


def update_sitemap(slug: str, domain: str, priority: str = "0.9") -> bool:
    """向 dist/sitemap.xml 追加新的 URL entry"""
    sitemap_path = DIST_DIR / "sitemap.xml"
    if not sitemap_path.exists():
        print("⚠️ sitemap.xml 不存在，跳过")
        return False

    tree = ET.parse(str(sitemap_path))
    root = tree.getroot()

    # 检查是否已存在
    target_url = f"{domain}/{slug}.html"
    for url_elem in root.findall("url"):
        loc = url_elem.find("loc")
        if loc is not None and loc.text == target_url:
            print(f"   ⚠️ Sitemap 已包含 {target_url}，跳过")
            return True

    url_elem = ET.SubElement(root, "url")
    ET.SubElement(url_elem, "loc").text = target_url
    ET.SubElement(url_elem, "lastmod").text = datetime.today().strftime("%Y-%m-%d")
    ET.SubElement(url_elem, "changefreq").text = "weekly"
    ET.SubElement(url_elem, "priority").text = priority

    ET.indent(tree, space="  ", level=0)
    tree.write(str(sitemap_path), encoding="utf-8", xml_declaration=True)
    print(f"   📅 Sitemap 已更新: +{target_url}")
    return True


def git_auto_push(slug: str, keyword: str, mode: str) -> bool:
    """git add → commit → push"""
    files = [
        f"data/{slug}.json",
        f"dist/{slug}.html",
        "dist/sitemap.xml",
    ]
    if mode == "chapter":
        files.append("dist/index.html")
        files.append("build_site.py")

    # git add
    add_cmd = ["git", "add"] + files
    result = subprocess.run(add_cmd, cwd=str(ROOT), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ git add 失败: {result.stderr}")
        return False

    # git commit
    msg = f"attack(gsc): {keyword}"
    result = subprocess.run(
        ["git", "commit", "-m", msg],
        cwd=str(ROOT), capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"❌ git commit 失败: {result.stderr}")
        return False
    print(f"   📝 Committed: {msg}")

    # git push
    print("   🚀 Pushing to GitHub...")
    result = subprocess.run(
        ["git", "push"],
        cwd=str(ROOT), capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"❌ git push 失败: {result.stderr}")
        return False
    print("   ✅ Push 成功！Cloudflare Pages 正在自动部署")
    return True


def chapter_mode_append(slug: str, topic: str) -> bool:
    """向 build_site.py 的 chapters 列表追加一行 entry"""
    build_site_path = ROOT / "build_site.py"
    content = build_site_path.read_text(encoding="utf-8")

    # 找到 chapters 列表最后一个元素（Confined Spaces）
    marker = '{"topic": "29 CFR 1926.800-806 — Confined Spaces'
    if marker not in content:
        print("❌ 找不到 chapters 列表标记，build_site.py 结构可能已变化")
        return False

    insert_after = '        {"topic": "29 CFR 1926.800-806 — Confined Spaces (密闭空间)", "slug": "confined-spaces", "short_title": "Confined Spaces"},'
    new_entry = f'        {{"topic": "{topic}", "slug": "{slug}", "short_title": "{topic[:30]}"}},\n'

    modified = content.replace(
        insert_after,
        insert_after + "\n" + new_entry
    )

    if modified == content:
        print("❌ 修改 build_site.py 失败")
        return False

    build_site_path.write_text(modified, encoding="utf-8")
    print(f"   📝 已添加章节到 build_site.py: {slug}")

    # 运行 build_site.py 重建首页
    print("   🔨 运行 build_site.py 重建全站...")
    result = subprocess.run(
        ["python3", str(build_site_path)],
        cwd=str(ROOT), capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"❌ build_site.py 失败: {result.stderr}")
        return False
    print("   ✅ 全站重建完成")
    return True


def main():
    parser = argparse.ArgumentParser(description="GSC Long-Tail Attack — 一键长尾词攻击脚本")
    parser.add_argument("keyword", type=str, help="GSC 长尾关键词")
    parser.add_argument("--num", type=int, default=20, help="题量 (10-40, default 20)")
    parser.add_argument("--mode", type=str, default="bonus", choices=["bonus", "chapter"], help="模式 (default bonus)")
    args = parser.parse_args()

    # 检查 git 状态（忽略 data/ 和 dist/ 未追踪文件）
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(ROOT), capture_output=True, text=True
    )
    dirty_lines = [
        line for line in status.stdout.strip().split("\n")
        if line.strip() and not line.startswith("?? data/") and not line.startswith("?? dist/")
    ]
    if dirty_lines:
        print("⚠️ Working directory 不干净：")
        print("\n".join(dirty_lines[:10]))
        print("请先 commit 或 stash 已有改动")
        sys.exit(1)

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

    # Step 3: 保存 JSON
    if not save_json(slug, data):
        sys.exit(0)

    # Chapter mode: 追加到 build_site.py 并重建全站
    if args.mode == "chapter":
        if not chapter_mode_append(slug, topic):
            sys.exit(1)
        print("   ✅ Chapter 模式: build_site.py 已生成 HTML 和首页")
    else:
        # Bonus mode: 手动渲染单页 HTML
        if not render_html(slug, topic, data, config.DOMAIN):
            sys.exit(1)

    # Step 5: 更新 sitemap
    priority = "0.9" if args.mode == "bonus" else "0.7"
    update_sitemap(slug, config.DOMAIN, priority)

    # Step 6: Git auto push
    if not git_auto_push(slug, args.keyword, args.mode):
        sys.exit(1)


if __name__ == "__main__":
    main()
