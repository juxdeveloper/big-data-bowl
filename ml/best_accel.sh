#!/bin/sh
# Prueba los aceleradores de Colab en orden de computo pico (BF16/FP16 TFLOPS)
# y entrena en el primero que se aprovisione.
cd /home/ubuntu/hack/hackathon-unam
C="/home/ubuntu/.local/bin/colab --auth=adc"

try() { # $1 = flag, $2 = variante, $3 = etiqueta
  echo "== probando $3 =="
  out=$(timeout 150 $C new "$1" "$2" 2>&1)
  echo "$out"
  name=$(echo "$out" | sed -n "s/.*Creating session '\([^']*\)'.*/\1/p" | head -1)
  if echo "$out" | grep -q "Session READY"; then
    echo "DISPONIBLE: $3 (sesion $name)"
    echo "$name" > ml/.session
    echo "$3" > ml/.accel
    return 0
  fi
  [ -n "$name" ] && timeout 40 $C stop -s "$name" >/dev/null 2>&1
  return 1
}

try --gpu G4 "G4 (1000 TFLOPS)" ||
  try --gpu H100 "H100 (989 TFLOPS)" ||
  try --tpu V6E1 "TPU v6e-1 (918 TFLOPS)" ||
  try --gpu A100 "A100 (312 TFLOPS)" ||
  try --tpu V5E1 "TPU v5e-1 (197 TFLOPS)" ||
  try --gpu L4 "L4 (121 TFLOPS)" ||
  try --gpu T4 "T4 (65 TFLOPS)" || { echo "NINGUN ACELERADOR DISPONIBLE"; exit 1; }

S=$(cat ml/.session)
A=$(cat ml/.accel)
echo "== entrenando en $A (sesion $S) =="
$C upload -s "$S" ml/asv_train.csv asv_train.csv
$C exec -s "$S" --timeout 420 -f ml/train_colab.py
$C download -s "$S" /content/asv_model.json backend/artifacts/asv_model.json
echo "== LISTO en $A =="
