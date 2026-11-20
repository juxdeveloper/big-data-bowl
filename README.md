# ASV — Alignment Success Value

**Equipo: Data Rushers** · NFL Big Data Bowl 2026 (UNAM · AWS · NFL) · Perfil **Entrenador**

Construimos un tablero para entrenadores que responde una sola pregunta: cuál es el mejor acomodo posible de cada equipo de la NFL, en perfil general, ofensivo y defensivo, a partir de 8,522 jugadas de pase y 8.3 millones de registros de tracking de las semanas 1–8 de 2021. La métrica ASV mide cuántas jugadas exitosas por cada 100 snaps gana un acomodo por encima de lo que un modelo situacional esperaba, de modo que ningún equipo sube de ranking solo por haber enfrentado situaciones fáciles. El hallazgo es que el acomodo óptimo casi nunca es el más usado: en varios equipos, formaciones con menos de 40 snaps superan por más de 5 jugadas por 100 a su formación base, y el mapa del campo muestra exactamente qué once jugadores y en qué coordenadas pre-snap producen esa ventaja. Lo usaría un coordinador ofensivo o defensivo preparando un plan de juego, y un entrenador en jefe decidiendo rotaciones, con el asistente Rusher (Amazon Nova vía Bedrock) consultando las métricas reales en vez de improvisar cifras.

## Cómo correrlo

```bash
.venv/bin/python backend/precompute.py                 # genera backend/artifacts/*.json (~20 s)
.venv/bin/uvicorn backend.main:app --port 8000         # API
(cd dashboard && ../.hackathon/.tools/node/bin/npm run build)   # build del tablero
```

## Metodología

- **Éxito de jugada**: gana ≥45% de las yardas necesarias en 1er down, ≥60% en 2do, 100% en 3ro/4to, sin intercepción.
- **Expectativa**: regresión logística (Newton-IRLS con ridge) sobre 16 rasgos situacionales, validada por partido (AUC 0.631, log-loss 0.661 contra 0.691 de la base).
- **ASV**: media de (éxito observado − esperado) por acomodo, contraída hacia cero con Bayes empírico (k=40 snaps).
- **Acomodo**: `offenseFormation + personnelO` en ataque, `personnelD + pff_passCoverage` en defensa. Las coordenadas del mapa son la posición media de cada jugador en el frame del snap, normalizada a atacar hacia +X.
- **Modelo en acelerador**: probamos los aceleradores de Colab en orden de cómputo pico. G4 y H100 no tienen entitlement en la cuenta y la TPU v6e-1 no se aprovisionó, así que el entrenamiento corrió en **NVIDIA A100** (312 TFLOPS BF16). Entrenamos dos contrincantes:
  - `ml/train_colab.py`: MLP 61-96-32-1 sobre rasgos situacionales. AUC 0.6305.
  - `ml/train_deep_colab.py`: **modelo de trayectorias sobre el tracking completo**. Cada jugada entra como un tensor de 22 jugadores × 25 frames × 8 canales (posición relativa a la línea de golpeo, velocidad, aceleración, orientación y dirección de movimiento), 4,687,100 observaciones de tracking en total. Codificador por jugador, agregación de conjunto separada por unidad (así el orden de los jugadores no altera la predicción), espejo lateral del campo como aumento y validación cruzada en 5 pliegues agrupados por partido. 70,241 parámetros, AUC 0.6366.
- **Por qué producción usa la logística**: el modelo de trayectorias gana 5.8 milésimas de AUC con 4,000 veces más parámetros. Medir el trayecto completo confirma que el acomodo pre-snap ya contiene casi toda la señal, que es precisamente la tesis de ASV. El tablero muestra la comparación de los tres modelos en vez de esconderla.

## Equipo

Data Rushers.

## Límites declarados

Solo jugadas de pase de 2021 semanas 1–8. El tracking termina ~0.5 s después del lanzamiento, así que no cubre la recepción ni las yardas posteriores. Las anotaciones se derivan del texto del play-by-play, no de una columna estructurada. El dataset no contiene lesiones ni listas de inactivos: "fuera del acomodo" significa que el jugador tuvo snaps de pase con el equipo pero no entra en el once óptimo.
