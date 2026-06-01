# GSC Long-Tail Attack Script — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One-click script `gsc_attack.py` that takes a GSC long-tail keyword, generates 20 targeted quiz questions via Claude API, renders static HTML, updates sitemap, and auto-pushes to GitHub.

**Architecture:** Standalone CLI script that imports `build_site.py` utilities (API client, Jinja2 env, extract_json, config). Bonus mode creates a standalone page; chapter mode appends to build_site's chapters list and triggers full rebuild.

**Tech Stack:** Python 3, Jinja2 (template rendering), Anthropic Claude API (question generation), argparse (CLI), subprocess (git + build_site invocation)

---

### Task 1: Script Skelton — argparse + keyword processing

**Files:**
- Create: `gsc_attack.py`

- [ ] **Step 1: Create `gsc_attack.py` with argparse and keyword→slug/topic logic**

```python
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
```

- [ ] **Step 2: Verify script parses arguments correctly**

```bash
python3 gsc_attack.py "osha guardrail height quiz" --num 15 --mode bonus
```

Expected output (not exact):
```
📎 Keyword: osha guardrail height quiz
   Slug: osha-guardrail-height-quiz
   Topic: Osha Guardrail Height Quiz Quiz
   Mode: bonus
   Questions: 15
```

- [ ] **Step 3: Commit**

```bash
git add gsc_attack.py
git commit -m "feat: gsc_attack.py skeleton with argparse and keyword processing"
```

---

### Task 2: Import and reuse build_site utilities

**Files:**
- Modify: `gsc_attack.py`

- [ ] **Step 1: Add imports and API call wrapper to gsc_attack.py**

After the `ROOT` line, add:

```python
import sys
sys.path.insert(0, str(ROOT))

import config  # noqa
from build_site import get_client, call_claude, extract_json  # type: ignore  # noqa
```

Note: `build_site.py` uses `from config import ...` at module level, so `config.py` must exist with `CLAUDE_API_KEY`, `DOMAIN`, `MODEL`, `MAX_TOKENS`, `TEMPERATURE`. Verified already present.

- [ ] **Step 2: Add import verification inside main()**

After the argparse block in `main()`:

```python
    if not config.CLAUDE_API_KEY:
        print("❌ 请在 config.py 中设置 CLAUDE_API_KEY")
        sys.exit(1)

    print(f"   Model: {config.MODEL}")
```

- [ ] **Step 3: Verify imports work**

```bash
python3 -c "from build_site import get_client, call_claude, extract_json; print('imports OK')"
```

Expected: `imports OK`

- [ ] **Step 4: Commit**

```bash
git add gsc_attack.py
git commit -m "feat: gsc_attack.py imports build_site utilities"
```

---

### Task 3: Claude Prompt for long-tail keyword + API call

**Files:**
- Modify: `gsc_attack.py`

- [ ] **Step 1: Add build_prompt and api_generate functions to gsc_attack.py**

After `keyword_to_slug_topic()`, add:

```python
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
```

- [ ] **Step 2: Integrate api_generate into main()**

After the config check in `main()`, add:

```python
    # Step 2: API 调用
    data = api_generate(args.keyword, topic, args.num)
    if data is None:
        sys.exit(1)
```

- [ ] **Step 3: Test with real API call (5 questions for speed)**

```bash
python3 gsc_attack.py "fall protection guardrail height" --num 5 --mode bonus
```

Expected: API call succeeds, prints "✅ 生成 5 道题", prints JSON data structure.

- [ ] **Step 4: Commit**

```bash
git add gsc_attack.py
git commit -m "feat: gsc_attack.py Claude prompt and API call"
```

---

### Task 4: Save JSON to data/ directory

**Files:**
- Modify: `gsc_attack.py`

- [ ] **Step 1: Add save_json function**

```python
import json

DATA_DIR = ROOT / "data"

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
```

- [ ] **Step 2: Integrate into main()**

After `api_generate()` call:

```python
    # Step 3: 保存 JSON
    if not save_json(slug, data):
        sys.exit(0)
```

- [ ] **Step 3: Test**

```bash
rm -f data/fall-protection-guardrail-height.json
python3 gsc_attack.py "fall protection guardrail height" --num 5 --mode bonus
```

Expected: `💾 已保存: data/fall-protection-guardrail-height.json`

- [ ] **Step 4: Test duplicate handling**

```bash
python3 gsc_attack.py "fall protection guardrail height" --num 5 --mode bonus
# Type "n" when prompted
```

Expected: `⏭ 跳过，不覆盖`

- [ ] **Step 5: Commit**

```bash
git add gsc_attack.py
git commit -m "feat: gsc_attack.py save JSON to data/"
```

---

### Task 5: Jinja2 render → static HTML

**Files:**
- Modify: `gsc_attack.py`

- [ ] **Step 1: Add render_html function**

```python
from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = ROOT / "template"
DIST_DIR = ROOT / "dist"
DIST_DIR.mkdir(parents=True, exist_ok=True)


def render_html(slug: str, data: dict, domain: str) -> bool:
    """用 quiz_template.html 渲染单页静态 HTML"""
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    try:
        template = env.get_template("quiz_template.html")
    except Exception as e:
        print(f"❌ 找不到模板 quiz_template.html: {e}")
        return False

    # 构建 FAQ Schema 前 10 题
    import json as _json
    schema_entities = []
    for q in data["questions"][:10]:
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

    seo = data["seo_metadata"]
    questions = data["questions"]
    # 模板中 {% for opt in q.options %} 期望 list of strings
    # options 格式: ["A. text", "B. text", ...] — 与 JSON 一致，无需转换

    html = template.render(
        title=seo["unique_h1"],
        description=seo["meta_description"],
        keywords=",".join(seo.get("primary_keywords", [])),
        canonical_url=f"{domain}/{slug}.html",
        domain=domain,
        questions=questions,
        chapter_slug=slug,
        chapter_num=0,
        prev_page_url=None,
        next_page_url=None,
        prev_chapter=None,
        next_chapter=None,
        short_title=seo["unique_h1"][:30],
        faq_schema=faq_schema,
    )

    path = DIST_DIR / f"{slug}.html"
    path.write_text(html, encoding="utf-8")
    print(f"   📄 已渲染: {path}")
    return True
```

- [ ] **Step 2: Integrate into main()**

After `save_json()`:

```python
    # Step 4: 渲染 HTML
    if not render_html(slug, data, config.DOMAIN):
        sys.exit(1)
```

- [ ] **Step 3: Test render**

```bash
python3 gsc_attack.py "fall protection guardrail height" --num 5 --mode bonus
```

Expected: `📄 已渲染: dist/fall-protection-guardrail-height.html`

- [ ] **Step 4: Verify HTML content**

```bash
grep -c 'google-site-verification' dist/fall-protection-guardrail-height.html
grep '<title>' dist/fall-protection-guardrail-height.html | head -1
grep -c 'article' dist/fall-protection-guardrail-height.html
```

Expected:
```
1
<title>...包含 fall protection guardrail height...</title>
5  (one per question)
```

- [ ] **Step 5: Commit**

```bash
git add gsc_attack.py
git commit -m "feat: gsc_attack.py Jinja2 render to static HTML"
```

---

### Task 6: Update sitemap.xml

**Files:**
- Modify: `gsc_attack.py`

- [ ] **Step 1: Add update_sitemap function**

```python
import xml.etree.ElementTree as ET
from datetime import datetime


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
```

- [ ] **Step 2: Integrate into main()**

After `render_html()`:

```python
    # Step 5: 更新 sitemap
    priority = "0.9" if args.mode == "bonus" else "0.7"
    update_sitemap(slug, config.DOMAIN, priority)
```

- [ ] **Step 3: Test sitemap update**

```bash
python3 gsc_attack.py "scaffold inspection requirements" --num 5 --mode bonus
grep "scaffold-inspection-requirements" dist/sitemap.xml
```

Expected: Shows the new URL entry in sitemap.

- [ ] **Step 4: Test duplicate prevention**

```bash
python3 gsc_attack.py "scaffold inspection requirements" --num 5 --mode bonus
# Choose 'y' to overwrite JSON
```

Expected: `⚠️ Sitemap 已包含 ..., 跳过`

- [ ] **Step 5: Commit**

```bash
git add gsc_attack.py
git commit -m "feat: gsc_attack.py sitemap.xml auto-update"
```

---

### Task 7: Git auto commit + push

**Files:**
- Modify: `gsc_attack.py`

- [ ] **Step 1: Add git_auto_push function**

```python
import subprocess


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
```

- [ ] **Step 2: Add git dirty check before push**

After the config check at the top of `main()`:

```python
    # 检查 git 状态
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(ROOT), capture_output=True, text=True
    )
    if status.stdout.strip():
        print("⚠️ Working directory 不干净，请先 commit 或 stash 已有改动")
        print(status.stdout)
        sys.exit(1)
```

- [ ] **Step 3: Integrate into main()**

After sitemap update:

```python
    # Step 6: Git auto push
    git_auto_push(slug, args.keyword, args.mode)
```

- [ ] **Step 4: Clean existing test artifacts before testing push**

```bash
rm -f data/fall-protection-guardrail-height.json dist/fall-protection-guardrail-height.html
git checkout dist/sitemap.xml
git commit -m "chore: cleanup test artifacts"
```

- [ ] **Step 5: End-to-end test with git push**

```bash
python3 gsc_attack.py "osha excavation safety trenching" --num 5 --mode bonus
```

Expected:
```
📝 Committed: attack(gsc): osha excavation safety trenching
🚀 Pushing to GitHub...
✅ Push 成功！Cloudflare Pages 正在自动部署
```

- [ ] **Step 6: Verify manual review of pushed content**

Open `https://osha-fall-protection.pages.dev/osha-excavation-safety-trenching.html` in browser, verify:
- Page loads with Tailwind styling
- 5 quiz cards render
- Clicking options shows red/green feedback
- Rationale expands

- [ ] **Step 7: Commit**

(Already auto-pushed by the script itself)

---

### Task 8: Chapter mode support

**Files:**
- Modify: `gsc_attack.py`

- [ ] **Step 1: Add chapter_mode function**

```python
def chapter_mode_append(slug: str, topic: str) -> bool:
    """向 build_site.py 的 chapters 列表追加一行 entry"""
    build_site_path = ROOT / "build_site.py"
    content = build_site_path.read_text(encoding="utf-8")

    # 找到 chapters 列表最后一个元素的位置
    # 现有格式: {"topic": "...", "slug": "...", "short_title": "..."},
    # 在最后一个 ], 之前插入新 entry
    marker = '{"topic": "29 CFR 1926.800-806 — Confined Spaces'
    if marker not in content:
        print("❌ 找不到 chapters 列表标记，build_site.py 结构可能已变化")
        return False

    new_entry = f'        {{"topic": "{topic}", "slug": "{slug}", "short_title": "{topic[:30]}..."}},\n'
    # 在 Confined Spaces entry 之后插入
    insert_after = '        {"topic": "29 CFR 1926.800-806 — Confined Spaces (密闭空间)", "slug": "confined-spaces", "short_title": "Confined Spaces"},'
    modified = content.replace(
        insert_after,
        insert_after + "\n" + new_entry.rstrip(",")
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
```

- [ ] **Step 2: Integrate into main()**

After JSON save, before HTML render:

```python
    # Step 3.5 (chapter mode): 追加到 build_site.py 并重建
    if args.mode == "chapter":
        if not chapter_mode_append(slug, topic):
            sys.exit(1)
        # chapter 模式由 build_site.py 负责渲染，跳过手动 render_html
        print("   ✅ Chapter 模式: build_site.py 已生成 HTML 和首页")
    else:
        # Step 4: 渲染 HTML (bonus mode)
        if not render_html(slug, data, config.DOMAIN):
            sys.exit(1)
```

- [ ] **Step 3: Update git_auto_push for chapter mode**

Modify the files list in `git_auto_push()`:

```python
    files = [
        f"data/{slug}.json",
        "dist/sitemap.xml",
    ]
    if mode == "chapter":
        files.append("build_site.py")
        files.extend([f"dist/{f.name}" for f in DIST_DIR.glob(f"{slug}*.html")])
        files.append("dist/index.html")
    else:
        files.append(f"dist/{slug}.html")
```

- [ ] **Step 4: Test chapter mode**

```bash
python3 gsc_attack.py "osha ppe requirements quiz" --num 10 --mode chapter
```

Expected: Adds entry to build_site.py, runs build_site.py, generates all pages, pushes.

- [ ] **Step 5: Verify chapter appears on homepage**

Open `https://osha-fall-protection.pages.dev/` and verify new chapter card is visible.

- [ ] **Step 6: Commit**

(Auto-pushed by script)

---

### Task 9: Cleanup & edge cases

**Files:**
- Modify: `gsc_attack.py`

- [ ] **Step 1: Add cleanup function for test runs**

```python
def cleanup(slug: str) -> None:
    """删除生成的测试文件（仅用于调试）"""
    import os as _os
    files_to_rm = [
        DATA_DIR / f"{slug}.json",
        DIST_DIR / f"{slug}.html",
    ]
    for f in files_to_rm:
        if f.exists():
            _os.remove(f)
            print(f"   🗑 已删除: {f}")
```

Add `--cleanup` argument:

```python
    parser.add_argument("--cleanup", type=str, default=None, help="删除指定 slug 的测试文件")
```

And at start of `main()`:

```python
    if args.cleanup:
        cleanup(args.cleanup)
        return
```

- [ ] **Step 2: Add git dirty check refinement**

The dirty check at script start should only block if there are changes unrelated to `data/` and `dist/`:

```python
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
```

- [ ] **Step 3: Final end-to-end test with 20 questions**

```bash
python3 gsc_attack.py "osha subpart m guardrail height requirements 2026" --num 20 --mode bonus
```

Expected: Full pipeline runs, page live.

- [ ] **Step 4: Commit final changes**

```bash
git add gsc_attack.py
git commit -m "feat: gsc_attack.py cleanup and edge case handling"
git push
```

---

### Verification Checklist

After all tasks complete, run these checks:

```bash
# 1. Help text works
python3 gsc_attack.py --help

# 2. Bonus mode end-to-end
python3 gsc_attack.py "osha ladder safety test" --num 10 --mode bonus

# 3. Chapter mode end-to-end (manual cleanup first)
python3 gsc_attack.py "osha confined space entry" --num 15 --mode chapter

# 4. Verify live pages
# Open in browser:
#   https://osha-fall-protection.pages.dev/osha-ladder-safety-test.html
#   https://osha-fall-protection.pages.dev/osha-confined-space-entry.html

# 5. Duplicate slug behavior
python3 gsc_attack.py "osha ladder safety test" --num 5 --mode bonus
# Type "n" → should skip

# 6. CLI validation
python3 gsc_attack.py "test" --num 5   # should fail (num too low)
python3 gsc_attack.py "test" --num 50  # should fail (num too high)
```
