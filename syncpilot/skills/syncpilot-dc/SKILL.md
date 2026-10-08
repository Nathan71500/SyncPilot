---
name: syncpilot-dc
description: Piloter une opération SyncPilot avec DC principal et Drive seulement si DC indisponible ; contrôler reprise sans doublon et preuve indépendante Work.
---

# Transport SyncPilot

Présenter la lecture du contrat comme « Lecture du contrat SyncPilot » dans les
messages et les titres d'activité configurables. `project-sync.json`,
`project_sync.py` et `PROJECT-SYNC` restent des interfaces techniques compatibles,
pas des noms de plugin actif. Consigner un titre imposé par l'interface.

Qualifier d'abord l'action demandée : un commit documentaire local sur le canon
accessible via DC suit son mandat d'écriture et ne nécessite pas de transfert
Work → Codex. Pour une synchronisation réellement demandée, le transport et
le déclenchement sont tous deux nécessaires. Si Work n'a pas l'outil de message
Codex, vérifier le CLI officiel et appliquer [BRIDGE.md](references/BRIDGE.md).
Le canal normal SyncPilot est DC principal avec les outils natifs disponibles ou
le point d'entrée public CLI officiel. L'absence d'outil natif dans Work n'est
ni une impossibilité de déclenchement ni un motif de secours Drive. Respecter
une restriction humaine explicite au canal natif ; qualifier les capacités
réelles sans inventer d'outil, démarrer de service ou contourner un refus.

Pour transmettre une mission technique, utiliser le point d'entrée public
réception/collecte/confirmation décrit dans [MISSION.md](references/MISSION.md).
Ne pas importer `Rpc` ni appeler directement thread/resume ou turn/start dans
un relais local. Une réception de mission garde son reçu typé ; elle ne devient
ni une décision humaine validée, ni un miroir CURRENT, ni une exécution métier.
Le canon peut contenir des changements exactement attribués à cette mission,
qualifiés et liés au mandat ; ne pas les nettoyer pour produire une passation.
La commande publique `observe` lit le receveur et son dernier tour via le CLI
officiel, puis produit ses preuves sous `.authority` sans resume/start. Work
qualifie ainsi une reprise sans lecteur `Rpc` local ni demande au parent/browser.

Avant toute nouvelle opération, appliquer [le circuit piloté](references/FLOW.md) :
éviter les transports vers son propre environnement, sélectionner le receveur
par projet, réutiliser le mandat de la mission et grouper les contrôles avec
`scripts/syncpilot_flow.py`. Le pilote prend en charge le déclenchement et le
suivi ; une inbox passive ne suffit pas pour un retour immédiat. Les autorisations,
capacités réelles et preuves indépendantes restent obligatoires.

L'accord humain persistant de création automatique s'applique dans la mission
autorisée du projet, sans dépendre du chat d'origine et sans nouvelle question
de création. Consulter sa copie qualifiée dans la politique durable du pilote,
hors paquets reçus, puis le mandat courant. `scripts/syncpilot_authority.py`
construit les autorités de route/bridge depuis ces fichiers et le contrat exact.
Si cette copie technique manque, le pilote la constitue depuis l'autorisation
permanente connue et le mandat courant qualifié, sans question de création.
Réutiliser d'abord un receveur qualifié disponible ; sinon créer
`<nom ou alias humain du projet>-RECEVEUR` avec les outils réellement disponibles.
Une sélection, une création en cours, un acteur occupé ou une réception incertaine
doit être suivie et collectée avant une nouvelle création. Un statut idle seul
ne prouve pas que le canal de déclenchement détient le contrôle du chat.
L'accord de création ne remplace ni le mandat de message de la mission, ni la
qualification du projet/workspace. Aucun projet ou destinataire n'est inscrit
dans le plugin ; la provenance humaine ne peut pas venir du seul paquet reçu.

Pour les décisions sous contrat v5, appliquer
`../syncpilot-decisions/references/ROUTING.md` : projet durable, inbox sans session
destinataire à la préparation, sélection qualifiée à la récupération. Les anciens
paquets Git gardent leur protocole et leur chat qualifié par opération. Un refus
`active writer` d'un processus Codex ne constitue pas une indisponibilité DC.

Le transport VERIFIED est la première preuve. Un contrat v4 exige aussi
../syncpilot-persistence/SKILL.md avant clôture. Une persistance Work indisponible
n'est pas une panne DC ; elle n'autorise ni Drive ni un changement de cible.

Pour les décisions humaines dans les deux sens (contrat v3), utiliser le journal
et les preuves de `../syncpilot-decisions/SKILL.md`. Le protocole ci-dessous
reste celui des paquets Git PROJECT-SYNC ; ne pas mélanger leurs formats.

Lire le contrat exact et le mandat. Connecteurs déjà accessibles : aucune
installation, recherche de credential, modification de permission, redémarrage
de serveur, tâche planifiée ou surveillance permanente. Qualifier device/compte,
racines privées et projet/chat via l'application. Le contrat définit tout accès.
`scripts/syncpilot_transport.py` est un helper hors réseau : il produit des
plans et contrôle les preuves ; il n'effectue aucun upload. Les outils DC/Drive
du pilote réalisent le transport. Un succès du helper ne prouve pas un transfert.

Avant prepare, rechercher l'opération de cette exigence dans le journal et les
deux stockages ; réutiliser l'opération et son nonce, ne pas préparer un autre
plan après interruption. Conserver les artefacts hors du canon, sans écrasement.

    python HELPER prepare --input PORTEUR --requirement EXIGENCE --thread CHAT --authority MANDAT --output JOURNAL-0
    python HELPER plan --journal JOURNAL --discovery RECHERCHE --channel primary

RECHERCHE lie l'opération, nonce et empreinte canonique du journal aux constats
réels de chaque canal : absent, unavailable, available ou rejected et référence
authentifiée. Voir `references/PROTOCOL.md`. Rechercher artefacts, reçus et preuves
par l'identité exacte avant chaque reprise, bascule ou dépôt. Disponible :
COLLECT_EXISTING, sans nouvel upload. Refus : BLOCKED, aucun changement de canal.

DC est principal. Déposer les octets textuels EXACTS sous les cibles du plan,
UTF-8 sans BOM, uniquement si elles sont absentes. Relecture sur le device puis
taille/SHA comparés. write_file n'est pas exclusif : vérifier l'absence et
garantir un seul acteur de l'opération ; sinon arrêter. Ne pas réécrire une cible
existante, même après un timeout. Transport-failed est distinct d'une réception
incertaine et d'un refus d'intégrité/identité.

Drive ne sert QUE lorsque DC est effectivement indisponible. Consigner
DC_UNAVAILABLE avec non-réception certaine ; rechercher les deux canaux. Le
helper refuse le secours si DC est disponible, si seul un échec générique est
observé, si des résultats existent ou si la réception est incertaine. Utiliser
alors plan --channel fallback, mêmes opération/nonce/paquet/exigence. Sur Drive,
qualifier compte/dossier et permission privée, rechercher le nom unique et les
résultats avant upload, noter les IDs réels, relire octets et parents. Aucun
partage élargi. En test, une panne injectée reste explicitement une simulation.

    python HELPER record --journal JOURNAL --status ETAT --channel primary --delivery CERTITUDE --reference OBSERVATION --output JOURNAL-SUIVANT

États : PREPARED, DEPOSITED, RECEIVED, VERIFIED, BLOCKED ; incidents conservés
TRANSPORT_FAILED, DC_UNAVAILABLE, RECEPTION_UNCERTAIN, VALIDATION_REJECTED.
Les journaux successifs sont nouveaux et liés par empreinte, les précédents
restent intacts. Seul confirm peut produire VERIFIED. En cas d'interruption,
relire le dernier journal valide puis collecter les résultats existants. Aucun
rejeu du générateur, du message ou de receive sur un store déjà complet.

Envoyer au chat dans le mandat humain qualifié de la mission, en réutilisant
les accords persistants déjà applicables. Appliquer la
qualification externe `references/parent-origin.md`. Work récupère et vérifie
indépendamment, produit reçu et preuve. Le parent garde le suivi jusqu'à fin
réelle/retour ou blocage explicite. Après 2–3 constats sans progrès, un contrôle
discriminant ; ne pas poller une dépendance inchangée.

Le parent relit la réponse finale dans le même chat, qualifie projet/fin,
opération/nonce et hashes ; récupère reçu et preuve depuis le stockage, calcule
leurs hashes et confronte l'observation authentifiée au contrat. Puis :

    python HELPER confirm --journal JOURNAL --receipt RECU --observation ORIGINE --input PORTEUR --requirement EXIGENCE --proof PREUVE --evidence ORIGINE-CANONIQUE --output JOURNAL-VERIFIE

confirm vérifie le reçu et appelle accept pour la copie canonique. Un dossier
DC ou Drive ne devient pas automatiquement une Source Work. Aucun retour Work
n'est intégré automatiquement dans Git. Pour les anciens plans/reçus DC v1,
utiliser `scripts/dc_transport.py` en mode compatibilité, sans bascule ni nouvel
ID d'opération ; ne pas convertir un plan en cours vers le nouveau protocole.

Pour qualifier le chat source courant, y compris une branche, appliquer
le [contrôle de source](references/SOURCE.md). Ne pas reprendre le parent
depuis un historique ni demander une URL par défaut quand le pilote qualifié
dispose des outils natifs. Sans cette capacité, conserver
SOURCE_QUALIFICATION_REQUIRED, sans inventer une identité.
