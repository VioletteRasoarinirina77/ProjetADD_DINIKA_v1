"""Synthèse du panneau Risque/Quant (D7) -- logique pure, sans Streamlit.

Pourquoi ce module existe : la logique de calcul du panneau était mêlée aux
appels Streamlit, donc impossible à tester automatiquement. Deux critères du
CDC (D7) ne pouvaient donc pas être vérifiés :

- synthèse affichée en moins de 3 secondes ;
- bandeau d'avertissement permanent.

Ici, tout est calculable et testable sans interface. `panel_quant.py` se
contente d'afficher ce que ce module produit.
"""

import time

from pydantic import BaseModel

from backtest.walk_forward import walk_forward_backtest
from config.instruments import OrigineDonnees, obtenir_config
from contracts.schemas import Bougie, ParametresRisqueCalcules, SignalQuantitatif
from paper_trading.simulator import separer_validation_et_hors_echantillon
from risk.position_sizing import CAPITAL_VIRTUEL_DEFAUT
from services.quant_engine import calculer_signal_quantitatif

# Bandeau exigé par la charte éthique du projet : affiché EN HAUT du panneau,
# en permanence, quelles que soient les données.
BANDEAU_AVERTISSEMENT = (
    "⚠️ Outil d'aide à la décision — aucune exécution d'ordre réel, aucune promesse "
    "de gain. Validation en simulation (paper-trading) uniquement."
)

LIBELLE_ORIGINE = {
    OrigineDonnees.REEL_GELE: "Données réelles gelées (pack Piste Data, SHA-256 vérifié)",
    OrigineDonnees.SYNTHETIQUE: "Données SYNTHÉTIQUES de démonstration — aucun résultat réel",
}

SEUIL_SYNTHESE_SECONDES = 3.0  # critère CDC D7
TAILLE_HORS_ECHANTILLON_PANNEAU = 60


class SynthesePanneauRisque(BaseModel):
    """Tout ce que le panneau Risque affiche, prêt à être rendu."""

    instrument_id: str
    origine_donnees: OrigineDonnees
    libelle_origine: str
    signal: SignalQuantitatif
    sharpe: float | None
    drawdown_max: float | None
    taux_reussite: float | None
    nb_trades: int
    nb_bougies_analysees: int
    duree_calcul_secondes: float
    explication_taille_nulle: str | None = None
    bandeau_avertissement: str = BANDEAU_AVERTISSEMENT


def libelle_origine_donnees(instrument_id: str) -> str:
    """Libellé honnête de l'origine des données d'un instrument (point 4)."""
    return LIBELLE_ORIGINE[obtenir_config(instrument_id).origine_donnees]


def expliquer_taille_nulle(instrument_id: str, risque: ParametresRisqueCalcules) -> str | None:
    """Explique, chiffres à l'appui, pourquoi aucun contrat n'est recommandé (sinon None).

    La taille est un ENTIER de contrats (jamais une fraction) : si le risque d'UN contrat dépasse le
    risque autorisé par trade, la taille est 0. Sans explication, un « 0 » affiché est incompréhensible.
    """
    if risque.taille_position_recommandee != 0:
        return None
    if risque.risque_par_contrat <= 0:
        return "0 contrat : ATR indisponible (historique trop court pour dimensionner le risque)."
    pourcentage = obtenir_config(instrument_id).risque.pourcentage_risque_par_trade
    capital_minimal = risque.risque_par_contrat / pourcentage
    return (
        f"0 contrat recommandé : le risque d'UN contrat ({risque.risque_par_contrat:,.0f} $) dépasse le "
        f"risque autorisé par trade ({risque.risque_max_dollars:,.0f} $ = {pourcentage:.0%} de "
        f"{risque.capital_virtuel:,.0f} $). Capital virtuel minimal pour 1 contrat avec cette "
        f"configuration : environ {capital_minimal:,.0f} $."
    )


def construire_synthese_panneau_risque(
    instrument_id: str,
    bougies: list[Bougie],
    taille_hors_echantillon: int = TAILLE_HORS_ECHANTILLON_PANNEAU,
    donnees_issues_du_pack: bool = False,
    capital_virtuel: float = CAPITAL_VIRTUEL_DEFAUT,
    fenetre_max_bougies: int | None = None,
) -> SynthesePanneauRisque:
    """Calcule le signal (D2 + D4) et la validation walk-forward (D3).

    Le walk-forward n'utilise que la zone de validation : la zone
    hors-échantillon reste réservée à D8 (aucune fuite d'information).

    `donnees_issues_du_pack` : l'origine affichée est celle des données
    RÉELLEMENT chargées, pas seulement celle déclarée dans la config. Un
    instrument marqué réel mais alimenté par une fixture est présenté comme
    synthétique -- on ne laisse jamais croire à un résultat réel qui n'en est pas un.
    """
    debut = time.perf_counter()
    config = obtenir_config(instrument_id)
    origine = (
        OrigineDonnees.REEL_GELE
        if donnees_issues_du_pack and config.origine_donnees is OrigineDonnees.REEL_GELE
        else OrigineDonnees.SYNTHETIQUE
    )

    if fenetre_max_bougies is not None:
        # Fenêtre glissante sur les bougies les plus RÉCENTES : garde la synthèse sous le seuil CDC
        # de 3 s sur un long historique. Aucun trou n'est créé : c'est une coupe de la série.
        bougies = bougies[-fenetre_max_bougies:]

    signal = calculer_signal_quantitatif(instrument_id, bougies, capital_virtuel)
    zone_validation, _ = separer_validation_et_hors_echantillon(bougies, taille_hors_echantillon)
    backtest = walk_forward_backtest(zone_validation, instrument_id, capital_virtuel=capital_virtuel)

    return SynthesePanneauRisque(
        instrument_id=instrument_id,
        origine_donnees=origine,
        libelle_origine=LIBELLE_ORIGINE[origine],
        signal=signal,
        sharpe=backtest.sharpe,
        drawdown_max=backtest.drawdown_max,
        taux_reussite=backtest.taux_reussite,
        nb_trades=backtest.nb_trades,
        nb_bougies_analysees=len(bougies),
        explication_taille_nulle=expliquer_taille_nulle(instrument_id, signal.risque),
        duree_calcul_secondes=round(time.perf_counter() - debut, 4),
    )
