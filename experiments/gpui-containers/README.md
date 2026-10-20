# Containers · Rust + gpui-pre

Petite app indépendante écrite directement avec **gpui-pre 0.3.9** et
**gpui-pre-platform 0.3.9**, snapshot de Zed `93d7456`. Aucun GPUI Kit,
GPUI Fast, catalogue d’assets Kit ou runtime Tokio applicatif. Le projet et son
verrouillage restent séparés du workspace FerryDock.

Même périmètre : liste de tous les containers, nom/image/état/statut, recherche,
Refresh manuel et erreurs visibles. La liste utilise `uniform_list` ; la vue et
le bouton utilisent `div`. Le contrôle de recherche local se branche sur
`EntityInputHandler` pour l’entrée texte native. Il gère les flèches, Home/End,
Backspace/Delete, Shift+flèches, Ctrl+A/C/X/V et le placement du curseur par clic.
Son curseur est fixe ; pas de sélection par glisser ni de défilement horizontal.

Depuis la racine FerryDock :

```sh
RUSTFLAGS='-C force-unwind-tables=no' CARGO_BUILD_JOBS=4 \
  cargo build --release --locked --manifest-path experiments/gpui-containers/Cargo.toml
./experiments/gpui-containers/target/release/gpui-containers
```

Configuration orientée taille : `opt-level=z`, LTO fat, une unité de génération,
`panic=abort`, symboles retirés, tables de déroulement désactivées pour les crates
compilées. Pas de compression de l’exécutable. Linux X11 uniquement pour cette
expérience ; sous Plasma Wayland, il passe par XWayland. Les bibliothèques système
et le pilote graphique restent nécessaires.

```sh
CONTAINER_SNAPSHOT="$PWD/.verification/gui-comparison/containers.ndjson" \
  GPUI_X11_SCALE_FACTOR=1 ./experiments/gpui-containers/target/release/gpui-containers
```

Sans snapshot, l’exécuteur de GPUI charge Docker via `async-process`. Un timer de
10 secondes borne l’opération ; le processus Docker est tué à l’abandon. Sortie
et fichier NDJSON limités à 4 Mio, stderr à 4 Kio. Le retour met l’état à jour sur
le thread graphique ; Refresh ne se chevauche pas et les dernières lignes valides
restent présentes après erreur. Aucun polling applicatif ni contrôle Docker.

Les sources du contrôle de saisie s’inspirent du patron natif de l’exemple
`gpui 0.2.2/examples/input.rs` de Zed, sous Apache-2.0 ; licence conservée dans
`LICENSE-APACHE`. Le rapport compte `src/main.rs` **et** `src/search.rs`.

Aucun test automatisé ajouté ou exécuté. Rapport et relevés locaux sous
`.verification/gui-comparison/`. L’ancienne version Kit et ses relevés sont
archivés dans `gpui-kit-baseline/` sous ce dossier. Le changement concerne aussi
le backend et les options de compilation : l’avant/après ne mesure pas Kit seul.
