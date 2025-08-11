from flask import Flask, request, jsonify, send_from_directory
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from flask_cors import CORS
import os

app = Flask(__name__, static_folder="admin", static_url_path="/admin")
CORS(app, resources={r"/api/*": {"origins": "*"}})

DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set. Provide it via environment variable.")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)

@app.get("/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok"}
    except SQLAlchemyError as e:
        return {"status": "db_error", "detail": str(e)}, 500

@app.post("/api/verify_license")
def verify_license():
    email = (request.form.get("email") or (request.json or {}).get("email") if request.is_json else "").strip().lower()
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
        return jsonify({"status":"erro", "msg":"Falha DB"}), 500

def _check_admin_key(req):
    key = req.headers.get("x-api-key") or req.args.get("api_key") or ""
    return ADMIN_API_KEY and key == ADMIN_API_KEY

@app.post("/api/admin/licenses")
def admin_add_or_activate():
    if not _check_admin_key(request):
        return {"error":"unauthorized"}, 401
    data = request.get_json(silent=True) or request.form
    email = (data.get("email") or "").strip().lower()
    ativo = int(data.get("ativo", 1))
    if not email:
        return {"error":"email requerido"}, 400
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO licencas (email, ativo)
                VALUES (:email, :ativo)
                ON CONFLICT (email) DO UPDATE SET ativo=EXCLUDED.ativo
            """), {"email": email, "ativo": ativo})
        return {"status":"ok", "email": email, "ativo": ativo}
    except SQLAlchemyError as e:
        return {"error":"db", "detail": str(e)}, 500

@app.patch("/api/admin/licenses/deactivate")
def admin_deactivate():
    if not _check_admin_key(request):
        return {"error":"unauthorized"}, 401
    data = request.get_json(silent=True) or request.form
    email = (data.get("email") or "").strip().lower()
    if not email:
        return {"error":"email requerido"}, 400
    try:
        with engine.begin() as conn:
            res = conn.execute(text("UPDATE licencas SET ativo=0 WHERE lower(email)=:email"), {"email": email})
        return {"status":"ok", "updated": res.rowcount}
    except SQLAlchemyError as e:
        return {"error":"db", "detail": str(e)}, 500

@app.delete("/api/admin/licenses")
def admin_delete():
    if not _check_admin_key(request):
        return {"error":"unauthorized"}, 401
    email = (request.args.get("email") or "").strip().lower()
    if not email:
        return {"error":"email requerido"}, 400
    try:
        with engine.begin() as conn:
            res = conn.execute(text("DELETE FROM licencas WHERE lower(email)=:email"), {"email": email})
        return {"status":"ok", "deleted": res.rowcount}
    except SQLAlchemyError as e:
        return {"error":"db", "detail": str(e)}, 500

@app.get("/api/admin/licenses")
def admin_list():
    if not _check_admin_key(request):
        return {"error":"unauthorized"}, 401
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT id, email, ativo, created_at FROM licencas ORDER BY id DESC LIMIT 500")).mappings().all()
        items = []
        for r in rows:
            d = dict(r)
            if "created_at" not in d and "criado_em" in d:
                d["created_at"] = d.pop("criado_em")
            items.append(d)
        return {"items": items}
    except SQLAlchemyError as e:
        return {"error":"db", "detail": str(e)}, 500

@app.get("/")
def root_redirect():
    return send_from_directory(app.static_folder, "index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=True)
