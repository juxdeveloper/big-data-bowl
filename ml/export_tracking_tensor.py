"""
Exporta el tracking COMPLETO como tensor de trayectorias, listo para entrenar en Colab A100.
Usa los 8.3 millones de registros: 22 jugadores x 25 frames (2.5 s desde el snap) x 8 canales.

Salida: ml/asv_tensor.npz
  dyn   float16 [N, 22, 25, 8]  x_rel, y_c, s, a, sin(dir), cos(dir), sin(o), cos(o)
  stat  float16 [N, 22, 8]      es_ofensiva + rol PFF (5) + peso y altura normalizados
  mask  uint8   [N, 25]         1 si el frame existe en la jugada
  y     uint8   [N]             jugada exitosa
  keys  int32   [N, 2]          gameId, playId (para alinear con asv_train.csv)

Uso: .venv/bin/python ml/export_tracking_tensor.py
"""
import glob
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "ml"
OUT.mkdir(exist_ok=True)

T = 25          # frames desde el snap (2.5 s a 10 Hz)
NP_ = 22        # jugadores por jugada
CH = 8          # canales dinamicos
SCH = 8         # canales estaticos
T0 = time.time()


def log(m):
    print(f"[{time.time() - T0:7.1f}s] {m}", flush=True)


# ------------------------------------------------------------- etiquetas
plays = pd.read_csv(DATA / "plays.csv")
plays = plays[plays["down"] > 0].copy()
need = np.select(
    [plays["down"] == 1, plays["down"] == 2],
    [0.45 * plays["yardsToGo"], 0.60 * plays["yardsToGo"]],
    default=plays["yardsToGo"].astype(float),
)
plays["success"] = ((plays["prePenaltyPlayResult"] >= need) & (plays["passResult"] != "IN")).astype(int)
labels = plays.set_index(["gameId", "playId"])["success"]

players = pd.read_csv(DATA / "players.csv")
players["heightIn"] = players["height"].str.split("-").apply(
    lambda v: int(v[0]) * 12 + int(v[1]) if isinstance(v, list) and len(v) == 2 else np.nan
)
pmeta = players.set_index("nflId")[["weight", "heightIn"]]

pff = pd.read_csv(DATA / "pffScoutingData.csv", usecols=["gameId", "playId", "nflId", "pff_role"])
ROLES = ["Pass", "Pass Block", "Pass Route", "Pass Rush", "Coverage"]
OFF = {"Pass", "Pass Block", "Pass Route"}
pff["roleCode"] = pff["pff_role"].map({r: i for i, r in enumerate(ROLES)}).fillna(4).astype("int8")
pff["isOff"] = pff["pff_role"].isin(OFF).astype("int8")

TD = {
    "gameId": "int32", "playId": "int32", "nflId": "float32", "frameId": "int16",
    "team": "category", "playDirection": "category", "x": "float32", "y": "float32",
    "s": "float32", "a": "float32", "o": "float32", "dir": "float32", "event": "category",
}

dyn_parts, stat_parts, mask_parts, key_parts = [], [], [], []
files = sorted(glob.glob(str(DATA / "tracking" / "tracking_*.csv")))
log(f"procesando {len(files)} archivos de tracking")

for fi, f in enumerate(files):
    df = pd.read_csv(f, usecols=list(TD.keys()), dtype=TD)
    df = df[df["team"] != "football"].copy()
    df["nflId"] = df["nflId"].astype("int64")

    left = (df["playDirection"] == "left").values
    df["x_std"] = np.where(left, 120.0 - df["x"].values, df["x"].values).astype("float32")
    df["y_std"] = np.where(left, 53.3 - df["y"].values, df["y"].values).astype("float32")
    df["o_std"] = np.where(left, (df["o"].values + 180.0) % 360.0, df["o"].values).astype("float32")
    df["dir_std"] = np.where(left, (df["dir"].values + 180.0) % 360.0, df["dir"].values).astype("float32")

    # frame del snap (con respaldo cuando falta el evento)
    ev = df["event"].astype(str)
    sn = df[ev.isin(["ball_snap", "autoevent_ballsnap"])]
    sf = sn.groupby(["gameId", "playId"], observed=True)["frameId"].min().rename("sf").reset_index()
    allp = df[["gameId", "playId"]].drop_duplicates()
    sf = allp.merge(sf, on=["gameId", "playId"], how="left")
    sf["sf"] = sf["sf"].fillna(6).astype("int16")
    df = df.merge(sf, on=["gameId", "playId"], how="left")
    df["rel"] = (df["frameId"] - df["sf"]).astype("int16")
    df = df[(df["rel"] >= 0) & (df["rel"] < T)]

    # linea de golpeo: mediana de x_std de los 22 en el snap
    s0 = df[df["rel"] == 0]
    los = s0.groupby(["gameId", "playId"], observed=True)["x_std"].median().rename("los").reset_index()
    df = df.merge(los, on=["gameId", "playId"], how="left")
    df["x_rel"] = (df["x_std"] - df["los"]).astype("float32")

    # orden canonico de jugadores: ofensiva primero, por rol, luego por posicion lateral
    df = df.merge(pff, on=["gameId", "playId", "nflId"], how="left")
    df["roleCode"] = df["roleCode"].fillna(4).astype("int8")
    df["isOff"] = df["isOff"].fillna(0).astype("int8")
    order = df[df["rel"] == 0][["gameId", "playId", "nflId", "isOff", "roleCode", "y_std"]].copy()
    order = order.sort_values(["gameId", "playId", "isOff", "roleCode", "y_std"], ascending=[True, True, False, True, True])
    order["slot"] = order.groupby(["gameId", "playId"]).cumcount().astype("int8")
    order = order[order["slot"] < NP_]
    df = df.merge(order[["gameId", "playId", "nflId", "slot"]], on=["gameId", "playId", "nflId"], how="inner")

    # indice global de jugada dentro de este archivo
    keys = order[["gameId", "playId"]].drop_duplicates().reset_index(drop=True)
    keys["pi"] = np.arange(len(keys), dtype="int32")
    df = df.merge(keys, on=["gameId", "playId"], how="inner")

    n = len(keys)
    dyn = np.zeros((n, NP_, T, CH), dtype="float16")
    mask = np.zeros((n, T), dtype="uint8")

    rad = np.pi / 180.0
    feats = np.stack([
        df["x_rel"].values,
        df["y_std"].values - 26.65,
        df["s"].values,
        df["a"].values,
        np.sin(df["dir_std"].values * rad),
        np.cos(df["dir_std"].values * rad),
        np.sin(df["o_std"].values * rad),
        np.cos(df["o_std"].values * rad),
    ], axis=1).astype("float16")
    feats = np.nan_to_num(feats)
    dyn[df["pi"].values, df["slot"].values, df["rel"].values] = feats
    mask[df["pi"].values, df["rel"].values] = 1

    # estaticos por jugador
    st = order[order["slot"] < NP_].merge(
        pmeta, left_on="nflId", right_index=True, how="left"
    ).merge(keys, on=["gameId", "playId"], how="inner")
    stat = np.zeros((n, NP_, SCH), dtype="float16")
    roleoh = np.zeros((len(st), 5), dtype="float16")
    roleoh[np.arange(len(st)), st["roleCode"].values] = 1
    stat[st["pi"].values, st["slot"].values] = np.concatenate([
        st["isOff"].values.reshape(-1, 1).astype("float16"),
        roleoh,
        ((st["weight"].values - 250.0) / 50.0).reshape(-1, 1).astype("float16"),
        ((np.nan_to_num(st["heightIn"].values, nan=74.0) - 74.0) / 3.0).reshape(-1, 1).astype("float16"),
    ], axis=1)

    kk = keys[["gameId", "playId"]].values.astype("int32")
    yy = np.array([labels.get((int(g), int(p)), 255) for g, p in kk], dtype="uint8")
    ok = yy != 255
    dyn_parts.append(dyn[ok]); stat_parts.append(stat[ok])
    mask_parts.append(mask[ok]); key_parts.append(kk[ok])
    if fi == 0:
        log(f"  primer archivo: {ok.sum()} jugadas, tensor {dyn[ok].shape}")
    if (fi + 1) % 20 == 0:
        log(f"  {fi + 1}/{len(files)}")

dyn = np.concatenate(dyn_parts); stat = np.concatenate(stat_parts)
mask = np.concatenate(mask_parts); keys = np.concatenate(key_parts)
y = np.array([labels[(int(g), int(p))] for g, p in keys], dtype="uint8")
log(f"tensor final dyn={dyn.shape} ({dyn.nbytes / 1e6:.0f} MB en RAM) y={y.mean():.4f}")

np.savez_compressed(OUT / "asv_tensor.npz", dyn=dyn, stat=stat, mask=mask, y=y, keys=keys)
log(f"escrito {OUT / 'asv_tensor.npz'} ({(OUT / 'asv_tensor.npz').stat().st_size / 1e6:.1f} MB)")
