use gpui_kit::component::{
    ActiveTheme, Disableable, Sizable, Theme, ThemeMode,
    button::Button,
    input::{Input, InputEvent, InputState},
    table::{Column, DataTable, TableDelegate, TableState},
};
use gpui_kit::{prelude::*, *};
use serde::Deserialize;
use std::{fs::File, io::Read, process::Stdio, time::Duration};
use tokio::io::AsyncReadExt;

const MAX_BYTES: usize = 4 << 20;

#[derive(Deserialize)]
#[serde(rename_all = "PascalCase")]
struct Container {
    names: String,
    image: String,
    state: String,
    status: String,
}

#[derive(Default)]
struct Containers {
    rows: Vec<Container>,
    visible: Vec<usize>,
}

impl Containers {
    fn filter(&mut self, query: &str) {
        let query = query.trim().to_lowercase();
        self.visible = self
            .rows
            .iter()
            .enumerate()
            .filter_map(|(i, row)| {
                [&row.names, &row.image, &row.state]
                    .iter()
                    .any(|s| s.to_lowercase().contains(&query))
                    .then_some(i)
            })
            .collect();
    }
}

impl TableDelegate for Containers {
    fn columns_count(&self, _: &App) -> usize {
        4
    }
    fn rows_count(&self, _: &App) -> usize {
        self.visible.len()
    }
    fn column(&self, index: usize, _: &App) -> Column {
        let (id, label, width) = [
            ("name", "Nom", 250.),
            ("image", "Image", 330.),
            ("state", "État", 110.),
            ("status", "Statut", 240.),
        ][index];
        Column::new(id, label)
            .width(px(width))
            .resizable(false)
            .movable(false)
    }
    fn render_td(
        &mut self,
        row: usize,
        column: usize,
        _: &mut Window,
        cx: &mut Context<TableState<Self>>,
    ) -> impl IntoElement {
        let row = &self.rows[self.visible[row]];
        let value = [&row.names, &row.image, &row.state, &row.status][column];
        div()
            .w_full()
            .text_ellipsis()
            .text_size(px(13.))
            .text_color(if column == 2 && row.state == "running" {
                rgb(0x74d7b1).into()
            } else {
                cx.theme().foreground
            })
            .child(value.clone())
    }
}

struct ContainerApp {
    search: Entity<InputState>,
    table: Entity<TableState<Containers>>,
    busy: bool,
    error: Option<String>,
}

impl ContainerApp {
    fn new(window: &mut Window, cx: &mut Context<Self>) -> Self {
        let search =
            cx.new(|cx| InputState::new(window, cx).placeholder("Rechercher nom, image ou état…"));
        let table = cx.new(|cx| {
            TableState::new(Containers::default(), window, cx)
                .sortable(false)
                .col_movable(false)
                .col_selectable(false)
                .row_selectable(false)
        });
        cx.subscribe(&search, |this, _, event, cx| {
            if matches!(event, InputEvent::Change) {
                this.filter(cx);
            }
        })
        .detach();
        let mut app = Self {
            search,
            table,
            busy: false,
            error: None,
        };
        app.refresh(cx);
        app
    }

    fn filter(&mut self, cx: &mut Context<Self>) {
        let query = self.search.read(cx).value().to_string();
        self.table.update(cx, |table, cx| {
            table.delegate_mut().filter(&query);
            table.scroll_to_row(0, cx);
            cx.notify();
        });
        cx.notify();
    }

    fn refresh(&mut self, cx: &mut Context<Self>) {
        if self.busy {
            return;
        }
        self.busy = true;
        self.error = None;
        let task = cx.background_executor().spawn(async { load_containers() });
        cx.spawn(async move |this, cx| {
            let result = task.await;
            let _ = this.update(cx, |this, cx| {
                this.busy = false;
                match result {
                    Ok(rows) => {
                        this.table
                            .update(cx, |table, _| table.delegate_mut().rows = rows);
                        this.filter(cx);
                    }
                    Err(err) => this.error = Some(format!("Lecture impossible : {err:#}")),
                }
                cx.notify();
            });
        })
        .detach();
        cx.notify();
    }
}

impl Render for ContainerApp {
    fn render(&mut self, _: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        let data = self.table.read(cx).delegate();
        let status = if self.busy {
            "Chargement…".into()
        } else {
            format!(
                "{} / {} containers · tous les états",
                data.visible.len(),
                data.rows.len()
            )
        };
        div()
            .size_full()
            .flex()
            .flex_col()
            .p_6()
            .gap_4()
            .bg(cx.theme().background)
            .text_color(cx.theme().foreground)
            .child(
                div()
                    .flex()
                    .items_center()
                    .justify_between()
                    .child(
                        div()
                            .text_size(px(26.))
                            .font_weight(FontWeight::BOLD)
                            .child("Containers"),
                    )
                    .child(
                        div()
                            .text_sm()
                            .text_color(cx.theme().muted_foreground)
                            .child("Rust · GPUI Kit"),
                    ),
            )
            .child(
                div()
                    .flex()
                    .items_center()
                    .gap_3()
                    .child(div().flex_1().child(Input::new(&self.search)))
                    .child(
                        Button::new("refresh")
                            .label("Refresh")
                            .disabled(self.busy)
                            .on_click(cx.listener(|this, _, _, cx| this.refresh(cx))),
                    ),
            )
            .child(
                div()
                    .text_sm()
                    .text_color(cx.theme().muted_foreground)
                    .child(status),
            )
            .when_some(self.error.clone(), |view, error| {
                view.child(div().text_sm().text_color(cx.theme().danger).child(error))
            })
            .child(
                div()
                    .flex_1()
                    .min_h_0()
                    .child(DataTable::new(&self.table).small().bordered(false)),
            )
    }
}

async fn bounded(
    reader: impl tokio::io::AsyncRead + Unpin,
    limit: usize,
) -> anyhow::Result<Vec<u8>> {
    let mut bytes = Vec::new();
    reader
        .take((limit + 1) as u64)
        .read_to_end(&mut bytes)
        .await?;
    anyhow::ensure!(bytes.len() <= limit, "sortie supérieure à {limit} octets");
    Ok(bytes)
}

fn load_containers() -> anyhow::Result<Vec<Container>> {
    let bytes = if let Some(path) = std::env::var_os("CONTAINER_SNAPSHOT") {
        let mut bytes = Vec::new();
        File::open(path)?
            .take((MAX_BYTES + 1) as u64)
            .read_to_end(&mut bytes)?;
        anyhow::ensure!(bytes.len() <= MAX_BYTES, "snapshot supérieur à 4 Mio");
        bytes
    } else {
        // The temporary runtime lives on a GPUI background worker, never on the UI thread.
        tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()?
            .block_on(async {
                let mut child = tokio::process::Command::new("docker")
                    .args(["ps", "--all", "--no-trunc", "--format", "{{json .}}"])
                    .stdout(Stdio::piped())
                    .stderr(Stdio::piped())
                    .kill_on_drop(true)
                    .spawn()?;
                let operation = async {
                    let (out, err) = tokio::try_join!(
                        bounded(child.stdout.take().unwrap(), MAX_BYTES),
                        bounded(child.stderr.take().unwrap(), 4096)
                    )?;
                    let status = child.wait().await?;
                    anyhow::ensure!(
                        status.success(),
                        "Docker : {status} · {}",
                        String::from_utf8_lossy(&err)
                    );
                    Ok::<_, anyhow::Error>(out)
                };
                tokio::time::timeout(Duration::from_secs(10), operation).await?
            })?
    };
    bytes
        .split(|b| *b == b'\n')
        .filter(|line| !line.is_empty())
        .map(|line| serde_json::from_slice(line).map_err(Into::into))
        .collect()
}

fn main() {
    gpui_kit::application()
        .with_assets(gpui_kit::assets::Assets)
        .run(|cx| {
            gpui_kit::init(cx);
            Theme::change(ThemeMode::Dark, None, cx);
            cx.on_window_closed(|cx, _| {
                if cx.windows().is_empty() {
                    cx.quit();
                }
            })
            .detach();
            gpui_kit::open_window(
                WindowOptions {
                    window_bounds: Some(WindowBounds::Windowed(Bounds::centered(
                        None,
                        size(px(1000.), px(680.)),
                        cx,
                    ))),
                    titlebar: Some(TitlebarOptions {
                        title: Some("FerryDock · GPUI".into()),
                        ..Default::default()
                    }),
                    app_id: Some("dev.ferrydock.GpuiContainers".into()),
                    ..Default::default()
                },
                cx,
                |window, cx| cx.new(|cx| ContainerApp::new(window, cx)),
            )
            .expect("could not open GPUI window");
            cx.activate(true);
        });
}
