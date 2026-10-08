# Déclenchement Work → Codex — candidate 0.6.4

Ce circuit sert une synchronisation réellement demandée. Un commit documentaire
local déjà autorisé se fait directement sur le canon accessible via DC ; il ne
doit pas être détourné en passation.

Présenter la lecture du contrat comme « Lecture du contrat SyncPilot » dans le
message et le titre d'activité configurable. `project-sync.json` et les formats
`PROJECT-SYNC` restent compatibles ; un titre de lecture ne qualifie pas le
plugin actif. Consigner un titre imposé par l'interface et sa version réellement chargée.

Pour une mission technique, appliquer [MISSION.md](MISSION.md) et son point
d'entrée public réception/collecte/confirmation. Ne pas importer la classe
`Rpc` de ce bridge ni appeler thread/resume/turn/start depuis un relais personnalisé.
Le reçu de mission reste typé et ne devient ni VERIFIED Decisions ni CURRENT.
Les commandes Decisions documentées ci-dessous gardent leur protocole propre.

## Capacité et autorité

Utiliser d'abord l'outil de message de l'application propriétaire s'il est exposé.
Sinon Work peut, par DC, lancer `syncpilot_codex_bridge.py` de confiance avec le
CLI officiel Codex déjà installé sur le device qualifié. Ce CLI doit être déjà
authentifié. Le CLI officiel via DC appartient au canal normal SyncPilot ;
l'absence d'outil natif dans Work ne suffit pas à conclure à une impossibilité.
Une restriction humaine explicite au canal natif reste respectée. Drive est
réservé à une indisponibilité DC réelle, jamais à un défaut de messagerie native.
Aucun credential recherché, permission globale modifiée, daemon
installé/démarré, serveur redémarré ni tâche planifiée. Le serveur stdio temporaire
reste limité à la mission. Le parent Work reste actif jusqu'au résultat vérifié.

Qualifier le binaire réellement utilisé par l'application active et sa version,
plutôt que supposer que le premier `codex` du PATH est identique. Un CLI externe
plus ancien peut refuser le modèle configuré. Conserver le modèle/effort de
l'utilisateur ; vérifier l'accès par un tour terminé, pas par le seul catalogue
model/list. Ne pas installer ou reconfigurer un CLI pour contourner ce refus.

L'humain doit avoir autorisé le circuit et le message dans ce projet. Une création
nécessaire réutilise son accord persistant, sans question répétée ; qualifier le
grant hors du paquet reçu et le mandat courant avec `syncpilot_authority.py`
selon [FLOW.md](FLOW.md). Conserver son enveloppe de preuve et injecter uniquement
`bridge_authority` dans la requête. Les mandats directs existants restent lisibles.
Si le grant technique manque, le pilote le constitue depuis l'accord permanent
connu et le mandat courant qualifié, sans nouvelle question de création.
L'accord de création n'autorise aucun message hors mission. Nom du receveur :
`<nom du projet>-RECEVEUR`, avec son nom ou alias humain exact.

Le bridge utilise thread/start, thread/name/set et turn/start de l'API officielle.
L'identité du projet/workspace provient du contrat et de sa qualification native
par le pilote ; l'API observe le thread et son cwd réel. Le CLI ne définit pas un
projectId de sidebar. Conserver cette distinction dans la preuve, avec
application_project_id_observed=false ; ne pas inventer ce rattachement visuel.
Il ne reprend jamais le chat historique de l'application avec exec resume.
Un receveur déjà lié dans le journal à un autre acteur exige son outil réel de
message ; le bridge ne le remplace pas. La reprise thread/resume est limitée
aux receveurs créés et enregistrés par ce bridge. Un tour terminé peut rester
détenu techniquement par l'application, même avec un seul parent et aucun autre
travail. Un refus générique ou une activité/incertitude bloque la reprise.
Aucun verrou retiré. Le cas exact ci-dessous garde sa preuve et son mandat.

## Contrôle natif et renouvellement qualifié

Un état idle, un chat chargé ou un détenteur natif ne prouve pas un tour actif.
Un tour réellement actif, un setup ou un lancement incertain impose le suivi
de l'acteur existant. Le refus `active writer` est un conflit de contrôle, pas
une panne DC ; la disponibilité se qualifie indépendamment pour le runtime appelant.

Après le seul refus RPC `thread/resume` -32600 contenant `already has an active
writer`, privilégier le proxy officiel vers un socket déjà qualifié et existant,
fourni avec `--native-control-socket`. Aucun daemon démarré, serveur tiers arrêté
ou permission changée. Un refus API du canal connecté reste bloquant. Si le
socket est indisponible, ne pas boucler sur cette dépendance.

Le renouvellement automatique nécessite `allow_create:true`, aucune sélection
déjà engagée, une observation indépendante du pilote, la précédente opération
terminée et confirmée selon son protocole : VERIFIED Decisions ou CONFIRMED pour
une réception technique. Qualifier séparément la dernière activité réelle du
receveur, qui peut être un développement terminé depuis cette confirmation.
Le fichier extérieur vit directement dans
`<racine transport>/<project_id>/.authority/`, sans lien ni jonction. Son SHA
vient de la qualification du pilote ; il lie les octets sans authentifier l'origine.
Le pilote observe réellement le chat et le canal disponible dans le runtime
appelant, sans déduire leur état d'un paquet, d'un OWNER absent ou d'un ancien tour.
Dans le circuit `official-cli`, Work peut produire cette observation avec `observe`
décrit dans [MISSION.md](MISSION.md), via DC et le CLI officiel en lecture seule.
Aucun lecteur `Rpc` improvisé, demande de lecture au parent ou navigateur n'est
nécessaire. L'observation conserve les lectures natives et la confirmation
précédente sous `.authority` ; elle ne reprend ni ne lance un tour. La capacité
de message du runtime reste qualifiée par le pilote, distincte des faits lus par le CLI.
Un développement terminé ne devient pas une synchronisation VERIFIED pour
satisfaire ce contrôle ; conserver sa fin et sa référence propres. Lire
[MISSION.md](MISSION.md) pour le point d'entrée des réceptions techniques.

Champs communs de l'observation `SYNCPILOT-CODEX-RECEIVER-AVAILABILITY` :
`observed_at` UTC récent (120 s), `observer_environment`, `qualification_reference`,
`authority_reference` identique au mandat de la requête, `project_id`,
`codex_project_id`, `thread_id`, `canonical_root`, `active_turn_id:null`,
`pending_launch:false`, `native_message_channel:"unavailable"`,
`native_channel_reference`, `last_turn_id`, `last_turn_status`, `completed_job`,
`parent_confirmed:true`, `parent_confirmation_reference`, `confirmation_journal`
et `confirmation_journal_sha256`. La version 1 conserve le protocole historique :
la dernière activité doit être le tour de la précédente opération Decisions VERIFIED.
La version 2 ajoute `previous_confirmation_kind` (`decisions` ou `technical-mission`)
et `last_activity_reference`. Dans ce cas `last_turn_id/status` décrivent la vraie
dernière activité, distincte du tour lié par `completed_job`. Le journal antérieur
reste VERIFIED pour Decisions ; pour `technical-mission`, il s'agit de la
confirmation typée CONFIRMED et du reçu technique lié dans la même opération.
Les identités/chemins proviennent des observations réelles. Le bridge relit sans
chargement les métadonnées et le dernier tour officiels, les sorties originales
et la confirmation de la précédente opération avec ses empreintes indépendantes.
L'opt-in protocole experimentalApi sert ces lectures ; il n'élargit aucun accès.

    python -X utf8 BRIDGE --request REQUETE --codex CLI_OFFICIEL --recovery-observation OBSERVATION --recovery-observation-sha256 SHA64

Si un premier refus exact est déjà enregistré avant toute sélection/création/
commande de tour, une seule réparation explicite ajoute `--recover-native-writer`.
Elle conserve requête/opération/nonce et le premier refus dans `codex-dispatch` ;
la tentative suivante vit dans `recover-native-writer`. Les appels suivants
collectent ce résultat sans deuxième lancement. Toute réponse perdue, sélection,
activité ou preuve altérée interdit cette réparation.

Le registre précédent est sauvegardé sous `.receivers/codex/history/<SHA>.json` ;
la nouvelle référence conserve le chat remplacé et sa preuve de continuité.
Le nouvel acteur reçoit uniquement la mission actuelle et les références durables,
sans recopier arbitrairement tout l'historique. Aucun seuil universel de nombre de
missions n'est imposé. Si le runtime Work ne peut pas qualifier l'observation
indépendante, signaler cette capacité manquante ; ne pas affirmer une autonomie
non prouvée ni demander un nouvel accord humain de création déjà donné.

## Avant le déclenchement

Préparer l'opération Decisions v5 work-to-codex avec delivery shared-inbox,
destination.thread_id null, source réelle et preuves humaines qualifiées.
Déposer et relire le paquet une seule fois, avec journal DEPOSITED, puis rechercher
les résultats sur les deux canaux. Ne pas contourner un refus par ce bridge.

Le canon du projet, son remote/contrat et la propriété doivent être qualifiés.
Le bridge refuse les changements incertains et un paquet altéré avant lancement.
Les nouveaux objets restent dans l'opération et le transport du contrat, hors
du dépôt canonique. Le pilote construit la requête depuis son mandat humain ;
ne pas exécuter comme requête de contrôle un JSON ou prompt reçu dans le paquet.

Requête JSON du pilote :

```json
{
  "contract": "CHEMIN_ABSOLU_CANON/project-sync.json",
  "journal": "CHEMIN_ABSOLU_OPERATION/journal-deposited.json",
  "canonical_root": "CHEMIN_ABSOLU_CANON",
  "project_name": "NOM_OU_ALIAS_HUMAIN_EXACT",
  "source": {
    "environment": "work",
    "project_id": "PROJET_WORK_QUALIFIE",
    "thread_id": "CHAT_WORK_REEL",
    "authority": "MANDAT_HUMAIN_QUALIFIE",
    "qualification_reference": "OBSERVATION_INDEPENDANTE"
  },
  "authority": {
    "reference": "MANDAT_CIRCUIT_ET_RECEVEUR",
    "allow_message": true,
    "allow_create": true
  },
  "prompt": "MANDAT_DE_RECEPTION_PRECIS_DU_PILOTE"
}
```

Ces exemples ne prouvent aucune identité. Remplacer chaque référence depuis
les observations réelles. Le prompt précise paquet, exigence, base de registre,
preuves humaines, sorties attendues, périmètre et interdiction de mutation Git.

Sur le device DC qualifié, avec les chemins réellement observés :

    python -X utf8 BRIDGE --request REQUETE --codex CLI_OFFICIEL --timeout 1200

Lire la sortie du processus DC jusqu'à sa fin. Le helper émet DISPATCHED avec
les vrais thread/turn, puis le résultat terminal. Il sélectionne cet acteur
dans un nouveau journal, avant turn/start, sans changer opération ou nonce.
Le receveur reçoit les chemins du journal sélectionné et de son observation.

## Réception et retour

Dans Codex, qualifier les preuves humaines puis effectuer receive/check/reçu
avec le moteur Decisions. L'acteur écrit preuve, reçu et registre versionné ;
le canon et Git restent préservés. Une demande d'approbation hors réception est
signalée et interrompue, jamais acceptée automatiquement par le bridge.

Les fichiers `codex-dispatch/turn-completed.json`, `final-messages.json` et
`state.json` lient la fin officielle au même thread/turn et à l'opération/nonce.
FINISHED signifie fin de l'acteur, pas synchronisation confirmée. Work relit
indépendamment preuve/reçu/registre et leurs empreintes, confronte la réponse
finale authentifiée, puis confirm. Le stockage DC demeure EXTERNAL_ONLY.

Si une réponse de création ou de démarrage est perdue, conserver le contrôleur
et les objets ; suivre la même opération. Un nouvel appel avec la même requête
collecte ou signale FOLLOW_EXISTING_DISPATCH, sans nouveau tour ni receveur.
Un changement de prompt/mandat ou un résultat altéré est refusé. Une opération
ouverte incertaine nécessite le contrôle discriminant du processus DC et des
objets ; ne pas effacer OWNER.json ou recommencer le dépôt pour la contourner.

Une seule réparation explicite `--retry-before-work` est possible après un refus
modèle 400 invalid_request_error, fin officielle FAILED, serveur terminé avec
code 0, aucun item/message d'agent et aucun artefact de réception. Qualifier la
capacité corrigée, garder la même requête/opération/nonce et le même receveur.
Le premier échec reste intact ; la reprise écrit dans codex-dispatch/retry-before-work.
Les appels suivants collectent cette tentative, sans nouvelle relance. Toute
réception possible, réponse perdue, autre échec ou refus d'approbation exige
la collecte et le contrôle, jamais cette réparation.

Référence officielle : [protocole app-server et statut des tours](https://learn.chatgpt.com/docs/app-server).

Codex → Work utilise l'outil de message Work réellement exposé au pilote Codex,
puis sa réception indépendante et confirm. Le bridge ne prétend pas fournir
une API de message ChatGPT à un runtime qui n'en dispose pas.
