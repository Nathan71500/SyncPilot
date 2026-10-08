# Persistance Work v1

Le contrat v4 ajoute work_persistence ; v1/v2/v3 restent lisibles, mais aucun
ancien contrat ne promet implicitement une disponibilité durable dans Work.
migrate crée une proposition distincte à partir de v3, sans perdre ses paramètres.

    python SCRIPT migrate --contract V3 --persistence CONFIG --output V4-CANDIDAT
    python SCRIPT prepare --contract V4 --transport BINDING --artifacts INVENTAIRE --output JOURNAL
    python SCRIPT plan --journal JOURNAL --observation DECOUVERTE
    python SCRIPT record --journal JOURNAL --status UPLOAD_ATTEMPTED --name FICHIER --reference AUTORITE --output JOURNAL-SUIVANT
    python SCRIPT confirm --contract V4 --journal JOURNAL --observation RELECTURE-WORK --output PREUVE
    python SCRIPT accept --contract V4 --journal JOURNAL --proof PREUVE --observation RELECTURE-PARENT --origin ORIGINE --output RESULTAT
    python SCRIPT check --contract V4 --journal JOURNAL --observation NOUVELLE-RELECTURE

BINDING contient operation_id, nonce, destination, destination_thread, status
VERIFIED, proof_sha256, receipt_sha256 et authority. Le pilote le produit seulement
après confirm du vrai transport ou des décisions ; le JSON n'authentifie personne.
Pour une décision Work→Codex, le binding désigne le vrai destinataire Codex de
la preuve de transport ; la publication et sa preuve restent qualifiées côté
Work, sur la cible du contrat. Pour Codex→Work, les deux destinations sont Work.
Les couples projet/chat doivent correspondre exactement à l'un des participants.
Conserver le binding original et ses preuves : ne pas réécrire leur destinataire
pour satisfaire un contrôle de persistance.
INVENTAIRE est {files:[{name,size,sha256},...]}, dérivé du périmètre vérifié complet.
Le helper ne possède ni credentials ni réseau. Le pilote qualifie les appels.

Le journal conserve la cible, le registre, le hash canonique du contrat, le binding
de transport et le périmètre ; son persistence_id est déterministe. Ses événements
successifs sont chaînés par hash et écrits dans de nouveaux fichiers. Les sources
transportées et les preuves antérieures ne changent pas.

DECOUVERTE/RELECTURE contient persistence_id, operation_id, nonce, target exacte,
registry exacte, registry_verified et routing_verified booléens observés,
authority, observed_at UTC avec fuseau, complete booléen, outcome
available/unknown/unavailable/rejected, project_source_ingested booléen et files.
Chaque fichier observé : name, reference native retournée library-file: ou
project-file:, size, sha256 recalculé, linked, access_confirmed,
read_in_new_context. Ces trois derniers champs sont des constats d'appels réels,
pas des cases à remplir pour satisfaire le helper. Une recherche partielle ne
prouve pas une absence. Filtrer les autres fichiers de la Page hors du périmètre.

Absence complète avant une écriture : UPLOAD_ONCE. Référence existante sans lien :
LINK_EXISTING. Lien existant : REVALIDATE. Écriture incertaine ou recherche
incomplète : COLLECT_EXISTING. Persistance indisponible : BLOCKED, sans faux
DC_UNAVAILABLE. Mismatch contenu/identité : refus ; consigner VALIDATION_REJECTED
et arrêter. WRITE_NOT_COMMITTED exige une observation réelle d'échec sans commit.

La preuve porte les bindings, tous les fichiers et l'observation Work. ORIGINE
contient destination_thread, target, proof_sha256 (hash canonique du JSON de la
preuve), authority provenant de la récupération authentifiée. Le parent contrôle
les octets du reçu/proof et les bindings, puis fait une relecture indépendante.
Les timestamps ne remplacent pas les vrais appels : confirm refuse une observation
antérieure au dernier événement, future, ou vieille de plus de cinq minutes.
Seul accept produit le journal PERSISTENCE_VERIFIED dans son résultat. record
refuse cet état positif : conserver le journal retourné après le vrai contrôle
de la preuve, sans transformer une observation ou un reçu en confirmation.

Le registre contient le résultat, les références, le contrat/source exacts et la
preuve. Le pilote contrôle sa persistance et le routage effectif, conserve un
avant/après et ne l'actualise pas si un autre acteur l'a changé. Ce protocole est
séquentiel et n'offre pas de verrou distribué ou de garantie globale exactly-once.

Page Files et Sources natives de projet sont deux cibles distinctes. L'adaptateur
automatisé Pages couvre page-files ; project-sources exige un outil ou une action
manuelle observable distincte. Une Page de test privée ne qualifie pas un projet
de production. La recette doit également prouver le routage depuis un nouveau
contexte, sans sélectionner une cible personnelle comme remplacement implicite.
