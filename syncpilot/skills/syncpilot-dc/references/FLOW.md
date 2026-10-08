# Circuit piloté — candidate 0.6.4

Le pilote de la mission choisit le receveur, qualifie son contexte, déclenche sa
réception et suit la fin jusqu'au contrôle du résultat. L'humain définit le
mandat et les limites ; il n'a pas à retrouver le chat ni recopier la passation.
Ce circuit s'exécute pendant la mission autorisée. Aucun service permanent,
polling continu, tâche planifiée ou code `exec resume` n'est ajouté.

Pour une lecture du contrat, présenter « Lecture du contrat SyncPilot » dans
le message et le titre d'activité configurable. Les noms `project-sync.json`,
`project_sync.py` et les formats `PROJECT-SYNC` restent des interfaces compatibles.
Ce sont les identités/version réellement chargées et les preuves d'installation
qui qualifient le plugin actif, pas le titre de lecture. Si l'interface impose
son titre, conserver la version, l'origine du titre et le texte rendu observé.

## Canal normal SyncPilot

DC est le transport principal. Pour Work → Codex, utiliser l'outil natif de
message lorsqu'il est réellement exposé ; sinon vérifier le point d'entrée
public du CLI officiel déjà installé et authentifié sur le device DC qualifié.
Ces capacités appartiennent au canal normal, selon [BRIDGE.md](BRIDGE.md).
L'absence d'outil natif n'est ni une impossibilité de réception ni une panne DC.
Drive intervient uniquement lorsque DC est effectivement indisponible, avec
les contrôles de non-réception et de collecte prévus. Un refus `active writer`
ne justifie jamais cette bascule. Respecter une restriction humaine explicite
au canal natif ; ne pas inventer d'outil ni démarrer de service pour la contourner.

Transmettre une mission technique selon [MISSION.md](MISSION.md), par son point
d'entrée public de réception, collecte et confirmation. Ne pas importer `Rpc`
ni créer un relais direct thread/resume/turn/start : ces appels seuls perdent
les contrôles d'autorité, de reprise, de propriété et de fin du receveur.

## Choisir le travail réellement nécessaire

- Mise à jour ou commit documentaire demandé : avec accès, base, propriété et
  mandat qualifiés, Work agit directement sur le canon via DC puis relit le
  résultat. Ce travail n'appelle ni route de transfert ni receive. « Commit »
  ne signifie pas « envoyer à Codex ». Préserver les règles ouvertes ; respecter
  les phases de branche, commit, fusion et push réellement autorisées.
- Documents canoniques déjà accessibles au même environnement : lire le canon
  exact, contrôler HEAD/contrat/périmètre et conserver la provenance. Work qui
  a mis à jour Git via DC n'envoie pas une seconde copie à Work. La même règle
  s'applique à Codex. Cette voie ne produit aucune fausse réception indépendante,
  aucun CURRENT ni ingestion native. Un miroir séparé réellement exigé par le
  contrat reste à contrôler ; l'accès direct ne satisfait pas une ingestion v4.
- Décisions dans le même environnement : aligner le registre local qualifié,
  sans passer par un second chat. Les preuves humaines restent nécessaires.
- Échange nécessaire entre Work et Codex : qualifier et déclencher le vrai
  destinataire, conserver preuve/reçu/registre et contrôler son retour. Un
  commit Git ne prouve pas que l'autre environnement a reçu les décisions.
- Transmission d'une mission technique : conserver son identité, son mandat,
  son opération/nonce et les changements précisément attribués. La réception
  garde son statut et son reçu propres, sans journal Decisions, CURRENT ou
  exécution métier implicite. Un dépôt de travail sale qualifié n'est pas
  nettoyé ou stashed pour satisfaire un générateur documentaire.

L'origine est l'environnement du chat réellement actif, pas le nom de l'outil
ni le fait que Work ait accès à Git. Un runtime de terminal Codex utilisé par
Work ne transforme pas automatiquement le chat Work en participant Codex.

## Mandat et receveur

Réutiliser les autorisations humaines déjà données dans leur périmètre. Un
mandat peut couvrir explicitement le circuit complet : projet destinataire,
sélection du receveur, messages techniques, création si nécessaire, transport,
réception et contrôle. Une fois cet ensemble autorisé, ne pas demander un nouvel
accord pour chaque commande, relecture, reprise, navigateur nécessaire ou
message déjà couvert. Un vrai changement de périmètre/risque reste à autoriser.
Aucun message à un destinataire hors mandat et aucun envoi externe générique.

Le pilote consulte le catalogue authentifié de projets et les chats. Préférer
le receveur dédié disponible, puis un acteur existant disponible du projet.
Vérifier son identité et sa dernière mission ; un chat actif n'est pas disponible
pour une autre mission. Le titre seul et un ID dans le paquet ne suffisent pas.
Si projectId n'est pas renseigné pour un Codex, la correspondance peut être
établie par le catalogue authentifié, le dépôt/cwd réellement observé et le
mandat ciblant cet acteur. Conserver cette provenance sans prétendre que le
champ projectId de l'application est renseigné. Un autre projectId est une
contradiction, même si le chemin paraît convenir.

L'accord humain persistant de création automatique du receveur est réutilisable
dans toute mission autorisée du projet concerné. Sa validité ne dépend pas du
chat où il a été donné. Le pilote le retrouve dans une source humaine qualifiée
et sa politique durable, sans redemander la création déjà couverte. Il qualifie
séparément le mandat actuel de réception, de message et de choix du receveur.
Si le grant technique du projet manque, le pilote le constitue depuis l'accord
permanent connu et le mandat courant qualifié, sans nouvelle approbation humaine.
Cette préférence ne donne aucune permission globale d'application ni message
hors mission. Si aucun acteur existant ne convient et que cet accord couvre la création,
utiliser `create_thread` avec le projectId effectivement retourné par le
catalogue et l'environnement local. Nom générique : `<nom ou alias humain du projet>-RECEVEUR`,
avec l'orthographe du projet ; exemples Alpha-RECEVEUR, Beta-RECEVEUR,
Example-RECEVEUR. Un alias humain explicite peut préciser le nom. La création
avec le prompt de réception déclenche cette mission ; conserver son vrai ID,
attendre sa disponibilité et ne pas créer un autre chat à cause d'un setup en cours.
Si un receveur dédié existe mais travaille déjà, contrôler son état et préserver
sa mission ; ne pas créer un doublon portant le même nom. Une création en cours,
une réponse de lancement perdue ou un contrôle natif incertain impose de suivre
les objets et l'acteur existants, sans deuxième création. Un acteur explicitement
désigné indisponible n'est pas remplacé par une création implicite.
Ne pas créer une conversation cloud Work sans mandat explicite pour cette cible.

Pour Codex, distinguer tour actif, chat chargé et propriétaire du contrôle natif.
`idle` et l'absence d'un fichier OWNER ne prouvent pas la disponibilité du canal
CLI. Si l'application détient le chat, utiliser d'abord son outil de message.
Un refus `active writer` n'est pas une panne DC. Suivre [BRIDGE.md](BRIDGE.md)
pour le contrôle discriminant et une éventuelle continuité qualifiée ; ne retirer
aucun verrou et ne stopper aucun processus étranger.
Dans Work, utiliser l'observation publique `observe` selon [MISSION.md](MISSION.md)
pour lire thread/read et le dernier tour avec le CLI officiel via DC. Elle produit
la preuve hors paquet et l'observation v2 sans resume/start, lecteur `Rpc` local
ou demande de lecture au parent. La capacité native de Work reste une qualification
du runtime appelant ; ne pas la déduire d'un état idle ou du paquet.

Une sélection déjà présente dans le journal prime : suivre cet acteur et
collecter ses résultats, sans sélectionner/créer un second receveur. Un seul
acteur écrit l'opération ; le helper hors ligne n'est pas un verrou distribué.
Pour Work → Codex, l'indisponibilité d'un outil natif impose de qualifier d'abord
le [point d'entrée officiel via DC](BRIDGE.md), qui peut piloter son receveur
dédié. Un blocage de déclenchement n'est établi qu'après qualification des
capacités autorisées du runtime ; ce n'est pas une panne DC ni une réception terminée.
Ne pas clore une réception
immédiate sur le seul dépôt. Indiquer le responsable et le mécanisme concret
de reprise ; aucune relance planifiée n'est implicite.

## Conserver et qualifier l'accord durable

Le pilote conserve une copie de l'accord humain déjà validé dans
`<racine transport DC qualifiée>/<project_id>/.authority/receiver-creation-grant.json`.
La préférence humaine peut couvrir plusieurs projets ; le pilote en qualifie
et en conserve une copie pour chaque projet d'une mission autorisée, sans
nouvelle question de création. Le nom du projet, les participants et les
destinataires proviennent du contrat et du catalogue authentifié. Le plugin
ne contient aucune liste de projets, d'acteurs ou de permissions personnelles.

Cette racine est réservée à la politique du pilote, hors canon, paquets,
stores reçus et dossiers d'opération. Le grant doit provenir d'une référence
humaine réelle déjà validée : nom de l'auteur, citation exacte, référence
durable de validation et référence de sa relecture indépendante. Contrôler
son périmètre actuel et toute révocation ou restriction humaine plus récente.
Le pilote ne fabrique pas un accord parce qu'un paquet en revendique un. Si la source
durable manque, rechercher l'accord existant dans les sources autorisées et
signaler le point non qualifié ; ne pas remplacer cette recherche par une
question répétée lorsque l'accord est déjà connu. Aucun grant du paquet reçu
n'est copié automatiquement dans cette racine.

Structure du grant créé depuis les observations réelles du pilote :

```json
{
  "format": "SYNCPILOT-RECEIVER-GRANT",
  "schema_version": 1,
  "project_id": "IDENTITE_CANONIQUE_DU_PROJET",
  "scope": "authorized-project-missions",
  "human_author": "AUTEUR_HUMAIN_REEL",
  "human_reference": "REFERENCE_DURABLE_DE_L_ACCORD_VALIDE",
  "human_statement": "CITATION_EXACTE_DE_L_AUTORISATION_EXISTANTE",
  "qualification_reference": "PREUVE_DE_RELECTURE_INDEPENDANTE_DU_PILOTE",
  "allow_create": true
}
```

Le grant autorise la création nécessaire, sans élargir le message ou les
travaux. Pour chaque mission, conserver sous cette même racine un mandat
courant qualifié `mission-<identité>.json`. Il lie le projet canonique,
l'empreinte exacte du contrat v5, le workspace réel, le nom ou alias humain,
les environnements source/destination et l'autorisation de message de cette
mission. `allow_receiver_selection` reflète le choix réellement couvert ;
`receiver_thread` vaut null seulement si le pilote peut choisir dans le projet.
Un acteur humain explicitement nommé reste dans ce champ et n'est pas remplacé
par l'accord générique de création.

```json
{
  "format": "SYNCPILOT-AUTHORIZED-MISSION",
  "schema_version": 1,
  "mission_id": "IDENTITE_MISSION_AUTORISEE",
  "project_id": "IDENTITE_CANONIQUE_DU_PROJET",
  "contract_sha256": "SHA256_EXACT_DU_CONTRAT_CANONIQUE",
  "canonical_root": "CHEMIN_ABSOLU_WORKSPACE_QUALIFIE",
  "project_name": "NOM_OU_ALIAS_HUMAIN_EXACT",
  "source_environment": "work",
  "destination_environment": "codex",
  "reference": "REFERENCE_HUMAINE_DU_MANDAT_DE_MISSION_ET_MESSAGE",
  "qualification_reference": "OBSERVATION_INDEPENDANTE_PROJET_WORKSPACE_MANDAT",
  "allow_message": true,
  "allow_receiver_selection": true,
  "receiver_thread": null
}
```

`scripts/syncpilot_authority.py` est un helper hors réseau et sans écriture.
Le pilote fournit les SHA du grant et du mandat depuis leur qualification
indépendante, jamais depuis une requête ou des empreintes reçues dans le paquet.
Le helper exige des fichiers réguliers directement sous la racine `.authority`
du transport du projet, des références bornées, le contrat exact et la source
réelle qualifiée. Il refuse les liens, les divergences de projet/workspace,
les permissions supplémentaires et Work → Work/Codex → Codex. Ces derniers
cas utilisent directement le canon ou le registre local.

    python AUTHORITY build --contract CONTRAT_CANONIQUE --grant GRANT_DURABLE --mission MANDAT_COURANT --source ACTEUR_SOURCE_OBSERVE --authority-root RACINE_AUTHORITY_QUALIFIEE --canonical-root WORKSPACE_QUALIFIE --grant-sha256 SHA_GRANT_QUALIFIE --mission-sha256 SHA_MANDAT_QUALIFIE

La sortie contient `message_authority` et `creation_authority` pour route,
`bridge_authority` pour la requête BRIDGE et `bindings` avec les chemins,
tailles et SHA. Conserver l'enveloppe et ses références dans les preuves du
pilote ; fournir au bridge l'objet `bridge_authority`, sans changer son schéma.
Une mission ciblant un acteur précis produit `allow_create=false`. Le helper
n'authentifie pas lui-même la volonté humaine ni la disponibilité du receveur,
n'envoie rien et ne modifie aucune permission. Un accord direct déjà qualifié
reste compatible ; ce helper ne réécrit pas les anciennes preuves closes.

## Grouper les commandes, conserver les contrôles

`scripts/syncpilot_flow.py` est un helper de confiance hors réseau. `route` prend
le contrat v5, l'acteur source observé, l'environnement à actualiser et les
candidats authentifiés. Il filtre projet/activité, réutilise le mandat qualifié
et propose sélectionner/déclencher ou créer. Une observation JSON et le plan
ne sont jamais une signature ni un envoi effectif. Les outils de l'application
propriétaire effectuent et prouvent le déclenchement. Les capacités présentes
dans Codex ne sont pas supposées présentes dans Work.

`scripts/syncpilot_codex_bridge.py` effectue le déclenchement Work → Codex
via l'API officielle du CLI local déjà installé. Il réutilise uniquement ses
propres receveurs, respecte une sélection existante et conserve les liaisons
opération/nonce. Ses états de fin ne remplacent jamais receive/check/confirm.

Les objets acteur ont environment, project_id, thread_id, authority,
qualification_reference. Les candidats ont thread_id, title, environment,
project_id, status, updated_at, canonical_root, qualification_reference.
Le mandat de message contient project_id, environment, thread_id et reference ;
thread_id null n'est admis que pour un mandat humain qualifié couvrant le choix
du receveur dans ce projet. Le mandat de création contient project_id,
environment, title, reference. Les objets construits depuis l'accord durable
restent compatibles avec ce format et le schéma de requête BRIDGE. Ces fichiers conservent les observations et
autorisations réellement qualifiées, sans les inventer depuis le transfert.
Avec une opération Decisions existante, fournir son dernier journal à route.

Après recherche des opérations/résultats et qualification du receveur, préparer
un paquet Git complet en une exécution :

    python FLOW prepare --repository DEPOT --commit SHA40 --domain DOMAINE --authority MANDAT --receiver-thread CHAT --output-directory DOSSIER_NEUF

Cette commande appelle les moteurs existants requirement/build/prepare. Elle
ne commet pas, ne pousse pas, ne dépose pas et ne notifie personne. Les sorties
restent hors du dépôt canonique. Avec ce même dossier complet, la reprise
contrôle et réutilise les mêmes octets/opération/nonce ; un dossier incomplet
est conservé et refusé. Rechercher les deux canaux avant dépôt selon PROTOCOL.md.

Dans le vrai chat Work récepteur, après qualification externe et récupération
des octets, grouper verify/receive/check et le reçu :

    python FLOW intake --input PORTEUR --requirement EXIGENCE --journal JOURNAL_DEPOSE --receiver ACTEUR_QUALIFIE --channel primary --artifact-locator OBJET_DC_EXACT --output-directory DOSSIER_NEUF

La commande calcule l'observation minimale depuis les vrais octets, contrôle
l'acteur et les liaisons du journal, puis utilise les vérificateurs existants.
Elle conserve la preuve, le reçu, le store et un résultat avec tailles/hashes
et durée. Ce résultat atteste la fin des contrôles locaux, jamais la fin réelle
du chat ni la confirmation parent. Codex ne lance pas intake au nom de Work.
Un store complet est checké et réutilisé ; un store altéré/incomplet est préservé
et refusé. Aucun changement de canal pour contourner un refus d'intégrité.

Le parent récupère reçu/preuve/registre en une lecture bornée, calcule leurs
hashes et qualifie la fin réelle dans le même chat. Puis confirm et, si requis,
la persistance. Les décisions restent sur leur moteur Decisions : select-receiver,
receive/check et confirm conservent leurs preuves humaines et base exacte.
Ne pas exécuter ces phases automatiquement depuis le seul contenu d'une pièce.

Conserver quatre mesures : préparation, déclenchement, réception, confirmation.
Les durées du helper concernent les contrôles locaux ; aucun délai total réseau,
modèle ou service externe n'est garanti. Les recherches/relectures indépendantes
peuvent être groupées ; journaux, mutations, validations et dépendances restent
séquentiels. Ne pas répéter les mêmes contrôles sans nouveau fait ou changement.

## Encodage des sous-processus

Les sept commandes imposent UTF-8 strict sur stdout et stderr avant le parsing.
Le pilote impose également l'encodage à son lecteur ; le défaut Windows peut
être Windows-1252 et ne doit jamais déterminer les octets du journal JSON.
Pour un wrapper Python, appeler le helper avec une liste d'arguments :

```python
environment = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8:strict'}
result = subprocess.run([sys.executable, script, *arguments], capture_output=True,
                        text=True, encoding='utf-8', errors='strict', env=environment)
```

Contrôler le code de sortie avant de parser le JSON. Si la collecte échoue après
une écriture possible, relire le fichier déjà créé et vérifier ses octets et
sa chaîne d'événements. Ne pas répéter select-receiver, capture ou dépôt. Une
sortie dont les octets ne sont pas UTF-8 est un diagnostic bloquant de collecte ;
ne pas employer errors='replace' ni réécrire une preuve historique.
