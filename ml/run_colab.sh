#!/bin/sh
# Orquesta el entrenamiento en Colab TPU v6e-1 de punta a punta.
set -e
cd /home/ubuntu/hack/hackathon-unam
C="/home/ubuntu/.local/bin/colab --auth=adc"

echo "== esperando sesion TPU =="
i=0
while [ $i -lt 60 ]; do
  if $C ls >/dev/null 2>&1; then echo "sesion activa"; break; fi
  i=$((i + 1))
  sleep 10
done

echo "== instalando jax =="
$C install jax jaxlib || echo "jax ya presente o fallo la instalacion"

echo "== subiendo dataset =="
$C upload ml/asv_train.csv asv_train.csv

echo "== entrenando =="
$C run ml/train_colab.py

echo "== descargando pesos =="
$C download asv_model.json backend/artifacts/asv_model.json
echo "== LISTO =="
