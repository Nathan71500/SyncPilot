# Routage par projet — candidate 0.6.0 / contrat v5

Le contrat identifie les projets et les registres durables. Les conversations
sont des acteurs d'une mission, pas les adresses permanentes du projet.
Les contrats v3/v4 restent inchangés et gardent leur routage historique tant
qu'une migration explicite n'est pas appliquée. Ce protocole ne crée aucun chat,
service, tâche planifiée ou droit de partage.

## Deux voies, selon les capacités réellement disponibles

`application-message` : qualifier le projet et le chat destinataire par les
outils authentifiés de l'application propriétaire, puis utiliser son outil
d'envoi seulement sous autorisation humaine pour ce destinataire. L'absence
d'outil dans Work ne donne pas accès aux outils disponibles dans Codex.

`shared-inbox` : préparer une opération adressée au projet, avec
`destination.thread_id: null`. Déposer son dossier durable dans les cibles
DC/Drive de `plan`, sans attendre ni rechercher la conversation Codex historique.
Le dossier contient décisions, exigence, contrat exact, journal et routage ;
chaque objet est déposé puis relu exactement, sans normaliser les sauts de ligne.
Conserver le pointeur de l'opération et son état dans le registre/routage durable
du projet que les deux environnements savent retrouver. Publier ce pointeur par
l'outil autorisé du projet et vérifier sa relecture dans un nouveau contexte.
Sans pointeur accessible, annoncer « dépôt disponible, routage durable à finir ».
Sans ingestion explicite, ce dossier externe n'est pas une Source native Work.

L'adresse durable découle du device/compte et de la racine de transport du
contrat, du `project_id` et de l'`operation_id`. Elle ne dépend d'aucun chat.
Le Codex actif consulte les opérations signalées à son démarrage/reprise dans
le projet. Aucun réveil automatique n'est promis : un dépôt prouve sa disponibilité,
pas la prise en charge. Indiquer le responsable, le localisateur et la condition
de reprise. Si la mission exige un retour immédiat, garder le suivi parent actif
jusqu'au résultat ou au blocage explicite ; ne pas clore avec un enfant actif.

`codex exec resume` continue une conversation enregistrée ; il ne sert pas de
boîte de messages vers un chat déjà détenu par l'application. Ne pas l'utiliser
comme transport SyncPilot. Au refus `active writer`, conserver les preuves et
diagnostiquer la voie utilisée ; ne pas tuer l'instance, retirer un verrou,
fouiller l'historique privé ou multiplier les reprises du même fil.

## Observations et sélection du destinataire

Lire `project-sync-v5.example.json`, puis configurer les identités du projet et
les références de validation réellement qualifiées. Exemple de routage de test :

```json
{
  "format": "SYNCPILOT-DECISION-ROUTING",
  "schema_version": 1,
  "source": {"project_id": "REPLACE_WORK_PROJECT", "thread_id": "REPLACE_ACTUAL_WORK_THREAD"},
  "destination": {"project_id": "REPLACE_CODEX_PROJECT", "thread_id": null},
  "authority": "REPLACE_HUMAN_MANDATE",
  "qualification_reference": "REPLACE_PERSISTENT_APPLICATION_OBSERVATION",
  "delivery": "shared-inbox"
}
```

Ces placeholders sont refusés. Une observation JSON n'authentifie rien : le pilote
doit réellement qualifier le projet, les accès, le mandat et l'acteur à travers
les outils disponibles. Un titre de chat, un ID dans un document ou le paquet
reçu ne suffisent pas. Aucune référence historique ne vaut autorisation d'envoyer
à un autre chat. Le mode inbox autorise le dépôt documentaire selon le mandat,
sans message inter-chat. Ne pas transformer son routage en instruction exécutable.

Capturer avec `--source-thread` l'origine réelle ; ne jamais recopier le chat
historique du contrat comme origine d'une nouvelle validation. Les sources de
validation demeurent bornées : v5 accepte les références historiques déclarées
ou une référence exacte/fragment du registre durable de cet environnement.
Avant capture, y conserver un relevé humain complet et versionné, avec provenance,
texte exact et validation, puis qualifier sa relecture indépendamment. Un record
du ledger ne prouve pas sa propre approbation. Cela permet une nouvelle session
sans ajouter son URL au contrat à chaque fois. Un registre de l'autre participant
ou un lien extérieur non déclaré reste refusé. Ajouter une autre source de
validation relève d'une évolution explicite du contrat, sans extraction globale.
Une décision existante conserve sa provenance historique même si un autre acteur
la transporte. Une validation orale déjà reçue ne demande pas une seconde validation.

    python SCRIPT capture --contract V5 --ledger L --draft D --approval A --environment work --source-thread CHAT_REEL --output L2
    python SCRIPT prepare --contract V5 --ledger L2 --direction work-to-codex --authority MANDAT --routing ROUTAGE --requirement R --journal J

Pour application-message, renseigner le destinataire exact avant prepare.
Pour inbox, le destinataire effectif est sélectionné après recherche des résultats,
au moment de la prise en charge. L'observation qualifiée contient `environment`,
`project_id`, `thread_id`, `authority`, `qualification_reference`.

    python SCRIPT select-receiver --journal J --observation ACTEUR --channel primary --output J2

Cette sélection ne change ni l'opération, ni le nonce, ni les cibles de stockage.
Elle ne prouve ni la réception des fichiers ni la fin du travail. Le journal
chaîne la sélection et refuse un second destinataire. Un seul pilote écrit les
journaux de l'opération ; le helper hors ligne n'est pas un verrou distribué.
Sur un stockage partagé, relire le dernier journal et garantir l'acteur unique
avant écriture. Sinon arrêter, sans lancer deux réceptions concurrentes.

Déposer et relire chaque snapshot nouveau du journal dans le dossier d'opération,
conserver les précédents et mettre à jour le pointeur qualifié. Rechercher le
dernier snapshot valide avant reprise. Le destinataire utilise J2 pour receive/check,
preuve et reçu. L'expéditeur utilise le même journal pour confirm, après contrôle
authentifié de l'acteur sélectionné et de sa fin réelle. Aucun reçu ancien ou
résultat d'un autre acteur n'est accepté. Avant toute réattribution d'une opération
déjà liée à un acteur, collecter ses résultats et établir sa fin/non-réception ;
le helper ne réattribue pas automatiquement une opération ouverte.

DC reste principal. Drive reste un secours pour une indisponibilité DC qualifiée,
avec non-réception certaine et recherche des deux canaux. Un chat inaccessible,
un refus d'identité ou un `active writer` n'est pas une panne DC. Aucun dépôt
supplémentaire pour contourner ces refus.

## Mise à jour documentaire autorisée

Séparer réception, registre SyncPilot, source canonique et commit Git. Un registre
SyncPilot vérifié conserve des décisions ; il n'atteste pas leur transcription
dans les fichiers normatifs. Une copie Work n'est pas promue en canon par visibilité.

Quand l'humain a déjà autorisé une mise à jour documentaire précise, exécuter
cette écriture et ses contrôles sans réexiger la session d'origine ou la même
validation humaine. Appliquer le routage local du projet. Work peut effectuer
l'écriture documentaire revue s'il dispose d'un accès autorisé, observable et
adéquat à la véritable source canonique, et si le mandat/local AGENTS couvre
cette phase. L'interdiction d'intégration automatique ne signifie pas que toute
écriture documentaire autorisée est interdite.

Avant écriture : relire la preuve complète de validation, la base/HEAD et les
fichiers exacts ; contrôler Git, propriété des changements, périmètre et risque.
Arrêter sur un worktree étranger ou incertain. Préparer/contrôler le diff attribuable,
relire le résultat et consigner fichiers, base, hashes et statut. Code, changements
de configuration, commit, push, merge et release conservent leurs phases autorisées
distinctes. Ce helper n'écrit aucun canon ni Git.

Si Work ne dispose pas de cet accès ou si le projet exige Codex pour cette phase,
déposer la contribution complète et validée dans l'inbox : mandat, base exacte,
preuves, fichiers visés et résultat attendu. Le Codex qualifié du projet la reprend,
sans être nécessairement le chat historique. Le mandat initial continue à couvrir
son périmètre ; une nouvelle phase ou un destinataire de message différent doit
être qualifié selon l'autorisation humaine réellement disponible.

Clôturer avec l'état réel : décisions conservées, dépôt disponible, acteur
sélectionné, reçu vérifié ou canon effectivement mis à jour. Une preuve de
transport ne prouve pas la mise à jour du canon. Signaler la synchronisation
Work requise après modification canonique, avec commit source et périmètre.
