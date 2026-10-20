"""Render the local measurements as one portable, dependency-free HTML file."""
import base64
from datetime import datetime
import gzip
import html
import json
from pathlib import Path
import statistics
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
APPS = {
    "nanoui": {
        "label": "Zig + NanoUI", "color": "#eec26d", "language": "Zig 0.17.0",
        "repo": "justrach/nanoui", "commit": "d61e253205472cef0854367125295d87c810c5b3",
        "binary": "experiments/nanoui-containers/zig-out/bin/nanoui-containers",
        "source": ["experiments/nanoui-containers/src/main.zig"],
        "build": ["experiments/nanoui-containers/build.zig", "experiments/nanoui-containers/build.zig.zon"],
        "flags": "ReleaseFast, strip=true, libc",
    },
    "mygo": {
        "label": "Go + MyGo", "color": "#77d7e6", "language": "Go 1.27.1",
        "repo": "egoist/mygo", "commit": "5fb60098a44a4c629cbdeac5f0ff80ce2f843c2f",
        "binary": "experiments/mygo-containers/build/mygo-containers",
        "source": ["experiments/mygo-containers/main.go"],
        "build": ["experiments/mygo-containers/go.mod"],
        "flags": "CGO_ENABLED=0, -trimpath, -tags mygo_noinspector, -ldflags '-s -w -X github.com/egoist/mygo.production=1'",
    },
    "gpui": {
        "label": "Rust + GPUI Kit", "color": "#85e2bf", "language": "Rust 1.99.0",
        "version": "gpui-kit 0.8.0 + GPUI Fast 0.1.10",
        "url": "https://docs.rs/gpui-kit/0.8.0/gpui_kit/",
        "binary": "target/release/gpui-containers",
        "source": ["experiments/gpui-containers/src/main.rs"],
        "build": ["experiments/gpui-containers/Cargo.toml"],
        "flags": "cargo build --release --locked, lto=thin, strip=true ; features gpui-fast, aucun test-support ni tree-sitter",
    },
}


def lines(paths):
    total = blank = comments = 0
    for path in paths:
        for line in (ROOT / path).read_text().splitlines():
            total += 1
            blank += not line.strip()
            comments += line.lstrip().startswith("//")
    return {"physical": total, "code": total - blank - comments, "blank": blank, "comments": comments}


def number(n, digits=2):
    return f"{n:,.{digits}f}".replace(",", " ").replace(".", ",")


def mib(n):
    return number(n / 1048576)


def image(path):
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


rows = {}
for key, app in APPS.items():
    runs = [json.loads((OUT / f"{key}-{i}.json").read_text()) for i in (1, 2, 3)]
    row = dict(app, runs=runs, lines=lines(app["source"]), build_lines=lines(app["build"]))
    for metric in ("idle_rss_median_bytes", "idle_pss_median_bytes", "idle_cpu_percent_one_core", "visible_after_seconds", "sampled_peak_rss_bytes"):
        values = [r[metric] for r in runs]
        row[metric] = {"median": statistics.median(values), "min": min(values), "max": max(values)}
    row["binary_bytes"] = (ROOT / app["binary"]).stat().st_size
    row["gzip_bytes"] = len(gzip.compress((ROOT / app["binary"]).read_bytes(), mtime=0))
    rows[key] = row

host = json.loads((OUT / "host.json").read_text())
data = {"host": host, "apps": rows, "protocol": "3 runs each; 6 initial nanoui/mygo runs alternating, 3 gpui runs added later; same snapshot, 4 s warmup, 20 s idle, 500 ms sampling"}
(OUT / "summary.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
nano, go, gpui = rows["nanoui"], rows["mygo"], rows["gpui"]
ratio = go["binary_bytes"] / nano["binary_bytes"]
stamp = datetime.now(ZoneInfo("America/Toronto")).strftime("%d/%m/%Y à %H:%M %Z")


def comparison(label, metric, formatter, unit=""):
    values = [r[metric]["median"] if isinstance(r[metric], dict) else r[metric] for r in rows.values()]
    maximum = max(values) or 1
    bars = ""
    for (key, app), value in zip(rows.items(), values):
        bars += f'<div class="bar-row"><span>{app["label"]}</span><div class="track"><i style="width:{value / maximum * 100:.3f}%;background:{app["color"]}"></i></div><strong>{formatter(value)} {unit}</strong></div>'
    return f'<article class="metric"><h3>{label}</h3>{bars}</article>'


charts = comparison("Binaire ELF · plus petit = mieux", "binary_bytes", mib, "Mio")
charts += comparison("Mémoire RSS · médiane au repos", "idle_rss_median_bytes", mib, "Mio")
charts += comparison("Mémoire PSS · partage réparti", "idle_pss_median_bytes", mib, "Mio")
charts += comparison("CPU au repos · 100 % = un cœur", "idle_cpu_percent_one_core", number, "%")

table = ""
for key, row in rows.items():
    l = row["lines"]
    table += f'''<tr><th><span class="dot" style="background:{row['color']}"></span>{row['label']}</th>
    <td>{mib(row['binary_bytes'])} Mio<br><small>{row['binary_bytes']:,} octets</small></td>
    <td>{mib(row['gzip_bytes'])} Mio</td>
    <td>{l['code']}<br><small>{l['physical']} physiques</small></td>
    <td>{row['build_lines']['physical']}</td>
    <td>{mib(row['idle_rss_median_bytes']['median'])} Mio</td>
    <td>{mib(row['idle_pss_median_bytes']['median'])} Mio</td>
    <td>{number(row['idle_cpu_percent_one_core']['median'])} %</td></tr>'''

details = ""
for key, row in rows.items():
    for r in row["runs"]:
        details += f'<tr><th>{row["label"]} · {r["run"]}</th><td>{mib(r["idle_rss_median_bytes"])} Mio</td><td>{mib(r["idle_pss_median_bytes"])} Mio</td><td>{number(r["idle_cpu_percent_one_core"])} %</td><td>{number(r["idle_seconds"])} s</td><td>{mib(r["sampled_peak_rss_bytes"])} Mio</td></tr>'

versions = ""
for key, row in rows.items():
    url = row.get("url") or f'https://github.com/{row["repo"]}/tree/{row["commit"]}'
    version = row.get("version") or f'{row["repo"]}@{row["commit"][:12]}'
    versions += f'<p><strong>{row["label"]}</strong> · {row["language"]}<br><a href="{url}">{version}</a><br><code>{html.escape(row["flags"])}</code></p>'

raw = base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode()).decode()
screenshots = ""
for key, row in rows.items():
    screenshots += f'<figure><figcaption><span class="dot" style="background:{row["color"]}"></span>{row["label"]} · fenêtre réelle</figcaption><a href="{image(OUT / f"{key}-1.png")}" target="_blank"><img alt="Liste des containers dans {row["label"]}" src="{image(OUT / f"{key}-1.png")}"></a></figure>'

page = f'''<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FerryDock · NanoUI / MyGo / GPUI</title>
<style>
:root{{--bg:#101619;--panel:#192226;--line:#304045;--text:#e4eeed;--muted:#a5b8b9;--mint:#85e2bf}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 system-ui,sans-serif}}main{{max-width:1240px;margin:auto;padding:56px 32px 64px}}a{{color:var(--mint)}}h1{{font-size:clamp(36px,5vw,62px);line-height:1.12;letter-spacing:-2px;margin:20px 0}}h2{{font-size:26px;margin:0 0 20px}}h3{{font-size:16px;margin:0 0 24px}}p{{margin:0 0 16px}}.eyebrow{{color:var(--mint);text-transform:uppercase;letter-spacing:2px;font-size:12px;font-weight:750}}.lede{{color:var(--muted);max-width:850px;font-size:19px}}.chips{{display:flex;gap:8px;flex-wrap:wrap;margin:24px 0 32px}}.chip{{background:#233337;border:1px solid var(--line);padding:5px 12px;border-radius:40px;font-size:12px}}section{{margin-top:48px}}.callout{{border-left:3px solid var(--mint);background:#192a29;padding:22px 26px;border-radius:0 12px 12px 0}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}.metric,.card{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:24px}}.bar-row{{display:grid;grid-template-columns:115px 1fr 90px;align-items:center;gap:12px;margin:15px 0;font-size:12px}}.bar-row strong{{text-align:right;font-variant-numeric:tabular-nums}}.track{{height:12px;background:#29363a;border-radius:20px;overflow:hidden}}.track i{{height:100%;display:block;border-radius:20px}}.muted,small{{color:var(--muted)}}small{{font-size:12px}}.dot{{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:8px}}.table-wrap{{overflow-x:auto;border:1px solid var(--line);border-radius:12px}}table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{padding:16px 14px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}}thead{{background:#223035}}tbody tr:last-child>*{{border-bottom:0}}th{{font-weight:600}}code{{font:12px/1.6 ui-monospace,monospace;overflow-wrap:anywhere;color:#d9e9dd}}figure{{margin:0;min-width:0}}figcaption{{margin-bottom:12px;font-size:14px;font-weight:650}}img{{width:100%;border:1px solid var(--line);border-radius:10px}}ul{{padding-left:20px}}li{{margin-bottom:9px}}details{{border:1px solid var(--line);border-radius:12px;padding:18px 22px;background:var(--panel)}}summary{{cursor:pointer;font-weight:650}}.download{{display:inline-block;margin-top:18px;padding:9px 16px;border:1px solid var(--line);border-radius:8px;text-decoration:none}}footer{{border-top:1px solid var(--line);margin-top:48px;padding-top:20px;color:var(--muted);font-size:12px}}@media(max-width:800px){{main{{padding:30px 18px}}.grid{{grid-template-columns:1fr}}.bar-row{{grid-template-columns:100px 1fr 80px}}}}@media print{{body{{--bg:#fff;--panel:#f4f6f6;--line:#ccd4d4;--text:#182728;--muted:#53686a;--mint:#226853}}main{{padding:0}}section,.metric{{break-inside:avoid}}.callout{{background:#e8f5ef}}.download{{display:none}}}}
</style></head><body><main>
<div class="eyebrow">FerryDock / laboratoire natif</div>
<h1>Trois langages.<br>La même liste de containers.</h1>
<p class="lede">Zig + NanoUI, Go + MyGo et Rust + GPUI Kit : trois petits prototypes natifs, un même inventaire Docker et des mesures prises sur ce bureau Linux.</p>
<div class="chips"><span class="chip">14 containers réels, données figées</span><span class="chip">1 000 × 680 pixels de surface cliente</span><span class="chip">3 passages par app</span><span class="chip">Aucun test ajouté ou exécuté</span></div>
<div class="callout"><strong>Trois prototypes, un même périmètre.</strong> Les médianes RSS au repos sont de {mib(nano["idle_rss_median_bytes"]["median"])} Mio pour NanoUI, {mib(go["idle_rss_median_bytes"]["median"])} Mio pour MyGo et {mib(gpui["idle_rss_median_bytes"]["median"])} Mio pour GPUI. Les cartes et le tableau ci-dessous donnent le poids, le code et le CPU de chaque app. L'avis sur le code reste qualitatif et limité à ces prototypes.</div>
<section><h2>Les chiffres</h2><div class="grid">{charts}</div><p class="muted" style="margin-top:16px;font-size:13px">Médiane des trois passages. Pour chaque passage, mémoire = médiane des échantillons ; CPU = temps CPU consommé / temps écoulé. Mio = 1 048 576 octets. Plus bas signifie moins de ressources consommées.</p></section>
<section><div class="table-wrap"><table><thead><tr><th>Prototype</th><th>Binaire ELF</th><th>Gzip du binaire</th><th>Lignes de code app</th><th>Lignes build</th><th>RSS</th><th>PSS</th><th>CPU au repos</th></tr></thead><tbody>{table}</tbody></table></div>
<p class="muted" style="font-size:13px;margin-top:14px">Lignes app : fichiers <code>main.zig</code> / <code>main.go</code> / <code>main.rs</code>, hors blancs et commentaires occupant toute la ligne. Lignes physiques : tous les retours à la ligne. Build : <code>build.zig + build.zig.zon</code> / <code>go.mod</code> / <code>Cargo.toml</code>, blancs compris. Bibliothèques, fichiers de verrouillage, README et script de mesure exclus. Les fichiers suivent les formateurs de chaque langage : une chaîne de builders Rust occupe souvent plusieurs lignes. Le nombre de lignes mesure la quantité de texte, pas sa qualité.</p></section>
<section><h2>Les trois apps</h2><p class="muted">Captures des fenêtres réelles après le premier passage, hors de l'intervalle mesuré. Les trois apps ont également affiché les 14 containers depuis Docker réel, hors mesures. Cliquez pour agrandir.</p><div class="grid">{screenshots}</div><p class="muted" style="font-size:13px;margin-top:16px">Périmètre commun : tous les containers, colonnes nom/image/état/statut, recherche, bouton Refresh, thème sombre, liste virtualisée. Aucun log, terminal, contrôle Docker ou suivi des métriques des containers. La typographie et la densité des lignes suivent les composants de chaque toolkit ; les interfaces ne sont pas des copies pixel à pixel.</p></section>
<section><h2>Qualité du code : lecture des sources</h2><div class="grid">
<article class="card"><h3 style="color:#eec26d">Zig + NanoUI</h3><p>État explicite et cycle de vie lisible : un snapshot possède son arène, puis le résultat revient sur le thread UI. La liste virtuelle ne construit que les lignes visibles. Les composants du toolkit composent le champ de recherche, le bouton et les lignes.</p><p>Le coût se trouve dans la plomberie : allocations, libération de l'arène, thread, callback C et indices filtrés sont gérés à la main. La lecture passe par libc (<code>popen/fread</code>) et la commande système <code>timeout</code>. Cela ajoute des dépendances Linux à cette petite implémentation.</p><p class="muted">Avis : compact pour du Zig natif, mais plus exigeant à faire évoluer et à relire côté mémoire/concurrence.</p></article>
<article class="card"><h3 style="color:#77d7e6">Go + MyGo</h3><p>La bibliothèque standard couvre directement JSON, fichiers et sous-processus avec délai. Une goroutine charge les lignes ; <code>RunOnMain</code> publie le résultat. <code>ui.Table</code> fournit les en-têtes et la virtualisation. La séparation chargement / filtre / vue tient dans un fichier.</p><p>Le ramasse-miettes évite le suivi manuel de la durée de vie des chaînes. Le binaire inclut le runtime Go. Un petit writer borné limite la sortie Docker ; l'ancien inventaire reste visible si une actualisation échoue.</p><p class="muted">Avis : chemin plus direct pour maintenir ce prototype, particulièrement pour quelqu'un habitué aux applications PHP/Node. Cette appréciation ne préjuge pas d'une app complète.</p></article>
<article class="card"><h3 style="color:#85e2bf">Rust + GPUI Kit</h3><p>Les composants Kit fournissent le champ de recherche, le bouton et la table virtualisée. Un <code>TableDelegate</code> décrit les colonnes et les cellules. L'état de l'app et celui de la table sont deux entités GPUI ; les résultats reviennent dans une mise à jour sur le thread graphique.</p><p>Rust garantit la durée de vie des données possédées sans ramasse-miettes. Le worker GPUI exécute la lecture ; un runtime Tokio temporaire gère le sous-processus Docker, son délai et ses flux bornés. L'interface conserve les dernières lignes valides en cas d'erreur. Aucun polling applicatif.</p><p class="muted">Avis : structure typée et composants réutilisables, mais davantage de signatures de traits, d'entités et de callbacks que dans la version Go. Cette version prend GPUI Kit 0.8.0 avec GPUI Fast 0.1.10, comme FerryDock, sans ses autres fonctionnalités.</p></article>
</div><p class="muted" style="margin-top:16px">Points communs dans les sources : I/O hors du thread graphique, actualisations sans chevauchement, sortie limitée à 4 Mio, commande Docker limitée à 10 s, erreurs affichées et absence de polling. Le chargement et le filtrage restent proportionnels au nombre de lignes ; la virtualisation concerne le rendu. Aucun test de correction, audit, profil de charge ou preuve d'accessibilité n'a été réalisé.</p></section>
<section><h2>Ce que cette comparaison mesure</h2><div class="grid"><article class="card"><h3>Un protocole court et reproductible</h3><ol><li>Copie locale de <code>docker ps --all --no-trunc --format '{{{{json .}}}}'</code>, limitée aux cinq champs utiles au prototype.</li><li>Les trois apps lisent le même fichier NDJSON : 14 lignes, empreinte SHA-256 identique.</li><li>Six lancements initiaux, ordre NanoUI / MyGo répété trois fois ; trois lancements GPUI ajoutés ensuite, sans refaire les six premiers. Toutes les compilations étaient terminées avant les mesures.</li><li>Surface cliente normalisée à 1 000 × 680 pixels ; <code>GPUI_X11_SCALE_FACTOR=1</code> pour GPUI afin de conserver la même échelle visuelle, fenêtre active, pointeur hors de la fenêtre, quatre secondes de stabilisation puis vingt secondes au repos.</li><li>Lecture de <code>/proc</code> toutes les 500 ms : RSS, PSS et temps CPU du processus et de ses descendants.</li><li>Capture après la mesure, puis fermeture du seul groupe de processus lancé.</li></ol></article><article class="card"><h3>Les limites utiles à connaître</h3><ul><li>Le CPU couvre l'affichage statique au repos. Il ne mesure ni défilement, recherche, rafraîchissements répétés, ni coût de Docker.</li><li>La RSS compte entièrement les pages partagées ; la PSS les répartit entre processus. Ni l'une ni l'autre ne couvre à elle seule toutes les allocations GPU.</li><li>CPU 100 % = un cœur logique. Un résultat affiché à 0,00 % signifie un coût inférieur à la résolution de cette fenêtre de mesure, pas une absence prouvée de travail.</li><li>Le binaire seul exclut les bibliothèques système chargées dynamiquement et le Docker CLI. Ce n'est pas la taille d'un paquet autonome.</li><li>Bureau réel partagé, caches chauds, aucun isolement des autres applications. Les chiffres ne constituent pas un classement universel.</li><li>FerryDock complet n'est pas mesuré : son périmètre dépasse largement ces listes minimales.</li></ul></article></div></section>
<section><h2>Le backend compte autant que le langage</h2><div class="callout"><p>Sur Linux, NanoUI dessine sur le <strong>CPU</strong>, puis affiche avec Cairo/GTK 3. MyGo dispose d'un rendu GPU OpenGL et d'un fallback CPU ; un lancement préalable sur cette machine a confirmé « drawn on the GPU » dans le journal MyGo (hors mesures, via MYGO_FRAME_STATS=all). NanoUI et MyGo utilisent ici GTK 3 via X11/XWayland. GPUI Fast utilise sa propre fenêtre X11 et son moteur GPU wgpu ; les mesures GPUI conservent les bibliothèques graphiques observées dans les données brutes. Les échantillons MyGo ont également chargé les bibliothèques GLX/Mesa, tandis que NanoUI n'a pas chargé OpenGL. Les mesures dépendent donc aussi du toolkit et de son backend. Le premier lancement GPUI suivait le HiDPI du bureau ; son relevé préliminaire a été écarté et les trois passages publiés ont été refaits à l’échelle 1.</p><p>NanoUI indique être né d'un portage du cœur de MyGo en Zig et conserver son architecture. Ce sont des approches apparentées, avec des niveaux de couverture différents : NanoUI mentionne notamment l'absence actuelle d'accessibilité et de plusieurs API desktop.</p><small>Sources primaires épinglées : <a href="https://github.com/justrach/nanoui/blob/d61e253205472cef0854367125295d87c810c5b3/README.md#platforms">NanoUI · plateformes</a>, <a href="https://github.com/justrach/nanoui/blob/d61e253205472cef0854367125295d87c810c5b3/README.md#credits">NanoUI · origine et crédits</a>, <a href="https://github.com/egoist/mygo/tree/5fb60098a44a4c629cbdeac5f0ff80ce2f843c2f/docs/ui">MyGo · documentation native</a>, <a href="https://docs.rs/gpui-kit/0.8.0/gpui_kit/">GPUI Kit · API 0.8.0</a>.</small></div></section>
<section><h2>Environnement et versions</h2><div class="grid"><article class="card"><p><strong>{html.escape(host['cpu'])}</strong><br>{host['logical_cpus']} CPU logiques · {number(int(host['memory_total_kib'].split()[1]) / 1048576,1)} Gio de RAM<br>{html.escape(host['system'])}<br>Plasma Wayland, affichage XWayland <code>:0</code></p><p class="muted">Aucune modification des containers, du contexte Docker, de FerryDock ou de ses dépendances. Les clones et la toolchain sont locaux à l'expérience.</p></article><article class="card">{versions}</article></div></section>
<section><details><summary>Voir les neuf passages et les données brutes</summary><div class="table-wrap" style="margin-top:20px"><table><thead><tr><th>Passage</th><th>RSS médiane</th><th>PSS médiane</th><th>CPU</th><th>Durée CPU</th><th>Pic RSS échantillonné</th></tr></thead><tbody>{details}</tbody></table></div><p class="muted" style="font-size:13px;margin-top:12px">Le pic RSS est le maximum des échantillons après apparition de la fenêtre, stabilisation incluse ; il n'est pas un pic absolu de démarrage. La durée est celle de l'intervalle au repos.</p><a class="download" href="data:application/json;base64,{raw}" download="ferrydock-gui-comparison.json">Télécharger les mesures JSON</a></details></section>
<footer>Produit le {stamp} · Rapport HTML autonome, captures et mesures intégrées. Sources dans <code>experiments/nanoui-containers</code> et <code>experiments/mygo-containers</code> et <code>experiments/gpui-containers</code>. Protocole dans <code>experiments/measure.py</code>. Aucun commit ni push.</footer>
</main></body></html>'''
(OUT / "rapport.html").write_text(page)
print(json.dumps({key: {"binary_bytes": row["binary_bytes"], "lines": row["lines"], "rss_mib": row["idle_rss_median_bytes"]["median"] / 1048576, "pss_mib": row["idle_pss_median_bytes"]["median"] / 1048576, "cpu_percent": row["idle_cpu_percent_one_core"]["median"]} for key, row in rows.items()}, indent=2))
