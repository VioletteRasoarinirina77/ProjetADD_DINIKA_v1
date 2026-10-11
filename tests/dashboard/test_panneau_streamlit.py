"""Test de fumée du panneau D7 exécuté réellement via Streamlit (AppTest)."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

PANNEAU = str(Path(__file__).parents[2] / "dashboard" / "panel_quant.py")


@pytest.fixture(scope="module")
def application():
    return AppTest.from_file(PANNEAU, default_timeout=120).run()


def test_le_panneau_s_execute_sans_exception(application):
    assert not application.exception


def test_le_bandeau_d_avertissement_est_affiche(application):
    assert any("aucune exécution d'ordre réel" in w.value for w in application.warning)


def test_par_defaut_le_panneau_affiche_le_pack_reel_gele_pour_es(application):
    assert application.selectbox[0].value == "ES"
    assert application.selectbox[1].value.startswith("Pack réel gelé")
    assert any("réelles gelées" in i.value for i in application.info)
    assert not any("SYNTHÉTIQUES" in i.value for i in application.info)


def test_le_panneau_es_reel_explique_pourquoi_la_taille_est_zero(application):
    """Avec 10 000 $ de capital, 1 contrat ES dépasse le risque autorisé : la taille est 0 et une
    alerte doit l'expliquer avec des chiffres plutôt que d'afficher un « 0 » sans contexte."""
    assert any("0 contrat recommandé" in w.value for w in application.warning)


def test_les_alertes_affichent_leur_temps_de_calcul_sous_5_secondes(application):
    lignes = [c.value for c in application.caption if "alerte(s) calculée(s) en" in c.value]
    assert lignes, "aucune légende de chronométrage des alertes trouvée"
    duree = float(lignes[0].split("en ")[1].split(" s")[0])
    assert duree < 5.0


def test_aucune_alerte_de_reconciliation_sans_anomalie_fournie(application):
    """Le panneau de démonstration n'appelle pas encore la réconciliation multi-sources : pas
    d'alerte de ce type tant qu'aucune anomalie ne lui est transmise."""
    assert not any("écart de" in w.value and "%" in w.value for w in application.warning)


def test_le_panneau_annonce_des_donnees_synthetiques_pour_les_fixtures():
    """Sur fixtures : jamais présentées comme réelles."""
    application = AppTest.from_file(PANNEAU, default_timeout=120).run()
    application.selectbox[1].select("Fixtures synthétiques (démonstration)").run()
    assert not application.exception
    assert any("SYNTHÉTIQUES" in i.value for i in application.info)
    assert not any("réelles gelées" in i.value for i in application.info)


def test_gold_ne_propose_que_les_fixtures_synthetiques():
    application = AppTest.from_file(PANNEAU, default_timeout=120).run()
    application.selectbox[0].select("GOLD").run()
    assert not application.exception
    assert list(application.selectbox[1].options) == ["Fixtures synthétiques (démonstration)"]


def test_le_drawdown_affiche_reste_un_pourcentage_vraisemblable(application):
    """Régression : l'ancien calcul affichait des drawdowns de plusieurs milliers de %."""
    valeurs = [m.value for m in application.metric if m.label == "Drawdown max"]
    assert valeurs, "métrique « Drawdown max » absente du panneau"
    assert all(v == "N/A" or float(v.rstrip("%")) <= 100.0 for v in valeurs)


def test_le_panneau_fonctionne_pour_chaque_instrument():
    application = AppTest.from_file(PANNEAU, default_timeout=120).run()
    for instrument in application.selectbox[0].options:
        application.selectbox[0].select(instrument).run()
        assert not application.exception, f"exception pour {instrument}"
