"""
ASV - Alignment Success Value | NFL Big Data Bowl 2026 (UNAM / AWS / NFL)
Backend FastAPI. Sirve artefactos precomputados (backend/precompute.py) y el agente Rusher.
Ejecuta: .venv/bin/uvicorn backend.main:app --reload
"""
import json
import os
import threading
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


def cargar_env():
    f = Path(__file__).resolve().parent.parent / ".env"
    if f.exists():
        for linea in f.read_text(encoding="utf-8-sig").splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                k, v = linea.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


cargar_env()

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "backend" / "artifacts"
DIST = ROOT / "dashboard" / "dist"

app = FastAPI(title="ASV - Alignment Success Value", version="1.0.0")


# ------------------------------------------------------------------ artefactos
@lru_cache(maxsize=1)
def league() -> dict:
    return json.loads((ART / "league.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def teams() -> dict:
    return json.loads((ART / "teams.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def players() -> dict:
    return json.loads((ART / "players.json").read_text(encoding="utf-8"))


ARTIFACTS_OK = all((ART / f).exists() for f in ("league.json", "teams.json", "players.json"))
if ARTIFACTS_OK:
    league(), teams(), players()  # calienta el cache al arrancar


@lru_cache(maxsize=1)
def nn_model() -> dict | None:
    """Pesos del MLP entrenado en Colab. Solo se reporta como contraste: la logistica
    iguala su AUC de prueba con 17 parametros en vez de 9,185."""
    f = ART / "asv_model.json"
    if not f.exists():
        return None
    d = json.loads(f.read_text(encoding="utf-8"))
    w = d.get("weights", {})
    n_params = sum(
        (len(r) if isinstance(r, list) else 1) * (len(r[0]) if isinstance(r, list) and r and isinstance(r[0], list) else 1)
        for r in w.values() for _ in [0]
    )
    return {
        "arch": d["metrics"].get("arch"),
        "device": d["metrics"].get("device"),
        "features": len(d.get("features", [])),
        "auc_test": d["metrics"].get("auc_test"),
        "logloss_test": d["metrics"].get("logloss_test"),
        "params": n_params,
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/meta")
def meta() -> dict:
    if not ARTIFACTS_OK:
        return {"ready": False}
    lg = league()
    return {
        "ready": True,
        "metric": lg["metric"],
        "model": lg["model"],
        "scope": lg["scope"],
        "teams": sorted(teams().keys()),
        "topOffenseConfigs": lg["topOffenseConfigs"],
        "topDefenseConfigs": lg["topDefenseConfigs"],
        "teamRankOffense": lg["teamRankOffense"],
        "teamRankDefense": lg["teamRankDefense"],
        "coefficients": lg["coefficients"],
        "challenger": nn_model(),
        "ai": {"enabled": bedrock_available(), "quota": QUOTA_LIMIT, "remaining": quota_remaining()},
    }


def _hydrate(nfl_ids):
    db = players()
    out = []
    for n in nfl_ids:
        p = db.get(str(n))
        if p:
            out.append(p)
    return out


@app.get("/api/team/{abbr}")
def team(abbr: str, profile: str = "GENERAL") -> JSONResponse:
    t = teams().get(abbr.upper())
    if not t:
        return JSONResponse({"error": "equipo no encontrado"}, status_code=404)
    key = profile.upper()
    prof = t["profiles"].get(key)
    if not prof:
        return JSONResponse({"error": "perfil no encontrado", "available": list(t["profiles"])}, status_code=404)
    db = players()
    lineup = []
    for slot in prof["lineup"]:
        p = db.get(str(slot["nflId"])) or {}
        lineup.append({
            **slot,
            "name": p.get("name", "—"),
            "jersey": p.get("jersey"),
            "position": p.get("position", ""),
            "team": p.get("team", abbr.upper()),
        })
    inactive = [
        {"nflId": p["nflId"], "name": p["name"], "jersey": p.get("jersey"),
         "position": p["position"], "plays": p["plays"], "team": p.get("team")}
        for p in _hydrate(prof["inactive"])
    ]
    inactive.sort(key=lambda r: -r["plays"])
    return JSONResponse({
        "team": abbr.upper(),
        "profile": key,
        "available": list(t["profiles"]),
        "config": prof["config"],
        "n": prof["n"],
        "asv": prof["asv"],
        "successRate": prof["successRate"],
        "expected": prof["expected"],
        "leagueAsv": prof.get("leagueAsv"),
        "alternatives": prof["alternatives"],
        "lineup": lineup,
        "inactive": inactive[:60],
    })


@app.get("/api/player/{nfl_id}")
def player(nfl_id: int) -> JSONResponse:
    p = players().get(str(nfl_id))
    if not p:
        return JSONResponse({"error": "jugador no encontrado"}, status_code=404)
    db = players()
    pos = p["position"]
    peers = [q for q in db.values() if q["position"] == pos and q["plays"] >= 20]

    def pct(field):
        vals = [q[field] for q in peers if q.get(field) is not None]
        mine = p.get(field)
        if mine is None or len(vals) < 5:
            return None
        return round(100.0 * sum(1 for v in vals if v <= mine) / len(vals), 1)

    return JSONResponse({
        **p,
        "peerGroup": {"position": pos, "n": len(peers)},
        "percentiles": {
            k: pct(k) for k in
            ("topSpeed", "topAccel", "pressureRate", "asvOnField", "plays", "completionPct", "yardsPerAttempt")
        },
    })


@app.get("/api/players")
def players_index(q: str = "", limit: int = 40) -> JSONResponse:
    ql = q.strip().lower()
    rows = [
        {"nflId": p["nflId"], "name": p["name"], "position": p["position"],
         "team": p.get("team"), "jersey": p.get("jersey"), "plays": p["plays"]}
        for p in players().values()
        if not ql or ql in p["name"].lower() or ql == p["position"].lower() or ql == str(p.get("team", "")).lower()
    ]
    rows.sort(key=lambda r: -r["plays"])
    return JSONResponse(rows[:limit])


# ------------------------------------------------------------------ Rusher (Bedrock)
QUOTA_LIMIT = 50
_quota_lock = threading.Lock()
_quota = {"day": None, "used": 0}
CDMX = timezone(timedelta(hours=-6))


def _today():
    return datetime.now(CDMX).date().isoformat()


def quota_remaining() -> int:
    with _quota_lock:
        if _quota["day"] != _today():
            return QUOTA_LIMIT
        return max(0, QUOTA_LIMIT - _quota["used"])


def quota_take() -> int:
    """Cuota en memoria: el servidor es efimero, no se escribe a disco. Se reinicia a las 00:00 CDMX."""
    with _quota_lock:
        if _quota["day"] != _today():
            _quota.update(day=_today(), used=0)
        if _quota["used"] >= QUOTA_LIMIT:
            return -1
        _quota["used"] += 1
        return QUOTA_LIMIT - _quota["used"]


@lru_cache(maxsize=1)
def bedrock_client():
    import boto3
    return boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))


def bedrock_available() -> bool:
    try:
        bedrock_client()
        return True
    except Exception:
        return False


# --- herramientas del agente: Rusher solo responde con numeros que salen de los artefactos
def tool_team_profile(team_abbr: str, profile: str = "GENERAL") -> dict:
    t = teams().get(str(team_abbr).upper())
    if not t:
        return {"error": f"equipo {team_abbr} no existe"}
    pr = t["profiles"].get(str(profile).upper()) or next(iter(t["profiles"].values()))
    db = players()
    return {
        "team": team_abbr.upper(), "profile": profile.upper(), "config": pr["config"],
        "snaps": pr["n"], "asv": pr["asv"], "successRate": pr["successRate"], "expected": pr["expected"],
        "lineup": [
            {"slot": s["slot"], "name": db.get(str(s["nflId"]), {}).get("name"),
             "jersey": db.get(str(s["nflId"]), {}).get("jersey"), "snaps": s["snaps"]}
            for s in pr["lineup"]
        ],
        "alternatives": pr["alternatives"][:4],
    }


def tool_player_stats(name_or_id: str) -> dict:
    db = players()
    s = str(name_or_id).strip()
    if s.isdigit() and s in db:
        return db[s]
    hits = [p for p in db.values() if s.lower() in p["name"].lower()]
    hits.sort(key=lambda p: -p["plays"])
    if not hits:
        return {"error": f"sin coincidencias para {name_or_id}"}
    return {"matches": len(hits), "player": hits[0]}


def tool_league_ranking(side: str = "OFFENSE", top: int = 10) -> dict:
    lg = league()
    key = "teamRankOffense" if str(side).upper().startswith("OFF") else "teamRankDefense"
    return {"side": side, "ranking": lg[key][: max(1, min(32, int(top)))],
            "topConfigs": lg["topOffenseConfigs" if key == "teamRankOffense" else "topDefenseConfigs"][:5]}


def tool_metric_definition() -> dict:
    lg = league()
    return {"metric": lg["metric"], "model": lg["model"], "scope": lg["scope"]}


TOOLS = {
    "team_profile": (tool_team_profile, "Acomodo optimo (ASV) de un equipo. Args: team_abbr, profile (GENERAL|ATAQUE|DEFENSA)."),
    "player_stats": (tool_player_stats, "Estadisticas de un jugador por nombre o nflId. Args: name_or_id."),
    "league_ranking": (tool_league_ranking, "Ranking ASV de los 32 equipos. Args: side (OFFENSE|DEFENSE), top."),
    "metric_definition": (tool_metric_definition, "Definicion formal de ASV, metricas del modelo y alcance de datos."),
}

TOOL_SPEC = [
    {"toolSpec": {
        "name": n,
        "description": d,
        "inputSchema": {"json": {
            "type": "object",
            "properties": (
                {"team_abbr": {"type": "string"}, "profile": {"type": "string"}} if n == "team_profile"
                else {"name_or_id": {"type": "string"}} if n == "player_stats"
                else {"side": {"type": "string"}, "top": {"type": "integer"}} if n == "league_ranking"
                else {}
            ),
            "required": (["team_abbr"] if n == "team_abbr" else []),
        }},
    }}
    for n, (_, d) in TOOLS.items()
]

SYSTEM = """Eres Rusher, analista asistente del tablero ASV (Alignment Success Value) del NFL Big Data Bowl 2026.
ASV mide cuantas jugadas exitosas por snap gana un acomodo (formacion + personal) por encima de lo esperado
dada la situacion de juego, sobre las semanas 1-8 de la temporada 2021 (solo jugadas de pase).

Reglas estrictas:
- Nunca inventes cifras. Toda cifra que digas debe venir de una herramienta. Si no la tienes, llama a la herramienta.
- Si una pregunta sale del alcance de los datos (lesiones, temporadas distintas, jugadas de carrera, patadas), dilo claramente.
- Responde como analista para un entrenador: la decision primero, luego el numero que la respalda.
- Maximo 120 palabras. Espanol neutro, sin emojis, sin adornos.
- ASV se expresa en jugadas exitosas por 100 snaps: multiplica por 100 al narrarlo."""


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=600)


@app.post("/api/chat")
def chat(body: ChatIn) -> JSONResponse:
    if not ARTIFACTS_OK:
        return JSONResponse({"error": "sin_datos", "message": "Los datos del analisis aun no estan listos."}, status_code=503)
    left = quota_take()
    if left < 0:
        return JSONResponse(
            {"error": "cuota_agotada", "remaining": 0,
             "message": "Rusher alcanzo sus 50 consultas del dia. La bolsa se renueva a las 00:00 (CDMX)."},
            status_code=429,
        )
    try:
        client = bedrock_client()
        model_id = os.environ.get("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0")
        messages = [{"role": "user", "content": [{"text": body.message}]}]
        used = []
        for _ in range(4):
            resp = client.converse(
                modelId=model_id,
                messages=messages,
                system=[{"text": SYSTEM}],
                toolConfig={"tools": TOOL_SPEC},
                inferenceConfig={"maxTokens": 600, "temperature": 0.2},
            )
            out = resp["output"]["message"]
            messages.append(out)
            calls = [c["toolUse"] for c in out.get("content", []) if "toolUse" in c]
            if not calls:
                text = "".join(c.get("text", "") for c in out.get("content", []))
                return JSONResponse({"reply": text.strip(), "tools": used, "remaining": left})
            results = []
            for tu in calls:
                fn = TOOLS.get(tu["name"], (None, None))[0]
                try:
                    data = fn(**(tu.get("input") or {})) if fn else {"error": "herramienta desconocida"}
                except Exception as e:
                    data = {"error": str(e)}
                used.append({"name": tu["name"], "input": tu.get("input")})
                results.append({"toolResult": {"toolUseId": tu["toolUseId"], "content": [{"json": data}]}})
            messages.append({"role": "user", "content": results})
        return JSONResponse({"reply": "No pude cerrar el analisis en los pasos disponibles.", "tools": used, "remaining": left})
    except Exception:
        return JSONResponse(
            {"error": "ia_no_disponible", "remaining": left,
             "message": "El servicio de chat no esta disponible en este momento. El analisis del tablero no depende de la IA."},
            status_code=503,
        )


# ------------------------------------------------------------------ frontend
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(DIST / "assets")), name="assets")

    @app.get("/")
    def index():
        return FileResponse(str(DIST / "index.html"))

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        f = DIST / full_path
        if f.is_file():
            return FileResponse(str(f))
        return FileResponse(str(DIST / "index.html"))
