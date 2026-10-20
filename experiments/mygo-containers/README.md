# Containers · Go + MyGo

Prototype natif minimal : liste virtualisée (`ui.Table`), recherche nom/image/état,
rechargement manuel et erreurs visibles. Lecture seule de tous les containers,
sans statistiques ni actions. Les lectures s'exécutent dans une goroutine ; les
résultats rejoignent le thread UI avec `mygo.RunOnMain`.

Go 1.27.1 ; MyGo épinglé au commit
`5fb60098a44a4c629cbdeac5f0ff80ce2f843c2f` par remplacement local. Depuis la
racine FerryDock, préparer la dépendance si elle n'existe pas :

```sh
git clone https://github.com/egoist/mygo .verification/gui-comparison/deps/mygo
git -C .verification/gui-comparison/deps/mygo checkout 5fb60098a44a4c629cbdeac5f0ff80ce2f843c2f
cd experiments/mygo-containers
go mod tidy
CGO_ENABLED=0 go build -trimpath -tags mygo_noinspector -ldflags '-s -w -X github.com/egoist/mygo.production=1' -o build/mygo-containers .
./build/mygo-containers
```

Une session graphique Linux et Docker CLI sont nécessaires. Le mode natif
dessine via MyGo ; il n'utilise ni HTML ni webview. Le framework charge des
bibliothèques système dynamiques : le binaire seul n'est pas un paquet autonome.

Pour une source reproductible commune aux deux prototypes :

```sh
CONTAINER_SNAPSHOT=/chemin/containers.ndjson ./build/mygo-containers
```

Une ligne JSON par container avec `ID`, `Names`, `Image`, `State`, `Status`, au
format de `docker ps --all --no-trunc --format '{{json .}}'`. Refresh relit cette
source. Docker a un délai maximal de 10 s ; données limitées à 4 Mio et stderr
à 4 Kio. Pas de polling. Après une erreur, la dernière liste valide reste visible.
Aucun test automatisé ajouté ou exécuté, conformément à la demande.
