# Entrega preliminar — Equipo Data Rushers

**Proyecto:** ASV (Alignment Success Value) · NFL Big Data Bowl 2026 (UNAM · AWS · NFL) · Perfil **Entrenador**

## 1. Repositorio

https://github.com/juxdeveloper/big-data-bowl

Rama `main`. No contiene credenciales: `.env` está en `.gitignore` y el chequeo de entrega confirma "Sin credenciales a la vista".

## 2. Demo

La aplicación está **corriendo ahora mismo** en el servidor, servida por Uvicorn en `127.0.0.1:8000` (API y tablero en la misma URL y puerto).

No hay URL pública porque el despliegue en AWS lo hace el organizador bajo la subruta `/evento/equipo/`. Para verla desde tu máquina, abre un túnel SSH:

```bash
ssh -i RUTA_A_TU_LLAVE -N -L 8000:127.0.0.1:8000 ubuntu@159.54.129.29
# luego abre http://localhost:8000
```

El prompt completo para que un agente local abra el túnel y revise la página está en `PROMPT-AGENTE-LOCAL.md`, en esta misma carpeta.

El servicio queda expuesto solo a `127.0.0.1`, nunca a internet: el túnel SSH es el único acceso.

Para levantarla desde cero:

```bash
cd ~/hack/hackathon-unam
.venv/bin/python backend/precompute.py                        # artefactos, ~20 s
(cd dashboard && ../.hackathon/.tools/node/bin/npm run build) # build del tablero
.venv/bin/uvicorn backend.main:app --port 8000                # sirve API + tablero
```

La URL pública **la asigna AWS al desplegar** bajo la subruta `/evento/equipo/`; no existe todavía porque el despliegue lo hace el organizador a partir del repositorio o del `.zip`. Todas las rutas del frontend son relativas sin diagonal inicial, así que la app funciona en cualquier subruta.

## 3. Archivo de entrega

`entrega-hackathon-unam-20261120-1826.zip` (en esta misma carpeta, 233.2 MB, 176 archivos)

Generado con `sh .hackathon/setup.sh --entregar`. El `.env` con las llaves del workshop queda fuera del `.zip` por diseño del empaquetador.

## 4. Estado verificado

| Comprobación | Resultado |
|---|---|
| `sh .hackathon/setup.sh --check` | `RESULTADO: TODO OK, puedes entregar.` |
| `npm run build` (tsc + vite) | exit 0 |
| `pytest tests/` | 17 pruebas pasan |
| Rutas relativas sin `/api`, sin `localhost` | OK (probado también en pytest) |
| Rusher sobre Amazon Bedrock (Nova Pro) | responde con herramientas reales sobre métricas calculadas |
| Entrenamiento en acelerador | NVIDIA A100 en Google Colab, 4,687,100 observaciones de tracking |

## 5. Qué mide ASV

Cuántas jugadas exitosas por cada 100 snaps gana un acomodo (formación + personal) **por encima de lo que el modelo situacional esperaba**. Así ningún equipo sube por haber enfrentado situaciones fáciles.

- Modelo de expectativa: regresión logística Newton-IRLS con ridge, 16 rasgos situacionales, validación por partido. AUC 0.631, log-loss 0.661 contra 0.691 de la tasa base.
- Contrastes entrenados en NVIDIA A100 (Google Colab):
  - MLP 61-96-32-1 sobre rasgos situacionales: AUC 0.6305.
  - **Modelo de trayectorias sobre el tracking completo**: cada jugada entra como tensor de 22 jugadores × 25 frames × 8 canales (4,687,100 observaciones), con codificador por jugador, agregación de conjunto por unidad, espejo lateral del campo como aumento y validación cruzada en 5 pliegues agrupados por partido. 70,241 parámetros, AUC 0.6366.
- Producción se queda con la logística: el modelo profundo gana 5.8 milésimas de AUC con 4,000 veces más parámetros. Eso confirma la tesis de ASV, que el acomodo pre-snap ya contiene casi toda la señal. La comparación de los tres modelos se muestra en el propio tablero en vez de esconderla.
- Contracción de Bayes empírico (k=40 snaps) para no premiar muestras chicas.

Tres perfiles por equipo: General (22 titulares), Ofensivo y Defensivo, cada uno con mapa del campo, alineación, rotación y perfil individual de jugador.
