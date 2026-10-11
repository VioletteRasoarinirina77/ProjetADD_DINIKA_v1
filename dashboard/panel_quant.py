"""Panneau Quant (D7).

Deux blocs volontairement séparés dans ce fichier :

1. afficher_panneau_risque_quant() -- LE panneau au sens strict de l'offre
   technique (§5.1 Sprint 3 : "chacune son panneau (marché / risque /
   sentiment)"). Le tien = risque. C'est une fonction RÉUTILISABLE : le jour
   de l'assemblage réel avec Harimamy (marché) et Oly (sentiment), on
   l'appelle directement dans leur mise en page à trois colonnes, sans
   copier-coller le reste de ce fichier.

2. Le corps du script (sélecteur d'instrument, D8, vue portefeuille) --
   une DÉMONSTRATION ÉLARGIE pour visualiser ton travail en attendant
   l'assemblage réel. D8 et la vue portefeuille sont un travail COMMUN aux
   trois pistes (pas "ton panneau" au sens strict), donc affichés à part,
   étiquetés comme tels, pas mélangés au panneau risque lui-même.

Ne modifie AUCUN fichier de D2/D3/D4/D8 -- se contente de les appeler et
d'afficher leurs résultats. Respecte le critère d'acceptation du CDC :
synthèse affichée en moins de 3 secondes, bandeau d'avertissement permanent.

Lancer avec :
    streamlit run dashboard/panel_quant.py
"""

import json
import sys
from pathlib import Path

# streamlit run n'ajoute au chemin Python QUE le dossier du script (dashboard/),
# jamais la racine du projet -- contrairement a "python -m ...". Sans cette ligne,
# "from backtest.walk_forward import ..." echoue avec ModuleNotFoundError, car
# Python ne sait pas ou trouver le dossier backtest/ (un niveau au-dessus).
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import streamlit as st

from config.instruments import INSTRUMENTS, OrigineDonnees, instruments_avec_donnees_reelles
from contracts.schemas import Bougie
from dashboard.alertes import NiveauAlerte, generer_alertes
from dashboard.synthese import construire_synthese_panneau_risque
from indicators.technical import ajouter_indicateurs, bougies_vers_dataframe
from integration.pack_repository import PackDataRepository
from paper_trading.portfolio import simuler_portefeuille
from paper_trading.simulator import (
    simuler_paper_trading_hors_echantillon,
)

RACINE_PACK = Path(__file__).parent.parent / "fixtures" / "integration" / "pack_es_v1"
SOURCE_FIXTURES = "Fixtures synthétiques (démonstration)"
SOURCE_PACK = "Pack réel gelé v1.0 (SHA-256 vérifié)"
# Sur le pack réel (4453 bougies), le walk-forward complet dépasse le seuil CDC de 3 s : le panneau
# travaille sur les dernières bougies (~4 ans de séances). Limite affichée à l'écran.
FENETRE_PANNEAU_PACK = 1000

FIXTURES_PAR_INSTRUMENT = {
    "GOLD": "backtest/bougies_gold_300h.json",
    "ES": "backtest/bougies_es_300h.json",
}



def charger_bougies(instrument_id: str) -> list[Bougie]:
    """Charge les fixtures synthétiques de démonstration de l'instrument (jamais le pack réel)."""
    chemin = Path(__file__).parent.parent / "fixtures" / FIXTURES_PAR_INSTRUMENT[instrument_id]
    with open(chemin) as f:
        donnees = json.load(f)
    return [Bougie(**d) for d in donnees]


def charger_bougies_pack(instrument_id: str) -> list[Bougie]:
    """Charge le pack gelé : le SHA-256 est vérifié AVANT tout calcul (ErreurIntegritePack sinon)."""
    return PackDataRepository(RACINE_PACK).candles_validees(instrument_id)


# =============================================================================
# BLOC 1 -- LE panneau D7 (risque), au sens strict de l'offre technique.
# C'est CETTE fonction qu'on branchera dans le tableau de bord commun assemblé
# avec Harimamy (panneau marché) et Oly (panneau sentiment) -- appelable
# telle quelle, dans une colonne Streamlit ou tout autre conteneur.
# =============================================================================
def afficher_panneau_risque_quant(
    instrument_id: str,
    bougies: list[Bougie],
    donnees_issues_du_pack: bool = False,
    capital_virtuel: float = 10_000.0,
    fenetre_max_bougies: int | None = None,
) -> None:
    """Affiche UNIQUEMENT le panneau risque/quant -- indicateurs, signal.

    actuel, validation walk-forward. Rien d'autre : le paper-trading et la
    vue portefeuille sont un travail commun, pas ce panneau individuel.

    Les calculs vivent dans dashboard/synthese.py (testé, critère < 3 s) ;
    cette fonction ne fait qu'afficher.
    """
    synthese = construire_synthese_panneau_risque(
        instrument_id,
        bougies,
        donnees_issues_du_pack=donnees_issues_du_pack,
        capital_virtuel=capital_virtuel,
        fenetre_max_bougies=fenetre_max_bougies,
    )
    if fenetre_max_bougies is not None:
        bougies = bougies[-fenetre_max_bougies:]
    signal = synthese.signal
    df = ajouter_indicateurs(bougies_vers_dataframe(bougies), instrument_id)

    # Bandeau permanent : EN HAUT du panneau (charte éthique), puis origine des données.
    st.warning(synthese.bandeau_avertissement)
    st.info(synthese.libelle_origine)
    st.caption(f"Bougies analysées : {synthese.nb_bougies_analysees}")

    # Alertes (D7, critère CDC : < 5 s) : signalent un état qui mérite l'attention immédiate,
    # au-delà des chiffres bruts affichés plus bas (drawdown élevé, taille nulle, etc.).
    alertes, duree_alertes = generer_alertes(synthese)
    afficheur = {
        NiveauAlerte.CRITIQUE: st.error,
        NiveauAlerte.AVERTISSEMENT: st.warning,
        NiveauAlerte.INFO: st.info,
    }
    for alerte in alertes:
        afficheur[alerte.niveau](alerte.message)
    st.caption(
        f"{len(alertes)} alerte(s) calculée(s) en {duree_alertes:.3f} s (critère CDC : < 5 s)"
    )

    st.subheader(f"Panneau Risque — {instrument_id}")

    col_graphiques, col_signal = st.columns([2, 1])
    with col_graphiques:
        st.caption("Prix et moyennes mobiles")
        st.line_chart(df[["close", "sma_20", "ema_20"]])
        st.caption("RSI (14)")
        st.line_chart(df[["rsi_14"]])

    with col_signal:
        st.caption("Signal actuel (D2 + D4)")
        rsi, atr = signal.indicateurs.rsi_14, signal.indicateurs.atr_14
        st.metric("RSI-14", f"{rsi:.1f}" if rsi is not None else "N/A")
        st.metric("ATR-14", f"{atr:.2f}" if atr is not None else "N/A")
        st.metric("Stop-loss", signal.risque.stop_loss)
        st.metric("Take-profit", signal.risque.take_profit)
        st.metric("Taille de position", signal.risque.taille_position_recommandee)
        if synthese.explication_taille_nulle:
            st.caption("Voir l'alerte ci-dessus pour le détail du calcul.")

    st.caption("Validation walk-forward (D3) — sur la zone de validation uniquement")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sharpe", synthese.sharpe if synthese.sharpe is not None else "N/A")
    c2.metric(
        "Drawdown max",
        f"{synthese.drawdown_max:.1%}" if synthese.drawdown_max is not None else "N/A",
        help=(
            "Chute maximale de la courbe de capital normalisée (100 % investi à chaque trade, "
            "sans levier), en proportion du sommet précédent. Ratio sans unité, hors capital virtuel."
        ),
    )
    c3.metric(
        "Taux de réussite",
        f"{synthese.taux_reussite:.0%}" if synthese.taux_reussite is not None else "N/A",
    )
    c4.metric("Nb trades", synthese.nb_trades)
    st.caption(f"Synthèse calculée en {synthese.duree_calcul_secondes:.2f} s (critère CDC : < 3 s)")


# =============================================================================
# BLOC 2 -- démonstration élargie (sélecteur, D8, vue portefeuille).
# PAS "ton panneau" au sens strict -- du travail commun (D7/D8, Sprint 3),
# affiché ici uniquement pour visualiser l'ensemble en attendant
# l'assemblage réel avec les 2 autres pistes.
# =============================================================================
st.set_page_config(page_title="DINIKA — Panneau Quant", layout="wide")
st.title("Piste Quantitatif — démonstration (D2, D3, D4, D7, D8)")
st.caption(
    "La section 'Panneau Risque' ci-dessous est la fonction réutilisable prête pour "
    "l'assemblage final. Le reste (D8, portefeuille) est une démonstration du travail "
    "commun, pas le panneau individuel lui-même."
)

ids_reels = instruments_avec_donnees_reelles()
liste_instruments = list(INSTRUMENTS.keys())
instrument_id = st.selectbox(
    "Instrument", liste_instruments, index=liste_instruments.index(ids_reels[0]) if ids_reels else 0
)

# La source « pack réel » n'est proposée que pour un instrument réellement adossé à un pack gelé.
sources_possibles = (
    [SOURCE_PACK, SOURCE_FIXTURES]
    if INSTRUMENTS[instrument_id].origine_donnees is OrigineDonnees.REEL_GELE
    else [SOURCE_FIXTURES]
)
source = st.selectbox("Source des données", sources_possibles)
capital_virtuel = st.number_input(
    "Capital virtuel ($)", min_value=1_000.0, value=10_000.0, step=1_000.0, format="%.0f"
)

utilise_le_pack = source == SOURCE_PACK
bougies = charger_bougies_pack(instrument_id) if utilise_le_pack else charger_bougies(instrument_id)
fenetre = FENETRE_PANNEAU_PACK if utilise_le_pack else None
bougies_demo = bougies[-fenetre:] if fenetre else bougies

afficher_panneau_risque_quant(
    instrument_id,
    bougies,
    donnees_issues_du_pack=utilise_le_pack,
    capital_virtuel=capital_virtuel,
    fenetre_max_bougies=fenetre,
)

st.divider()
st.subheader("Démonstration — Paper-trading (D8, travail commun)")
resultat_pt = simuler_paper_trading_hors_echantillon(
    bougies_demo, instrument_id, taille_hors_echantillon=60, capital_initial=capital_virtuel
)
st.caption(
    f"Zone hors-échantillon : à partir du {resultat_pt.debut_zone_hors_echantillon} "
    "— données jamais vues par le backtest walk-forward ci-dessus."
)
st.line_chart(pd.Series(resultat_pt.courbe_capital, name="Capital virtuel ($)"))

variation = resultat_pt.capital_final - resultat_pt.capital_initial
st.metric("Capital final", f"${resultat_pt.capital_final:,.2f}", delta=f"{variation:+,.2f} $")

if resultat_pt.journal:
    st.dataframe(pd.DataFrame([t.model_dump() for t in resultat_pt.journal]))
else:
    st.info("Aucun trade complet sur cet historique — normal avec peu de données ou un stop large.")

st.divider()
st.subheader("Démonstration — Vue portefeuille (D4/D7, travail commun)")
st.caption(
    "Répond au §6 du registre des risques de l'audit : "
    "plafonner l'exposition totale, pas juste par trade. "
    "Cette vue utilise toujours les fixtures SYNTHÉTIQUES de tous les instruments."
)

plafond_ratio = st.slider("Plafond d'exposition (multiple du capital)", 0.5, 10.0, 3.0, step=0.5)
bougies_tous_instruments = {iid: charger_bougies(iid) for iid in INSTRUMENTS}
resultat_portefeuille = simuler_portefeuille(bougies_tous_instruments, plafond_exposition_ratio=plafond_ratio)

cp1, cp2, cp3 = st.columns(3)
cp1.metric("Capital final (portefeuille)", f"${resultat_portefeuille.capital_final:,.2f}")
cp2.metric("Trades exécutés", len(resultat_portefeuille.trades))
cp3.metric("Trades rejetés (plafond)", len(resultat_portefeuille.trades_rejetes))

st.line_chart(pd.Series(resultat_portefeuille.courbe_capital, name="Capital du portefeuille ($)"))

if resultat_portefeuille.trades_rejetes:
    st.caption("Trades refusés car ils auraient dépassé le plafond d'exposition :")
    st.dataframe(pd.DataFrame([r.model_dump() for r in resultat_portefeuille.trades_rejetes]))
