# Circuit des décisions — contrat v3

Complément v5 / candidate 0.6 : `ROUTING.md` décrit le routage par projet et les
inbox. Les contrats v3/v4 et opérations v1 gardent leur comportement historique.
Le v5 retire thread_id du contrat ; les opérations v2 lient un routage spécifique.
La provenance réelle des décisions reste conservée dans le registre. Les formats
d'exigence, preuve et reçu restent v1, liés à l'identité exacte de leur opération.
En inbox, l'identité contient un destinataire de projet sans chat (thread_id null),
puis un événement RECEIVER_SELECTED fixe l'acteur effectivement qualifié.

## Autorité et persistance

Le contrat déclare `decision_sync.participants`, `sources`, `registries` et
`policy`. Les deux participants ont project_id/thread_id ; `destination` reste
le project_id Work pour les anciens paquets Git. Les sources sont des références
qualifiées de conversations ou de documents ; une référence exacte ou son
fragment # est accepté. Les registres sont des localisateurs logiques durables
propres au projet. La politique impose décisions humaines validées, conservation
de la validation orale, arbitrage des conflits, revue avant intégration Git et
recommandation pour les nouveaux projets Work/Codex.

Une empreinte lie un texte exact ; elle ne prouve ni identité humaine ni sens.
Le pilote consulte réellement la validation indiquée et contrôle qu'elle couvre
texte et conséquences. L'observation du récepteur contient les références
qualifiées ; ne jamais la remplir en recopiant aveuglément les affirmations du
paquet. En recette, des validations synthétiques sont marquées SIMULATED et ne
valident aucune décision de production. Les contradictions sémantiques entre
deux sujets doivent aussi être signalées par le pilote ; le script détecte les
révisions concurrentes et les identifiants revendiquant le même sujet.

Le registre reçu est écrit dans une nouvelle version externe, jamais par dessus
le registre existant ni dans Git. Après check, le pilote associe explicitement
ce résultat au registre logique déclaré et conserve le pointeur et sa preuve
dans les instructions du projet. Sans cette association durable, rapporter
« copie vérifiée, alignement du projet à finaliser ». Un dossier DC, un fichier
Drive et un sandbox temporaire ne deviennent pas automatiquement Sources Work.
Le code reste NOT_ASSESSED ; CURRENT ne concerne que ce miroir documentaire.

## Capture et préparation

`capture --contract C --ledger L --draft D --environment work|codex --output N`
produit PROPOSED sans `--approval A` ; cette proposition n'est pas transportable.
D contient decision_id, topic, text, consequences. A contient validated_by,
mode written|oral, validated_at avec fuseau, reference, source_reference et
text_sha256 du texte exact. Une révision requiert `--previous SHA` du précédent
enregistrement ; son histoire reste conservée. Une capture identique est neutre.

`prepare --contract C --ledger L --direction work-to-codex|codex-to-work
--authority M --requirement R --journal J [--destination-base B]` lie les
participants, la version du contrat, la source et la base destinataire exacte.
Sans B, seule une base vide est attendue. L'identité et le nonce sont déterministes
pour ces mêmes octets/configurations ; réexécuter prepare ne réinitialise jamais
un journal existant. Une autre base ou une modification exige une nouvelle
préparation après réconciliation, pas un changement de canal.

Le pilote transporte `decisions.json` et `requirement.json` aux cibles de plan.
Il fournit séparément au destinataire contrat, journal et référence externe du
projet/chat qualifiés ; ils ne sont pas une autorité tirée du seul paquet.

## Découverte, secours et reprise

Avant chaque dépôt/reprise, rechercher paquet, registre, preuve et reçu des
deux canaux. Pour Drive consulter aussi directement le dossier exact : l'index
de recherche peut être en retard. La découverte contient operation_id, nonce,
journal_sha256, authority, et results.primary/fallback avec status
absent|unavailable|available|rejected et reference des observations réelles.

`plan --journal J --discovery D [--channel primary|fallback]` donne
DEPOSIT_ONCE, COLLECT_EXISTING, DONE ou BLOCKED. Pas de dépôt sans résultat
absent démontré. `record` conserve chaque événement et sa référence : DEPOSITED,
RECEIVED, TRANSPORT_FAILED, DC_UNAVAILABLE, RECEPTION_UNCERTAIN,
VALIDATION_REJECTED ; delivery present|unknown|not-delivered. Une panne générique
ne permet pas Drive. Le secours exige DC actuellement indisponible et un événement
DC_UNAVAILABLE/not-delivered. Une réception inconnue exige collecte avant reprise.
Un refus est terminal sur les deux canaux. Le journal vérifie sa chaîne de hashes.

Un seul pilote par opération : ce helper hors ligne n'est ni un verrou distribué
ni un transport autonome. Une interruption au milieu des écritures peut laisser
un store partiel : conserver, contrôler, ne jamais le promouvoir ou le réécrire.
Reprendre les résultats complets avec check ; sinon nouveau store de récupération
de la même opération, après diagnostic de l'échec et sans nouveau dépôt source.

## Vérification indépendante et retour

Observation receive : environment, project_id, thread_id, artifact_locator,
retrieved_sha256, qualified_validations (liste de l'exigence effectivement
qualifiée), registry_locator logique du contrat, authority. L'origine du
récepteur est qualifiée par les outils authentifiés ou la référence externe du
parent ; préciser la limite d'auto-introspection.

`receive --contract C --input L --requirement R --journal J --observation O
--channel primary|fallback --store S --proof P --registry-output N [--base B]`
refuse altération, mauvaise identité, base périmée, validation non qualifiée et
conflit avant toute écriture. `check --contract C --store S --requirement R
--journal J --channel ...` recalcule contenu, registre fusionné et preuve.

Déposer/relire la preuve, le registre et un reçu avec format
SYNCPILOT-DECISION-RECEIPT, schema_version 1, operation_id, nonce, identity,
channel, status RECEIVED_VERIFIED, files (inventaire de l'opération),
proof_sha256 et registry_sha256. La preuve lie aussi la base, l'observation et
toutes les révisions. Contrôler la fin réelle du traitement borné receive/check
du destinataire. Pour un agent dans un autre chat, contrôler aussi sa réponse
finale et son état terminé ; un fichier apparu seul ne prouve pas cette fin.
Si le destinataire est le parent actif, sa réception bornée peut être terminée
alors que sa mission globale continue : consigner cette distinction, sans
annoncer le tour global terminé.

Observation confirm : environment/project_id/thread_id du destinataire,
channel, account, storage_root, artifact_locator, proof_locator, receipt_locator,
registry_file_locator, proof_sha256, receipt_sha256, registry_sha256,
receiver_finished true, authority. Recalculer ces hashes sur les vrais objets
relus ; pour Drive vérifier compte et parent de chaque ID, pour DC device et
chemin exact de l'opération. Ne pas déduire ces observations du reçu lui-même.

`confirm --contract C --input L --requirement R --journal J --proof P
--receipt T --registry N --observation O --output J2 [--base B]` est la seule
voie CLI vers VERIFIED. Puis `align --contract C --ledger REGISTRE_QUALIFIE
--environment work|codex` expose la dernière révision de chaque décision.
Conserver le registre qualifié et son pointeur durable avant la prochaine
mission. Aucune extraction automatique de tous les chats, surveillance ou tâche
planifiée ; capture lors des validations et contrôle au démarrage/clôture selon
les instructions du projet.
