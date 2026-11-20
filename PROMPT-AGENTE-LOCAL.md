# Prompt para el agente en tu máquina local

Copia y pega todo lo que está dentro del bloque. Reemplaza `RUTA_A_TU_LLAVE` por la ruta de tu llave privada (por ejemplo `~/.ssh/id_rsa` o la `.pem` que te dio Oracle).

---

```
Necesito que revises una aplicación web que corre en un servidor remoto al que llegas por SSH. No está publicada en internet: se accede por un túnel SSH que tú vas a abrir.

DATOS DE CONEXIÓN
- Host: 159.54.129.29
- Puerto SSH: 22
- Usuario: ubuntu
- Llave privada: RUTA_A_TU_LLAVE
- La app escucha en el servidor en 127.0.0.1:8000 (solo accesible desde dentro del servidor)

PASO 1 — Abre el túnel SSH en segundo plano y déjalo vivo:

  ssh -i RUTA_A_TU_LLAVE -N -L 8000:127.0.0.1:8000 ubuntu@159.54.129.29

Si el puerto 8000 local ya está ocupado, usa 8080 en el lado local:

  ssh -i RUTA_A_TU_LLAVE -N -L 8080:127.0.0.1:8000 ubuntu@159.54.129.29

PASO 2 — Comprueba que el túnel funciona:

  curl -s http://localhost:8000/health

Debe responder exactamente {"status":"ok"}. Si no responde, revisa que el túnel siga corriendo antes de seguir.

PASO 3 — Abre http://localhost:8000 en un navegador real (usa automatización de navegador, no solo curl) y revisa la aplicación. Se llama ASV (Alignment Success Value), es un tablero de análisis de la NFL del equipo Data Rushers. Toma capturas de pantalla de cada punto.

QUÉ REVISAR, en este orden:

1. Portada: debe cargar un titular que dice cuántas jugadas exitosas por 100 snaps gana un equipo con un acomodo específico, y debajo un mapa oscuro de campo de futbol americano con cascos numerados.
2. Los tres perfiles: haz clic en los botones "General", "Ofensivo" y "Defensivo". General debe mostrar 22 cascos en el mapa; Ofensivo y Defensivo, 11 cada uno. Verifica que las cifras de ASV, éxito observado y éxito esperado cambien al cambiar de perfil.
3. Selector de equipo: cambia el equipo (arriba a la derecha, los 32 equipos de la NFL) y confirma que el mapa, las tablas y el titular se actualizan sin errores.
4. Hover en el mapa: pasa el cursor sobre un casco. Debe aparecer una tarjeta oscura con el nombre del jugador, su dorsal, el puesto donde se alinea, snaps en el acomodo, dominio del puesto y su posición promedio en yardas.
5. Clic en un casco: debe abrir el perfil del jugador (la URL cambia a algo como #/jugador/25511). Revisa que aparezca el avatar grande con el dorsal, el nombre en grande, edad, peso, altura, universidad y posición, y debajo una cuadrícula de estadísticas (pases completos, yardas, presiones, velocidad máxima, amonestaciones) y barras de percentiles contra jugadores de su misma posición.
6. Tablas: vuelve atrás y revisa las tablas de alineación y la de "Fuera del acomodo". Haz clic en una fila de cada tabla: también debe abrir el perfil del jugador.
7. Rusher (el asistente de IA): botón negro abajo a la derecha, con un contador de consultas. Ábrelo y pregúntale: "¿Cuál es el mejor acomodo ofensivo de KC y por qué?". Debe responder con cifras concretas y mostrar debajo qué herramienta consultó. Verifica que el contador baje de 50 a 49.
8. Diseño responsivo: prueba en 1440px, 768px y 375px de ancho. Reporta cualquier desborde horizontal, texto cortado, tabla que se salga del contenedor o casco que quede fuera del mapa.
9. Consola del navegador: reporta cualquier error de JavaScript o petición de red fallida.

ENTREGABLE
Dame un reporte con: qué funciona, qué está roto o se ve mal (con captura y el ancho de pantalla donde ocurre), y una lista de ajustes concretos ordenada por impacto visual. Sé específico y crítico con el diseño: debe verse como una herramienta financiera profesional, sobria, sin emojis, con tipografía densa y números alineados.

No modifiques nada en el servidor remoto. Solo observa y reporta.
```

---

## Si el túnel falla

Comprueba desde tu máquina que el puerto SSH responde:

```bash
nc -vz 159.54.129.29 22
```

Y que el servidor sigue sirviendo, ya dentro de la sesión SSH:

```bash
ssh -i RUTA_A_TU_LLAVE ubuntu@159.54.129.29 'curl -s localhost:8000/health'
```

Si no responde, relanza la app en el servidor:

```bash
cd ~/hack/hackathon-unam
setsid .venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000 > api.log 2>&1 < /dev/null &
```
