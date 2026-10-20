# Comparaison minimale NanoUI / MyGo / GPUI

Trois projets indépendants et une intégration Kit archivée, sans modification de l'application FerryDock :

- [`nanoui-containers`](nanoui-containers/README.md) : Zig, NanoUI.
- [`mygo-containers`](mygo-containers/README.md) : Go, MyGo, interface native.
- GPUI Kit / GPUI Fast : version conservée sous `.verification/gui-comparison/gpui-kit-baseline/`, avec ses sources, binaire et trois relevés.
- [`gpui-containers`](gpui-containers/README.md) : Rust, gpui-pre 0.3.9 direct, sans Kit ni GPUI Fast.

Même périmètre : liste de tous les containers (nom, image, état, statut), recherche
et actualisation manuelle. Docker CLI en arrière-plan ; aucune action sur les
containers, aucun polling, aucun test automatisé ajouté ou lancé.

Le rapport local autonome est dans
`.verification/gui-comparison/rapport.html`. Les dépendances téléchargées,
la toolchain Zig, les captures et les résultats bruts restent sous ce dossier
ignoré. Les binaires et caches de chaque prototype sont aussi ignorés.

Pour répéter une mesure sur le bureau Linux, après compilation :

```sh
mkdir -p .verification/gui-comparison
docker ps --all --no-trunc --format '{{json .}}' > .verification/gui-comparison/containers.ndjson
python experiments/measure.py nanoui experiments/nanoui-containers/zig-out/bin/nanoui-containers \
  --snapshot .verification/gui-comparison/containers.ndjson \
  --output .verification/gui-comparison --run 1
python experiments/measure.py mygo experiments/mygo-containers/build/mygo-containers \
  --snapshot .verification/gui-comparison/containers.ndjson \
  --output .verification/gui-comparison --run 1
python experiments/measure.py gpui experiments/gpui-containers/target/release/gpui-containers \
  --snapshot .verification/gui-comparison/containers.ndjson \
  --output .verification/gui-comparison --run 1
```

`measure.py` ouvre une fenêtre X11/XWayland à la fois, normalise sa surface cliente à
1000 × 680 pixels, attend quatre secondes,
échantillonne pendant vingt secondes, prend une capture après la mesure et ferme
uniquement son groupe de processus. Il nécessite `xdotool`, ImageMagick et l'accès
au bureau. CPU : 100 % = un cœur logique ; mémoire : RSS et PSS via `/proc`.
L'échantillon contient les descendants vivants du processus ; le CPU comprend
aussi les enfants déjà attendus. Le pic RSS est un maximum échantillonné après
apparition de la fenêtre, pas un maximum absolu du démarrage. La capture figée
écarte Docker des mesures au repos. Le rapport utilise trois passages par app :
trois nouveaux relevés Zig avec les API portables de sa bibliothèque standard,
les trois relevés MyGo conservés, trois relevés Kit archivés et trois relevés gpui-pre,
soit douze passages courants sur le même snapshot. L'ancienne série Zig libc/timeout
est conservée dans `nanoui-libc-baseline/`, hors des graphiques. Ces mesures ne couvrent ni une charge interactive ni de grands inventaires.

Pour GPUI, le script fixe `GPUI_X11_SCALE_FACTOR=1` uniquement dans le processus
mesuré, pour conserver les quatre colonnes et une échelle comparable aux deux
autres toolkits. Le prototype lancé normalement suit l'échelle du bureau.
