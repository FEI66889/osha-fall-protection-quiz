#!/usr/bin/env python3
"""
OSHA Quiz 批量生成 + 部署就绪管线

流程: Claude API → JSON → Jinja2 渲染 → dist/*.html + sitemap.xml
用法: python build_site.py
"""

import json
import math
import os
import re
import time
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

import config  # noqa: F401 — 隐式使用 config 变量
from config import CLAUDE_API_KEY, DOMAIN, MODEL, MAX_TOKENS, TEMPERATURE, QUESTIONS_PER_CHAPTER, OUTPUT_DIR

QUESTIONS_PER_PAGE = 10

# ====================== Claude 客户端 ======================
_client: object | None = None

def get_client() -> object:
    """懒加载 Anthropic 客户端，无 API Key 时不 import 也不报错"""
    global _client
    if _client is not None:
        return _client
    if not CLAUDE_API_KEY:
        return None  # type: ignore[return-value]
    try:
        from anthropic import Anthropic  # type: ignore[import-untyped]
    except ImportError:
        print("❌ 请先安装: pip install anthropic")
        raise SystemExit(1)
    _client = Anthropic(api_key=CLAUDE_API_KEY)
    return _client

ROOT = Path(__file__).resolve().parent
TEMPLATE_DIR = ROOT / "template"
DATA_DIR = ROOT / "data"
DIST = ROOT / OUTPUT_DIR
DIST.mkdir(parents=True, exist_ok=True)


# ====================== 本地 JSON 数据加载 ======================
def find_local_json(slug: str) -> Path | None:
    """在 data/ 目录查找对应 slug 的 JSON 文件"""
    patterns = [
        f"*-{slug}.json",
        f"{slug}.json",
    ]
    for pattern in patterns:
        matches = list(DATA_DIR.glob(pattern))
        if matches:
            return matches[0]
    return None


def load_local_data(slug: str) -> dict | None:
    """从本地 JSON 文件加载题目数据"""
    path = find_local_json(slug)
    if path is None:
        return None
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if "questions" not in data or "seo_metadata" not in data:
        print(f"   ⚠️ {path.name} 缺少必要字段，跳过")
        return None
    return data


def has_local_data() -> bool:
    """检测 data/ 目录是否存在可用的 JSON 文件"""
    if not DATA_DIR.exists():
        return False
    return len(list(DATA_DIR.glob("*.json"))) > 0


# ====================== Prompt 工程 ======================
def build_prompt(topic: str, chapter_num: int, num: int = QUESTIONS_PER_CHAPTER) -> str:
    """为指定章节构建唯一化 Prompt，对抗内容重复度"""
    return f"""你是一个拥有12年 OSHA 现场安全检查经验的资深工程师和培训师。
请为章节主题"{topic}"生成{num}道高质量单选题。

核心要求：
- 每道题必须结合真实施工场景（高层建筑、桥梁、室内装修、船舶维修等不同场景轮换）
- 解析部分必须包含：具体法规引用（29 CFR 1926.xxx）+ 真实案例后果 + 常见错误分析
- 语言风格自然、专业，避免模板化句式
- 选项长度均匀，干扰项看起来合理但专业知识可排除
- 为这个章节生成独特的 SEO 元数据（标题不能和其他章节雷同）

返回以下 JSON 格式（纯 JSON，不要任何额外文字，不要 markdown 代码块）：

{{
  "seo_metadata": {{
    "unique_h1": "具体且独特的 H1 标题，包含长尾关键词",
    "meta_description": "150字以内独特描述，包含 2-3 个长尾词，吸引点击但不夸张",
    "primary_keywords": ["关键词1", "关键词2", "关键词3"]
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


# ====================== API 调用 ======================
def call_claude(prompt: str, max_retries: int = 3) -> dict | None:
    """调用 Claude API 并健壮提取 JSON"""
    client = get_client()
    if client is None:
        return None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text

            # 健壮 JSON 提取：取第一个 { 到最后一个 }
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                print(f"   ⚠️ 第 {attempt} 次未找到 JSON，重试...")
                time.sleep(2)
                continue

            data = json.loads(match.group(0))

            # 结构校验
            if "questions" not in data or "seo_metadata" not in data:
                print(f"   ⚠️ 第 {attempt} 次缺少必要字段，重试...")
                time.sleep(2)
                continue

            return data

        except json.JSONDecodeError as e:
            print(f"   ⚠️ 第 {attempt} 次 JSON 解析失败: {e}")
            time.sleep(2)
        except Exception as e:
            print(f"   ⚠️ 第 {attempt} 次 API 异常: {e}")
            time.sleep(3)

    print("   ❌ 已达最大重试次数，跳过此章节")
    return None


# ====================== 静态回退（离线测试用）======================
def load_fallback_data(chapter_num: int, topic: str) -> dict:
    """无 API 或 API 失败时的本地样本数据，确保管线可离线跑通"""
    return {
        "seo_metadata": {
            "unique_h1": f"OSHA {topic} — Chapter {chapter_num} Practice Questions",
            "meta_description": f"Free OSHA 30-Hour Construction practice questions covering {topic}. Includes detailed rationales with 29 CFR references. No registration required.",
            "primary_keywords": [topic, "OSHA 30-Hour", "construction safety"],
        },
        "questions": [
            {
                "question": f"[FALLBACK] A competent person inspects a jobsite and identifies a hazard related to {topic}. What is the first action required under OSHA?",
                "options": [
                    "A. Document the hazard and continue work",
                    "B. Immediately eliminate or control the hazard before work continues",
                    "C. Notify OSHA within 24 hours",
                    "D. Have workers sign a waiver before entering the area",
                ],
                "answer": "B",
                "analysis": f"Under the General Duty Clause and relevant 29 CFR 1926 standards, identified hazards must be controlled or eliminated before employees are exposed. For {topic}, specific standards apply. [FALLBACK — 请配置 API Key 生成完整内容]",
            }
        ],
    }


# ====================== 分页渲染 ======================
def render_paginated_chapter(
    data: dict,
    chapter_num: int,
    slug: str,
    short_title: str,
    prev_chapter: dict | None = None,
    next_chapter: dict | None = None,
    prev_chapter_pages: int = 0,
) -> list[str]:
    """
    按 QUESTIONS_PER_PAGE 分页渲染一个章节。
    返回该章节所有生成的文件名列表。
    """
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("quiz_template.html")

    questions = data["questions"]
    total_pages = math.ceil(len(questions) / QUESTIONS_PER_PAGE)
    seo = data["seo_metadata"]
    generated_files = []

    for page_num in range(1, total_pages + 1):
        start = (page_num - 1) * QUESTIONS_PER_PAGE
        end = start + QUESTIONS_PER_PAGE
        page_questions = questions[start:end]

        # 文件名 (disk) vs URL path (clean, no .html)
        if page_num == 1:
            filename = f"{slug}.html"
            url_path = f"{slug}"
            canonical_url = f"{DOMAIN}/{slug}"
        else:
            filename = f"{slug}-{page_num}.html"
            url_path = f"{slug}-{page_num}"
            canonical_url = f"{DOMAIN}/{slug}"  # 子页 canonical 指向第 1 页

        # 页面内导航
        prev_page_url = None
        next_page_url = None
        if page_num > 1:
            prev_page_url = f"{slug}" if page_num == 2 else f"{slug}-{page_num - 1}"
        if page_num < total_pages:
            next_page_url = f"{slug}-{page_num + 1}"

        # 标题加页码
        page_title = seo["unique_h1"]
        meta_desc = seo["meta_description"]
        if total_pages > 1:
            page_title = f"{page_title} — Page {page_num} of {total_pages}"
            if page_num > 1:
                meta_desc = f"{meta_desc} (Page {page_num} of {total_pages})"

        # 跨章导航链接
        prev_chapter_link = None
        prev_chapter_label = ""
        next_chapter_link = None
        next_chapter_label = ""

        if page_num == 1:
            # 第 1 页：prev 链到上一章最后一页
            if prev_chapter:
                if prev_chapter_pages > 1:
                    prev_chapter_link = f"{prev_chapter['slug']}-{prev_chapter_pages}"
                else:
                    prev_chapter_link = f"{prev_chapter['slug']}"
                prev_chapter_label = prev_chapter["short_title"]

        if page_num == total_pages:
            # 最后一页：next 链到下一章第 1 页
            if next_chapter:
                next_chapter_link = f"{next_chapter['slug']}"
                next_chapter_label = next_chapter["short_title"]

        # 如果章内还有下一页，跨章导航用本页自己的 next page
        # （跨章 only 出现在最后一页）

        html = template.render(
            title=page_title,
            description=meta_desc,
            keywords=", ".join(seo["primary_keywords"]),
            chapter_title=short_title,
            chapter_slug=slug,
            questions=page_questions,
            chapter_num=chapter_num,
            total_questions=len(questions),
            generated_date=datetime.today().strftime("%Y-%m-%d"),
            domain=DOMAIN,
            page_num=page_num,
            total_pages=total_pages,
            canonical_url=canonical_url,
            prev_page_url=prev_page_url,
            next_page_url=next_page_url,
            prev_chapter_link=prev_chapter_link,
            prev_chapter_label=prev_chapter_label,
            next_chapter_link=next_chapter_link,
            next_chapter_label=next_chapter_label,
        )

        output_path = DIST / filename
        output_path.write_text(html, encoding="utf-8")
        generated_files.append(url_path)
        print(f"   ✅ {filename} → /{url_path} (p{page_num}/{total_pages}, {len(page_questions)} questions)")

    return generated_files


# ====================== Sitemap ======================
# ====================== 首页 ======================
def generate_index(chapters: list[dict[str, str]]) -> None:
    """生成首页，列出全部章节"""
    items_html = ""
    for i, ch in enumerate(chapters, 1):
        items_html += f"""      <a href="{ch['slug']}" class="block bg-white rounded-xl border border-gray-200 p-5 hover:border-primary-300 hover:shadow-md transition-all">
        <div class="flex items-center gap-3">
          <span class="inline-flex items-center justify-center w-10 h-10 rounded-full bg-primary-50 text-primary-600 font-bold text-sm shrink-0">{i:02d}</span>
          <div>
            <h2 class="font-semibold text-gray-800 text-sm sm:text-base">{ch['short_title']}</h2>
            <p class="text-xs text-gray-400 mt-0.5">{ch['topic'].split(' — ')[0]} · 40 Questions · 4 Pages</p>
          </div>
          <span class="ml-auto text-gray-300 text-lg">→</span>
        </div>
      </a>\n"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="google-site-verification" content="google0b06af105e67b274">
<title>Free OSHA 30-Hour Construction Practice Tests — 400 Questions, No Login</title>
<meta name="description" content="Free OSHA 30-Hour Construction practice tests with 400 realistic jobsite scenarios across 10 chapters. Fall Protection, Scaffold, Electrical, Excavation, Cranes, PPE, HazCom, and more. Detailed 29 CFR references. No registration needed.">
<meta name="keywords" content="OSHA 30-Hour practice, construction safety quiz, OSHA test free, fall protection, scaffold safety, electrical safety">
<link rel="canonical" href="{DOMAIN}/">
<meta property="og:title" content="Free OSHA 30-Hour Construction Practice Tests — 400 Questions, No Login">
<meta property="og:description" content="10 chapters, 400 questions with detailed 29 CFR references. Free, no registration.">
<meta property="og:type" content="website">
<meta property="og:url" content="{DOMAIN}/">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "Free OSHA 30-Hour Practice",
  "url": "{DOMAIN}",
  "description": "Free OSHA 30-Hour Construction practice tests with 400 questions and detailed 29 CFR references.",
  "potentialAction": {{
    "@type": "SearchAction",
    "target": {{
      "@type": "EntryPoint",
      "urlTemplate": "{DOMAIN}/?q={{search_term_string}}"
    }},
    "query-input": "required name=search_term_string"
  }}
}}
</script>
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {{
      "@type": "Question",
      "name": "Is this OSHA practice test really free?",
      "acceptedAnswer": {{
        "@type": "Answer",
        "text": "Yes. All 400 questions across 10 chapters are completely free. No registration, no login, no credit card required. Start practicing immediately."
      }}
    }},
    {{
      "@type": "Question",
      "name": "What topics does the OSHA 30-Hour Construction practice cover?",
      "acceptedAnswer": {{
        "@type": "Answer",
        "text": "Covers all major OSHA 30-Hour Construction topics: Fall Protection (29 CFR 1926.501), Scaffold Safety (1926.450-454), Electrical Safety (1926.400-449), Excavation & Trenching (1926.650-652), Cranes & Derricks (1926.550), PPE & Lifesaving (1926.100-107), Hazard Communication (1926.1100), Materials Handling (1926.250-252), Stairways & Ladders (1926.1050-1060), and Confined Spaces (1926.800-806)."
      }}
    }},
    {{
      "@type": "Question",
      "name": "Do the questions include OSHA regulation references?",
      "acceptedAnswer": {{
        "@type": "Answer",
        "text": "Yes. Every question includes a detailed rationale with specific 29 CFR 1926 regulation citations, real-world jobsite scenarios, and analysis of common mistakes — not just the correct answer."
      }}
    }},
    {{
      "@type": "Question",
      "name": "How many questions are there?",
      "acceptedAnswer": {{
        "@type": "Answer",
        "text": "400 questions total — 40 questions per chapter across 10 chapters. Each chapter is split into 4 pages of 10 questions for easy study sessions."
      }}
    }}
  ]
}}
</script>
<link rel="stylesheet" href="/tailwind.css">
</head>
<body class="bg-gray-50 min-h-screen text-gray-900">

<header class="bg-white border-b border-gray-200 sticky top-0 z-40 shadow-sm">
  <div class="max-w-3xl mx-auto px-4 py-4 flex items-center gap-3">
    <span class="text-2xl">🏗️</span>
    <div>
      <h1 class="font-bold text-base sm:text-lg text-gray-800">Free OSHA 30-Hour Practice</h1>
      <p class="text-xs text-gray-400">10 Chapters · 400 Questions · Detailed 29 CFR References</p>
    </div>
  </div>
</header>

<main class="max-w-3xl mx-auto px-4 py-8">
  <div class="mb-8">
    <h2 class="text-xl font-extrabold text-gray-900">Choose a Chapter</h2>
    <p class="text-gray-500 text-sm mt-1">Each chapter has 40 realistic jobsite scenarios with OSHA regulation references and detailed analysis.</p>
  </div>

  <div class="space-y-3">
{items_html}  </div>
</main>

<footer class="max-w-3xl mx-auto px-4 pb-10 text-center">
  <p class="text-xs text-gray-400">Generated {datetime.today().strftime('%Y-%m-%d')} · For OSHA 30-Hour Construction training · Content not legal advice</p>
</footer>

</body>
</html>"""

    ipath = DIST / "index.html"
    ipath.write_text(html, encoding="utf-8")
    print(f"\n✅ index.html → {ipath}")


# ====================== Robots.txt ======================
def generate_robots() -> None:
    """生成 robots.txt，指引搜索引擎爬取"""
    robots = f"""User-agent: *
Allow: /
Sitemap: {DOMAIN}/sitemap.xml

# 404 页面无害，不屏蔽任何路径
"""
    rpath = DIST / "robots.txt"
    rpath.write_text(robots, encoding="utf-8")
    print(f"✅ robots.txt → {rpath}")


# sitemap 用纯字符串构建，避免 xml.etree 命名空间坑
def generate_sitemap(urls: list[str]) -> None:
    """生成符合 Google 规范的 sitemap.xml"""
    entries = []
    for url in urls:
        # page 1 (no numeric suffix) = 0.9, sub-pages = 0.7, root = 1.0
        if url == "":
            priority = "1.0"
            loc = f"{DOMAIN}/"
        elif url.endswith("-2") or url.endswith("-3") or url.endswith("-4"):
            priority = "0.7"
            loc = f"{DOMAIN}/{url}"
        else:
            priority = "0.9"
            loc = f"{DOMAIN}/{url}"
        entries.append(
            "  <url>\n"
            f"    <loc>{loc}</loc>\n"
            f"    <lastmod>{datetime.today().strftime('%Y-%m-%d')}</lastmod>\n"
            "    <changefreq>weekly</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            "  </url>"
        )

    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries)
        + "\n</urlset>\n"
    )

    spath = DIST / "sitemap.xml"
    spath.write_text(sitemap, encoding="utf-8")
    print(f"\n✅ sitemap.xml → {spath}")


# ====================== 主流程 ======================
def main() -> None:
    # ----- 章节定义（按 OSHA 30-Hour 大纲）-----
    chapters: list[dict[str, str]] = [
        {"topic": "29 CFR 1926.501 — Fall Protection (坠落防护)", "slug": "fall-protection", "short_title": "Fall Protection"},
        {"topic": "29 CFR 1926.450-454 — Scaffold Safety (脚手架安全)", "slug": "scaffold-safety", "short_title": "Scaffold Safety"},
        {"topic": "29 CFR 1926.400-449 — Electrical Safety (电气安全)", "slug": "electrical-safety", "short_title": "Electrical Safety"},
        {"topic": "29 CFR 1926.650-652 — Excavation & Trenching (基坑与沟槽)", "slug": "excavation-trenching", "short_title": "Excavation & Trenching"},
        {"topic": "29 CFR 1926.550-555 — Cranes & Derricks (起重机安全)", "slug": "cranes-derricks", "short_title": "Cranes & Derricks"},
        {"topic": "29 CFR 1926.100-107 — PPE & Lifesaving Equipment (个人防护装备)", "slug": "ppe-equipment", "short_title": "PPE & Lifesaving"},
        {"topic": "29 CFR 1926.1100-1152 — Hazard Communication (危害告知)", "slug": "hazard-communication", "short_title": "Hazard Communication"},
        {"topic": "29 CFR 1926.250-252 — Materials Handling & Storage (物料搬运)", "slug": "materials-handling", "short_title": "Materials Handling"},
        {"topic": "29 CFR 1926.1050-1060 — Stairways & Ladders (楼梯与梯子)", "slug": "stairways-ladders", "short_title": "Stairways & Ladders"},
        {"topic": "29 CFR 1926.800-806 — Confined Spaces (密闭空间)", "slug": "confined-spaces", "short_title": "Confined Spaces"},
    ]

    # ----- 检测本地数据 ----
    use_local = has_local_data()

    if not CLAUDE_API_KEY:
        if use_local:
            print("=" * 60)
            print(f"📂 检测到 {len(list(DATA_DIR.glob('*.json')))} 个本地 JSON 数据文件，使用本地模式")
            print("   编辑 data/*.json 修改题目，运行 python3 build_site.py 重新生成")
            print("=" * 60)
        else:
            print("=" * 60)
            print("⚠️  未配置 CLAUDE_API_KEY 且无本地数据，将使用 FALLBACK 模式")
            print("   编辑 config.py 填入 API Key 启用 AI 生成")
            print("   或在 data/ 下放置 JSON 数据文件")
            print("=" * 60)

    urls: list[str] = []
    total_questions = 0
    chapter_pages: dict[str, int] = {}  # slug → total_pages，用于跨章导航

    # ----- 第一遍：加载数据，计算每章页数 -----
    chapter_data: list[dict] = []
    for i, ch in enumerate(chapters, 0):
        topic = ch["topic"]
        slug = ch["slug"]
        num = i + 1

        data: dict | None = None
        if use_local:
            data = load_local_data(slug)
        elif CLAUDE_API_KEY:
            print(f"   📡 [{num}/{len(chapters)}] Calling API for {topic[:60]}...")
            prompt = build_prompt(topic, chapter_num=num)
            data = call_claude(prompt)

        if data is None and not use_local:
            if CLAUDE_API_KEY:
                print("   ⚠️ API 失败，使用 FALLBACK 数据")
            data = load_fallback_data(num, topic)

        if data is None:
            print(f"   ⚠️ 跳过 {slug}")
            continue

        total_pages = math.ceil(len(data["questions"]) / QUESTIONS_PER_PAGE)
        chapter_pages[slug] = total_pages
        chapter_data.append({
            "data": data,
            "ch": ch,
            "num": num,
            "total_pages": total_pages,
        })

    # ----- 第二遍：渲染 -----
    for idx, cd in enumerate(chapter_data):
        data = cd["data"]
        ch = cd["ch"]
        num = cd["num"]
        slug = ch["slug"]

        print(f"\n{'=' * 50}")
        print(f"🚀 [{num}/{len(chapters)}] {ch['topic'][:60]}...")
        print(f"{'=' * 50}")
        print(f"   📄 从 {find_local_json(slug).name} 加载 ({len(data['questions'])} 题)")

        prev_ch = chapters[idx - 1] if idx > 0 else None
        next_ch = chapters[idx + 1] if idx < len(chapter_data) - 1 else None
        prev_pages = chapter_pages.get(prev_ch["slug"], 0) if prev_ch else 0

        generated = render_paginated_chapter(
            data=data,
            chapter_num=num,
            slug=slug,
            short_title=ch["short_title"],
            prev_chapter=prev_ch,
            next_chapter=next_ch,
            prev_chapter_pages=prev_pages,
        )
        urls.extend(generated)
        total_questions += len(data["questions"])

    # ----- 生成首页 -----
    generate_index(chapters)
    urls.append("")  # root URL for sitemap

    # ----- 生成 robots.txt -----
    generate_robots()

    # ----- 收尾 -----
    generate_sitemap(urls)

    print(f"\n{'=' * 50}")
    print(f"🎉 全量生成完成！")
    print(f"   页面数: {len(urls)}（{len(chapter_data)} 章 × ~{QUESTIONS_PER_CHAPTER // QUESTIONS_PER_PAGE} 页 + 首页）")
    print(f"   总题量: {total_questions}")
    print(f"   输出目录: {DIST.resolve()}")
    print(f"\n   下一步:")
    print(f"   1. 检查 {OUTPUT_DIR}/ 下的 HTML 文件")
    print(f"   2. git push 到仓库")
    print(f"   3. 在 Cloudflare Pages / Vercel 连接仓库一键部署")
    print(f"   4. 去 Google Search Console 提交 {DOMAIN}/sitemap.xml")


if __name__ == "__main__":
    main()
