"""Paper trading / simulation (D8).

IMPORTANT : ce module ne modifie AUCUN fichier de D2 (indicators/technical.py),
D3 (backtest/walk_forward.py) ou D4 — il les RÉUTILISE tels quels. Ce que ce
module ajoute : le PnL en DOLLARS, la courbe de capital, le journal horodaté.

CORRECTION (validation hors-échantillon) : la première version de ce module
rejouait la stratégie sur LA MÊME fixture que celle utilisée pour valider D3
(walk-forward) — ce n'était pas un vrai hors-échantillon, juste un rejeu de
données déjà vues. Ce module découpe maintenant l'historique en 2 zones
ÉTANCHES et CHRONOLOGIQUES :

  [--------- zone_validation (utilisée par D3) ---------][--- zone_hors_echantillon (D8) ---]
   la stratégie est calibrée/testée ici, en walk-forward     jamais vue par D3 : c'est ici que
                                                               D8 doit prouver qu'elle marche
                                                               "en avant", pas seulement sur le
                                                               passé qui a servi à la valider.

Les indicateurs restent calculés sur TOUT l'historique (nécessaire pour leur
"chauffe" — SMA-20 a besoin de 20 bougies avant, etc. — sans que ça viole la
règle anti-look-ahead : un indicateur causal reste causal, peu importe où on
commence à EXÉCUTER des trades). Seule l'OUVERTURE de nouveaux trades est
restreinte à la zone hors-échantillon.

Critère du CDC rappelé : validation hors-échantillon sur ≥ 2 instruments,
aucun ordre réel — ce module ne fait jamais qu'une simulation en mémoire.
"""

from datetime import datetime

from pydantic import BaseModel

from backtest.walk_forward import calibrer_multiplicateur_atr, simuler_trades
from config.instruments import obtenir_config, resoudre_capital_virtuel
from contracts.schemas import Bougie
from indicators.technical import ajouter_indicateurs, bougies_vers_dataframe
from risk.position_sizing import calculer_risque

CAPITAL_INITIAL_DEFAUT = 10_000.0
TAILLE_HORS_ECHANTILLON_DEFAUT = 30  # nb de bougies les plus récentes, réservées à D8


class JournalTrade(BaseModel):
    """Une ligne du journal horodaté exigé par le CDC pour D8."""

    instrument_id: str
    entree_ts: datetime
    sortie_ts: datetime
    prix_entree: float
    prix_sortie: float
    taille_position: float
    pnl_dollars: float
    capital_apres: float


class ResultatPaperTrading(BaseModel):
    """Résultat complet d'une simulation D8 : journal horodaté, courbe de capital, capital final."""

    instrument_id: str
    capital_initial: float
    capital_final: float
    journal: list[JournalTrade]
    courbe_capital: list[float]  # capital après chaque trade (le point 0 = capital de départ)
    debut_zone_hors_echantillon: datetime | None = None  # None = pas de découpage (voir avertissement)
    # Multiplicateur ATR-stop réellement utilisé. En mode hors-échantillon, c'est
    # la valeur calibrée par D3 sur la zone de validation (point de revue 11) ;
    # None = ancienne fonction, qui utilise la configuration par défaut.
    multiplicateur_atr_utilise: float | None = None


def separer_validation_et_hors_echantillon(
    bougies: list[Bougie], taille_hors_echantillon: int
) -> tuple[list[Bougie], list[Bougie]]:
    """Découpe l'historique en 2 zones étanches, dans l'ORDRE CHRONOLOGIQUE :.

    la zone hors-échantillon est toujours la partie la PLUS RÉCENTE (on valide
    sur le passé, on simule "en avant" sur ce qui vient après — jamais l'inverse).
    """
    bougies_triees = sorted(bougies, key=lambda b: b.timestamp)
    if taille_hors_echantillon >= len(bougies_triees):
        raise ValueError(
            f"taille_hors_echantillon ({taille_hors_echantillon}) doit être strictement "
            f"inférieure au nombre total de bougies ({len(bougies_triees)})."
        )
    zone_validation = bougies_triees[:-taille_hors_echantillon]
    zone_hors_echantillon = bougies_triees[-taille_hors_echantillon:]
    return zone_validation, zone_hors_echantillon



def _atr_au_moment_de_l_entree(df, entree_ts) -> float | None:
    """Retrouve l'ATR utilisé par simuler_trades() (D3) au moment de CE trade,.

    sans dupliquer sa logique : c'est l'ATR de la bougie juste AVANT l'entrée.
    """
    position = df.index.get_loc(entree_ts)
    if position == 0:
        return None
    valeur = df.iloc[position - 1]["atr_14"]
    return None if valeur is None else float(valeur)


def _construire_journal(
    trades_en_points: list[dict],
    df: object,
    instrument_id: str,
    capital_initial: float,
    multiplicateur_atr_stop_override: float | None = None,
) -> ResultatPaperTrading:
    """Logique commune : traduit une liste de trades (en points) en journal.

    horodaté + courbe de capital (en dollars). Partagée par les 2 fonctions
    publiques ci-dessous pour ne jamais dupliquer cette traduction.
    """
    config = obtenir_config(instrument_id)
    capital = capital_initial
    courbe_capital = [capital]
    journal: list[JournalTrade] = []

    for trade in trades_en_points:
        atr_entree = _atr_au_moment_de_l_entree(df, trade["entree_ts"])
        risque = calculer_risque(
            trade["prix_entree"],
            atr_entree,
            instrument_id,
            capital,
            multiplicateur_atr_stop_override=multiplicateur_atr_stop_override,
        )
        taille = risque.taille_position_recommandee

        pnl_dollars = trade["pnl_points"] * config.multiplicateur_contrat * taille
        capital += pnl_dollars
        courbe_capital.append(capital)

        journal.append(
            JournalTrade(
                instrument_id=instrument_id,
                entree_ts=trade["entree_ts"],
                sortie_ts=trade["sortie_ts"],
                prix_entree=trade["prix_entree"],
                prix_sortie=trade["prix_sortie"],
                taille_position=round(taille, 4),
                pnl_dollars=round(pnl_dollars, 2),
                capital_apres=round(capital, 2),
            )
        )

    return ResultatPaperTrading(
        instrument_id=instrument_id,
        capital_initial=capital_initial,
        capital_final=round(capital, 2),
        journal=journal,
        courbe_capital=courbe_capital,
        multiplicateur_atr_utilise=multiplicateur_atr_stop_override,
    )



def simuler_paper_trading_hors_echantillon(
    bougies_historique_complet: list[Bougie],
    instrument_id: str,
    taille_hors_echantillon: int = TAILLE_HORS_ECHANTILLON_DEFAUT,
    capital_initial: float | None = None,
) -> ResultatPaperTrading:
    """VRAIE version D8 : ne simule que sur la zone hors-échantillon, jamais.

    vue par walk_forward_backtest() (D3). C'est la fonction à utiliser pour
    respecter l'exigence CDC "validation hors-échantillon".
    """
    capital_initial = resoudre_capital_virtuel(instrument_id, capital_initial)
    zone_validation, zone_hors_echantillon = separer_validation_et_hors_echantillon(
        bougies_historique_complet, taille_hors_echantillon
    )

    # Les indicateurs ont besoin de tout l'historique pour "chauffer" (SMA-20, MACD...),
    # mais restent causaux -- aucune fuite d'info du futur, même en gardant le contexte.
    df_complet = ajouter_indicateurs(
    bougies_vers_dataframe(bougies_historique_complet),
    instrument_id,
    )
    debut_hors_echantillon = zone_hors_echantillon[0].timestamp
    df_validation = df_complet.loc[df_complet.index < debut_hors_echantillon]
    df_hors_echantillon = df_complet.loc[df_complet.index >= debut_hors_echantillon]

    # Point 11 : le paramètre est calibré par D3 UNIQUEMENT sur la zone de
    # validation (jamais sur la zone hors-échantillon), puis appliqué tel quel.
    k_calibre = calibrer_multiplicateur_atr(df_validation, instrument_id, capital_initial)

    trades_en_points = simuler_trades(
        df_hors_echantillon, instrument_id, capital_initial, k_calibre
    )
    resultat = _construire_journal(
        trades_en_points, df_complet, instrument_id, capital_initial, k_calibre
    )
    resultat.debut_zone_hors_echantillon = debut_hors_echantillon

    # Preuve que zone_validation n'a servi qu'à D3 : sa dernière bougie précède
    # strictement la première de la zone hors-échantillon (aucun chevauchement).
    assert zone_validation[-1].timestamp < zone_hors_echantillon[0].timestamp
    return resultat


def simuler_paper_trading(
    bougies: list[Bougie],
    instrument_id: str,
    capital_initial: float | None = None,
) -> ResultatPaperTrading:
    """ANCIENNE version, CONSERVÉE pour compatibilité (ex. le panneau D7 déjà.

    livré) mais À ÉVITER pour prouver une performance : elle rejoue les MÊMES
    données que celles utilisées pour D3, donc n'est PAS un vrai hors-échantillon.
    Préférer simuler_paper_trading_hors_echantillon() pour toute validation.
    """
    capital_initial = resoudre_capital_virtuel(instrument_id, capital_initial)
    df = ajouter_indicateurs(
    bougies_vers_dataframe(bougies),
    instrument_id,
)
    trades_en_points = simuler_trades(df, instrument_id, capital_initial)
    return _construire_journal(trades_en_points, df, instrument_id, capital_initial)


if __name__ == "__main__":
    import json
    from pathlib import Path

    chemin = Path(__file__).parent.parent / "fixtures" / "backtest/bougies_gold_150h.json"
    with open(chemin) as f:
        donnees = json.load(f)
    bougies = [Bougie(**d) for d in donnees]

    resultat = simuler_paper_trading_hors_echantillon(bougies, "GOLD", taille_hors_echantillon=30)
    print(resultat.model_dump_json(indent=2))
