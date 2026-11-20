"""
ASV - Alignment Success Value
Precomputo offline. Genera backend/artifacts/*.json que el backend sirve en runtime.
Uso: .venv/bin/python backend/precompute.py
"""
import json
import glob
import os
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "backend" / "artifacts"
OUT.mkdir(parents=True, exist_ok=True)

T0 = time.time()


def log(msg):
    print(f"[{time.time() - T0:7.1f}s] {msg}", flush=True)


# ---------------------------------------------------------------- tablas base
log("cargando tablas base")
games = pd.read_csv(DATA / "games.csv")
players = pd.read_csv(DATA / "players.csv")
plays = pd.read_csv(DATA / "plays.csv")
pff = pd.read_csv(DATA / "pffScoutingData.csv")

# altura a pulgadas
def height_in(h):
    try:
        f, i = str(h).split("-")
        return int(f) * 12 + int(i)
    except Exception:
        return np.nan


players["heightIn"] = players["height"].map(height_in)
players["age"] = (
    pd.Timestamp("2021-09-09") - pd.to_datetime(players["birthDate"], errors="coerce")
).dt.days / 365.25

# ---------------------------------------------------------------- situacion
plays = plays.merge(games[["gameId", "week", "homeTeamAbbr", "visitorTeamAbbr"]], on="gameId", how="left")
plays["isHomeOffense"] = plays["possessionTeam"] == plays["homeTeamAbbr"]
plays["scoreDiff"] = np.where(
    plays["isHomeOffense"],
    plays["preSnapHomeScore"] - plays["preSnapVisitorScore"],
    plays["preSnapVisitorScore"] - plays["preSnapHomeScore"],
)
# yardas reales a la zona de anotacion
plays["yardsToEZ"] = np.where(
    plays["yardlineSide"].isna(),
    50,
    np.where(plays["yardlineSide"] == plays["possessionTeam"], 100 - plays["yardlineNumber"], plays["yardlineNumber"]),
)
# reloj a segundos restantes del cuarto
clk = plays["gameClock"].astype(str).str.split(":", expand=True)
plays["clockSec"] = pd.to_numeric(clk[0], errors="coerce").fillna(0) * 60 + pd.to_numeric(clk[1], errors="coerce").fillna(0)

# exito de jugada (definicion estandar de football analytics)
need = np.select(
    [plays["down"] == 1, plays["down"] == 2],
    [0.45 * plays["yardsToGo"], 0.60 * plays["yardsToGo"]],
    default=plays["yardsToGo"].astype(float),
)
plays["success"] = ((plays["prePenaltyPlayResult"] >= need) & (plays["passResult"] != "IN")).astype(int)
plays["isTD"] = plays["playDescription"].str.contains("TOUCHDOWN", case=False, na=False).astype(int)

ANALYZABLE = plays[(plays["down"] > 0)].copy()
log(f"jugadas analizables: {len(ANALYZABLE)}")

# ---------------------------------------------------------------- modelo
def design_matrix(df):
    """Rasgos situacionales. Controlan el contexto para que ASV no premie situaciones faciles."""
    cols = {}
    cols["ytg"] = df["yardsToGo"].clip(0, 25) / 25.0
    cols["ytg2"] = (df["yardsToGo"].clip(0, 25) / 25.0) ** 2
    cols["ez"] = df["yardsToEZ"] / 100.0
    cols["ez2"] = (df["yardsToEZ"] / 100.0) ** 2
    cols["sdiff"] = np.tanh(df["scoreDiff"] / 14.0)
    cols["clock"] = df["clockSec"] / 900.0
    cols["q4late"] = ((df["quarter"] >= 4) & (df["clockSec"] < 300)).astype(float)
    for d in (2, 3, 4):
        cols[f"down{d}"] = (df["down"] == d).astype(float)
    cols["shortytg"] = (df["yardsToGo"] <= 3).astype(float)
    cols["longytg"] = (df["yardsToGo"] >= 10).astype(float)
    cols["redzone"] = (df["yardsToEZ"] <= 20).astype(float)
    X = pd.DataFrame(cols).astype("float64")
    return X.values, list(X.columns)


def fit_logreg(X, y, l2=1.0, iters=60):
    """Newton-IRLS con ridge. Puro numpy para que la inferencia viva dentro del stack."""
    Xb = np.hstack([np.ones((X.shape[0], 1)), X])
    w = np.zeros(Xb.shape[1])
    R = np.eye(Xb.shape[1]) * l2
    R[0, 0] = 0.0
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-np.clip(Xb @ w, -30, 30)))
        g = Xb.T @ (p - y) + R @ w
        W = np.clip(p * (1 - p), 1e-6, None)
        H = Xb.T * W @ Xb + R
        try:
            step = np.linalg.solve(H, g)
        except np.linalg.LinAlgError:
            break
        w -= step
        if np.max(np.abs(step)) < 1e-8:
            break
    return w


def predict(w, X):
    Xb = np.hstack([np.ones((X.shape[0], 1)), X])
    return 1.0 / (1.0 + np.exp(-np.clip(Xb @ w, -30, 30)))


def auc(y, p):
    o = np.argsort(p)
    y = np.asarray(y)[o]
    r = np.arange(1, len(y) + 1)
    n1, n0 = y.sum(), (1 - y).sum()
    if n1 == 0 or n0 == 0:
        return float("nan")
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


log("entrenando modelo de expectativa situacional")
X, feat_names = design_matrix(ANALYZABLE)
y = ANALYZABLE["success"].values.astype("float64")

# split por partido para que no haya fuga entre jugadas del mismo juego
gids = ANALYZABLE["gameId"].unique()
rng = np.random.default_rng(42)
rng.shuffle(gids)
test_games = set(gids[: max(1, int(len(gids) * 0.2))])
is_test = ANALYZABLE["gameId"].isin(test_games).values

w = fit_logreg(X[~is_test], y[~is_test], l2=2.0)
p_te = predict(w, X[is_test])
p_tr = predict(w, X[~is_test])
base_rate = float(y[~is_test].mean())
ll = lambda yy, pp: float(-np.mean(yy * np.log(np.clip(pp, 1e-9, 1)) + (1 - yy) * np.log(np.clip(1 - pp, 1e-9, 1))))
metrics = {
    "n_train": int((~is_test).sum()),
    "n_test": int(is_test.sum()),
    "auc_test": round(auc(y[is_test], p_te), 4),
    "auc_train": round(auc(y[~is_test], p_tr), 4),
    "logloss_test": round(ll(y[is_test], p_te), 4),
    "logloss_baseline": round(ll(y[is_test], np.full(is_test.sum(), base_rate)), 4),
    "base_success_rate": round(base_rate, 4),
}
log(f"modelo listo: {metrics}")

w_full = fit_logreg(X, y, l2=2.0)
ANALYZABLE["expected"] = predict(w_full, X)
ANALYZABLE["asv_play"] = ANALYZABLE["success"] - ANALYZABLE["expected"]

# ---------------------------------------------------------------- un solo barrido de tracking
log("barriendo 122 archivos de tracking (snap frame + picos de velocidad)")
TDTYPES = {
    "gameId": "int32", "playId": "int32", "nflId": "float32", "frameId": "int16",
    "jerseyNumber": "float32", "team": "category", "playDirection": "category",
    "x": "float32", "y": "float32", "s": "float32", "a": "float32", "event": "category",
}
snap_parts, perf_parts = [], []
files = sorted(glob.glob(str(DATA / "tracking" / "tracking_*.csv")))
for i, f in enumerate(files):
    try:
        df = pd.read_csv(f, usecols=list(TDTYPES.keys()), dtype=TDTYPES)
    except Exception as e:
        log(f"  omitido {os.path.basename(f)}: {e}")
        continue
    df = df[df["team"] != "football"]
    left = (df["playDirection"] == "left").values
    df["x_std"] = np.where(left, 120.0 - df["x"].values, df["x"].values)
    df["y_std"] = np.where(left, 53.3 - df["y"].values, df["y"].values)

    perf = df.groupby(["gameId", "playId", "nflId"], observed=True).agg(
        maxS=("s", "max"), maxA=("a", "max")
    ).reset_index()
    perf_parts.append(perf)

    ev = df["event"].astype(str)
    sn = df[ev.isin(["ball_snap", "autoevent_ballsnap"])]
    sf = sn.groupby(["gameId", "playId"], observed=True)["frameId"].min().rename("snapFrame").reset_index()
    allp = df[["gameId", "playId"]].drop_duplicates()
    sf = allp.merge(sf, on=["gameId", "playId"], how="left")
    sf["snapFrame"] = sf["snapFrame"].fillna(6).astype("int16")
    s = df.merge(sf, on=["gameId", "playId"], how="inner")
    s = s[s["frameId"] == s["snapFrame"]]
    s = s[["gameId", "playId", "nflId", "jerseyNumber", "team", "x_std", "y_std"]].rename(
        columns={"team": "trackTeam"}
    )
    snap_parts.append(s)
    if (i + 1) % 25 == 0:
        log(f"  {i + 1}/{len(files)} archivos")

snap = pd.concat(snap_parts, ignore_index=True)
perf = pd.concat(perf_parts, ignore_index=True)
del snap_parts, perf_parts
snap["nflId"] = snap["nflId"].astype("int64")
perf["nflId"] = perf["nflId"].astype("int64")
log(f"snap rows {len(snap)} | perf rows {len(perf)}")

# posicion relativa a la linea de golpeo, ya normalizada a atacar hacia +X
los = ANALYZABLE[["gameId", "playId", "quarter"]].copy()
snap = snap.merge(los, on=["gameId", "playId"], how="inner")
# la mediana de x_std de los 22 jugadores en el snap es un proxy robusto del centro de la formacion
los_std = snap.groupby(["gameId", "playId"])["x_std"].median().rename("los_x").reset_index()
snap = snap.merge(los_std, on=["gameId", "playId"], how="left")
snap["x_rel"] = snap["x_std"] - snap["los_x"]

# ---------------------------------------------------------------- configuraciones
pffj = pff.merge(
    ANALYZABLE[["gameId", "playId", "quarter", "possessionTeam", "defensiveTeam", "success", "asv_play",
                "offenseFormation", "personnelO", "personnelD", "pff_passCoverage", "dropBackType", "isTD"]],
    on=["gameId", "playId"], how="inner",
)
pffj["side"] = np.where(pffj["pff_role"].isin(["Pass", "Pass Block", "Pass Route"]), "OFF", "DEF")
pffj["team"] = np.where(pffj["side"] == "OFF", pffj["possessionTeam"], pffj["defensiveTeam"])
pffj["configOff"] = pffj["offenseFormation"].fillna("UNKNOWN") + " | " + pffj["personnelO"].fillna("UNKNOWN")
pffj["configDef"] = pffj["personnelD"].fillna("UNKNOWN") + " | " + pffj["pff_passCoverage"].fillna("UNKNOWN")
pffj["config"] = np.where(pffj["side"] == "OFF", pffj["configOff"], pffj["configDef"])

snap_pos = snap.merge(
    pffj[["gameId", "playId", "nflId", "pff_positionLinedUp", "pff_role", "side", "team", "config"]],
    on=["gameId", "playId", "nflId"], how="inner",
)
log(f"snap+pff rows {len(snap_pos)}")

# ---------------------------------------------------------------- ASV por equipo/configuracion
K_SHRINK = 40.0
league = ANALYZABLE.copy()


def config_table(side):
    pl = ANALYZABLE.copy()
    if side == "OFF":
        pl["team"] = pl["possessionTeam"]
        pl["config"] = pl["offenseFormation"].fillna("UNKNOWN") + " | " + pl["personnelO"].fillna("UNKNOWN")
        pl["asv"] = pl["asv_play"]
    else:
        pl["team"] = pl["defensiveTeam"]
        pl["config"] = pl["personnelD"].fillna("UNKNOWN") + " | " + pl["pff_passCoverage"].fillna("UNKNOWN")
        pl["asv"] = -pl["asv_play"]
    g = pl.groupby(["team", "config"]).agg(
        n=("asv", "size"), raw=("asv", "mean"), sr=("success", "mean"),
        exp=("expected", "mean"), td=("isTD", "sum"),
    ).reset_index()
    g["asv"] = g["raw"] * (g["n"] / (g["n"] + K_SHRINK))
    lg = pl.groupby("config").agg(nL=("asv", "size"), rawL=("asv", "mean")).reset_index()
    lg["asvL"] = lg["rawL"] * (lg["nL"] / (lg["nL"] + K_SHRINK))
    return g.merge(lg[["config", "nL", "asvL"]], on="config", how="left"), lg


off_tab, off_lg = config_table("OFF")
def_tab, def_lg = config_table("DEF")
log("tablas ASV por configuracion listas")

# ---------------------------------------------------------------- once ideal por equipo/configuracion
SLOT_ORDER_HINT = ["QB", "C", "LG", "RG", "LT", "RT"]


def lineup(team, side, config, min_plays=4):
    sel = snap_pos[(snap_pos["team"] == team) & (snap_pos["side"] == side) & (snap_pos["config"] == config)]
    if len(sel) == 0:
        return []
    slots = (
        sel.groupby("pff_positionLinedUp")
        .agg(n=("nflId", "size"), x=("x_rel", "mean"), y=("y_std", "mean"))
        .reset_index()
        .sort_values("n", ascending=False)
    )
    slots = slots.head(13)
    out = []
    used = set()
    for _, r in slots.iterrows():
        cand = sel[sel["pff_positionLinedUp"] == r["pff_positionLinedUp"]]
        counts = cand.groupby("nflId").size().sort_values(ascending=False)
        pick = None
        for nid in counts.index:
            if nid not in used:
                pick = int(nid)
                break
        if pick is None:
            continue
        used.add(pick)
        sub = cand[cand["nflId"] == pick]
        out.append({
            "slot": str(r["pff_positionLinedUp"]),
            "nflId": pick,
            "x": round(float(sub["x_rel"].mean()), 2),
            "y": round(float(sub["y_std"].mean()), 2),
            "snaps": int(counts.loc[pick]),
            "slotShare": round(float(counts.loc[pick] / counts.sum()), 3),
            "role": str(sub["pff_role"].mode().iloc[0]) if len(sub) else "",
        })
        if len(out) == 11:
            break
    return out


# ---------------------------------------------------------------- estadisticas por jugador
log("agregando estadisticas por jugador")
jersey = snap.groupby("nflId")["jerseyNumber"].agg(lambda s: float(s.mode().iloc[0]) if len(s.mode()) else np.nan)
peak = perf.groupby("nflId").agg(topSpeed=("maxS", "max"), avgPeakSpeed=("maxS", "mean"), topAccel=("maxA", "max"))

pstat = pffj.groupby("nflId").agg(
    plays=("playId", "size"),
    pressures=("pff_hurry", lambda s: int(np.nansum(s))),
    hits=("pff_hit", lambda s: int(np.nansum(s))),
    sacks=("pff_sack", lambda s: int(np.nansum(s))),
    pressAllowed=("pff_hurryAllowed", lambda s: int(np.nansum(s))),
    hitsAllowed=("pff_hitAllowed", lambda s: int(np.nansum(s))),
    sacksAllowed=("pff_sackAllowed", lambda s: int(np.nansum(s))),
    beaten=("pff_beatenByDefender", lambda s: int(np.nansum(s))),
    asvOnField=("asv_play", "mean"),
).reset_index()

roles = pffj.groupby(["nflId", "pff_role"]).size().unstack(fill_value=0)
rushSnaps = roles.get("Pass Rush", pd.Series(0, index=roles.index))
blockSnaps = roles.get("Pass Block", pd.Series(0, index=roles.index))
covSnaps = roles.get("Coverage", pd.Series(0, index=roles.index))
routeSnaps = roles.get("Pass Route", pd.Series(0, index=roles.index))
passSnaps = roles.get("Pass", pd.Series(0, index=roles.index))

# pasador: completos, intentos, intercepciones, capturas recibidas
qb = pffj[pffj["pff_role"] == "Pass"].merge(
    plays[["gameId", "playId", "passResult", "playResult"]], on=["gameId", "playId"], how="left"
)
qbstat = qb.groupby("nflId").agg(
    attempts=("passResult", "size"),
    completions=("passResult", lambda s: int((s == "C").sum())),
    interceptions=("passResult", lambda s: int((s == "IN").sum())),
    sacksTaken=("passResult", lambda s: int((s == "S").sum())),
    scrambles=("passResult", lambda s: int((s == "R").sum())),
    netYards=("playResult", "sum"),
    passTD=("isTD", "sum"),
).reset_index()

# amonestaciones
fouls = []
for i in (1, 2, 3):
    c = plays[[f"foulNFLId{i}", f"foulName{i}"]].dropna()
    c.columns = ["nflId", "foul"]
    fouls.append(c)
fouls = pd.concat(fouls, ignore_index=True)
fouls["nflId"] = fouls["nflId"].astype("int64")
foul_count = fouls.groupby("nflId").size().rename("penalties")
foul_kinds = {
    int(k): {str(a): int(b) for a, b in v["foul"].value_counts().head(3).items()}
    for k, v in fouls.groupby("nflId")
}

# equipo principal
main_team = pffj.groupby("nflId")["team"].agg(lambda s: s.mode().iloc[0])

pdb = players.set_index("nflId")
players_out = {}
for _, r in pstat.iterrows():
    nid = int(r["nflId"])
    if nid not in pdb.index:
        continue
    p = pdb.loc[nid]
    q = qbstat[qbstat["nflId"] == nid]
    rec = {
        "nflId": nid,
        "name": str(p["displayName"]),
        "position": str(p["officialPosition"]),
        "team": str(main_team.get(nid, "")),
        "jersey": int(jersey.get(nid)) if not pd.isna(jersey.get(nid, np.nan)) else None,
        "heightIn": None if pd.isna(p["heightIn"]) else int(p["heightIn"]),
        "height": str(p["height"]),
        "weight": int(p["weight"]),
        "age": None if pd.isna(p["age"]) else round(float(p["age"]), 1),
        "college": None if pd.isna(p["collegeName"]) else str(p["collegeName"]),
        "plays": int(r["plays"]),
        "rushSnaps": int(rushSnaps.get(nid, 0)),
        "blockSnaps": int(blockSnaps.get(nid, 0)),
        "coverageSnaps": int(covSnaps.get(nid, 0)),
        "routeSnaps": int(routeSnaps.get(nid, 0)),
        "passSnaps": int(passSnaps.get(nid, 0)),
        "pressures": int(r["pressures"]), "hits": int(r["hits"]), "sacks": int(r["sacks"]),
        "pressuresAllowed": int(r["pressAllowed"]), "hitsAllowed": int(r["hitsAllowed"]),
        "sacksAllowed": int(r["sacksAllowed"]), "beaten": int(r["beaten"]),
        "penalties": int(foul_count.get(nid, 0)),
        "penaltyKinds": foul_kinds.get(nid) or {},
        "asvOnField": round(float(r["asvOnField"]), 4),
        "topSpeed": None if nid not in peak.index else round(float(peak.loc[nid, "topSpeed"]), 2),
        "topAccel": None if nid not in peak.index else round(float(peak.loc[nid, "topAccel"]), 2),
    }
    nrush = rec["rushSnaps"]
    nblk = rec["blockSnaps"]
    rec["pressureRate"] = round((rec["pressures"] + rec["hits"] + rec["sacks"]) / nrush, 4) if nrush >= 10 else None
    rec["pressureAllowedRate"] = round(
        (rec["pressuresAllowed"] + rec["hitsAllowed"] + rec["sacksAllowed"]) / nblk, 4
    ) if nblk >= 10 else None
    if len(q):
        qq = q.iloc[0]
        rec.update({
            "attempts": int(qq["attempts"]), "completions": int(qq["completions"]),
            "completionPct": round(float(qq["completions"] / qq["attempts"]), 4) if qq["attempts"] else None,
            "interceptions": int(qq["interceptions"]), "sacksTaken": int(qq["sacksTaken"]),
            "scrambles": int(qq["scrambles"]), "netYards": int(qq["netYards"]),
            "yardsPerAttempt": round(float(qq["netYards"] / qq["attempts"]), 2) if qq["attempts"] else None,
            "passTD": int(qq["passTD"]),
        })
    players_out[str(nid)] = rec

log(f"jugadores con estadisticas: {len(players_out)}")

# ---------------------------------------------------------------- armado por equipo
log("armando acomodos por equipo")
teams = sorted(set(plays["possessionTeam"]) | set(plays["defensiveTeam"]))
teams_out = {}
MIN_N = 12

for t in teams:
    entry = {"team": t, "profiles": {}}
    for side, tab in (("OFF", off_tab), ("DEF", def_tab)):
        sub = tab[(tab["team"] == t) & (tab["n"] >= MIN_N)].sort_values("asv", ascending=False)
        if len(sub) == 0:
            sub = tab[tab["team"] == t].sort_values("asv", ascending=False)
        if len(sub) == 0:
            continue
        best = sub.iloc[0]
        lu = lineup(t, side, best["config"])
        alts = [
            {"config": str(r["config"]), "n": int(r["n"]), "asv": round(float(r["asv"]), 4),
             "successRate": round(float(r["sr"]), 4), "expected": round(float(r["exp"]), 4),
             "leagueAsv": round(float(r["asvL"]), 4) if not pd.isna(r["asvL"]) else None}
            for _, r in sub.head(6).iterrows()
        ]
        entry["profiles"]["ATAQUE" if side == "OFF" else "DEFENSA"] = {
            "side": side,
            "config": str(best["config"]),
            "n": int(best["n"]),
            "asv": round(float(best["asv"]), 4),
            "successRate": round(float(best["sr"]), 4),
            "expected": round(float(best["exp"]), 4),
            "leagueAsv": round(float(best["asvL"]), 4) if not pd.isna(best["asvL"]) else None,
            "lineup": lu,
            "alternatives": alts,
        }
    # perfil general: los 22 de los dos mejores acomodos del equipo
    o = entry["profiles"].get("ATAQUE")
    d = entry["profiles"].get("DEFENSA")
    if o and d:
        entry["profiles"]["GENERAL"] = {
            "side": "BOTH",
            "config": f"{o['config']}  vs  {d['config']}",
            "n": o["n"] + d["n"],
            "asv": round((o["asv"] + d["asv"]) / 2, 4),
            "successRate": round((o["successRate"] + (1 - d["successRate"])) / 2, 4),
            "expected": round((o["expected"] + d["expected"]) / 2, 4),
            "leagueAsv": None,
            "lineup": [dict(x, unit="OFF") for x in o["lineup"]] + [dict(x, unit="DEF") for x in d["lineup"]],
            "alternatives": [],
        }
    # inactivos: jugadores del equipo que no estan en el once elegido
    roster = sorted({int(n) for n in pffj[pffj["team"] == t]["nflId"].unique()})
    for name, prof in entry["profiles"].items():
        on = {x["nflId"] for x in prof["lineup"]}
        prof["inactive"] = [n for n in roster if n not in on and str(n) in players_out]
    teams_out[t] = entry

# ---------------------------------------------------------------- liga / hallazgos
lgoff = off_lg.sort_values("asvL", ascending=False)
lgdef = def_lg.sort_values("asvL", ascending=False)
team_rank_off = off_tab.groupby("team").apply(
    lambda g: np.average(g["asv"], weights=g["n"]), include_groups=False
).sort_values(ascending=False)
team_rank_def = def_tab.groupby("team").apply(
    lambda g: np.average(g["asv"], weights=g["n"]), include_groups=False
).sort_values(ascending=False)

league_out = {
    "metric": {
        "name": "ASV",
        "longName": "Alignment Success Value",
        "definition": "ASV = media(exito observado - exito esperado) por acomodo, contraida hacia cero con k=40 snaps.",
        "successDefinition": "Jugada exitosa: gana >=45% de las yardas necesarias en 1er down, >=60% en 2do, 100% en 3ro/4to, sin intercepcion.",
        "expectation": "Regresion logistica (Newton-IRLS con ridge) sobre 16 rasgos situacionales: down, yardas por ganar, yardas a la zona de anotacion, diferencia de marcador, reloj y sus interacciones.",
        "units": "fraccion de jugada (0.05 = 5 jugadas exitosas extra por cada 100 snaps sobre lo esperado)",
        "shrinkage": "Bayes empirico, k=40",
        "limitations": [
            "Solo jugadas de pase (dropbacks) de las semanas 1 a 8 de la temporada 2021.",
            "El tracking cubre desde el pre-snap hasta ~0.5 s despues del lanzamiento, no la recepcion ni las yardas posteriores.",
            "Las coordenadas del acomodo son promedios en el frame del snap, no una jugada individual.",
            "Las anotaciones se derivan del texto del play-by-play, no de una columna estructurada.",
        ],
    },
    "model": metrics,
    "coefficients": {n: round(float(c), 4) for n, c in zip(["intercept"] + feat_names, w_full)},
    "scope": {
        "games": int(plays["gameId"].nunique()),
        "plays": int(len(plays)),
        "analyzedPlays": int(len(ANALYZABLE)),
        "trackingRows": int(len(perf)),
        "players": len(players_out),
        "teams": len(teams_out),
        "weeks": [int(games["week"].min()), int(games["week"].max())],
        "season": 2021,
    },
    "topOffenseConfigs": [
        {"config": str(r["config"]), "n": int(r["nL"]), "asv": round(float(r["asvL"]), 4)}
        for _, r in lgoff.head(8).iterrows()
    ],
    "topDefenseConfigs": [
        {"config": str(r["config"]), "n": int(r["nL"]), "asv": round(float(r["asvL"]), 4)}
        for _, r in lgdef.head(8).iterrows()
    ],
    "teamRankOffense": [{"team": k, "asv": round(float(v), 4)} for k, v in team_rank_off.items()],
    "teamRankDefense": [{"team": k, "asv": round(float(v), 4)} for k, v in team_rank_def.items()],
}

OUT.joinpath("league.json").write_text(json.dumps(league_out, indent=1), encoding="utf-8")
OUT.joinpath("teams.json").write_text(json.dumps(teams_out, separators=(",", ":")), encoding="utf-8")
OUT.joinpath("players.json").write_text(json.dumps(players_out, separators=(",", ":")), encoding="utf-8")
log("artefactos escritos en backend/artifacts/")
log("LISTO")
