# sedna-galaxy-plugin

Outil Galaxy `sedna_fetch` : il charge un jeu de données [Sedna](https://catalog-backend.apps.genovalia.ulaval.ca) dans l'historique Galaxy, sous forme d'échantillons (`tabular`) et de tous ses VCF (collection `vcf`).

Pour parcourir visuellement les jeux de données disponibles avant de les charger, voir le catalogue Sedna : **https://sedna.apps.genovalia.ulaval.ca/en/catalogue**. L'identifiant affiché sur cette page (ex. `alcant1`) est celui à retrouver dans la liste déroulante **Jeu de données** de l'outil.

## Prérequis

- Une instance Galaxy avec le profil 23.0 ou plus récent, et le paquet Python `requests` (2.32) disponible.
- Une connexion réseau de Galaxy vers `catalog-backend.apps.genovalia.ulaval.ca` et `metadata.genovalia.ulaval.ca` (routes publiques, aucun VPN requis).
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

3. Redémarrer Galaxy, puis vérifier : l'outil **Sedna: charger un jeu de données** apparaît dans la section **Genovalia** de la boîte à outils.

## Utilisation

- **Jeton Keycloak** : facultatif. Sans jeton, la liste contient les jeux de données publics. Avec un jeton, la liste contient les jeux de données auxquels votre compte a accès. Le jeton expire vite et reste visible dans les paramètres du job.
- **Jeu de données** : liste déroulante avec filtre (tapez pour filtrer).

Sorties : un fichier d'échantillons (`tabular`) et une collection de fichiers VCF — un par VCF disponible pour le jeu de données (la plupart n'en ont qu'un). L'URL de l'API Sedna n'est pas un champ du formulaire : elle est fixée dans le code et vérifiée chaque jour par les tests de contrat.

## Limites

- Le jeton est visible dans les paramètres du job.
- La tâche de génération de chaque VCF attend au plus 1 h.
- Les deux sorties viennent d'un seul job : un échec sur un VCF marque aussi les échantillons en échec dans l'historique, même si le fichier échantillons a bien été écrit (voir [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) pour diagnostiquer).

## Tests de contrat

`tests/test_contracts.py` vérifie les API publiques dont dépend le plugin (catalogue Sedna, échantillons, VCF, metadata-api v2, liste déroulante, cohérence de l'URL codée en dur). Lecture seule, sans jeton :

```bash
pip install -r requirements-dev.txt
pytest -q tests/test_contracts.py
```

Le workflow `.github/workflows/contract-tests.yml` les lance chaque jour à 11 h UTC contre la production (déclenchable aussi à la main depuis l'onglet **Actions**) et notifie le canal Slack `github-ci` en cas d'échec.

## Pour aller plus loin

[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) : tester le plugin en local avec Docker, et le publier sur le Galaxy Tool Shed.
