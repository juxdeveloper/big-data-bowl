"""
Exporta la tabla de entrenamiento (nivel jugada) que se entrena en Colab TPU v6e-1.
Salida: ml/asv_train.csv  (8.5k filas, ~60 columnas -> subible a Colab en segundos)
Uso: .venv/bin/python ml/export_dataset.py
"""
import glob
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "ml"
OUT.mkdir(exist_ok=True)

games = pd.read_csv(DATA / "games.csv")
plays = pd.read_csv(DATA / "plays.csv").merge(
    games[["gameId", "week", "homeTeamAbbr", "visitorTeamAbbr"]], on="gameId", how="left"
)
plays = plays[plays["down"] > 0].copy()

home_off = plays["possessionTeam"] == plays["homeTeamAbbr"]
plays["scoreDiff"] = np.where(
    home_off,
    plays["preSnapHomeScore"] - plays["preSnapVisitorScore"],
    plays["preSnapVisitorScore"] - plays["preSnapHomeScore"],
)
plays["yardsToEZ"] = np.where(
    plays["yardlineSide"].isna(), 50,
    np.where(plays["yardlineSide"] == plays["possessionTeam"], 100 - plays["yardlineNumber"], plays["yardlineNumber"]),
)
clk = plays["gameClock"].astype(str).str.split(":", expand=True)
plays["clockSec"] = pd.to_numeric(clk[0], errors="coerce").fillna(0) * 60 + pd.to_numeric(clk[1], errors="coerce").fillna(0)
need = np.select(
    [plays["down"] == 1, plays["down"] == 2],
    [0.45 * plays["yardsToGo"], 0.60 * plays["yardsToGo"]],
    default=plays["yardsToGo"].astype(float),
)
plays["success"] = ((plays["prePenaltyPlayResult"] >= need) & (plays["passResult"] != "IN")).astype(int)

# --- rasgos espaciales del snap: dispersion de la formacion (una pasada por tracking)
TD = {"gameId": "int32", "playId": "int32", "nflId": "float32", "frameId": "int16",
      "team": "category", "playDirection": "category", "x": "float32", "y": "float32",
      "s": "float32", "a": "float32", "event": "category"}
rows = []
for f in sorted(glob.glob(str(DATA / "tracking" / "tracking_*.csv"))):
    df = pd.read_csv(f, usecols=list(TD.keys()), dtype=TD)
    df = df[df["team"] != "football"]
    left = (df["playDirection"] == "left").values
    df["x_std"] = np.where(left, 120.0 - df["x"].values, df["x"].values)
    df["y_std"] = np.where(left, 53.3 - df["y"].values, df["y"].values)
    ev = df["event"].astype(str)
    sn = df[ev.isin(["ball_snap", "autoevent_ballsnap"])]
    sf = sn.groupby(["gameId", "playId"], observed=True)["frameId"].min().rename("sf").reset_index()
    s = df.merge(sf, on=["gameId", "playId"], how="inner")
    s = s[s["frameId"] == s["sf"]]
    g = s.groupby(["gameId", "playId"], observed=True).agg(
        ySpread=("y_std", "std"), yMin=("y_std", "min"), yMax=("y_std", "max"),
        xSpread=("x_std", "std"), snapSpeed=("s", "mean"),
    ).reset_index()
    rows.append(g)
spatial = pd.concat(rows, ignore_index=True)
plays = plays.merge(spatial, on=["gameId", "playId"], how="left")
plays["fieldWidthUsed"] = plays["yMax"] - plays["yMin"]

keep = [
    "gameId", "playId", "week", "possessionTeam", "defensiveTeam", "success",
    "down", "yardsToGo", "yardsToEZ", "scoreDiff", "clockSec", "quarter",
    "offenseFormation", "personnelO", "personnelD", "pff_passCoverage", "pff_passCoverageType",
    "dropBackType", "pff_playAction", "defendersInBox",
    "ySpread", "xSpread", "fieldWidthUsed", "snapSpeed",
]
plays[keep].to_csv(OUT / "asv_train.csv", index=False)
print("filas", len(plays), "->", OUT / "asv_train.csv")
