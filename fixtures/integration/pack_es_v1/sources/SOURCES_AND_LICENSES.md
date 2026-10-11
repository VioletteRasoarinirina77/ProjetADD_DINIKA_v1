\# DINIKA - Sources et licences



Version du pack : 1.0



\## 1. Source principale des données de marché



Fournisseur :

Databento



Dataset :

GLBX.MDP3



Instrument :

ES - E-mini S\&P 500 Futures



Utilisation dans DINIKA :

Source principale des données historiques OHLCV et des statistiques disponibles.



Documentation officielle Databento :

https://databento.com/docs



Documentation API historique :

https://databento.com/docs/api-reference-historical



Guide de démarrage :

https://databento.com/docs/quickstart



\## 2. Accès aux données Databento



L'accès aux données historiques Databento est effectué via le service Historical de Databento.



Le projet DINIKA utilise une clé API Databento stockée en dehors du code source.



La clé API ne doit jamais être incluse dans le ZIP Quant.



Le dataset v1.0 déjà extrait et gelé est fourni dans :



dataset/ES\_quant\_daily\_v1.0.csv



\## 3. Conditions d'utilisation



Les conditions applicables dépendent notamment du dataset, du marché concerné et du type d'utilisation.



Avant toute redistribution publique ou utilisation commerciale, les conditions et licences applicables doivent être vérifiées auprès de Databento et, lorsque nécessaire, auprès de la place de marché concernée.



Le présent pack est destiné au travail interne du projet DINIKA et à la recherche académique associée.



Il ne constitue pas une autorisation de redistribution publique des données de marché.



\## 4. CME Group



CME Group est utilisé dans DINIKA comme source officielle de référence pour les informations contractuelles du produit ES.



CME est notamment utilisé pour :



\- identification du produit ;

\- multiplicateur ;

\- tick minimum ;

\- valeur du tick ;

\- cycle des contrats ;

\- échéances ;

\- horaires de marché ;

\- informations contractuelles.



CME n'est pas la source principale des OHLCV historiques du dataset Quant v1.0.



Documentation officielle CME :

https://www.cmegroup.com/



Centre des politiques de données de marché :

https://www.cmegroup.com/market-data/license-data/market-data-policy-education-center.html



Information License Agreement :

https://www.cmegroup.com/market-data/files/information-license-agreement-ila-guide.pdf



\## 5. Restrictions importantes



Les données de marché CME sont soumises à des droits et conditions d'utilisation.



Le fait qu'une donnée soit techniquement accessible ne signifie pas qu'elle peut être librement redistribuée.



Toute redistribution externe, utilisation commerciale, utilisation non-display ou intégration dans un produit destiné à des utilisateurs externes doit faire l'objet d'une vérification des licences applicables.



\## 6. Dataset gelé DINIKA



Le fichier :



dataset/ES\_quant\_daily\_v1.0.csv



est une extraction préparée pour le projet DINIKA.



SHA-256 :



23af73a8a6160b45ead19c53503bf5ef56b1a010a63535297eecbc4b1dbb83ac



Le fichier v1.0 est gelé.



Toute modification doit produire une nouvelle version.



\## 7. Références complémentaires



Databento Data Usage :

https://databento.com/docs/portal/data-usage



Databento Historical API :

https://databento.com/docs/api-reference-historical



CME Information Policies :

https://www.cmegroup.com/market-data/license-data/information-policies.html



\## 8. Règle pour le projet DINIKA



Pour reproduire les résultats de la thèse :



1\. utiliser le dataset gelé v1.0 ;

2\. vérifier son SHA-256 ;

3\. respecter DATA\_CONTRACT.md ;

4\. ne pas modifier silencieusement le CSV ;

5\. créer une nouvelle version en cas de modification ;

6\. ne pas redistribuer publiquement les données brutes sans avoir vérifié les droits applicables.

