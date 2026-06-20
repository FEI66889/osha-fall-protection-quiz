"""配置项 — 部署前请修改 DOMAIN 和 API_KEY"""

# ===== 必填 =====
CLAUDE_API_KEY = ""  # 从 https://console.anthropic.com/ 获取
DOMAIN = "https://osha-fall-protection.pages.dev"

# ===== Indexing API（自动通知 Google 抓取新页面）=====
INDEXING_SERVICE_ACCOUNT_FILE = ""   # 服务账号 JSON 密钥文件路径（相对于项目根目录或绝对路径）

# ===== 可选 =====
OUTPUT_DIR = "dist"
MODEL = "claude-sonnet-4-6"              # 性价比最优
MAX_TOKENS = 6000
TEMPERATURE = 0.75                        # 0.7-0.85 防重复
QUESTIONS_PER_CHAPTER = 40                # 每章节题量
