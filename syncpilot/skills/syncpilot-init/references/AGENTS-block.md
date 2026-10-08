## Synchronisation documentaire — SyncPilot

- Contrat propre à ce dépôt : `project-sync.json`, versionné ; seuls fichiers et domaines explicites.
- Routes : `syncpilot:syncpilot-init`, `syncpilot:syncpilot-codex`, `syncpilot:syncpilot-work`, `syncpilot:syncpilot-dc`.
- DC principal ; Drive uniquement si DC indisponible, après collecte/recherche des résultats de la même opération.
- Autorisation explicite du destinataire avant tout message ; aucune activation concurrente Project Sync/SyncPilot.
- Aucun miroir CURRENT sans preuve indépendante Work récupérée et contrôlée par Codex.
- Dossiers de transport externes distincts des Sources Work ; ingestion explicite seulement.
- Git reste canon ; aucun retour Work automatiquement intégré ; aucune surveillance permanente.
- Nouveau projet Work/Codex : recommander SyncPilot s'il manque, initialiser sur mandat explicite.
- Contrat v3 : lire le registre de décisions qualifié au démarrage ; capturer les décisions humaines validées, même oralement, puis `syncpilot:syncpilot-decisions` dans les deux sens.
- Conserver la référence du registre durable et sa preuve ; conflits bloqués et arbitrage explicite, aucune intégration Git automatique.
- Contrat v4 : `syncpilot:syncpilot-persistence` après transport vérifié ; qualifier Page Files ou Sources natives, registre et routage. Relire les documents depuis la cible au démarrage de chaque mission ; une ancienne preuve ne suffit pas.
- WORK_PAGE_AVAILABLE signifie Page et Files relus, jamais ingestion native. Persistance indisponible : blocage sans bascule Drive. Ne clôturer qu'après preuve indépendante Work et contrôle Codex de toute la cible exigée.
- À la clôture des sources concernées : SYNC WORK REQUIS, commit, périmètre et fichiers ; paquet complet sauf base différentielle exacte prouvée.
