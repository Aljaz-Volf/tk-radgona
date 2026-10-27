# TK Gornja Radgona

Database-backed website and club operations application for Teniški klub Gornja Radgona. The original static concept remains available as `index.html`; the active application is the modular Flask project in `app/`.

The public site is in Slovenian and preserves the original clay-orange, tennis-ball yellow, court green, Barlow Condensed/Inter identity and dark colour scheme. Public content is read from the database. An empty database produces honest empty states rather than fictional club statistics.

## Architecture

```text
app/
├── __init__.py          application factory
├── config.py            environment-based configuration
├── extensions.py        SQLAlchemy, Migrate, Login, CSRF, rate limiting
├── models.py            relational domain model and constraints
├── forms.py             validated Flask-WTF forms
├── routes/              public, auth, admin, league, reservations blueprints
├── services/            audit, sanitizing, score/standings, bookings, uploads
├── templates/           accessible Jinja public/admin UI
└── static/              responsive CSS and small ES6 interactions
migrations/              Alembic migration history
tests/                   pytest application and business-rule coverage
run.py                   local and WSGI entry point
```

SQLite is the zero-configuration local/test fallback. Production is designed for PostgreSQL (including a per-court transaction advisory lock that serializes competing reservation attempts).

## Implemented features

- Secure login with scrypt password hashing, Flask-Login sessions, CSRF protection, safe redirect validation, login/reset rate limits, role checks and time-limited password-reset tokens.
- Administrator and member roles; administrator-created accounts and permission management; no default or hardcoded administrator.
- Database-driven public homepage, news, club pages, league/archive, player pages, results, standings, reservations and photo galleries.
- Administration dashboard with live database statistics and activity audit log.
- News drafts/publication scheduling, categories, sanitized rich text and validated images.
- League seasons, divisions, player assignment, match schedules, validated set scores and automatic standings (points, wins, set difference, game difference).
- Public court reservations through Courtiplay, with direct iPhone/Android/web links, registration guidance and support contacts. The local reservation domain and overlap protection remain available for administrative/history needs but are not presented as a competing public booking system.
- Published/hidden galleries with multi-image upload and a keyboard-accessible lightbox available only to authenticated members and administrators.
- Editable club information and contact/SEO settings.
- Responsive navigation, mobile tables/forms, focus states, flash messages, empty states, reduced-motion support and dark mode.

## Local setup (Python 3.12+)

PowerShell example:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
flask --app run db upgrade
flask --app run init-db
flask --app run create-admin
flask --app run run --debug
```

Open `http://127.0.0.1:5000`. `init-db` is idempotent: it applies pending Alembic migrations and ensures the two built-in role records exist. Use `flask --app run seed-development --confirm-fictional` only for explicitly labelled local demo records; that command refuses to run when `FLASK_ENV=production`.

Run tests:

```powershell
pytest
```

## Configuration

Copy `.env.example` to `.env` and replace at least:

- `SECRET_KEY`: long random value, unique per environment.
- `DATABASE_URL`: PostgreSQL SQLAlchemy URL, for example Neon with `sslmode=require`.
- `SESSION_COOKIE_SECURE=true`: required behind production HTTPS.
- `RATELIMIT_STORAGE_URI`: use shared Redis-compatible storage when running multiple processes; in-memory storage is local-only.
- SMTP variables: required for delivery of password-reset messages.
- `STORAGE_BACKEND`: `local` for development or `s3` for production.
- `S3_*`: bucket, region, optional S3-compatible endpoint, credentials and optional public CDN base. Without a public base, media is served through five-minute signed URLs.
- `UPLOAD_FOLDER`: local persistent path used only by the development backend.

Never commit `.env`. The repository ignores the environment, local database, uploads, caches and virtual environments.

## Database and production

Apply schema changes with `flask --app run db upgrade`. Do not use `db.create_all()` as a deployment migration mechanism. A typical persistent Python host can start the application with:

```text
gunicorn --workers 2 --threads 4 --timeout 60 run:app
```

Before production deployment:

1. Provision PostgreSQL and configure `DATABASE_URL`/TLS.
2. Configure SMTP and test a password-reset delivery end to end.
3. Set `STORAGE_BACKEND=s3` and configure durable S3-compatible object storage (AWS S3, Cloudflare R2 or an equivalent service). The adapter validates image contents, sets the media type, deletes removed gallery files and supports either a public CDN base or short-lived signed delivery. Ephemeral container filesystems are not acceptable for production media.
4. Configure shared rate-limit storage, HTTPS, secure cookies, backups, log retention and health monitoring (`GET /zdravje`).
5. Run migrations, `init-db`, and the interactive `create-admin` command.
6. Run `pytest`, then exercise login, article upload, result entry and competing booking requests in staging.

No production credentials, hosting changes or live-domain changes are included in this repository.

## League assumptions

The official Liga Radgona rules still require club confirmation. Defaults are deliberately configurable per season:

- 2 points for a win and 0 for a loss.
- Ordering: points, wins, set difference, then game difference.
- Best-of-three score validation supports ordinary completed sets and a deciding match tiebreak (for example `6-4, 3-6, 10-8`).
- Head-to-head is not used as an automatic tie-break until the club confirms when and how it applies.

Administrators can change win/loss points and publish the official rules on each season. Changing scoring inputs requires re-saving a result (or invoking the standings recalculation service) so stored standings are rebuilt.

## Migration from the current website

The live WordPress site must remain untouched until an owner approves cutover.

1. **Inventory and backup:** obtain authorization; capture a full database/media backup, DNS values, redirects, forms and analytics configuration.
2. **Export:** use an authorized WordPress export and media copy. Treat the export as untrusted input; sanitize HTML and validate media before import.
3. **Map content:** map posts to `NewsArticle`, albums/media to galleries, and stable club pages to `ClubContent`. Verify names, dates and league records with a club representative; do not silently publish development seed data.
4. **Preserve URLs:** produce an old-to-new URL manifest and configure permanent redirects for every important indexed path. Keep the current domain canonical only after cutover.
5. **Stage:** deploy to a private staging host backed by a separate PostgreSQL database and media bucket. Test roles, mobile layouts, mail, migrations, backups and restore procedures.
6. **Approve and switch:** freeze edits briefly, take a final backup/delta export, obtain explicit approval, lower DNS TTL if appropriate, then change DNS/reverse-proxy routing.
7. **Rollback:** retain the prior site, database dump, media and DNS values throughout an agreed observation window. Roll back traffic if health, authentication, data integrity or redirects fail.

## Security notes

Rich text uses an allowlist sanitizer, uploads are verified by Pillow rather than filename alone, mutations use POST plus CSRF, and protected routes enforce permissions on the server. Audit records capture actor/action/entity/IP metadata but never passwords. For privacy, define a retention policy for audit and reservation data before production use.
