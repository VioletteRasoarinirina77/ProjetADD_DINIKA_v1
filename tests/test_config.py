"""Tests de la configuration par instrument — à lancer avec: pytest tests/test_instruments.py"""

import pytest
from pydantic import ValidationError

from config.instruments import (
    INSTRUMENTS,
    VARIABLE_ENV_CAPITAL,
    InstrumentConfig,
    OrigineDonnees,
    SourceDonnees,
    TypeSource,
    instruments_avec_donnees_reelles,
    obtenir_config,
    resoudre_capital_portefeuille,
    resoudre_capital_virtuel,
)


def test_le_registre_contient_au_moins_deux_instruments():
    """Le CDC exige >= 2 instruments pour le paper-trading (D8)."""
    assert len(INSTRUMENTS) >= 2


def test_chaque_instrument_a_une_source_primaire_unique():
    for instrument_id, cfg in INSTRUMENTS.items():
        primaires = [s for s in cfg.sources if s.est_primaire]
        assert len(primaires) == 1, f"{instrument_id} doit avoir exactement 1 source primaire"


def test_obtenir_config_leve_une_erreur_si_instrument_inconnu():
    with pytest.raises(KeyError):
        obtenir_config("INSTRUMENT_QUI_N_EXISTE_PAS")


def test_es_est_marque_comme_adosse_a_un_dataset_gelE_reel():
    """ES a un pack v1.0 livré et vérifié par SHA-256 (point de revue 4)."""
    assert obtenir_config("ES").origine_donnees is OrigineDonnees.REEL_GELE


def test_gold_est_marque_comme_synthetique():
    """GOLD n'a aucun pack gelé livré : ne doit jamais être confondu avec ES
    dans un rapport ou un mémoire présentés comme fondés sur des données réelles
    (point de revue 4)."""
    assert obtenir_config("GOLD").origine_donnees is OrigineDonnees.SYNTHETIQUE


def test_instruments_avec_donnees_reelles_ne_contient_que_es():
    assert instruments_avec_donnees_reelles() == ["ES"]


def test_un_instrument_sans_origine_donnees_explicite_est_synthetique_par_defaut():
    """Garde-fou anti-confusion : un nouvel instrument ajouté sans préciser
    origine_donnees ne doit jamais être traité par défaut comme réel."""
    config = InstrumentConfig(
        instrument_id="TEST_NOUVEAU",
        multiplicateur_contrat=1.0,
        sources=[
            SourceDonnees(nom="A", symbole="X", type_source=TypeSource.FUTURE, est_primaire=True)
        ],
    )
    assert config.origine_donnees is OrigineDonnees.SYNTHETIQUE


def test_deux_sources_primaires_est_refuse():
    """Garde-fou anti-ambiguïté (guide partie 3, §3 — réconciliation multi-sources)."""
    with pytest.raises(ValidationError):
        InstrumentConfig(
            instrument_id="TEST",
            multiplicateur_contrat=1.0,
            sources=[
                SourceDonnees(
                    nom="A", symbole="X", type_source=TypeSource.FUTURE, est_primaire=True
                ),
                SourceDonnees(
                    nom="B", symbole="Y", type_source=TypeSource.CFD, est_primaire=True
                ),
            ],
        )


# --------------------------------------------------------------------------- D-012 : capital virtuel


def test_source_primaire_renvoie_bien_la_source_marquee_primaire():
    source = obtenir_config("ES").source_primaire()
    assert source.est_primaire is True


def test_resoudre_capital_virtuel_priorise_l_argument_explicite(monkeypatch):
    monkeypatch.setenv(VARIABLE_ENV_CAPITAL, "999999")
    assert resoudre_capital_virtuel("ES", 42.0) == 42.0


def test_resoudre_capital_virtuel_sans_rien_utilise_le_defaut_de_l_instrument(monkeypatch):
    monkeypatch.delenv(VARIABLE_ENV_CAPITAL, raising=False)
    assert resoudre_capital_virtuel("ES", None) == obtenir_config("ES").capital_virtuel_defaut
    assert resoudre_capital_virtuel("GOLD", None) == obtenir_config("GOLD").capital_virtuel_defaut


def test_resoudre_capital_virtuel_lit_la_variable_d_environnement(monkeypatch):
    monkeypatch.setenv(VARIABLE_ENV_CAPITAL, "50000")
    assert resoudre_capital_virtuel("ES", None) == 50_000.0


def test_resoudre_capital_virtuel_rejette_une_variable_d_environnement_non_numerique(monkeypatch):
    monkeypatch.setenv(VARIABLE_ENV_CAPITAL, "pas-un-nombre")
    with pytest.raises(ValueError, match="doit être un nombre"):
        resoudre_capital_virtuel("ES", None)


def test_resoudre_capital_virtuel_rejette_une_variable_d_environnement_negative_ou_nulle(monkeypatch):
    monkeypatch.setenv(VARIABLE_ENV_CAPITAL, "0")
    with pytest.raises(ValueError, match="strictement positif"):
        resoudre_capital_virtuel("ES", None)


def test_resoudre_capital_portefeuille_prend_le_plus_grand_defaut_des_instruments_demandes(monkeypatch):
    monkeypatch.delenv(VARIABLE_ENV_CAPITAL, raising=False)
    attendu = max(obtenir_config("ES").capital_virtuel_defaut, obtenir_config("GOLD").capital_virtuel_defaut)
    assert resoudre_capital_portefeuille(["GOLD", "ES"], None) == attendu


def test_resoudre_capital_portefeuille_priorise_l_argument_explicite(monkeypatch):
    monkeypatch.setenv(VARIABLE_ENV_CAPITAL, "999999")
    assert resoudre_capital_portefeuille(["GOLD", "ES"], 123.0) == 123.0
