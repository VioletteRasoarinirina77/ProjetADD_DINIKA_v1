"""Tests de integration/verifier_contrat.py."""

from integration.verifier_contrat import verifier_liste_de_bougies

BOUGIE_VALIDE = {
    "instrument_id": "GOLD", "source": "COMEX", "timeframe": "1h",
    "timestamp": "2026-01-01T10:00:00Z",
    "open": 2400.0, "high": 2401.0, "low": 2399.0, "close": 2400.5, "volume": 100,
}


def test_liste_entierement_valide():
    nb_valides, erreurs = verifier_liste_de_bougies([BOUGIE_VALIDE, BOUGIE_VALIDE])
    assert nb_valides == 2
    assert erreurs == []


def test_champ_manquant_est_detecte_avec_son_index():
    bougie_incomplete = {"instrument_id": "GOLD", "source": "COMEX"}
    nb_valides, erreurs = verifier_liste_de_bougies([BOUGIE_VALIDE, bougie_incomplete])

    assert nb_valides == 1
    assert len(erreurs) == 1
    assert erreurs[0]["index"] == 1


def test_timestamp_naif_est_detecte():
    bougie_timestamp_naif = {**BOUGIE_VALIDE, "timestamp": "2026-01-01T10:00:00"}  # pas de fuseau horaire
    nb_valides, erreurs = verifier_liste_de_bougies([bougie_timestamp_naif])

    assert nb_valides == 0
    assert "timestamp" in str(erreurs[0]["erreurs"])


def test_volume_negatif_est_detecte():
    bougie_volume_negatif = {**BOUGIE_VALIDE, "volume": -10}
    nb_valides, erreurs = verifier_liste_de_bougies([bougie_volume_negatif])
    assert nb_valides == 0


def test_liste_vide_ne_plante_pas():
    nb_valides, erreurs = verifier_liste_de_bougies([])
    assert nb_valides == 0
    assert erreurs == []


def test_toutes_les_erreurs_sont_rapportees_pas_seulement_la_premiere():
    """Important pour l'usage réel : Harimamy doit voir TOUS les problèmes
    d'un coup, pas les corriger un par un à chaque relance."""
    bougies = [BOUGIE_VALIDE, {"instrument_id": "GOLD"}, {"instrument_id": "ES"}]
    nb_valides, erreurs = verifier_liste_de_bougies(bougies)
    assert nb_valides == 1
    assert len(erreurs) == 2
