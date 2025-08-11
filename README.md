# Invest Bot License API + Admin Panel (Ready)

## Como usar
1) Rode o schema no Neon:
```bash
psql "$DATABASE_URL" -f schema.sql
```

2) Local:
```bash
pip install -r requirements.txt
python app.py
# ou
gunicorn app:app --workers=2 --threads=4 --timeout=60
```

3) Deploy no Render:
- Build: `pip install -r requirements.txt`
- Start: `gunicorn app:app --workers=2 --threads=4 --timeout=60`
- Env Vars: `DATABASE_URL`, `ADMIN_API_KEY`

4) Admin:
- Abra `/admin/` e informe sua API Key (x-api-key).

## Endpoints
- POST `/api/verify_license`
- GET `/api/admin/licenses` (x-api-key)
- POST `/api/admin/licenses` (x-api-key)
- PATCH `/api/admin/licenses/deactivate` (x-api-key)
- DELETE `/api/admin/licenses?email=...` (x-api-key)
