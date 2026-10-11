"""Tests de la ligne de commande integration/verifier_contrat.py."""

import json
import sys

import pytest

from integration import verifier_contrat

BOUGIE_OK = {
    "instrument_id": "ES", "source": "databento", "timeframe": "1D",
    "timestamp": "2026-01-05T00:00:00+00:00",
    "open": 100.0, "high": 110.0, "low": 95.0, "close": 105.0, "volume": 10.0,
}


def _lancer(monkeypatch, args):
    monkeypatch.setattr(sys, "argv", ["verifier_contrat", *args])
    with pytest.raises(SystemExit) as sortie:
        verifier_contrat.main()
    return sortie.value.code


def test_fichier_conforme_sort_avec_code_0(tmp_path, monkeypatch, capsys):
    fichier = tmp_path / "ok.json"
    fichier.write_text(json.dumps([BOUGIE_OK]), encoding="utf-8")
    assert _lancer(monkeypatch, [str(fichier)]) == 0
    assert "1/1" in capsys.readouterr().out


def test_fichier_non_conforme_sort_avec_code_1(tmp_path, monkeypatch, capsys):
    mauvaise = {**BOUGIE_OK, "high": 50.0}  # high < low : viole la règle OHLC
    fichier = tmp_path / "ko.json"
    fichier.write_text(json.dumps([BOUGIE_OK, mauvaise]), encoding="utf-8")
    assert _lancer(monkeypatch, [str(fichier)]) == 1
    assert "NON conforme" in capsys.readouterr().out


def test_json_qui_n_est_pas_une_liste_est_refuse(tmp_path, monkeypatch, capsys):
    fichier = tmp_path / "objet.json"
    fichier.write_text(json.dumps(BOUGIE_OK), encoding="utf-8")
    assert _lancer(monkeypatch, [str(fichier)]) == 1
    assert "LISTE" in capsys.readouterr().out


def test_plus_de_dix_erreurs_est_tronque_a_l_affichage(tmp_path, monkeypatch, capsys):
    mauvaises = [{**BOUGIE_OK, "high": 50.0} for _ in range(12)]
    fichier = tmp_path / "beaucoup.json"
    fichier.write_text(json.dumps(mauvaises), encoding="utf-8")
    assert _lancer(monkeypatch, [str(fichier)]) == 1
    assert "2 autre(s) erreur(s)" in capsys.readouterr().out


def test_lecture_via_url(monkeypatch, capsys):
    class _Reponse:
        def raise_for_status(self):
            pass

        def json(self):
            return [BOUGIE_OK]

    monkeypatch.setattr(verifier_contrat.httpx, "get", lambda url, timeout: _Reponse())
    assert _lancer(monkeypatch, ["--url", "http://exemple.test/candles"]) == 0
