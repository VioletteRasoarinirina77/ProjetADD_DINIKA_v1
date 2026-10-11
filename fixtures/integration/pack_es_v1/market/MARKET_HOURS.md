\# DINIKA - Horaires et sessions de marché



Version : 1.0

Instrument : ES - E-mini S\&P 500 Futures

Marché : CME Globex



\## 1. Référence de session



La référence contractuelle CME utilisée par DINIKA indique une session :



Dimanche 18:00 ET

à

Vendredi 17:00 ET



avec une période quotidienne de maintenance :



17:00 ET à 18:00 ET



Timezone de référence du marché :



America/New\_York



\## 2. Convention du dataset



Les timestamps du dataset Quant v1.0 sont stockés en :



UTC



et apparaissent sous la forme :



YYYY-MM-DD 00:00:00+00:00



Ce timestamp est la convention temporelle de stockage du dataset.



Il ne doit PAS être interprété comme :



\- l'heure d'ouverture CME ;

\- l'heure de clôture CME ;

\- une heure de transaction précise.



\## 3. Jours disponibles



Le dataset peut contenir des timestamps correspondant au dimanche.



Il ne faut donc pas appliquer automatiquement une règle "lundi-vendredi uniquement" au dataset v1.0.



\## 4. Gaps



Les gaps calendaires identifiés sont documentés dans :



quality/GAPS.json



Ils ne sont pas automatiquement considérés comme des erreurs.



\## 5. Conversion temporelle



Pour les traitements Quant :



\- conserver le timestamp UTC ;

\- ne pas supprimer les observations du dimanche uniquement en raison du jour de semaine ;

\- utiliser America/New\_York uniquement lorsqu'une analyse liée aux horaires CME est nécessaire.

