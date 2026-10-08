---
name: syncpilot-persistence
description: Rendre les documents reçus accessibles durablement dans Work, contrôler leur relecture indépendante et bloquer toute fausse déclaration de Source de projet.
---

Candidate 0.6 : un contrat v5 avec `work_persistence` conserve les mêmes contrôles
que v4. Le chat Work réel vient de l'opération qualifiée, pas d'une session fixée
dans le contrat. Pour une réception Work → Codex, fournir `prepare --work-thread`
avec le chat Work qualifié séparément. Sans cible explicite, v5 ne promet aucune
persistance native. Voir `../syncpilot-decisions/references/ROUTING.md`.

# Disponibilité durable dans Work

Présenter la lecture du contrat comme « Lecture du contrat SyncPilot » dans les
messages et les titres d'activité configurables. `project-sync.json` et les
formats `PROJECT-SYNC` restent compatibles ; consigner un titre imposé par l'interface.

Lire le contrat v4, ses instructions et le mandat. Ne modifier aucune Source
canonique, permission ou installation pour contourner un blocage. Utiliser le
skill après le contrôle indépendant du transport documentaire ou des décisions.
CURRENT du miroir ne signifie pas que Work sait retrouver le document ensuite.

La cible vient de work_persistence : page-files ou project-sources, projet,
container_id et registre qualifiés. Pour page-files, container_id est l'ID exact
d'une Page existante. Lire cette Page et son guidage avant toute écriture. Le
projet déclaré doit avoir été qualifié extérieurement avec le propriétaire :
une Page personnelle ne prouve pas à elle seule son rattachement à un projet.

Pages est une dépendance optionnelle. Réutiliser les accès disponibles ; ne pas
installer, ouvrir un compte ou augmenter des accès sans mandat. write_page_reference
dépose un fichier dans les Files canoniques d'une Page ; cela ne prouve aucune
ingestion aux Sources natives d'un projet. Pour une cible project-sources sans
outil observable, afficher BLOCKED avec la cause et l'action manuelle requise.
Ne pas changer de cible ou passer par Drive pour faire disparaître ce blocage.

Lire [PROTOCOL.md](references/PROTOCOL.md). Le helper scripts/work_persistence.py
est hors réseau : il valide et produit des plans, pas des uploads. Ses observations
sont des entrées qualifiées par le pilote, pas des signatures d'identité.

1. Vérifier le paquet, la preuve et le reçu par les skills transport/décisions.
   Le binding VERIFIÉ vient de ce contrôle réel, jamais d'un paquet autoproclamé.
   Inventorier tous les documents du périmètre reçu, ainsi que les registres à
   publier lorsque la mission les affecte. Calculer leurs tailles/empreintes.
2. Préparer l'opération de persistance en conservant l'opération/nonce du transport.
   Avant toute écriture ou reprise, relire le registre, la Page et les vrais
   fichiers accessibles. Recherche partielle ou résultat incertain : collecter,
   sans uploader. Reçu disponible : contrôler et réutiliser.
3. Pour UPLOAD_ONCE, enregistrer UPLOAD_ATTEMPTED avant l'appel puis utiliser
   write_page_reference avec le fichier exact et la Page qualifiée. Conserver
   immédiatement la référence opaque retournée et son digest hors du canon.
   Timeout : inspecter Files/Library, aucun second upload aveugle. Seul un échec
   réellement confirmé not_committed peut résoudre l'incertitude.
4. Relire le fichier par read_page_reference et recalculer son empreinte depuis
   ses vrais octets. Un résultat opaque n'est jamais inventé depuis un nom.
   Relire la Page avant edit_page ; insérer le lien de fichier existant avec les
   gardes de séquence/hash, puis contrôler la présence du lien après sauvegarde.
   write_page_reference seul ne modifie pas le contenu de la Page.
5. Dans un nouveau contexte de lecture, retrouver le lien dans la Page et relire
   le fichier avec un nouvel appel. Produire la preuve persistante, liée à la
   cible, au contrat et aux preuves du transport. Le parent récupère cette preuve,
   contrôle son origine et refait sa propre relecture ; accept valide le résultat.
6. Enregistrer le résultat et les références dans le registre durable du contrat.
   Sauvegarder le pointeur qualifié avec contrôle avant/après, sans écraser une
   mise à jour concurrente. Le routage du projet doit désigner ce registre et la
   Page ; s'il manque et que l'accès n'est pas autorisé, afficher le blocage.
   Au démarrage suivant, vérifier le commit/périmètre attendu puis check avec de
   vrais nouveaux appels. Une preuve ancienne ne suffit pas à confirmer la fraîcheur.

Statuts explicites : RECEIVED_VERIFIED_PERSISTENCE_PENDING, WORK_PAGE_AVAILABLE,
PROJECT_SOURCE_AVAILABLE, BLOCKED. WORK_PAGE_AVAILABLE atteste des fichiers
liés et lisibles dans la Page qualifiée, jamais des Sources natives de projet.
Ne déclarer la mission terminée que pour la cible exigée, tous ses fichiers et
le routage vérifié. Une disponibilité Work n'atteste pas la complétude métier.
Les refus d'intégrité ou d'identité restent terminaux sur tous les canaux.
