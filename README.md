# RAW — REAL AS WE

RAW is a Django streetwear shop and brand site built around the supplied campaign photography and the official RAW mark. The logo source is preserved as `store/static/store/images/raw-logo-original.jpeg`; its white background is intentional and its silhouette has not been redrawn. Twenty provided photographs were optimized as WebP versions for campaign and starter-catalogue use.

## What is included

- Editorial home, shop, product pages, About, contact, terms and privacy pages.
- Responsive navigation, search, filters, product variation selection, quick view, cart and account pages.
- Django admin product/category/inventory/order control and staff dashboard.
- Guest checkout saves an order with **Pending WhatsApp confirmation** before opening WhatsApp at **+255 775 794 221**. Opening WhatsApp records only that the link was opened; it cannot detect a sent message, payment or confirmation.
- Customer registration, profile, saved addresses and account order history.
- Product image validation, database-backed cart/orders, stock reservation on admin confirmation, and stock restoration on cancellation.
- SQLite for local development; PostgreSQL through `DATABASE_URL` for production. Docker Compose includes PostgreSQL.
- Sitemap, robots.txt, metadata, responsive image loading, keyboard-friendly dialogs and reduced-motion behavior.

## Run locally (macOS/Linux)

```sh
cd raw-store
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_raw
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. Admin is at `/admin/`; the staff dashboard is at `/studio/`.

## Run locally (Windows PowerShell)

```powershell
cd raw-store
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
py manage.py migrate
py manage.py seed_raw
py manage.py createsuperuser
py manage.py runserver
```

If PowerShell blocks activation, use `\.venv\Scripts\python.exe manage.py ...` for each command.

## Starter catalogue data

`python manage.py seed_raw` creates sample products using the supplied photos. The listed prices (for example TZS 35,000 tees and TZS 65,000 hoodies) and quantity of five per size are starter placeholders, not verified RAW price or stock commitments. Review every product, SKU, variant, price, stock count, description and category in Django Admin before accepting real customer orders. The six supplied photos represent available campaign imagery; replace/reorder them in Admin as the real product photography is confirmed.

## PostgreSQL / Docker

For a local Docker deployment, set a unique `POSTGRES_PASSWORD` and `DJANGO_SECRET_KEY` in your shell or a private `.env`, then run:

```sh
docker compose up --build
docker compose exec web python manage.py createsuperuser
```

The app will be at `http://localhost:8000/`. Use HTTPS and set `SECURE_SSL_REDIRECT=True` in a real deployment. Never commit `.env` or production secrets.

For a hosting platform, provision PostgreSQL, install `requirements.txt`, set `DATABASE_URL`, `DJANGO_SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`, run `python manage.py migrate` and `python manage.py collectstatic --noinput`, then serve `config.wsgi:application` with Gunicorn. Configure persistent media storage/backups for product uploads. Set a real SMTP provider via `EMAIL_BACKEND` and `DEFAULT_FROM_EMAIL` to deliver password reset emails; the default local backend prints email to the console.

## Configuration and operational limits

- No OpenAI key, GitHub token, payment credential, WhatsApp API token, email-provider credentials, production domain, or hosting account is needed for this implementation. WhatsApp checkout is a user-reviewed `wa.me` handoff, not an API message sender.
- Payment is coordinated manually after WhatsApp confirmation. There is no card/mobile-money gateway and no automated payment state.
- Delivery price is “to be confirmed”; no unsupported delivery fee is added.
- Password reset is wired through Django auth; configure an email provider for customer delivery in production.
- Staff dashboard totals are database-backed. “Confirmed value” sums confirmed through delivered order subtotals; it is not a record of money collected. No payment gateway exists to report paid sales.
- Inventory is reserved when staff confirms the order, and returned to stock if a committed order is cancelled.
- `DEBUG=True` and SQLite are for local development. Use a generated secret, PostgreSQL, HTTPS, persistent media, and backups in production.

## Quality checks

```sh
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

The tests cover page/catalog responses, variation stock checks, database order creation, multi-line WhatsApp content and inventory transitions. They do not test real WhatsApp delivery, real payment, production hosting, email delivery, cross-device browser rendering or a live production database.
