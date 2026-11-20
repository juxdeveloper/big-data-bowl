"""
Entrenamiento en Colab TPU v6e-1 (JAX).
Modelo: MLP sobre rasgos situacionales + acomodo (formacion, personal, cobertura, dispersion pre-snap).
Objetivo: P(jugada exitosa). Salida: asv_model.json con pesos para inferencia en numpy puro
dentro del stack permitido del hackaton (sin JAX ni sklearn en el backend).

Se ejecuta con el CLI de Colab:
  colab --auth=adc new --tpu V6E1
  colab --auth=adc upload ml/asv_train.csv
  colab --auth=adc run ml/train_colab.py
  colab --auth=adc download asv_model.json
"""
import json

import numpy as np
import pandas as pd

import os

CSV = next(p for p in ("asv_train.csv", "/asv_train.csv", "/content/asv_train.csv") if os.path.exists(p))
df = pd.read_csv(CSV)
print("filas", len(df), "desde", CSV)

NUM = ["down", "yardsToGo", "yardsToEZ", "scoreDiff", "clockSec", "quarter",
       "pff_playAction", "defendersInBox", "ySpread", "xSpread", "fieldWidthUsed", "snapSpeed"]
CAT = ["offenseFormation", "personnelO", "personnelD", "pff_passCoverage", "pff_passCoverageType", "dropBackType"]

X_num = df[NUM].astype(float)
X_num = X_num.fillna(X_num.median())
mu, sd = X_num.mean(), X_num.std().replace(0, 1)
X_num_z = (X_num - mu) / sd

dummies = []
cat_levels = {}
for c in CAT:
    v = df[c].fillna("NA").astype(str)
    keep = v.value_counts()
    keep = keep[keep >= 25].index.tolist()
    cat_levels[c] = keep
    for lv in keep:
        dummies.append(pd.Series((v == lv).astype(float), name=f"{c}={lv}"))

X = pd.concat([X_num_z] + dummies, axis=1)
feat_names = list(X.columns)
Xv = X.values.astype("float32")
yv = df["success"].values.astype("float32")
print("rasgos", Xv.shape)

# split por partido: ninguna jugada del mismo juego cruza entre train y test
gids = df["gameId"].unique()
rng = np.random.default_rng(7)
rng.shuffle(gids)
test = set(gids[: int(len(gids) * 0.2)])
m = df["gameId"].isin(test).values
Xtr, ytr, Xte, yte = Xv[~m], yv[~m], Xv[m], yv[m]

import jax
import jax.numpy as jnp

print("dispositivos JAX:", jax.devices())

H1, H2 = 96, 32
key = jax.random.PRNGKey(0)
k1, k2, k3 = jax.random.split(key, 3)
params = {
    "W1": jax.random.normal(k1, (Xtr.shape[1], H1)) * (1.0 / np.sqrt(Xtr.shape[1])),
    "b1": jnp.zeros(H1),
    "W2": jax.random.normal(k2, (H1, H2)) * (1.0 / np.sqrt(H1)),
    "b2": jnp.zeros(H2),
    "W3": jax.random.normal(k3, (H2, 1)) * 0.01,
    "b3": jnp.zeros(1),
}


def fwd(p, x):
    h = jnp.tanh(x @ p["W1"] + p["b1"])
    h = jnp.tanh(h @ p["W2"] + p["b2"])
    return (h @ p["W3"] + p["b3"]).ravel()


def loss(p, x, y, wd=3e-4):
    z = fwd(p, x)
    bce = jnp.mean(jnp.logaddexp(0.0, z) - y * z)
    l2 = sum(jnp.sum(v**2) for k, v in p.items() if k.startswith("W"))
    return bce + wd * l2


grad = jax.jit(jax.grad(loss))
lossj = jax.jit(loss)

Xtr_j, ytr_j, Xte_j, yte_j = map(jnp.asarray, (Xtr, ytr, Xte, yte))
lr = 0.02
mom = {k: jnp.zeros_like(v) for k, v in params.items()}
best, best_params, patience = 1e9, params, 0
for it in range(4000):
    g = grad(params, Xtr_j, ytr_j)
    mom = {k: 0.9 * mom[k] + g[k] for k in params}
    params = {k: params[k] - lr * mom[k] for k in params}
    if it % 100 == 0:
        te = float(lossj(params, Xte_j, yte_j))
        if te < best - 1e-5:
            best, best_params, patience = te, params, 0
        else:
            patience += 1
            if patience >= 6:
                print(f"paro temprano en it={it}")
                break
        print(f"it {it:4d} train {float(lossj(params, Xtr_j, ytr_j)):.4f} test {te:.4f}")

params = best_params


def auc(y, p):
    o = np.argsort(p)
    y = np.asarray(y)[o]
    r = np.arange(1, len(y) + 1)
    n1, n0 = y.sum(), (1 - y).sum()
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


sig = lambda z: 1 / (1 + np.exp(-np.clip(z, -30, 30)))
pte = sig(np.asarray(fwd(params, Xte_j)))
ptr = sig(np.asarray(fwd(params, Xtr_j)))
base = float(ytr.mean())
ll = lambda y, p: float(-np.mean(y * np.log(np.clip(p, 1e-9, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-9, 1))))
metrics = {
    "auc_test": round(auc(yte, pte), 4),
    "auc_train": round(auc(ytr, ptr), 4),
    "logloss_test": round(ll(yte, pte), 4),
    "logloss_baseline": round(ll(yte, np.full(len(yte), base)), 4),
    "n_train": int(len(ytr)),
    "n_test": int(len(yte)),
    "base_success_rate": round(base, 4),
    "device": str(jax.devices()[0]),
    "arch": f"MLP {Xtr.shape[1]}-{H1}-{H2}-1 tanh",
}
print(metrics)

out = {
    "kind": "mlp_tanh",
    "features": feat_names,
    "numeric": NUM,
    "catLevels": cat_levels,
    "center": {k: float(v) for k, v in mu.items()},
    "scale": {k: float(v) for k, v in sd.items()},
    "weights": {k: np.asarray(v).tolist() for k, v in params.items()},
    "metrics": metrics,
}
with open("/content/asv_model.json", "w") as f:
    json.dump(out, f)
print("escrito asv_model.json")
