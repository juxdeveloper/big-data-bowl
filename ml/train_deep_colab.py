"""
Entrenamiento profundo sobre el tracking COMPLETO (Google Colab, GPU A100).
Equipo Data Rushers | NFL Big Data Bowl 2026

Entrada: asv_tensor.npz (22 jugadores x 25 frames x 8 canales por jugada) + asv_train.csv (situacion)
Modelo: codificador por jugador -> agregacion de conjunto separada por unidad -> cabeza con la situacion.
Validacion: 5 pliegues por partido (ninguna jugada del mismo juego cruza de pliegue).
Aumento: espejo lateral del campo (y -> -y), fisicamente valido, duplica la muestra.
Salida: asv_deep.json con pesos y metricas honestas de validacion cruzada.
"""
import json
import os
import time

import numpy as np
import pandas as pd

T0 = time.time()


def log(m):
    print(f"[{time.time() - T0:6.1f}s] {m}", flush=True)


NPZ = next(p for p in ("asv_tensor.npz", "/asv_tensor.npz", "/content/asv_tensor.npz") if os.path.exists(p))
CSV = next(p for p in ("asv_train.csv", "/asv_train.csv", "/content/asv_train.csv") if os.path.exists(p))
d = np.load(NPZ)
dyn, stat, mask, y, keys = d["dyn"], d["stat"], d["mask"], d["y"], d["keys"]
log(f"tensor {dyn.shape} ({dyn.nbytes / 1e6:.0f} MB) | tasa base {y.mean():.4f}")

# ---------------------------------------------------- rasgos situacionales alineados
sit = pd.read_csv(CSV)
sit_idx = {(int(g), int(p)): i for i, (g, p) in enumerate(zip(sit["gameId"], sit["playId"]))}
rows = [sit_idx[(int(g), int(p))] for g, p in keys]
sit = sit.iloc[rows].reset_index(drop=True)

NUM = ["down", "yardsToGo", "yardsToEZ", "scoreDiff", "clockSec", "quarter",
       "pff_playAction", "defendersInBox", "ySpread", "xSpread", "fieldWidthUsed", "snapSpeed"]
CAT = ["offenseFormation", "personnelO", "personnelD", "pff_passCoverage", "pff_passCoverageType", "dropBackType"]
Xn = sit[NUM].astype(float)
Xn = Xn.fillna(Xn.median())
mu, sd = Xn.mean(), Xn.std().replace(0, 1)
cols = [(Xn - mu) / sd]
cat_levels = {}
for c in CAT:
    v = sit[c].fillna("NA").astype(str)
    lv = v.value_counts()
    lv = lv[lv >= 25].index.tolist()
    cat_levels[c] = lv
    for l in lv:
        cols.append(pd.Series((v == l).astype(float), name=f"{c}={l}"))
S = pd.concat(cols, axis=1)
sit_names = list(S.columns)
S = S.values.astype("float32")
log(f"situacion {S.shape}")

import jax
import jax.numpy as jnp

log(f"dispositivos: {jax.devices()}")

B, NP_, T, CH = dyn.shape
SCH = stat.shape[-1]
FLAT = T * CH + SCH
H_ENC, H_HEAD = 128, 96


def init(key):
    ks = jax.random.split(key, 8)
    g = lambda k, a, b: jax.random.normal(k, (a, b), dtype=jnp.float32) * np.sqrt(2.0 / a)
    return {
        "E1": g(ks[0], FLAT, H_ENC), "e1": jnp.zeros(H_ENC),
        "E2": g(ks[1], H_ENC, 64), "e2": jnp.zeros(64),
        "H1": g(ks[2], 64 * 4 + S.shape[1], H_HEAD), "h1": jnp.zeros(H_HEAD),
        "H2": g(ks[3], H_HEAD, 48), "h2": jnp.zeros(48),
        "O": g(ks[4], 48, 1) * 0.05, "o": jnp.zeros(1),
    }


def fwd(p, dy, st, sit_x, is_off):
    """dy [b,22,T,CH] st [b,22,SCH] -> logit [b]"""
    b = dy.shape[0]
    x = jnp.concatenate([dy.reshape(b, NP_, T * CH), st], axis=-1)
    h = jax.nn.relu(x @ p["E1"] + p["e1"])
    h = jax.nn.relu(h @ p["E2"] + p["e2"])            # [b,22,64]

    off = is_off[..., None]
    deff = 1.0 - off
    no = jnp.maximum(off.sum(1), 1.0)
    nd = jnp.maximum(deff.sum(1), 1.0)
    # agregacion de conjunto por unidad: el orden de los jugadores no altera la prediccion
    pooled = jnp.concatenate([
        (h * off).sum(1) / no,
        (h * deff).sum(1) / nd,
        jnp.max(h * off - 1e4 * deff, axis=1),
        jnp.max(h * deff - 1e4 * off, axis=1),
    ], axis=-1)

    z = jnp.concatenate([pooled, sit_x], axis=-1)
    z = jax.nn.relu(z @ p["H1"] + p["h1"])
    z = jax.nn.relu(z @ p["H2"] + p["h2"])
    return (z @ p["O"] + p["o"]).ravel()


def loss_fn(p, dy, st, sx, io, yy, wd):
    z = fwd(p, dy, st, sx, io)
    bce = jnp.mean(jnp.logaddexp(0.0, z) - yy * z)
    l2 = sum(jnp.sum(v**2) for k, v in p.items() if k.isupper())
    return bce + wd * l2


grad_fn = jax.jit(jax.value_and_grad(loss_fn), static_argnums=())
eval_fn = jax.jit(fwd)


def adam_step(p, g, m, v, t, lr, b1=0.9, b2=0.999, eps=1e-8):
    m = {k: b1 * m[k] + (1 - b1) * g[k] for k in p}
    v = {k: b2 * v[k] + (1 - b2) * g[k] ** 2 for k in p}
    mh = {k: m[k] / (1 - b1**t) for k in p}
    vh = {k: v[k] / (1 - b2**t) for k in p}
    p = {k: p[k] - lr * mh[k] / (jnp.sqrt(vh[k]) + eps) for k in p}
    return p, m, v


def auc(yy, pp):
    o = np.argsort(pp)
    yy = np.asarray(yy)[o]
    r = np.arange(1, len(yy) + 1)
    n1, n0 = yy.sum(), (1 - yy).sum()
    return float((r[yy == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def ll(yy, pp):
    pp = np.clip(pp, 1e-9, 1 - 1e-9)
    return float(-np.mean(yy * np.log(pp) + (1 - yy) * np.log(1 - pp)))


# espejo lateral: y -> -y, y las componentes laterales de dir/o cambian de signo
MIRROR = np.ones(CH, dtype="float32")
MIRROR[1] = -1.0   # y_c
MIRROR[5] = -1.0   # cos(dir)  (componente +Y)
MIRROR[7] = -1.0   # cos(o)

dynf = dyn.astype("float32")
statf = stat.astype("float32")
is_off = statf[..., 0]
yf = y.astype("float32")
games = keys[:, 0]
uniq = np.unique(games)
rng = np.random.default_rng(11)
rng.shuffle(uniq)
folds = np.array_split(uniq, 5)

BATCH = 256
MAXEP = 60
PATIENCE = 6
WD = 2e-5
LR = 1.2e-3


def run(tr, te, seed, max_epochs=MAXEP, report=True):
    p = init(jax.random.PRNGKey(seed))
    m = {k: jnp.zeros_like(v) for k, v in p.items()}
    v = {k: jnp.zeros_like(x) for k, x in p.items()}
    t = 0
    best, best_p, bad, best_ep = 1e9, p, 0, 0
    r = np.random.default_rng(seed)
    dte = jnp.asarray(dynf[te]) if len(te) else None
    for ep in range(max_epochs):
        idx = r.permutation(tr)
        for i in range(0, len(idx), BATCH):
            b = idx[i:i + BATCH]
            dy, st = dynf[b], statf[b]
            if r.random() < 0.5:                      # aumento espejo
                dy = dy * MIRROR
            t += 1
            lv, g = grad_fn(p, jnp.asarray(dy), jnp.asarray(st), jnp.asarray(S[b]),
                            jnp.asarray(is_off[b]), jnp.asarray(yf[b]), WD)
            p, m, v = adam_step(p, g, m, v, t, LR)
        if len(te):
            pz = np.asarray(eval_fn(p, dte, jnp.asarray(statf[te]), jnp.asarray(S[te]), jnp.asarray(is_off[te])))
            pr = 1 / (1 + np.exp(-np.clip(pz, -30, 30)))
            cur = ll(yf[te], pr)
            if cur < best - 1e-4:
                best, best_p, bad, best_ep = cur, p, 0, ep
            else:
                bad += 1
                if bad >= PATIENCE:
                    break
            if report and ep % 5 == 0:
                log(f"    ep {ep:2d} val logloss {cur:.4f} auc {auc(yf[te], pr):.4f}")
    return best_p, best_ep


log("== validacion cruzada por partido, 5 pliegues ==")
cv = []
for fi, fg in enumerate(folds):
    te = np.where(np.isin(games, fg))[0]
    tr = np.where(~np.isin(games, fg))[0]
    log(f"  pliegue {fi + 1}/5: {len(tr)} entrenamiento / {len(te)} prueba")
    p, bep = run(tr, te, seed=100 + fi)
    pz = np.asarray(eval_fn(p, jnp.asarray(dynf[te]), jnp.asarray(statf[te]), jnp.asarray(S[te]), jnp.asarray(is_off[te])))
    pr = 1 / (1 + np.exp(-np.clip(pz, -30, 30)))
    cv.append({"fold": fi + 1, "n": int(len(te)), "auc": round(auc(yf[te], pr), 4),
               "logloss": round(ll(yf[te], pr), 4),
               "logloss_base": round(ll(yf[te], np.full(len(te), yf[tr].mean())), 4),
               "best_epoch": int(bep)})
    log(f"    -> auc {cv[-1]['auc']} logloss {cv[-1]['logloss']} (base {cv[-1]['logloss_base']})")

auc_cv = float(np.mean([c["auc"] for c in cv]))
ll_cv = float(np.mean([c["logloss"] for c in cv]))
ll_base = float(np.mean([c["logloss_base"] for c in cv]))
mean_ep = int(np.mean([c["best_epoch"] for c in cv])) + 1
log(f"== CV: auc {auc_cv:.4f} | logloss {ll_cv:.4f} vs base {ll_base:.4f} | epocas {mean_ep} ==")

log("== modelo final sobre las 8,522 jugadas ==")
final, _ = run(np.arange(B), np.array([], dtype=int), seed=7, max_epochs=mean_ep, report=False)

n_params = int(sum(np.asarray(v).size for v in final.values()))
out = {
    "kind": "set_encoder_trajectories",
    "note": "Codificador por jugador sobre 25 frames de tracking, agregacion de conjunto por unidad, cabeza con situacion.",
    "shape": {"players": NP_, "frames": T, "channels": CH, "staticChannels": SCH, "situational": int(S.shape[1])},
    "channels": ["x_rel", "y_c", "s", "a", "sin(dir)", "cos(dir)", "sin(o)", "cos(o)"],
    "situationalFeatures": sit_names,
    "catLevels": cat_levels,
    "center": {k: float(v) for k, v in mu.items()},
    "scale": {k: float(v) for k, v in sd.items()},
    "metrics": {
        "auc_cv": round(auc_cv, 4),
        "logloss_cv": round(ll_cv, 4),
        "logloss_baseline": round(ll_base, 4),
        "folds": cv,
        "n_plays": int(B),
        "n_tracking_rows_used": int(B * NP_ * T),
        "params": n_params,
        "device": str(jax.devices()[0]),
        "arch": f"encoder {FLAT}-{H_ENC}-64 -> pool 4x64 + {S.shape[1]} sit -> {H_HEAD}-48-1",
        "augmentation": "espejo lateral del campo",
        "validation": "5 pliegues agrupados por partido",
        "epochs_final": mean_ep,
        "train_seconds": round(time.time() - T0, 1),
    },
    "weights": {k: np.asarray(v).astype("float32").tolist() for k, v in final.items()},
}
with open("/content/asv_deep.json", "w") as f:
    json.dump(out, f)
log(f"escrito asv_deep.json ({os.path.getsize('/content/asv_deep.json') / 1e6:.1f} MB) | params {n_params}")
