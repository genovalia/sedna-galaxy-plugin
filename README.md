# sedna-galaxy-plugin

Outil Galaxy `sedna_fetch` : il charge un jeu de données [Sedna](https://catalog-backend.apps.genovalia.ulaval.ca) dans l'historique Galaxy, sous forme d'échantillons (`tabular`) et de VCF (`vcf`).

Statut : testé en local (Docker) et contre l'API Sedna de production (échantillons + VCF, metadata-api v2) — voir [Tests de contrat](#tests-de-contrat) et [Limites](#limites).

## Contenu

- `sedna_fetch.xml` : définition de l'outil (formulaire et sorties)
- `sedna_fetch.py` : appels à l'API Sedna (échantillons, VCF)
- `sedna_options.py` : listes déroulantes (jeux de données, VCF), titres depuis la metadata-api v2
- `.shed.yml` : métadonnées pour le Tool Shed
- `tests/test_contracts.py` : tests de contrat en lecture seule contre les API de production

## Prérequis

- Une instance Galaxy avec le profil 23.0 ou plus récent.
- Le paquet Python `requests` (version 2.32), déclaré par l'outil et disponible dans l'environnement Python de Galaxy.
- Une connexion réseau de Galaxy vers l'API Sedna (par défaut : `https://catalog-backend.apps.genovalia.ulaval.ca`) et vers la metadata-api (`https://metadata.genovalia.ulaval.ca`). Le DNS et le HTTPS doivent fonctionner depuis le conteneur ou le serveur Galaxy, pas seulement depuis votre poste. Ces deux routes sont publiques (`*.apps.genovalia.ulaval.ca` / `*.genovalia.ulaval.ca`) : aucun VPN n'est nécessaire pour les atteindre, contrairement à l'API OpenShift ou à la base Postgres.
- Un jeton Keycloak, seulement pour les jeux de données non publics.

## Installation (instance Galaxy de production/partagée)

1. Cloner le dépôt sur le serveur qui exécute Galaxy :

   ```bash
   git clone git@github.com:genovalia/sedna-galaxy-plugin.git
   ```

2. Ajouter l'outil au fichier `tool_conf.xml` de Galaxy :

   ```xml
   <section id="genovalia" name="Genovalia">
       <tool file="/chemin/vers/sedna-galaxy-plugin/sedna_fetch.xml" />
   </section>
   ```

3. Redémarrer Galaxy.

4. Vérifier : l'outil **Sedna: charger un jeu de données** apparaît dans la section **Genovalia** de la boîte à outils, et les logs contiennent `Loaded tool id: sedna_fetch`.

## Tester en local avec Docker (sans toucher à une instance partagée)

Pour une instance Galaxy jetable, qui charge l'outil directement depuis votre copie de travail (utile pour développer ou faire tester quelqu'un avant de livrer) :

1. Préparer deux fichiers de config sur l'hôte (en dehors du dépôt, par ex. dans un répertoire scratch) :

   `tool_conf.xml` :
   ```xml
   <toolbox>
       <section id="genovalia" name="Genovalia">
           <tool file="/sedna-galaxy-plugin/sedna_fetch.xml" />
       </section>
   </toolbox>
   ```

   `galaxy.yml` :
   ```yaml
   galaxy:
     tool_config_file: /galaxy/server/config/tool_conf.xml
     admin_users: admin@local.test
     allow_user_creation: true
     allow_user_deletion: false
     require_login: false

   gravity:
     gunicorn:
       bind: 127.0.0.1:8090   # ou 0.0.0.0:8080 si vous gardez le réseau bridge Docker, voir note ci-dessous
   ```

2. Lancer le conteneur (réseau host, le plus simple pour que l'outil puisse atteindre les API Sedna/metadata-api) :

   ```bash
   docker run -d --name sedna-galaxy-test --network host \
     -v /chemin/vers/sedna-galaxy-plugin:/sedna-galaxy-plugin:ro \
     -v /chemin/vers/tool_conf.xml:/galaxy/server/config/tool_conf.xml:ro \
     -v /chemin/vers/galaxy.yml:/galaxy/server/config/galaxy.yml:ro \
     quay.io/galaxyproject/galaxy-min:26.1.2
   ```

3. Attendre ~45 s puis vérifier : `docker logs sedna-galaxy-test 2>&1 | grep "Loaded tool id: sedna_fetch"`.

4. Ouvrir `http://localhost:8090` dans un navigateur (ou l'IP/port choisis). Auto-inscription activée, pas de mot de passe admin à configurer pour un test jetable.

5. Itérer : modifier `sedna_fetch.py`/`.xml` sur l'hôte, puis `docker restart sedna-galaxy-test` (pas de rebuild, c'est un bind mount).

6. Nettoyer : `docker rm -f sedna-galaxy-test` une fois le test terminé — c'est une instance jetable, pas un service à laisser tourner.

Points d'attention connus de l'image `galaxy-min:26.1.2` :
- `GALAXY_CONFIG_TOOL_CONFIG_FILE` (variable d'env) n'est **pas** pris en compte ; il faut monter un `galaxy.yml` qui fixe `tool_config_file`.
- Le bind gunicorn par défaut est `localhost:8080` **à l'intérieur** du conteneur. Avec `-p HOSTPORT:8080` (réseau bridge), ça ne répond pas tant que `gravity.gunicorn.bind` n'est pas mis à `0.0.0.0:8080` dans `galaxy.yml`, suivi d'un `docker restart` (un reload seul ne suffit pas).
- Si l'outil n'arrive pas à joindre l'API Sedna depuis le conteneur alors que `curl` fonctionne depuis l'hôte : le réseau bridge Docker bloque parfois la sortie, surtout avec un VPN actif sur l'hôte. Recréer le conteneur avec `--network host` (Linux) règle généralement le problème — pas besoin de VPN pour les routes `*.apps.genovalia.ulaval.ca` / `*.genovalia.ulaval.ca`, elles sont publiques.

## Utilisation

- **URL de l'API Sedna** : la valeur par défaut est l'instance de production. Modifiez-la pour une autre instance.
- **Jeton Keycloak** : facultatif. Sans jeton, la liste contient les jeux de données publics. Avec un jeton, la liste contient les jeux de données auxquels votre compte a accès, avec leur nom et leur espèce. Le jeton expire vite et reste visible dans les paramètres du job — ne pas réutiliser un job existant comme modèle sans le retirer/regénérer.
- **Jeu de données** : liste déroulante avec filtre (tapez pour filtrer). Chaque entrée affiche le titre, le nombre d'échantillons et le nombre de variants, tiré de la metadata-api v2.
- **VCF** : à remplir seulement si le jeu de données contient plusieurs VCF.

Sorties : un fichier d'échantillons (`tabular`) et un fichier VCF (`vcf`). Le téléchargement compressé (`.vcf.gz`) est décompressé à la réception.

### Lire un job en échec dans l'historique

L'outil produit ses deux sorties (échantillons et VCF) dans un seul job, avec `detect_errors="exit_code"`. Si l'étape VCF échoue après que les échantillons ont déjà été écrits avec succès, Galaxy marque quand même **les deux sorties** en échec (le fichier échantillons est bien présent sur disque, mais le job entier est rouge). Avant de conclure que l'outil est cassé :
- vérifier directement avec `curl` l'URL amont que l'étape en échec appelle (même hôte/chemin/paramètres) — un 404/50x confirme que le problème vient de l'API Sedna/metadata-api, pas du plugin ;
- consulter les paramètres du job dans Galaxy (icône ℹ️) pour voir la commande exacte exécutée et l'URL construite.

## Limites

- Le jeton est visible dans les paramètres du job.
- La tâche de génération du VCF attend au plus 1 h (`--max-wait`, 3600 s).
- Un seul job produit les deux sorties ; un échec sur l'une fait échouer visuellement les deux (voir ci-dessus).

## Tests de contrat

`tests/test_contracts.py` vérifie les API publiques dont dépend le plugin : le catalogue Sedna, les échantillons, les VCF, le refus de `generate-vcf` sans jeton, les titres et descriptions de la metadata-api v2, et la liste déroulante elle-même. Les tests sont en lecture seule et n'utilisent pas de jeton.

```bash
pip install -r requirements-dev.txt
pytest -q tests/test_contracts.py
```

Le workflow `.github/workflows/contract-tests.yml` les lance chaque jour à 11 h UTC contre la production. Il peut aussi être lancé à la main depuis l'onglet **Actions**. Un échec signifie qu'une API a changé ou est indisponible ; GitHub envoie alors une notification à l'auteur du dernier commit.

Les variables `SEDNA_URL`, `METADATA_URL` et `CONTRACT_DATASET_ID` permettent de viser une autre instance ou un autre jeu de données.
