from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import os, logging

app = Flask(__name__, static_folder="admin", static_url_path="/admin")
CORS(app, resources={r"/api/*": {"origins": "*"}})
logging.basicConfig(level=logging.INFO)

# ---- ENV ----
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set.")

# Usar psycopg3 com SQLAlchemy
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Engine
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)

# ---- Garante tabela/colunas no boot ----
def ensure_schema():
    with engine.begin() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS licencas (
          id SERIAL PRIMARY KEY,
          email TEXT UNIQUE NOT NULL,
          ativo INTEGER NOT NULL DEFAULT 1,
          created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        """))
        # Caso tenha banco antigo com 'criado_em', mantemos e garantimos created_at também
        conn.execute(text("""
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='licencas' AND column_name='created_at'
          ) THEN
            ALTER TABLE licencas
            ADD COLUMN created_at TIMESTAMP NOT NULL DEFAULT NOW();
          END IF;
        END$$;
        """))

ensure_schema()

# ---- Saúde ----
@app.get("/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok"}
    except SQLAlchemyError as e:
        app.logger.exception("db error (health)")
        return {"status": "db_error", "detail": str(e)}, 500

# ---- Verificação para o BOT ----
@app.post("/api/verify_license")
def verify_license():
    email = (request.form.get("email") or (request.json or {}).get("email") if request.is_json else "")
    email = (email or "").strip().lower()
    if not email:
        return jsonify({"status":"erro", "msg":"Email inválido"}), 200
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("SELECT ativo FROM licencas WHERE lower(email)=:email LIMIT 1"),
                {"email": email}
            ).mappings().first()
        if row is None:
            return jsonify({"status":"erro", "msg":"Licença não encontrada"}), 200
        if int(row["ativo"]) == 1:
            return jsonify({"status":"ok"}), 200
        else:
            return jsonify({"status":"erro", "msg":"Licença suspensa"}), 200
    except SQLAlchemyError as e:
        app.logger.exception("db error (verify)")
        return jsonify({"status":"erro","msg":"Falha DB","detail":str(e)}), 500

# ---- Admin helper ----
def check_key(req):
    key = req.headers.get("x-api-key") or req.args.get("api_key") or ""
    return ADMIN_API_KEY and key == ADMIN_API_KEY

# ---- Admin: listar ----
@app.get("/api/admin/licenses")
def admin_list():
    if not check_key(request):
        return {"error":"unauthorized"}, 401
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT
                  id,
                  email,
                  ativo,
                  COALESCE(created_at, criado_em) AS created_at
                FROM licencas
                ORDER BY id DESC
                LIMIT 500
            """)).mappings().all()
        return {"items": [dict(r) for r in rows]}
    except SQLAlchemyError as e:
        app.logger.exception("db error (list)")
        return {"error":"db", "detail": str(e)}, 500

# ---- Admin: criar/ativar (upsert) ----
@app.post("/api/admin/licenses")
@app.post("/api/admin/licenses")
def admin_add_or_activate():
    if not check_key(request):
        return {"error":"unauthorized"}, 401
    data = request.get_json(silent=True) or request.form
    email = (data.get("email") or "").strip().lower()
    try:
        ativo = int(data.get("ativo", 1))
    except Exception:
        return {"error":"ativo inválido"}, 400
    if not email:
        return {"error":"email requerido"}, 400
    try:
        with engine.begin() as conn:
            # garante UNIQUE em email (caso tabela antiga não tenha)
            conn.execute(text("""
                DO $$
                BEGIN
                  IF NOT EXISTS (
                    SELECT 1 FROM pg_indexes
                    WHERE schemaname = 'public'
                      AND indexname = 'licencas_email_key'
                  ) THEN
                    BEGIN
                      ALTER TABLE licencas
                      ADD CONSTRAINT licencas_email_key UNIQUE (email);
                    EXCEPTION WHEN duplicate_table THEN
                      -- ignora se já existir
                      NULL;
                    END;
                  END IF;
                END$$;
            """));
            conn.execute(text("""
                INSERT INTO licencas (email, ativo)
                VALUES (:email, :ativo)
                ON CONFLICT (email) DO UPDATE SET ativo=EXCLUDED.ativo
            """), {"email": email, "ativo": ativo})
        return {"status":"ok", "email": email, "ativo": ativo}
    except SQLAlchemyError as e:
        app.logger.exception("db error (upsert)")
        return {"error":"db", "detail": str(e)}, 500

# ---- Admin: desativar ----
@app.patch("/api/admin/licenses/deactivate")
def admin_deactivate():
    if not check_key(request):
        return {"error":"unauthorized"}, 401
    data = request.get_json(silent=True) or request.form
    email = (data.get("email") or "").strip().lower()
    if not email:
        return {"error":"email requerido"}, 400
    try:
        with engine.begin() as conn:
            res = conn.execute(text("UPDATE licencas SET ativo=0 WHERE lower(email)=:email"),
                               {"email": email})
        return {"status":"ok", "updated": res.rowcount}
    except SQLAlchemyError as e:
        app.logger.exception("db error (deactivate)")
        return {"error":"db", "detail": str(e)}, 500

# ---- Admin: excluir ----
@app.delete("/api/admin/licenses")
def admin_delete():
    if not check_key(request):
        return {"error":"unauthorized"}, 401
    email = (request.args.get("email") or "").strip().lower()
    if not email:
        return {"error":"email requerido"}, 400
    try:
        with engine.begin() as conn:
            res = conn.execute(text("DELETE FROM licencas WHERE lower(email)=:email"),
                               {"email": email})
        return {"status":"ok", "deleted": res.rowcount}
    except SQLAlchemyError as e:
        app.logger.exception("db error (delete)")
        return {"error":"db", "detail": str(e)}, 500

# ---- Servir o painel ----
@app.get("/")
def root():
    return send_from_directory(app.static_folder, "index.html")

@app.get("/admin/")
def admin_root():
    return send_from_directory(app.static_folder, "index.html")

# ---- Erros de API sempre em JSON ----
@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "not_found", "path": request.path}), 404
    return e

@app.errorhandler(500)
def internal_error(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "server", "detail": str(e)}), 500
    return e

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=True)
