# اجرای ACEWIN CRM با Docker

این پروژه با یک `docker-compose.yml` واحد در ریشه‌ی مخزن به‌طور کامل کانتینری شده: سه سرویس
`db` (PostgreSQL)، `backend` (FastAPI) و `frontend` (React build شده + Nginx).

## پیش‌نیاز
- Docker Engine 24+ و پلاگین `docker compose` (v2)

## راه‌اندازی سریع

```bash
cp .env.example .env
# .env را باز کنید و حداقل این دو مقدار را عوض کنید:
#   POSTGRES_PASSWORD
#   SECRET_KEY   (با: python -c "import secrets; print(secrets.token_hex(32))")

docker compose up -d --build
```

- فرانت‌اند: http://localhost:8080
- API: http://localhost:8000 (مستندات Swagger: http://localhost:8000/docs)
- سلامت سرویس: http://localhost:8000/api/health و http://localhost:8000/api/ready

فرانت‌اند از طریق Nginx مسیر `/api/*` را به backend پراکسی می‌کند، پس در حالت عادی هیچ
تنظیم CORS خاصی لازم نیست و همه چیز از یک origin سرو می‌شود.

## معماری Docker

| فایل | نقش |
|---|---|
| `backend/Dockerfile` | build چندمرحله‌ای Python 3.12 (venv جدا در builder، ایمیج نهایی slim، کاربر غیر-root، `HEALTHCHECK`) |
| `backend/docker/entrypoint.sh` | صبر برای آماده‌شدن Postgres، اجرای `alembic upgrade head`، سپس `exec` واقعی پردازه (PID 1 برای سیگنال‌ها) |
| `frontend/Dockerfile` | build چندمرحله‌ای: مرحله‌ی `node:20-alpine` برای build ویت، سپس `nginx:alpine` برای سرو استاتیک |
| `frontend/docker/nginx.conf` | سرو SPA (با fallback به `index.html`)، پراکسی `/api/` به backend، کش immutable برای assetهای hash‌دار |
| `docker-compose.yml` | orchestration کامل: healthcheck، `depends_on: condition: service_healthy`، volumeهای persist، شبکه‌ی مجزا |

## دیتای Olist برای Analytics Engine

موتور Analytics به فایل‌های CSV دیتاست Olist در `backend/data/olist/` نیاز دارد (این فایل‌ها
عمداً داخل ایمیج نیستند، چون حجیم و مخصوص محیط اجرا هستند). این پوشه به‌صورت bind mount به
کانتینر backend وصل است — کافی‌ست CSVها را همان‌جا روی هاست کپی کنید؛ کش feature table نیز در
`backend/data/_cache/` روی هاست ماندگار می‌ماند و بین rebuildها از بین نمی‌رود.

## دیتای نمونه (Seed)

سرویس `seed` با `--profile tools` جدا نگه داشته شده تا با `docker compose up` معمولی اجرا نشود:

```bash
docker compose --profile tools run --rm seed
```

برای دیتاست نمایشی/دمو به‌جای `seed.py`، در `docker-compose.yml` مقدار `entrypoint` سرویس
`seed` را به `["python", "seed_demo.py"]` تغییر دهید (جزئیات در docstring خودِ `seed_demo.py`).

## PostgreSQL در برابر SQLite

- `docker-compose.yml` همیشه Postgres را با هم راه می‌اندازد (مسیر رسمی staging/production).
- اگر بخواهید backend را بدون Docker و با SQLite محلی اجرا کنید (`backend/.env.example` →
  `DATABASE_URL=sqlite:///./crm.db`)، migration لازم نیست؛ جدول‌ها در startup با
  `Base.metadata.create_all` ساخته می‌شوند. این مسیر ربطی به Docker Compose ندارد.

## متغیرهای محیطی

همه‌ی متغیرهای قابل تنظیم و مقدار پیش‌فرض‌شان در `.env.example` (ریشه‌ی پروژه) مستند شده‌اند:
پورت‌های host، اطلاعات Postgres، `SECRET_KEY`، تنظیمات SMTP، و تنظیمات provider هوش مصنوعی
Copilot (`AI_PROVIDER=none` یعنی بدون هیچ فراخوانی شبکه‌ای — مقدار پیش‌فرض امن).

## دستورات مفید

```bash
docker compose logs -f backend        # لاگ زنده‌ی backend
docker compose exec backend alembic upgrade head   # اجرای دستی migration
docker compose down                   # توقف (دیتای Postgres در volume می‌ماند)
docker compose down -v                # توقف + پاک‌کردن volume دیتابیس (⚠️ غیرقابل بازگشت)
docker compose up -d --build backend  # rebuild و ری‌استارت فقط backend
```
