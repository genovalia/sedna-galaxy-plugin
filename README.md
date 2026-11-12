# sedna-galaxy-plugin

Outil Galaxy `sedna_fetch` : il charge un jeu de données [Sedna](https://catalog-backend.apps.genovalia.ulaval.ca) dans l'historique Galaxy, sous forme d'échantillons (`tabular`) et de VCF (`vcf_bgzip`).

## Contenu

- `sedna_fetch.xml` : définition de l'outil (formulaire et sorties)
- `sedna_fetch.py` : appels à l'API Sedna (échantillons, VCF)
- `sedna_options.py` : listes déroulantes (jeux de données, VCF)
- `.shed.yml` : métadonnées pour le Tool Shed

## Prérequis

- Une instance Galaxy avec le profil 23.0 ou plus récent.
- Le paquet Python `requests` (version 2.32), déclaré par l'outil et disponible dans l'environnement Python de Galaxy.
- Une connexion réseau de Galaxy vers l'API Sedna (par défaut : `https://catalog-backend.apps.genovalia.ulaval.ca`). Le DNS et le HTTPS doivent fonctionner depuis le conteneur ou le serveur Galaxy, pas seulement depuis votre poste.
- Un jeton Keycloak, seulement pour les jeux de données non publics.

## Installation

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

4. Vérifier : l'outil **Sedna: charger un jeu de données** apparaît dans la section **Genovalia** de la boîte à outils.

### Avec Docker

Si Galaxy tourne dans un conteneur, montez le dépôt en lecture seule et pointez Galaxy sur un `tool_conf.xml` qui contient la section ci-dessus. Attention : dans l'image `galaxy-min` 26.1.2, la variable d'environnement `GALAXY_CONFIG_TOOL_CONFIG_FILE` n'est pas prise en compte. Il faut monter un `galaxy.yml` qui fixe `tool_config_file` (voir la configuration de test dans le projet Sedna).

## Utilisation

- **URL de l'API Sedna** : la valeur par défaut est l'instance de production. Modifiez-la pour une autre instance.
- **Jeton Keycloak** : facultatif. Sans jeton, la liste contient les jeux de données publics. Avec un jeton, la liste contient les jeux de données auxquels votre compte a accès, avec leur nom et leur espèce.
- **Jeu de données** : liste déroulante avec filtre (tapez pour filtrer). Chaque entrée affiche le titre, le nombre d'échantillons et le nombre de variants.
- **VCF** : à remplir seulement si le jeu de données contient plusieurs VCF.

Sorties : un fichier d'échantillons (`tabular`) et un fichier VCF en texte (`vcf`). Le téléchargement compressé (`.vcf.gz`) est décompressé à la réception.

## Limites

- Le jeton est visible dans les paramètres du job.
- La tâche de génération du VCF attend au plus 1 h (`--max-wait`, 3600 s).
- Le parcours complet a été testé contre une API simulée. Il n'a pas encore été testé contre l'API Sedna de production.

## Tests de contrat

`tests/test_contracts.py` vérifie les API publiques dont dépend le plugin : le catalogue Sedna, les échantillons, les VCF, le refus de `generate-vcf` sans jeton, les titres et descriptions de la metadata-api, et la liste déroulante elle-même. Les tests sont en lecture seule et n'utilisent pas de jeton.

```bash
pip install -r requirements-dev.txt
pytest -q tests/test_contracts.py
```

Le workflow `.github/workflows/contract-tests.yml` les lance chaque jour à 11 h UTC contre la production. Il peut aussi être lancé à la main depuis l'onglet **Actions**. Un échec signifie qu'une API a changé ou est indisponible ; GitHub envoie alors une notification à l'auteur du dernier commit.

Les variables `SEDNA_URL`, `METADATA_URL` et `CONTRACT_DATASET_ID` permettent de viser une autre instance ou un autre jeu de données.
