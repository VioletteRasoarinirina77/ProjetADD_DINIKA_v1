"""Vérificateur de conformité au contrat d'interface.

À DONNER À HARIMAMY (et Oly si pertinent) pour qu'elle puisse vérifier,
DE SON CÔTÉ et QUAND ELLE VEUT, que son flux de Bougies respecte le contrat
attendu par la Piste Quant — sans attendre le jour de l'intégration (S8-S9)
pour découvrir un champ manquant ou mal typé.

Usage :
    python -m integration.verifier_contrat chemin/vers/bougies.json
    python -m integration.verifier_contrat --url https://piste-data-api/bougies/GOLD

Principe : ce script réutilise LE MÊME schéma Pydantic (Bougie) que celui
utilisé en interne par toute la Piste Quant — donc "passe ce script" veut
dire EXACTEMENT "sera accepté par indicators/technical.py, backtest/,
paper_trading/, et l'API main.py", pas une approximation.
"""

import argparse
import json
import sys

import httpx
from pydantic import ValidationError

from contracts.schemas import Bougie


def verifier_liste_de_bougies(donnees: list[dict]) -> tuple[int, list[dict]]:
    """Valide chaque élément contre le schéma Bougie. Renvoie (nb_valides, erreurs).

    plutôt que de s'arrêter à la première erreur — utile pour voir d'un coup
    TOUS les problèmes d'un flux, pas un par un à chaque relance.
    """
    nb_valides = 0
    erreurs = []

    for i, element in enumerate(donnees):
        try:
            Bougie(**element)
            nb_valides += 1
        except ValidationError as erreur:
            erreurs.append({"index": i, "donnee": element, "erreurs": erreur.errors()})

    return nb_valides, erreurs


def _afficher_rapport(nb_valides: int, total: int, erreurs: list[dict]) -> None:
    print(f"\n{'=' * 60}")
    print(f"RÉSULTAT : {nb_valides}/{total} bougies conformes au contrat Bougie")
    print(f"{'=' * 60}\n")

    if not erreurs:
        print("✅ Tout le flux est conforme — prêt pour l'intégration avec la Piste Quant.")
        return

    print(f"❌ {len(erreurs)} bougie(s) NON conforme(s) :\n")
    for erreur in erreurs[:10]:  # limite l'affichage pour rester lisible sur un gros flux
        print(f"  Bougie #{erreur['index']} :")
        for detail in erreur["erreurs"]:
            champ = ".".join(str(p) for p in detail["loc"])
            print(f"    - champ '{champ}' : {detail['msg']}")
        print()

    if len(erreurs) > 10:
        print(f"  ... et {len(erreurs) - 10} autre(s) erreur(s) non affichée(s).\n")

    print("Corrige ces champs AVANT le jour de l'intégration (S8-S9) pour éviter")
    print("un choc de dernière minute — ce script peut être relancé autant de fois")
    print("que nécessaire, il ne modifie jamais tes données.")


def main() -> None:
    """Point d'entrée CLI : lit un fichier ou une URL, vérifie contre le schéma Bougie."""
    parser = argparse.ArgumentParser(
        description="Vérifie qu'un flux de Bougies respecte le contrat d'interface de la Piste Quant."
    )
    groupe = parser.add_mutually_exclusive_group(required=True)
    groupe.add_argument(
        "fichier", nargs="?", help="Chemin vers un fichier JSON contenant une liste de Bougies"
    )
    groupe.add_argument("--url", help="URL renvoyant une liste de Bougies au format JSON")
    args = parser.parse_args()

    if args.url:
        reponse = httpx.get(args.url, timeout=10.0)
        reponse.raise_for_status()
        donnees = reponse.json()
    else:
        with open(args.fichier, encoding="utf-8") as f:
            donnees = json.load(f)

    if not isinstance(donnees, list):
        print("❌ Le JSON fourni doit être une LISTE de bougies (même avec une seule bougie).")
        sys.exit(1)

    nb_valides, erreurs = verifier_liste_de_bougies(donnees)
    _afficher_rapport(nb_valides, len(donnees), erreurs)
    sys.exit(0 if not erreurs else 1)


if __name__ == "__main__":
    main()
