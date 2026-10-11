\# DINIKA - ES Quant Data Pack v1.0



\## Objet



Ce pack contient le dataset officiel préparé par DINIKA DATA pour le moteur Quant.



Instrument :



ES - E-mini S\&P 500 Futures



Timeframe officiel :



Daily



Source principale :



Databento



\## Dataset officiel



Fichier :



dataset/ES\_quant\_daily\_v1.0.csv



Période :



2012-02-29 à 2026-09-13



Nombre de lignes :



4453



Nombre de colonnes :



36



Timezone :



UTC



SHA-256 :



23af73a8a6160b45ead19c53503bf5ef56b1a010a63535297eecbc4b1dbb83ac



Le dataset v1.0 est gelé et ne doit pas être modifié.



\## Contenu du pack



dataset/

&#x20;   Dataset officiel ES.



contract/

&#x20;   Contrat de données pour Quant.



quality/

&#x20;   Contrôles qualité, valeurs manquantes et gaps.



metadata/

&#x20;   Métadonnées instrument et dataset.



provenance/

&#x20;   Provenance et pipeline de préparation.



api/

&#x20;   Instructions d'accès pour Quant.



market/

&#x20;   Timeframe, horaires et conventions prix/volume.



fixtures/

&#x20;   Jeux de tests valides et volontairement invalides.



reproducibility/

&#x20;   Manifest et SHA-256 pour la reproductibilité.



sources/

&#x20;   Documentation des sources et licences.



\## Fichiers importants



Pour commencer :



1\. contract/DATA\_CONTRACT.md

2\. api/QUANT\_API.md

3\. dataset/ES\_quant\_daily\_v1.0.csv

4\. metadata/ES\_METADATA.json

5\. quality/QUALITY\_REPORT.json



\## Qualité



Résultats v1.0 :



\- doublons timestamp : 0

\- doublons timestamp + instrument : 0

\- OHLC invalides : 0

\- volumes négatifs : 0

\- Open Interest négatif : 0

\- ordre chronologique : valide

\- gaps calendaires > 3 jours : 3



Les gaps sont documentés dans quality/GAPS.json.



\## Valeurs manquantes



Les champs OHLCV obligatoires ne contiennent aucune valeur manquante.



Open Interest et Settlement peuvent contenir des valeurs manquantes.



Aucune imputation silencieuse n'est appliquée.



\## Utilisation



Quant doit utiliser le fichier :



dataset/ES\_quant\_daily\_v1.0.csv



Pour les règles de structure :



contract/DATA\_CONTRACT.md



Pour l'accès :



api/QUANT\_API.md



Pour la reproductibilité :



reproducibility/DATASET\_MANIFEST.json

reproducibility/SHA256SUMS.txt



\## Versioning



La version 1.0 est gelée.



Toute modification du dataset doit produire une nouvelle version.



Exemple :



v1.1



ou



v2.0



Le fichier v1.0 ne doit pas être remplacé silencieusement.

