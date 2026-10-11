"""Calcul des limites d'exposition D4."""

import math


def limiter_position_par_exposition(
    nombre_contrats: int,
    prix_entree: float,
    multiplicateur_contrat: float,
    capital: float,
    exposition_max_pourcentage_capital: float | None,
) -> tuple[int, float | None, bool]:
    """Applique une limite notionnelle optionnelle et retourne (taille, plafond, limitée)."""
    if exposition_max_pourcentage_capital is None:
        return nombre_contrats, None, False
    plafond = capital * exposition_max_pourcentage_capital / 100.0
    valeur_contrat = prix_entree * multiplicateur_contrat
    if valeur_contrat <= 0:
        return 0, plafond, True
    limite = math.floor(plafond / valeur_contrat)
    return min(nombre_contrats, limite), plafond, limite < nombre_contrats
