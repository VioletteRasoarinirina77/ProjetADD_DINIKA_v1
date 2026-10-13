"""Conventions communes à D2 (batch ET incrémental) : une seule source de vérité.

Deux règles y sont définies, pour que les deux implémentations ne puissent plus diverger :

1. **Chauffe (warm-up)** : nombre minimal d'observations avant qu'un indicateur soit publié.
   Avant ce seuil la valeur reste ``NaN`` (batch) ou ``None`` (incrémental) : on n'invente
   jamais une valeur calculée sur un historique insuffisant.

   | Indicateur      | Observations requises | Pourquoi                                       |
   |-----------------|-----------------------|------------------------------------------------|
   | ``sma_20``      | période SMA           | moyenne de N clôtures                          |
   | ``ema_20``      | période EMA           | amorçage sur N clôtures                        |
   | ``rsi_14``      | période RSI + 1       | N variations de clôture exigent N + 1 clôtures |
   | ``macd``        | période lente         | EMA lente disponible                           |
   | ``macd_signal`` | lente + signal - 1    | EMA du MACD disponible                         |
   | ``atr_14``      | période ATR + 1       | N vrais ranges exigent la clôture précédente   |

2. **Cohérence avec le contrat** : les champs du contrat ``IndicateursTechniques`` et les colonnes
   du DataFrame portent la période dans leur nom (``sma_20``, ``rsi_14``...). Modifier une période
   dans la configuration sans changer ces noms produirait une colonne qui ment (une SMA-50 appelée
   ``sma_20``). ``verifier_periodes_contrat`` refuse ce cas : changer une période exige une nouvelle
   version du contrat (SemVer), pas une modification silencieuse.
"""

from config.instruments import ParametresIndicateurs

# Périodes nominales portées par les noms du contrat v1 (sma_20, ema_20, rsi_14, atr_14).
PERIODES_CONTRAT: dict[str, int] = {
    "periode_sma": 20,
    "periode_ema": 20,
    "periode_rsi": 14,
    "periode_atr": 14,
}


def observations_requises(parametres: ParametresIndicateurs) -> dict[str, int]:
    """Nombre minimal d'observations pour publier chaque indicateur (voir le tableau du module)."""
    return {
        "sma_20": parametres.periode_sma,
        "ema_20": parametres.periode_ema,
        "rsi_14": parametres.periode_rsi + 1,
        "macd": parametres.macd_lente,
        "macd_signal": parametres.macd_lente + parametres.macd_signal - 1,
        "atr_14": parametres.periode_atr + 1,
    }


def verifier_periodes_contrat(parametres: ParametresIndicateurs) -> None:
    """Refuse une configuration dont les périodes contredisent les noms du contrat v1."""
    ecarts = {
        nom: (getattr(parametres, nom), attendu)
        for nom, attendu in PERIODES_CONTRAT.items()
        if getattr(parametres, nom) != attendu
    }
    if ecarts:
        details = ", ".join(
            f"{nom}={valeur} (contrat : {attendu})" for nom, (valeur, attendu) in ecarts.items()
        )
        raise ValueError(
            f"Périodes incompatibles avec les noms du contrat v1 : {details}. "
            "Les colonnes sma_20/ema_20/rsi_14/atr_14 portent leur période dans leur nom : "
            "changer une période exige une nouvelle version du contrat d'interface."
        )