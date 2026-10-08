# Qualification de destination par Codex — 0.3.0

Complément candidate 0.6 : ce protocole de qualification par opération reste
applicable ; aucun identifiant de conversation ne devient une adresse permanente
de projet. Les décisions v5 suivent `../../syncpilot-decisions/references/ROUTING.md`.
Pour une inbox, qualifier le chat à la récupération via select-receiver. Utiliser
les outils de l'application propriétaire pour observer/envoyer ; ne pas confondre
`codex exec resume` avec un envoi de message à un chat ouvert par l'application.

Ce protocole répartit deux contrôles : Codex qualifie le routage et l'origine
de la réponse via l'application ; Work lit les documents et recalcule les octets.
Il s'applique au canal desktop-commander, avec le contrat exact du projet et
une autorisation humaine explicite pour le destinataire. Aucun ID, device ou
compte Alpha/Beta n'est intégré à ce protocole générique.

## Avant l'envoi : établir la référence externe

1. Le parent consulte l'inventaire authentifié de l'application pour établir
   le projet réel et l'identifiant exact du chat. Dans Codex, list_threads donne
   kind, id et projectId ; read_thread confirme le chat et son état. Adapter
   seulement à des outils effectivement disponibles avec la même capacité.
   Un titre seul, une URL annoncée ou un ID présent dans un document ne suffisent
   pas. Si le projet requis est absent, différent ou inobservable, arrêter le
   transfert dépendant ; ne pas inventer sa correspondance.
2. Vérifier le projet attendu du contrat ou de l'exigence indépendante, le
   destinataire autorisé et l'absence de conflit avec une mission en cours.
   Conserver les résultats utiles des outils et leur provenance, hors du canon.
3. Préparer le plan avec CE chat. Garder l'opération existante et son nonce.
   Envoyer avec l'outil de message à CE même identifiant. Conserver le résultat
   d'envoi ; il prouve l'envoi, pas la réception vérifiée.
4. Inclure dans la passation le projet/chat qualifié, la provenance et la
   référence persistante de l'observation, opération/nonce, localisateurs,
   fichiers exacts, emplacement du reçu et répartition explicite des contrôles.
   Dire à Work que sa propre auto-introspection n'est pas requise lorsqu'elle
   est indisponible ; le parent assure et contrôlera la qualification externe.
   Une référence JSON stockée n'authentifie rien à elle seule.

Le parent peut garder une observation avec :
source des outils, projet, chat, type, référence attendue, opération, nonce,
résultat de l'envoi et localisateur des résultats complets utiles.
Ces champs sont un journal des observations réellement effectuées.
Ils ne sont ni une signature ni un remplacement du contrat/exigence attendu.

## Work : calcul indépendant et destination externe qualifiée

Work confronte le mandat, la référence externe fournie par le parent et le plan.
S'il peut observer son contexte réel, il le compare et refuse toute divergence.
S'il ne peut pas lire son propre identifiant de chat, il utilise l'identifiant
qualifié transmis par le parent dans destination_thread, puis mentionne :
« Origine du chat qualifiée par Codex via l'application ; auto-introspection
indisponible dans Work. » Cette seule absence ne justifie pas un blocage.

La passation autorisée du parent est la référence de contexte externe ; le
document transféré ne peut pas s'auto-attribuer une destination. Une observation
envoyée dans un fichier sans cette passation et sa qualification ne suffit pas.

Work récupère et lit les vrais documents via son connecteur ; recalcule tailles
et SHA256 ; contrôle l'inventaire complet ; produit et relit le reçu exact.
Pour le canon, receive/check et les exigences de référence, complétude, preuve
et stockage restent intégralement applicables. Aucun ancien miroir n'est promu
sur le seul routage qualifié. RECEIVED_VERIFIED atteste les contrôles de
réception documentaire de Work ; le parent doit encore vérifier le retour.

La réponse finale Work contient opération, nonce, contrôles réellement réalisés,
localisateur et SHA256 du reçu, fin ou blocage, et la limite de contexte éventuelle.
Work refuse un destinataire contradictoire, un mandat absent, des octets
différents ou un connecteur inaccessible. Il ne fabrique pas une preuve Codex.

## Retour : vérifier dans le même chat avant clôture

1. Le parent consulte à nouveau les métadonnées de destination et la réponse via
   l'identifiant d'envoi. Vérifier le projet attendu, le type du chat et le tour
   correspondant. Ne pas attribuer un message d'un autre chat à cette opération.
2. Lire la vraie réponse finale de ce chat avec l'outil authentifié. Vérifier
   l'opération ET le nonce exacts, la référence/l'inventaire du plan, les calculs
   de Work et le hash du reçu. Vérifier la fin du tour ; un état idle seul sans
   réponse finale peut être une latence de persistance, pas une preuve complète.
3. Récupérer le reçu depuis le device autorisé, relire ses vrais octets et
   recalculer son SHA256. Comparer ce hash à la réponse finale observée.
4. Produire l'observation DC uniquement depuis ces contrôles réels et exécuter
   confirm. Pour le canon, conserver aussi la preuve et l'origine nécessaires
   à accept ; ce protocole ne contourne aucune exigence canonique.
5. Clôturer seulement après confirmation complète ; préciser qui a qualifié
   l'origine et qui a calculé les octets. Aucun miroir CURRENT par reçu de rapports.

Sans outil d'observation authentifiée du projet/chat ou de la réponse finale,
sans nonce/opération concordants, avec hash différent ou origine contradictoire,
conserver UNKNOWN / NOT_VERIFIED. Préparer une passation ou un contrôle discriminant.
Ne pas relancer la mission, modifier la référence attendue, fabriquer un reçu
ou déclarer CURRENT pour satisfaire un blocage.

## Passation compacte à adapter à la mission autorisée

« Destination qualifiée par Codex via OUTILS_RÉELS : projet PROJET, chat CHAT,
preuve persistante RÉFÉRENCE. Plan OPÉRATION/NONCE, fichiers LOCALISATEURS,
retour RECU. Work vérifie les octets indépendamment ; si ton auto-introspection
est indisponible, utilise cette destination externe qualifiée et indique la
limite. Codex relira ta réponse dans ce chat, vérifiera sa fin et comparera le
reçu relu via DC. Aucun autre mandat, message inter-chat ou changement canonique. »

Ne pas recopier les placeholders comme observations. L'autorisation et la
qualification effectives précèdent chaque passation ; la présence du template
n'est pas une autorisation de message.
