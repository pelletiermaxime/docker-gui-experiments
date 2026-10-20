use bollard::{Docker, query_parameters::ListContainersOptionsBuilder};
use slint::{ComponentHandle, Model, ModelRc, StandardListViewItem, VecModel};
use std::time::{Duration, Instant};

slint::slint! {
    import { Button, LineEdit, StandardTableView, Palette } from "std-widgets.slint";
    export component ContainersWindow inherits Window {
        title: "FerryDock · Live Slint";
        width: 1000px;
        height: 680px;
        background: #171d21;
        default-font-size: 13px;
        in property <[[StandardListViewItem]]> rows;
        in property <[[StandardListViewItem]]> all-rows;
        in-out property <string> query;
        in property <int> total;
        in property <bool> busy;
        in property <string> error;
        callback refresh();
        callback filter();
        init => { Palette.color-scheme = ColorScheme.dark; }
        VerticalLayout {
            padding: 24px;
            spacing: 16px;
            HorizontalLayout {
                height: 36px;
                Text { text: "Containers"; font-size: 26px; color: #e0ece7; }
                Text { text: "Rust · Slint software · Bollard"; horizontal-alignment: right; color: #9fb2a8; }
            }
            HorizontalLayout {
                spacing: 12px;
                search := LineEdit {
                    placeholder-text: "Search name, image, state…";
                    text <=> root.query;
                    edited => { root.filter(); }
                }
                Button { text: "Refresh"; enabled: !root.busy; clicked => { root.refresh(); } }
            }
            Text {
                text: root.busy ? "Loading…" : root.rows.length + " / " + root.total + " containers · all states · live Bollard API";
                color: #9fb2a8;
            }
            if root.error != "": Text { text: root.error; color: #ffa4a4; wrap: word-wrap; }
            StandardTableView {
                columns: [
                    { title: "Name", width: 220px },
                    { title: "Image", width: 300px },
                    { title: "State", width: 100px },
                    { title: "Status", width: 250px },
                ];
                rows: root.rows;
                vertical-stretch: 1;
            }
        }
    }
}

struct Container {
    names: String,
    image: String,
    state: String,
    status: String,
}

fn filter(ui: &ContainersWindow) {
    let query = ui.get_query().trim().to_lowercase();
    let visible = ui
        .get_all_rows()
        .iter()
        .filter(|row| {
            row.iter()
                .take(3)
                .any(|cell| cell.text.to_lowercase().contains(&query))
        })
        .collect::<Vec<_>>();
    ui.set_rows(ModelRc::new(VecModel::from(visible)));
}

fn refresh(ui: &ContainersWindow) {
    if ui.get_busy() {
        return;
    }
    ui.set_busy(true);
    ui.set_error("".into());
    let weak = ui.as_weak();
    std::thread::spawn(move || {
        let result = load_containers();
        let _ = weak.upgrade_in_event_loop(move |ui| {
            ui.set_busy(false);
            match result {
                Ok(rows) => {
                    ui.set_total(rows.len() as i32);
                    let model = rows
                        .iter()
                        .map(|r| {
                            ModelRc::new(VecModel::from(
                                [&r.names, &r.image, &r.state, &r.status]
                                    .map(|s| StandardListViewItem::from(s.as_str()))
                                    .to_vec(),
                            ))
                        })
                        .collect::<Vec<_>>();
                    ui.set_all_rows(ModelRc::new(VecModel::from(model)));
                    filter(&ui);
                }
                Err(error) => ui.set_error(format!("Cannot load containers: {error:#}").into()),
            }
        });
    });
}

fn load_containers() -> anyhow::Result<Vec<Container>> {
    let started = Instant::now();
    let runtime = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()?;
    let (rows, mut ids): (Vec<Container>, Vec<String>) = runtime.block_on(async {
        tokio::time::timeout(Duration::from_secs(10), async {
            let docker = Docker::connect_with_defaults()?.negotiate_version().await?;
            let summaries = docker
                .list_containers(Some(
                    ListContainersOptionsBuilder::default().all(true).build(),
                ))
                .await?;
            anyhow::ensure!(
                summaries.len() <= 20_000,
                "Docker returned more than 20000 containers"
            );
            let mut rows = Vec::with_capacity(summaries.len());
            let mut ids = Vec::with_capacity(summaries.len());
            for item in summaries {
                ids.push(item.id.unwrap_or_default());
                rows.push(Container {
                    names: item
                        .names
                        .unwrap_or_default()
                        .iter()
                        .map(|n| n.trim_start_matches('/'))
                        .collect::<Vec<_>>()
                        .join(", "),
                    image: item.image.unwrap_or_default(),
                    state: item.state.map(|s| s.to_string()).unwrap_or_default(),
                    status: item.status.unwrap_or_default(),
                });
            }
            Ok::<_, anyhow::Error>((rows, ids))
        })
        .await
        .map_err(|_| anyhow::anyhow!("Docker request exceeded 10 seconds"))?
    })?;
    ids.sort_unstable();
    eprintln!(
        "Docker load: count={} elapsed_ms={} ids={}",
        rows.len(),
        started.elapsed().as_millis(),
        ids.join(",")
    );
    Ok(rows)
}

fn main() -> anyhow::Result<()> {
    slint::BackendSelector::new()
        .backend_name("winit".into())
        .renderer_name("software".into())
        .select()?;
    let ui = ContainersWindow::new()?;
    let weak = ui.as_weak();
    ui.on_filter(move || {
        if let Some(ui) = weak.upgrade() {
            filter(&ui);
        }
    });
    let weak = ui.as_weak();
    ui.on_refresh(move || {
        if let Some(ui) = weak.upgrade() {
            refresh(&ui);
        }
    });
    refresh(&ui);
    ui.run()?;
    Ok(())
}
