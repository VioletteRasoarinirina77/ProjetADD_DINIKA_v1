"""Vérifie la STRUCTURE de la configuration TLS (exigence CDC : TLS).

Ces tests ne lancent pas Docker : ils garantissent que la configuration
respecte les règles de sécurité (API non exposée en clair, proxy sur 443,
domaine paramétrable). L'exécution réelle sous Docker reste à faire.
"""

from pathlib import Path

import yaml

RACINE = Path(__file__).parents[1]


def _compose_tls() -> dict:
    with open(RACINE / "docker-compose.tls.yml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_l_api_n_est_pas_publiee_en_clair_sur_l_hote():
    service = _compose_tls()["services"]["piste-quant"]
    assert "ports" not in service
    assert "8002" in [str(p) for p in service["expose"]]


def test_le_proxy_expose_https_sur_le_port_443():
    ports = [str(p) for p in _compose_tls()["services"]["proxy-tls"]["ports"]]
    assert "443:443" in ports


def test_le_proxy_et_l_api_partagent_le_meme_reseau_interne():
    services = _compose_tls()["services"]
    assert set(services["proxy-tls"]["networks"]) & set(services["piste-quant"]["networks"])


def test_le_domaine_est_parametrable_et_le_proxy_relaie_vers_l_api():
    caddyfile = (RACINE / "deploy" / "Caddyfile").read_text(encoding="utf-8")
    assert "{$DINIKA_DOMAINE:localhost}" in caddyfile
    assert "reverse_proxy piste-quant:8002" in caddyfile


def test_le_caddyfile_est_monte_en_lecture_seule():
    volumes = _compose_tls()["services"]["proxy-tls"]["volumes"]
    assert any(v.startswith("./deploy/Caddyfile") and v.endswith(":ro") for v in volumes)


def test_aucun_secret_n_est_ecrit_en_dur_dans_la_configuration_tls():
    contenu = (RACINE / "docker-compose.tls.yml").read_text(encoding="utf-8").lower()
    for mot in ("password", "api_key", "secret", "token"):
        assert f"{mot}=" not in contenu
