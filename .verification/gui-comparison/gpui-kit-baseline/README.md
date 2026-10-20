# Containers · Rust + GPUI Kit

Prototype natif minimal avec la même pile UI que FerryDock : GPUI Kit **0.8.0**,
backend **GPUI Fast 0.1.10**, versions verrouillées dans `Cargo.lock`. Projet Cargo
indépendant ; le workspace et les sources de FerryDock ne sont pas modifiés.

Tous les containers, colonnes nom/image/état/statut, recherche et Refresh manuel.
Les composants Kit `Input`, `Button` et `DataTable` fournissent les contrôles et
la table virtualisée. Thème sombre, fenêtre initiale 1000 × 680.

Depuis la racine FerryDock :

```sh
CARGO_TARGET_DIR=target cargo build --release --locked \
  --manifest-path experiments/gpui-containers/Cargo.toml
./target/release/gpui-containers
```

Le target partagé réutilise les dépendances déjà compilées de FerryDock. Le
binaire est optimisé avec LTO thin et symboles retirés. Les bibliothèques
système et le pilote graphique restent nécessaires ; ce n'est pas un paquet
autonome. Le prototype n'active ni `tree-sitter`, ni `test-support`.

Pour la même source figée que les deux autres prototypes :

```sh
CONTAINER_SNAPSHOT="$PWD/.verification/gui-comparison/containers.ndjson" \
  ./target/release/gpui-containers
```

Sans cette variable, le worker GPUI lit Docker CLI. Un runtime Tokio temporaire
gère le sous-processus avec délai maximal de 10 secondes, sortie de 4 Mio maximum,
stderr de 4 Kio maximum et arrêt du processus en cas d'abandon. Fichiers NDJSON
également limités à 4 Mio. Le résultat revient sur le thread UI ; un Refresh en
cours empêche d'en lancer un second. Les erreurs restent visibles et la dernière
liste valide est conservée. Aucun polling ni contrôle des containers.

Aucun test ajouté ou exécuté. Le rapport et les mesures se trouvent sous
`.verification/gui-comparison/`.
