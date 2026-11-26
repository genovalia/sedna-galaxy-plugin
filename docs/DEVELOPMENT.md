# Développement et publication

Ce document complète le [README](../README.md) avec ce dont un développeur a besoin : tester le plugin en local avant de livrer, et le publier sur le Galaxy Tool Shed.

## Tester en local avec Docker

Pour une instance Galaxy jetable, qui charge l'outil directement depuis votre copie de travail :

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

4. Ouvrir `http://localhost:8090` dans un navigateur. Auto-inscription activée, pas de mot de passe admin à configurer pour un test jetable.

5. Itérer : modifier `sedna_fetch.py`/`.xml` sur l'hôte, puis `docker restart sedna-galaxy-test` (pas de rebuild, c'est un bind mount).

6. Nettoyer : `docker rm -f sedna-galaxy-test` une fois le test terminé.

Points d'attention connus de l'image `galaxy-min:26.1.2` :
- `GALAXY_CONFIG_TOOL_CONFIG_FILE` (variable d'env) n'est **pas** pris en compte ; il faut monter un `galaxy.yml` qui fixe `tool_config_file`.
- Le bind gunicorn par défaut est `localhost:8080` **à l'intérieur** du conteneur. Avec `-p HOSTPORT:8080` (réseau bridge), ça ne répond pas tant que `gravity.gunicorn.bind` n'est pas mis à `0.0.0.0:8080` dans `galaxy.yml`, suivi d'un `docker restart` (un reload seul ne suffit pas).
- Si l'outil n'arrive pas à joindre l'API Sedna depuis le conteneur alors que `curl` fonctionne depuis l'hôte : le réseau bridge Docker bloque parfois la sortie, surtout avec un VPN actif sur l'hôte. Recréer le conteneur avec `--network host` (Linux) règle généralement le problème — pas besoin de VPN pour les routes `*.apps.genovalia.ulaval.ca` / `*.genovalia.ulaval.ca`, elles sont publiques.

## Lire un job en échec dans l'historique (pendant un test)

L'outil produit ses deux sorties (échantillons et collection de VCF) dans un seul job, avec `detect_errors="exit_code"`. Si l'une des étapes VCF échoue après que les échantillons ont déjà été écrits avec succès, Galaxy marque quand même **les deux sorties** en échec. Avant de conclure que l'outil est cassé :
- vérifier directement avec `curl` l'URL amont que l'étape en échec appelle (même hôte/chemin/paramètres) — un 404/50x confirme que le problème vient de l'API Sedna/metadata-api, pas du plugin ;
- consulter les paramètres du job dans Galaxy (icône ℹ️) pour voir la commande exacte exécutée.

## Publier sur le Galaxy Tool Shed

Le [Tool Shed](https://toolshed.g2.bx.psu.edu/) est le dépôt public où une instance Galaxy va chercher un outil par nom/catégorie au lieu d'un `git clone` manuel. Le dépôt contient déjà `.shed.yml` (nom `sedna_fetch`, catégorie `Data Source`) ; `owner:` y est fixé au nom d'utilisateur du compte Tool Shed qui l'a effectivement créé (`svissault` sur le Tool Shed de test). Il ne reste qu'à créer/mettre à jour le dépôt côté Tool Shed avec [Planemo](https://planemo.readthedocs.io/).

1. Comptes requis : [Tool Shed de test](https://testtoolshed.g2.bx.psu.edu/) et [Tool Shed principal](https://toolshed.g2.bx.psu.edu/), même nom d'utilisateur sur les deux si possible (le champ `owner` de `.shed.yml` doit correspondre à ce nom d'utilisateur réel sur le shed ciblé, pas à un nom arbitraire — un dépôt appartient toujours au compte qui l'a créé).
2. `pip install planemo`, puis compléter `~/.planemo.yml` avec une clé API par shed (**User → Preferences → Manage API Key**) :

   ```yaml
   sheds:
     testtoolshed:
       key: "<clé API du Tool Shed de test>"
       username: "<votre nom d'utilisateur sur ce shed>"
     toolshed:
       key: "<clé API du Tool Shed principal>"
       username: "<votre nom d'utilisateur sur ce shed>"
   ```

   Vérifier la clé avant d'aller plus loin : `curl "https://<shed>/api/users?key=<clé>"` doit renvoyer une liste JSON (pas `401`/`err_msg`).
3. `planemo shed_lint --tools` — seule une vraie `ERROR` bloque la publication, les `WARNING` actuels sont connus et acceptés.
4. Créer d'abord sur le Tool Shed de test, jamais directement sur le principal : `planemo shed_create --shed_target testtoolshed` (le nom court est `testtoolshed`, pas `test_toolshed`). Installer ce dépôt dans une instance Galaxy jetable (voir ci-dessus) pour vérifier avant de publier ailleurs.
5. Une fois satisfait : `planemo shed_create --shed_target toolshed`.
6. Pour une mise à jour ultérieure (après avoir incrémenté `version=` dans `sedna_fetch.xml`, ou simplement changé la description/les métadonnées) : `planemo shed_update --check_diff --shed_target toolshed` (répéter sur `testtoolshed` d'abord). `shed_update` marche même sans changement de version — c'est ce qui a servi à publier la description mise à jour la première fois.

Une fois publié, l'outil s'installe depuis **Admin → Tool Sheds → Search and browse tool sheds** sur n'importe quelle instance Galaxy, sans `git clone` ni édition manuelle de `tool_conf.xml`.
