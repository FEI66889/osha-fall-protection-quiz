# Free OSHA 30-Hour Construction Practice Tests

400 realistic jobsite-scenario questions with detailed 29 CFR regulation references. **No registration, no login, completely free.**

**[👉 Start Practicing Now](https://osha-fall-protection.pages.dev)**

---

## What's Covered (10 Chapters, 40 Questions Each)

| Chapter | Topic | 29 CFR Reference |
|---------|-------|-------------------|
| 1 | Fall Protection | 1926.501 |
| 2 | Scaffold Safety | 1926.450-454 |
| 3 | Electrical Safety | 1926.400-449 |
| 4 | Excavation & Trenching | 1926.650-652 |
| 5 | Cranes & Derricks | 1926.550-555 |
| 6 | PPE & Lifesaving Equipment | 1926.100-107 |
| 7 | Hazard Communication | 1926.1100-1152 |
| 8 | Materials Handling & Storage | 1926.250-252 |
| 9 | Stairways & Ladders | 1926.1050-1060 |
| 10 | Confined Spaces | 1926.800-806 |

## Features

- **Real job-site scenarios** — not generic textbook questions
- **Detailed rationales** — every answer includes 29 CFR citations, real incident examples, and common mistake analysis
- **Paginated** — 10 questions per page, 4 pages per chapter
- **Instant feedback** — select an answer, see correct/incorrect immediately with full explanation
- **SEO-friendly** — structured data (Quiz, BreadcrumbList schemas), sitemap, canonical URLs
- **Mobile responsive** — works on phones, tablets, and desktops
- **Static HTML** — no JavaScript framework, loads instantly

## Tech Stack

- **Content**: JSON data files with 400 hand-crafted questions
- **Build**: Python 3 + Jinja2 → static HTML
- **CSS**: Tailwind CSS v4 (compiled, ~19KB / ~4KB gzipped)
- **Hosting**: Cloudflare Pages (global CDN, free tier)
- **Deploy**: `npx wrangler pages deploy dist/`

## How to Build Locally

```bash
# Install dependencies
pip install jinja2
npm install

# Build Tailwind CSS
npx @tailwindcss/cli -i src/input.css -o dist/tailwind.css --minify

# Generate site
python3 build_site.py

# Output in dist/
ls dist/
```

## How to Update Questions

1. Edit JSON files in `data/`
2. Run `python3 build_site.py`
3. Run `npx wrangler pages deploy dist --project-name osha-fall-protection`

Or to regenerate all questions via AI:

1. Set `CLAUDE_API_KEY` in `config.py`
2. Run `python3 build_site.py`

## License

MIT — use, modify, and share freely.
