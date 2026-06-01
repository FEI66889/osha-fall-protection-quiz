# GSC Long-Tail Attack Script — Design Spec

**Date:** 2026-06-01  
**Status:** Draft  
**Project:** OSHA Fall Protection Quiz (`osha-fall-protection`)

## 1. Purpose

一键脚本 `gsc_attack.py`：输入一个 GSC 长尾关键词，自动完成 JSON 生成 → HTML 渲染 → sitemap 更新 → git push 的完整闭环。

## 2. Scope

- 独立的 CLI 脚本，不修改 `build_site.py`
- 复用 `config.py`（API key、domain）、`template/quiz_template.html`（Jinja2）、`data/` 目录
- 两种模式：`bonus`（独立页，首页不出现）和 `chapter`（加入章节列表，首页导航可见）
- 单页渲染（无分页），默认 20 题，可通过 `--num` 调整

## 3. Interface

```bash
python3 gsc_attack.py "osha subpart m guardrail height requirements 2026" [--num 10] [--mode bonus|chapter]
```

### Arguments

| Arg | Required | Default | Description |
|-----|----------|---------|-------------|
| `keyword` | yes | — | GSC 长尾关键词字符串 |
| `--num` | no | 20 | 题量，10-40 范围 |
| `--mode` | no | `bonus` | `bonus` 或 `chapter` |

## 4. Processing Pipeline

### Step 1: Keyword → Slug + Topic

- **Topic:** 首字母大写 + 末尾加 " Quiz"，例如关键词 `osha subpart m guardrail height requirements 2026` → `Osha Subpart M Guardrail Height Requirements 2026 Quiz`
- **Slug:** 小写 + 非字母数字替换为 `-` + 去重 `-` + 去首尾 `-`，限制 max 60 chars
- **不调用任何外部 API 做补全**，纯字符串处理

### Step 2: Claude API → JSON

- 复用 `config.py` 的 `CLAUDE_API_KEY`, `DOMAIN`, `MODEL`, `MAX_TOKENS`, `TEMPERATURE`
- 复用 `build_site.py` 的 `get_client()` 和 `call_claude()`（通过 import）
- 构建专用 Prompt：
  - 以 keyword 为核心主题，要求 10-20 道 realistic scenario-based 单选题
  - 每道题含：question, options[4], answer(ABCD), analysis（含 29 CFR 法规引用 + 真实后果 + 常见错误）
  - 生成 `seo_metadata`（unique_h1/meta_description/primary_keywords），h1 和 description 必须包含原始关键词
  - 用于 YMYL 内容审查，require detailed rationale in analysis
- 如果 API 失败：
  - 重试 3 次（已内置在 `call_claude`）
  - 3 次全失败 → 报错退出，不生成空文件

### Step 3: Save JSON

- 保存到 `data/{slug}.json`（格式与现有 10 个 JSON 一致：`{seo_metadata, questions}`）

### Step 4: Jinja2 Render → Static HTML

- 复用 `template/quiz_template.html`
- 所有 20 道题渲染在单页，无分页
- 保留所有现有特性：语义化 HTML（`<article>`）、FAQPage Schema、canonical URL、og tags、Tailwind CSS、原生 JS 交互（点击选项红绿反馈 + 展开解析）
- 输出到 `dist/{slug}.html`
- 若 `--mode chapter`：向 `build_site.py` 的 `chapters` 列表追加一行 entry，然后 `subprocess.run(['python3', 'build_site.py'])` 重建全站（含首页导航 + 章节页渲染）

### Step 5: Update sitemap.xml

- 读取现有 `dist/sitemap.xml`，追加新 URL entry
- 或调用 `build_site.generate_sitemap()` 的追加逻辑
- Priority: 0.9（高优先级）用于 bonus 模式；0.7（普通）用于 chapter 模式新页

### Step 6: Git Auto-Push

```bash
git add data/{slug}.json dist/{slug}.html dist/sitemap.xml [dist/index.html]
git commit -m "attack(gsc): {keyword}"
git push
```

- commit message 含关键词，方便以后回溯

## 5. Dependencies

- `anthropic` (same as build_site.py)
- `jinja2` (same)
- `config` (same)
- `build_site` module — import `get_client`, `call_claude`, `extract_json`, `Environment`, `FileSystemLoader`
- Python stdlib: `argparse`, `re`, `subprocess`, `datetime`, `pathlib`

## 6. Files Created/Modified

| File | Action | Mode |
|-------|--------|------|
| `gsc_attack.py` | new | — |
| `data/{slug}.json` | new | both |
| `dist/{slug}.html` | new | both |
| `dist/sitemap.xml` | modified | both |
| `dist/index.html` | modified | `chapter` only |
| `build_site.py` | modified | `chapter` only (add entry to chapters list) |

## 7. Error Handling

| Scenario | Behavior |
|----------|----------|
| No `CLAUDE_API_KEY` in config | Exit with message "Set CLAUDE_API_KEY in config.py" |
| JSON file already exists for slug | Prompt user: overwrite or abort |
| API call fails (all retries exhausted) | Exit 1, don't create files |
| API returns malformed JSON | `extract_json()` fallback regex, then exit if still invalid |
| Git not clean (uncommitted changes) | Exit with message "commit or stash first" |
| Git push fails | Exit with error, show stderr |

## 8. Testing

- **Smoke test:** `python3 gsc_attack.py "fall protection test" --num 10 --mode bonus`
- **Verify:** JSON saved to `data/`, HTML in `dist/`, sitemap updated
- **Verify:** `grep` for keyword in output HTML `<title>` and `<h1>`
- **Chapter mode test:** `python3 gsc_attack.py "scaffold safety quiz" --num 15 --mode chapter`
- **Verify:** Homepage updated with new entry, sitemap includes new URL

## 9. What This Script Does NOT Do

- Does NOT modify existing JSON files
- Does NOT add internal links from old pages to new page (manual step)
- Does NOT submit sitemap to GSC (already submitted once)
- Does NOT install dependencies (assumes existing dev env)
