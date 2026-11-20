"""
Pre-renderiza cada respuesta de la API a archivos JSON para una demo publica estatica
(Firebase Hosting). El despliegue oficial en AWS sigue usando FastAPI; esto es solo
para tener una URL publica mientras el organizador despliega.

Uso: .venv/bin/python ml/build_static.py
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.main import league, players, team, player, players_index, teams  # noqa: E402

OUT = ROOT / "dashboard" / "dist" / "static"
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)


def dump(name, data):
    (OUT / name).write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")


lg = league()
meta = {
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
    "ai": {"enabled": False, "quota": 50, "remaining": 50},
}
try:
    from backend.main import deep_model, nn_model

    meta["challenger"] = nn_model()
    meta["deep"] = deep_model()
except Exception:
    meta["challenger"] = None
    meta["deep"] = None
dump("meta.json", meta)

n = 0
for t in meta["teams"]:
    for prof in ("GENERAL", "ATAQUE", "DEFENSA"):
        r = team(t, prof)
        if r.status_code == 200:
            dump(f"team-{t}-{prof}.json", json.loads(r.body))
            n += 1
print(f"equipos: {n} archivos")

m = 0
for nid in players().keys():
    r = player(int(nid))
    if r.status_code == 200:
        dump(f"player-{nid}.json", json.loads(r.body))
        m += 1
print(f"jugadores: {m} archivos")

dump("players.json", json.loads(players_index("", 400).body))
print(f"total {len(list(OUT.iterdir()))} archivos en {OUT}")
