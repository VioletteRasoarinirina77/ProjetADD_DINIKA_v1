# D2 — Indicateurs techniques : processus complet, de la donnée au résultat

> **À quoi sert ce document.** Comprendre, expliquer et démontrer D2 sans lire tout le code.
> Chaque étape indique : l'**entrée**, le **fichier et la fonction**, le **traitement**, la **sortie** (avec sa forme),
> un **exemple réel** tiré du PACK ES, et la **commande de test** qui le prouve.
> Tous les chiffres ont été relevés sur le code actuel et le PACK ES v1.0 (4453 bougies).

**Critères du cahier des charges (CDC §5.2) pour D2 :** mise à jour d'un indicateur en moins de 5 s ;
calcul incrémental ; valeurs reproductibles et testées ; aucun paramètre codé en dur.

---

## 1. En une page

D2 transforme les bougies quotidiennes du contrat **ES** (E-mini S&P 500) en un tableau enrichi de six
indicateurs. D2 **ne décide ni d'acheter ni de vendre** : il fournit l'information aux étapes suivantes.

```text
PACK ES gelé (CSV)  →  Bougie (validées)  →  tableau OHLCV  →  tableau D2 (11 colonnes)  →  D3 / D4 / D7 / D8
   4453 lignes          4453 objets            4453 × 5            4453 × 11
```

| Question | Réponse |
|---|---|
| Quelle donnée ? | `fixtures/integration/pack_es_v1/dataset/ES_quant_daily_v1.0.csv` (2012-02-29 → 2026-09-13) |
| Qui la lit ? | `integration/pack_repository.py` puis `integration/charger_donnees_pack.py` |
| Qui calcule ? | `indicators/technical.py` (batch) et `indicators/incremental.py` (une bougie à la fois) |
| Quelles règles communes ? | `indicators/conventions.py` (chauffe + cohérence du contrat) |
| Quels paramètres ? | `config/instruments.py` (SMA 20, EMA 20, RSI 14, ATR 14, MACD 12/26/9) |
| Qu'est-ce qui sort ? | SMA-20, EMA-20, RSI-14, MACD, signal MACD, ATR-14 |
| Qui les utilise ? | D3 (SMA-20 → signal), D4 (ATR-14 → stop et taille), D7 (affichage), API |

---

## 2. Les fichiers

| Fichier | Rôle |
|---|---|
| `integration/pack_repository.py` | Accès contrôlé au PACK : intégrité SHA-256, qualité, trous, journalisation |
| `integration/charger_donnees_pack.py` | CSV → objets `Bougie` (valeur absente = `None`, jamais inventée) |
| `contracts/schemas.py` | `Bougie` (entrée) et `IndicateursTechniques` (sortie incrémentale) |
| `config/instruments.py` | Toutes les périodes : aucun paramètre en dur ailleurs |
| `indicators/technical.py` | **Batch** : tout l'historique d'un coup |
| `indicators/incremental.py` | **Incrémental** : met à jour l'état avec une nouvelle bougie |
| `indicators/conventions.py` | Règle de chauffe unique + garde de cohérence des noms du contrat |
| `services/quant_engine.py` | Assemble D2 + D4 pour la dernière bougie (utilisé par l'API et D7) |

---

## 3. Étape par étape

### Étape 1 — Charger et valider les données

| | |
|---|---|
| **Entrée** | le dossier du PACK (`fixtures/integration/pack_es_v1`) |
| **Fichier / fonction** | `PackDataRepository(...).candles_validees("ES")` |
| **Traitement** | 1) recalcul du SHA-256 du CSV et comparaison avec `DATASET_MANIFEST.json` ; en cas d'écart, arrêt (`ErreurIntegritePack`). 2) lecture de `QUALITY_REPORT.json` (OHLC invalides, doublons, volumes négatifs, ordre chronologique). 3) lecture de `GAPS.json` (informatif, non bloquant). 4) lecture du CSV et construction des `Bougie`. 5) tri chronologique. 6) écriture d'une ligne dans le journal d'audit (version + SHA-256) |
| **Sortie** | `list[Bougie]`, 4453 éléments |
| **Règles de validation d'une `Bougie`** | prix strictement positifs ; `high ≥ open, close, low` ; `low ≤ open, close, high` ; timestamp avec fuseau UTC |

Le CSV contient 36 colonnes ; **seules 10 sont lues** (`timestamp, source, instrument_id, open, high, low, close,
volume, open_interest, settlement_price`). Les indicateurs déjà présents dans le CSV (`sma_20`, `atr_14`…) sont
**ignorés** : D2 calcule lui-même, ce qui permet ensuite de recouper (décision D-003).

*Exemple réel — la première bougie :*

```text
ES | databento | 1D | 2012-02-29 | open 1197.90 | high 1202.93 | low 1185.02 | close 1189.61
volume 2 291 237 | open_interest 2 736 498 | settlement 1191.70
```

`source="databento"` est la **provenance** de la donnée, pas un appel à Databento : le projet lit le PACK gelé.

**Test :** `pytest tests/integration/test_pack_repository.py --no-cov -q` → **17 passed**

### Étape 2 — Convertir en tableau de calcul

| | |
|---|---|
| **Entrée** | `list[Bougie]` |
| **Fichier / fonction** | `indicators/technical.py` → `bougies_vers_dataframe()` |
| **Traitement** | tri par date, le timestamp devient l'index ; conservation de `open, high, low, close, volume` |
| **Sortie** | tableau pandas **4453 × 5**, index = date UTC |

`open_interest` et `settlement_price` ne sont pas repris : D2 n'en a pas besoin.

### Étape 3 — Calculer les indicateurs

| | |
|---|---|
| **Entrée** | le tableau OHLCV + l'identifiant `"ES"` (qui donne accès aux paramètres) |
| **Fichier / fonction** | `indicators/technical.py` → `ajouter_indicateurs(df, "ES")` (bibliothèque `pandas-ta`) |
| **Sortie** | tableau **4453 × 11** : `open, high, low, close, volume` + 6 colonnes ci-dessous |

| Colonne | Indicateur | Paramètre | Rôle dans le projet |
|---|---|---|---|
| `sma_20` | moyenne mobile simple | 20 | **pilote le signal d'entrée de D3** (croisement Close/SMA) |
| `ema_20` | moyenne mobile exponentielle | 20 | affichage (D7), API |
| `rsi_14` | indice de force relative | 14 | affichage (D7), API |
| `macd` | écart entre EMA 12 et EMA 26 | 12 / 26 | API |
| `macd_signal` | EMA 9 du MACD | 9 | API |
| `atr_14` | volatilité (vrai range moyen, lissage de Wilder) | 14 | **pilote le stop-loss, le take-profit et la taille (D4)** |

Seuls la SMA-20 et l'ATR-14 influencent une décision. Les autres sont calculés et exposés, mais la stratégie de
référence ne les utilise pas.

### Étape 4 — Gérer la période de chauffe

Un indicateur n'est **publié qu'après** un nombre minimal d'observations. Avant, la valeur reste **vide** (`NaN`
dans le tableau, `None` en incrémental). **Rien n'est inventé.** La règle est unique, définie dans
`indicators/conventions.py` et appliquée par les deux implémentations :

| Indicateur | Observations requises | Raison | Valeurs vides en début de série |
|---|---|---|---|
| `sma_20` | 20 | moyenne de 20 clôtures | 19 |
| `ema_20` | 20 | amorçage sur 20 clôtures | 19 |
| `rsi_14` | 15 | 14 variations exigent 15 clôtures | 14 |
| `macd` | 26 | EMA lente disponible | 25 |
| `macd_signal` | 34 | 26 + 9 − 1 | 33 |
| `atr_14` | 15 | 14 vrais ranges exigent la clôture précédente | 14 |

*Exemple réel :* le **15ᵉ jour** (2012-03-16) donne le premier ATR : **12,08**. Le **20ᵉ jour** (2012-03-22) donne la
première SMA : **1211,82** (pour un Close de 1229,94).

**Garde de cohérence du contrat.** Les colonnes `sma_20`, `ema_20`, `rsi_14`, `atr_14` portent leur période dans
leur nom. Si quelqu'un met `periode_sma = 50` dans la configuration, D2 **refuse** de calculer et explique qu'il
faut une nouvelle version du contrat d'interface (au lieu de produire une SMA-50 baptisée `sma_20`).

**Tests :** `pytest tests/indicators/test_conventions.py --no-cov -q` → **12 passed**

### Étape 5 — Résultat

Dernière bougie du PACK (**2026-09-13**) :

```text
Close 7615.5 | SMA20 7687.5125 | EMA20 7678.649388 | RSI14 43.448091
MACD −10.681751 | MACD signal 2.645870 | ATR14 61.652914
```

Ces valeurs sont calculées sur le PACK réel, jamais saisies dans le code. Elles sont vérifiées par un test.

**Test :** `pytest tests/indicators/test_d2_pack_es.py --no-cov -q` → **5 passed**

### Étape 6 — Sortie vers les autres étapes

```text
D2 ── sma_20 + close ─────► D3  signal d'entrée et backtest
   ├─ atr_14 ──────────────► D4  stop-loss, take-profit, taille entière de contrats
   └─ tout ────────────────► D7  graphiques et métriques ; API FastAPI (/signal)
```

---

## 4. Deux implémentations : batch et incrémental

| | Batch | Incrémental |
|---|---|---|
| Fichier | `indicators/technical.py` | `indicators/incremental.py` |
| Fonction | `ajouter_indicateurs(df, "ES")` | `mettre_a_jour(etat, bougie)` |
| Entrée | tout l'historique | un état + **une** nouvelle bougie |
| Sortie | tableau 4453 × 11 | `(nouvel_etat, IndicateursTechniques)` |
| Usage | D3, D8, D7, analyse historique | API temps réel : `GET /signal`, `POST /bougie` |
| Formules | `pandas-ta` | EMA standard ; lissage de Wilder (RSI, ATR) |
| Coût | proportionnel à l'historique | **constant** par bougie |

**Comparaison sur les 4453 bougies :**
- Les valeurs vides sont **exactement au même endroit** (même règle de chauffe).
- Pendant la chauffe, les valeurs diffèrent légèrement (jusqu'à 6 points sur l'EMA, 4,9 sur le MACD, 1 sur l'ATR)
  car l'amorçage n'est pas identique.
- Après **500 bougies**, l'écart est **inférieur à 1e-6** pour les six indicateurs : les deux calculs sont équivalents.

**Tests :**
`pytest tests/indicators/test_incremental.py --no-cov -q` → **8 passed**
(dont `test_cout_de_mise_a_jour_est_constant_pas_croissant`, qui justifie le critère « < 5 s »).

---

## 5. Commandes de test D2

> **Pourquoi `--no-cov` ?** Le projet impose une couverture globale de 75 %. En lançant seulement une partie des
> tests, la couverture totale est plus basse (66 % pour D2/D3 seuls) et la commande échouerait sur ce seuil, même si
> tous les tests passent. `--no-cov` désactive la mesure pour un lancement partiel. `-q` réduit l'affichage ;
> remplacez-le par `-v` pour voir le nom de chaque test (utile pour une démonstration).

| # | Ce qu'on vérifie | Commande | Résultat attendu |
|---|---|---|---|
| 1 | D2 sur le PACK réel : bougies, ordre chronologique, valeurs de la dernière bougie | `pytest tests/indicators/test_d2_pack_es.py --no-cov -q` | 5 passed |
| 2 | Calcul batch : création des colonnes, chauffe, risque | `pytest tests/indicators/test_technical.py --no-cov -q` | 18 passed |
| 3 | Disponibilité des indicateurs, signal quantitatif complet | `pytest tests/indicators/test_indicators.py --no-cov -q` | 9 passed |
| 4 | Calcul incrémental : convergence, coût constant | `pytest tests/indicators/test_incremental.py --no-cov -q` | 8 passed |
| 5 | Chauffe commune, convergence sur le PACK, garde du contrat | `pytest tests/indicators/test_conventions.py --no-cov -q` | 12 passed |
| 6 | Recoupement avec la Piste Data (SMA identique, EMA convergente, ATR et RSI corrélés) | `pytest tests/integration/test_pack_indicateurs_et_calendrier.py --no-cov -q` | 6 passed |
| 7 | Chargement du PACK : SHA-256, qualité, trous | `pytest tests/integration/test_pack_repository.py --no-cov -q` | 17 passed |
| 8 | **Tout D2 d'un coup** | `pytest tests/indicators --no-cov -q` | **52 passed** |

**Commandes ciblées utiles en démonstration :**

| But | Commande |
|---|---|
| Voir uniquement les tests de chauffe | `pytest tests/indicators/test_conventions.py -k chauffe --no-cov -v` (8 passed) |
| Montrer qu'un PACK modifié est refusé (SHA-256) | `pytest tests/integration/test_pack_repository.py::test_integrite_refuse_un_dataset_modifie --no-cov -v` |
| Voir le nom de tous les tests D2 | `pytest tests/indicators --no-cov -v` |
| Style du code D2 | `ruff check indicators tests/indicators` (« All checks passed! ») |
| Suite complète avec couverture | `pytest` (346 passed, couverture 99,38 %) |
| Couverture de D2/D3 seuls | `pytest tests/indicators tests/backtest tests/strategy --cov-fail-under=0` |

---

## 6. Preuve des exigences du CDC

| Exigence | Preuve | Commande |
|---|---|---|
| Calcul incrémental | `incremental.py` + tests de convergence | `pytest tests/indicators/test_incremental.py --no-cov -q` |
| Mise à jour < 5 s (coût constant) | `test_cout_de_mise_a_jour_est_constant_pas_croissant` | idem |
| Valeurs reproductibles et testées | `test_d2_es_resultats_derniere_bougie` (valeurs exactes du PACK) | `pytest tests/indicators/test_d2_pack_es.py --no-cov -q` |
| Aucun paramètre en dur | périodes dans `config/instruments.py` ; garde `verifier_periodes_contrat` | `pytest tests/indicators/test_conventions.py --no-cov -q` |
| Donnée figée et vérifiée | SHA-256 contrôlé avant tout calcul | `pytest tests/integration/test_pack_repository.py --no-cov -q` |

---

## 7. Questions probables du jury

**Pourquoi recalculer les indicateurs alors que le CSV en contient déjà ?**
Pour rester indépendant et pouvoir recouper. Résultat : la SMA est identique à la référence, l'EMA converge, et
l'ATR et le RSI sont fortement corrélés (0,98 et 0,87). L'écart vient du lissage : D2 utilise celui de Wilder, la
référence une moyenne simple. Le choix de convention est soumis à l'encadreur.

**Pourquoi deux implémentations ?**
Le batch sert l'historique et le backtest. L'incrémental traite une nouvelle bougie à coût constant, ce qui prépare le
temps réel. Les deux sont prouvées équivalentes après la chauffe.

**Que signifie une valeur vide au début ?**
L'historique est insuffisant. Le système ne remplace jamais une valeur manquante par une valeur inventée.

**Quels indicateurs servent vraiment à décider ?**
La SMA-20 (signal) et l'ATR-14 (stop et taille). Les autres sont informatifs.

---

## 8. Limites et points ouverts

- **Convention ATR/RSI** (décision D-003) : D2 utilise Wilder ; la référence du CSV utilise une moyenne simple.
  À faire valider par l'encadreur. Proposition : D2 reste la référence.
- **État incrémental en mémoire** : il est reconstruit depuis le PACK au premier appel après un redémarrage de l'API.
- **Daily uniquement** : le PACK v1.0 est quotidien ; l'intraday et le temps réel sont des évolutions futures.