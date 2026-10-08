---
name: syncpilot-codex
description: Préparer un paquet Git exact pour le contrat du projet et contrôler la preuve indépendante Work ; transport DC principal, Drive uniquement si DC indisponible.
---

# SyncPilot côté Codex

Présenter la lecture du contrat comme « Lecture du contrat SyncPilot » dans les
messages et les titres d'activité configurables. `project-sync.json` et les
formats `PROJECT-SYNC` restent compatibles ; consigner un titre imposé par l'interface.

Commencer par `../syncpilot-dc/references/FLOW.md`. Le pilote sélectionne et
qualifie le receveur, puis déclenche la réception dans le périmètre du mandat.
Réutiliser un receveur du projet disponible ; si aucun acteur existant ne convient,
créer `<nom ou alias humain du projet>-RECEVEUR` dans le projet authentifié,
en réutilisant l'autorisation permanente qualifiée sans nouvelle question.
Pour Work → Codex, outils natifs disponibles ou point d'entrée public du CLI
officiel via DC constituent le canal normal ; une restriction humaine explicite
au canal natif reste respectée. Ne pas transmettre à un
second Codex des sources canoniques déjà accessibles au Codex courant.
Grouper requirement/build/prepare avec le helper batch ; aucune approbation
supplémentaire pour une étape ou reprise déjà couverte. Sans capacité de
déclenchement réelle, signaler le blocage précis ; ne pas promettre un réveil.

En contrat v5, lire `../syncpilot-decisions/references/ROUTING.md` et rechercher
les opérations signalées dans le registre durable du projet au démarrage/reprise.
Le Codex qualifié peut reprendre une contribution Work dans une autre conversation
que l'ancienne session contractuelle. Garantir un seul acteur et utiliser
`select-receiver` avant receive/check d'une inbox. Vérifier la preuve complète
et le mandat avant toute transcription documentaire dans les sources canoniques.

Avec un contrat v4, utiliser ../syncpilot-persistence/SKILL.md après le contrôle
du transport. Exiger la preuve de disponibilité pour la cible prévue et une
relecture indépendante ; CURRENT seul ne signifie pas synchronisation terminée.
Lire le registre qualifié et revalider les vrais fichiers au démarrage suivant.
Sans outil pour la cible exigée : BLOCKED.

Avec un contrat v3, lire d'abord le registre qualifié des décisions selon
`../syncpilot-decisions/SKILL.md` : prendre en compte les validations Work,
présenter leurs conséquences et tout conflit avant l'implémentation. Toute
décision validée dans Codex, même oralement, suit le circuit inverse vers Work.
La capture documentaire ne réapplique aucune décision dans Git automatiquement.
Si Git n'existe pas encore, utiliser uniquement ce circuit de décisions.

Lire AGENTS.md, le manuel actif et le contrat propre au projet. Afficher mission,
dépôt réel, remote, branche, worktree, HEAD complet, Git, diff borné, propriété,
autorité, phase, risques, contrôles et checkpoint ; réafficher en reprise Remote.
Pour le paquet Git décrit ci-dessous, exiger un worktree propre et un HEAD exact ; arrêter si des
changements étrangers ou incertains sont présents. Une mission technique suit
`../syncpilot-dc/references/MISSION.md` et peut qualifier un diff exactement
attribué sans le transformer en paquet Git ou en décisions validées. Aucun
stash, reset, commit, bascule de branche ou nettoyage automatique pour satisfaire
le générateur. Git reste canon ; aucun retour Work n'y est intégré automatiquement.

Utiliser Python 3.10+ et `scripts/project_sync.py` à son chemin absolu.
Le contrat à HEAD doit être versionné, le HEAD exact sur la branche configurée.
Sources : documents UTF-8 explicites, paquet complet seulement. L'exigence
indépendante est liée au commit, contrat, sources, domaines et destination :

    python SCRIPT requirement --repository DEPOT --commit SHA40 --domain DOMAINE --authority MANDAT --output EXIGENCE
    python SCRIPT build --repository DEPOT --requirement EXIGENCE --output PAQUET.zip --carrier PORTEUR.json

Les sorties sont hors du canon ou dans un dossier déjà ignoré, jamais écrasées.
Le porteur Base64 conserve les octets du ZIP ; ne pas le recréer en générant du
texte. La source est UNKNOWN sans attestation humaine préexistante liée au hash
canonique de l'exigence, avec approved_by, authority, missing_validated_items=[].
Intégrité et complétude métier sont deux contrôles distincts.

Appliquer `../syncpilot-dc/SKILL.md` pour la qualification, l'opération, le
transport, le secours et la reprise. La passation comprend les identités,
opération/nonce, exigence, commit, périmètre, localisateurs, tailles/hashes,
référence externe du chat qualifié et emplacement de retour. Aucun envoi à
un autre chat sans autorisation humaine explicite pour CE destinataire.

Work récupère les vrais octets puis exécute receive et check indépendamment.
Codex n'exécute jamais receive pour fabriquer une preuve Work. Après fin réelle
du tour Work, Codex relit reçu et preuve depuis la destination, recalcule leurs
hashes et qualifie l'origine dans le même projet/chat avant confirm puis accept.
Un JSON seul ne signe pas une identité ; les observations viennent des outils
authentifiés, pas des annonces des documents. Sans origine qualifiée : UNKNOWN.

    python SCRIPT accept --input PORTEUR --requirement EXIGENCE --proof PREUVE --evidence ORIGINE

L'artefact doit être le même objet exact que celui relu par Work. CURRENT est
borné à ce commit, paquet, domaine et destination ; ni fraîcheur d'un HEAD
ultérieur, ni validation métier, ni ingestion automatique en Sources Work.
Rapport court : résultat, contrôles, difficultés, réserves, fichiers/commits,
travail évitable, RETEX et suite. Sources modifiées pour Work : signaler
SYNC WORK REQUIS avec commit/périmètre. Après 2–3 essais sans progrès, test
discriminant ; aucune attente active d'une dépendance externe inchangée.
