"""Calcul des niveaux de stop-loss et take-profit D4."""


def calculer_niveaux(
    prix_entree: float, atr: float, multiplicateur_atr: float, ratio_risque_gain: float
) -> tuple[float, float, float]:
    """Retourne distance du stop, stop-loss et take-profit pour une position longue."""
    if prix_entree <= 0:
        raise ValueError("Le prix d'entrée doit être strictement positif.")
    if atr <= 0:
        raise ValueError("L'ATR doit être strictement positif.")
    if multiplicateur_atr <= 0:
        raise ValueError("Le multiplicateur ATR du stop doit être strictement positif.")
    if ratio_risque_gain <= 0:
        raise ValueError("Le ratio risque/gain doit être strictement positif.")
    distance = multiplicateur_atr * atr
    return distance, prix_entree - distance, prix_entree + ratio_risque_gain * distance
