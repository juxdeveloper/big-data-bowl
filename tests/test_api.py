"""Pruebas del contrato de la API y de la coherencia de la metrica ASV."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import ART, app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_meta_expone_metrica_y_modelo():
    d = client.get("/api/meta").json()
    assert d["ready"] is True
    assert d["metric"]["name"] == "ASV"
    assert len(d["teams"]) == 32
    # el modelo debe superar a la tasa base, no solo empatarla
    assert d["model"]["auc_test"] > 0.55
    assert d["model"]["logloss_test"] < d["model"]["logloss_baseline"]
    assert d["metric"]["limitations"], "la metrica debe declarar sus limites"


@pytest.mark.parametrize("profile", ["GENERAL", "ATAQUE", "DEFENSA"])
def test_cada_equipo_tiene_los_tres_perfiles(profile):
    d = client.get(f"/api/team/KC?profile={profile}").json()
    assert d["profile"] == profile
    n = 22 if profile == "GENERAL" else 11
    assert len(d["lineup"]) == n, f"{profile} debe alinear {n} jugadores"
    assert len({p["nflId"] for p in d["lineup"]}) == n, "ningun jugador se repite en el acomodo"
    # el acomodo elegido debe ser el de mayor ASV entre las alternativas
    if d["alternatives"]:
        assert d["asv"] == max(a["asv"] for a in d["alternatives"])


def test_el_acomodo_optimo_supera_la_expectativa():
    d = client.get("/api/team/TB?profile=ATAQUE").json()
    assert d["successRate"] > d["expected"], "ASV positivo implica exito sobre lo esperado"
    assert d["n"] >= 12, "muestra minima para no reportar ruido"


def test_fuera_del_acomodo_no_contiene_titulares():
    d = client.get("/api/team/SF?profile=ATAQUE").json()
    on = {p["nflId"] for p in d["lineup"]}
    assert not (on & {p["nflId"] for p in d["inactive"]})


def test_perfil_de_jugador_con_percentiles():
    d = client.get("/api/player/25511").json()  # Tom Brady
    assert d["name"] == "Tom Brady"
    assert d["position"] == "QB"
    assert d["attempts"] > 0 and 0 < d["completionPct"] < 1
    assert d["peerGroup"]["position"] == "QB"


def test_jugador_inexistente():
    assert client.get("/api/player/1").status_code == 404
    assert client.get("/api/team/XXX").status_code == 404


def test_busqueda_de_jugadores():
    d = client.get("/api/players?q=brady").json()
    assert any(p["name"] == "Tom Brady" for p in d)


def test_chat_degrada_sin_credenciales():
    """Requisito del evento: la app funciona aunque la IA no este disponible."""
    r = client.post("/api/chat", json={"message": "hola"})
    assert r.status_code in (200, 429, 503)
    body = r.json()
    assert "reply" in body or "message" in body


def test_cuota_de_rusher_se_descuenta():
    from backend.main import QUOTA_LIMIT, quota_remaining, quota_take

    antes = quota_remaining()
    quota_take()
    assert quota_remaining() == antes - 1
    assert QUOTA_LIMIT == 50


def test_artefactos_sin_credenciales_filtradas():
    for f in ("league.json", "teams.json", "players.json"):
        txt = (ART / f).read_text(encoding="utf-8").lower()
        for leak in ("aws_access_key", "aws_secret", "aws_session_token", "asia", "akia"):
            assert leak not in txt


def test_dashboard_usa_rutas_relativas():
    """Contrato de despliegue: la app vive en una subruta, nada de '/api' ni localhost."""
    src = Path(__file__).resolve().parent.parent / "dashboard" / "src"
    for f in src.rglob("*.ts*"):
        t = f.read_text(encoding="utf-8")
        assert "'/api" not in t and '"/api' not in t, f"ruta absoluta en {f.name}"
        assert "localhost" not in t and "127.0.0.1" not in t, f"host fijo en {f.name}"


def test_modelo_contrincante_documentado():
    f = ART / "asv_model.json"
    if not f.exists():
        pytest.skip("modelo de Colab no descargado")
    d = json.loads(f.read_text(encoding="utf-8"))
    assert d["metrics"]["auc_test"] > 0.55
    assert d["features"] and d["weights"]
