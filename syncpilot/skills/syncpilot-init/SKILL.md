---
name: syncpilot-init
description: Configurer SyncPilot sur demande explicite ; sources et destination du projet, DC principal, Drive seulement si DC indisponible, migration contrôlée.
---

# Configurer SyncPilot

Présenter la lecture du contrat comme « Lecture du contrat SyncPilot » dans les
messages et les titres d'activité configurables. `project-sync.json` et les
formats `PROJECT-SYNC` restent compatibles ; consigner un titre imposé par l'interface.

Candidate 0.6 : préférer le contrat v5 pour un nouveau projet et préparer
explicitement `decision_sync.py migrate-routing` pour un contrat v3/v4 existant.
Le v5 conserve projets, sources, accès, registres et éventuelle persistance,
mais retire les sessions fixes des participants. Lire
`../syncpilot-decisions/references/ROUTING.md` ; qualifier une inbox et son pointeur
durable sans inventer de réveil automatique. Aucun contrat de production ne migre
par le chargement de ce skill. `references/project-sync-v5.example.json` est un
template, pas une observation ni une autorisation.

En 0.5, les contrats v1/v2/v3 restent compatibles. Pour exiger une disponibilité
durable dans Work, qualifier une cible et un registre puis préparer explicitement
le contrat v4 `references/project-sync-v4.example.json`. Une Page avec ses Files
n'est pas une Source native du projet : préciser le type réellement disponible.
Le skill `../syncpilot-persistence/SKILL.md` contrôle cette étape après réception.
Ne pas inscrire une Page personnelle comme destination d'un projet sans vérifier
son rattachement et ses accès. Sans adaptateur observable de Sources natives,
la publication demandée dans ces Sources reste bloquée.

Lire AGENTS.md et le manuel actif. Afficher le préflight complet et arrêter avant
écriture si des travaux étrangers ou de propriétaire incertain sont présents.
Un protocole canonique spécifique reste prioritaire jusqu'à migration autorisée.

Le contrat reste `project-sync.json` pour préserver les routages et paquets existants.
Les versions 1 et 2 restent lisibles, sans migration implicite. Pour un nouveau
projet Work/Codex, recommander SyncPilot s'il manque ; ne pas installer sans mandat.
Partir du contrat v3 pour le transport et les décisions, ou du v4 avec une cible
durable qualifiée, dans `references/project-sync-v3.example.json` ou
`references/project-sync-v4.example.json`, et remplacer
toutes les valeurs de démonstration depuis des observations authentifiées :
remote exact, branche, projet Work, domaines et fichiers documentaires relatifs
explicites, device/racine/compte DC, dossier/compte Drive. Aucun compte, chemin,
machine ou projet d'une autre mission ne doit être repris.

Déclarer les deux participants, leurs sources de validations et registres durables.
Un projet créé dans Work avant Git peut laisser repository et reference_branch
à null : seules les décisions sont alors synchronisables. Qualifier les décisions
initiales avec `../syncpilot-decisions/SKILL.md`. Lors de la création autorisée du
dépôt, configurer remote et branche ensemble après contrôle. Une recommandation
globale quand le plugin est absent exige aussi une règle de démarrage dans le
manuel ou les instructions du projet ; ce plugin ne peut pas se charger lui-même.

DC est principal. Drive est uniquement un secours lorsque DC est indisponible,
après recherche des résultats sur les canaux configurés. Un échec de données,
d'intégrité ou d'identité n'est jamais un motif de bascule. Lire
`../../MIGRATION.md` avant toute migration. Le helper `syncpilot_transport.py
migrate` écrit une nouvelle proposition, conserve les paramètres identiques
et refuse les conversions qui perdraient une configuration existante.

Ajouter seulement le bloc attribuable `references/AGENTS-block.md`, vérifier
les paramètres et le contrat, puis le versionner uniquement sous une phase Git
autorisée. Initialiser ne lance aucun transfert, commit, push ou message.
L'accès à une racine DC ou Drive ne prouve pas son ingestion en Sources Work.
Clôture : fichiers, contrôles, réserves et étape suivante.
