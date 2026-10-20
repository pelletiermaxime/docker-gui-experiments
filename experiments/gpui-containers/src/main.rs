mod search;

use futures_lite::{AsyncReadExt, future};
use gpui::{prelude::*, *};
use search::Search;
use serde::Deserialize;
use std::{fs::File, io::Read, process::Stdio, time::Duration};

const MAX_BYTES: usize = 4 << 20;
const BACKGROUND: u32 = 0x171d21;
const MUTED: u32 = 0x9eb2a8;

#[derive(Deserialize)]
#[serde(rename_all = "PascalCase")]
struct Container {
    names: String,
    image: String,
    state: String,
    status: String,
}

struct Containers {
    search: Entity<Search>,
    rows: Vec<Container>,
    visible: Vec<usize>,
    busy: bool,
    error: Option<String>,
}

impl Containers {
    fn new(window: &mut Window, cx: &mut Context<Self>) -> Self {
        let search = cx.new(Search::new);
        cx.subscribe_in(&search, window, |this, _, _, window, cx| {
            this.filter(cx);
            window.refresh();
        })
        .detach();
        let mut app = Self {
            search,
            rows: Vec::new(),
            visible: Vec::new(),
            busy: false,
            error: None,
        };
        app.refresh(window, cx);
        app
    }

    fn filter(&mut self, cx: &mut Context<Self>) {
        let query = self.search.read(cx).value().trim().to_lowercase();
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
        cx.notify();
    }

    fn refresh(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        if self.busy {
            return;
        }
        self.busy = true;
        self.error = None;
        let timer = cx.background_executor().timer(Duration::from_secs(10));
        let task = cx.background_executor().spawn(async move {
            future::race(load_containers(), async {
                timer.await;
                anyhow::bail!("Docker : délai de 10 s dépassé")
            })
            .await
        });
        cx.spawn_in(window, async move |this, cx| {
            let result = task.await;
            let _ = this.update_in(cx, |this, window, cx| {
                this.busy = false;
                match result {
                    Ok(rows) => {
                        this.rows = rows;
                        this.filter(cx);
                    }
                    Err(err) => this.error = Some(format!("Lecture impossible : {err:#}")),
                }
                cx.notify();
                window.refresh();
                window.on_next_frame(|window, _| window.refresh());
            });
        })
        .detach();
        cx.notify();
        window.refresh();
    }
}

fn cells(values: [&str; 4], heading: bool) -> Div {
    let widths = [250., 330., 110., 230.];
    div().flex().items_center().h(px(32.)).px_2().children(
        values
            .into_iter()
            .zip(widths)
            .enumerate()
            .map(|(i, (value, width))| {
                div()
                    .w(px(width))
                    .flex_shrink_0()
                    .overflow_hidden()
                    .text_ellipsis()
                    .text_color(rgb(if heading {
                        MUTED
                    } else if i == 2 && value == "running" {
                        0x74d7b1
                    } else {
                        0xe0ece7
                    }))
                    .child(value.to_owned())
            }),
    )
}

impl Render for Containers {
    fn render(&mut self, _: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        let status = if self.busy {
            "Chargement…".into()
        } else {
            format!(
                "{} / {} containers · tous les états",
                self.visible.len(),
                self.rows.len()
            )
        };
        div()
            .size_full()
            .flex()
            .flex_col()
            .p_6()
            .gap_4()
            .text_size(px(13.))
            .bg(rgb(BACKGROUND))
            .text_color(rgb(0xe0ece7))
            .child(
                div()
                    .flex()
                    .items_center()
                    .justify_between()
                    .child(div().text_size(px(26.)).child("Containers"))
                    .child(div().text_color(rgb(MUTED)).child("Rust · GPUI")),
            )
            .child(
                div()
                    .flex()
                    .items_center()
                    .gap_3()
                    .child(div().flex_1().min_w_0().child(self.search.clone()))
                    .child(
                        div()
                            .id("refresh")
                            .px_4()
                            .py_2()
                            .rounded_md()
                            .border_1()
                            .border_color(rgb(0x34433c))
                            .bg(rgb(0x1e272c))
                            .cursor_pointer()
                            .text_color(rgb(if self.busy { MUTED } else { 0xe0ece7 }))
                            .on_click(cx.listener(|this, _, window, cx| this.refresh(window, cx)))
                            .child("Refresh"),
                    ),
            )
            .child(div().text_color(rgb(MUTED)).child(status))
            .when_some(self.error.clone(), |view, error| {
                view.child(div().text_color(rgb(0xffa4a4)).child(error))
            })
            .child(cells(["Nom", "Image", "État", "Statut"], true).bg(rgb(0x1e272c)))
            .child(
                uniform_list(
                    "containers",
                    self.visible.len(),
                    cx.processor(|this, range: std::ops::Range<usize>, _, _| {
                        range
                            .map(|i| {
                                let row = &this.rows[this.visible[i]];
                                cells([&row.names, &row.image, &row.state, &row.status], false)
                                    .bg(rgb(if i % 2 == 0 { 0x1e272c } else { BACKGROUND }))
                            })
                            .collect()
                    }),
                )
                .flex_1()
                .min_h_0(),
            )
    }
}

async fn bounded(
    reader: impl futures_lite::AsyncRead + Unpin,
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

async fn load_containers() -> anyhow::Result<Vec<Container>> {
    let bytes = if let Some(path) = std::env::var_os("CONTAINER_SNAPSHOT") {
        let mut bytes = Vec::new();
        File::open(path)?
            .take((MAX_BYTES + 1) as u64)
            .read_to_end(&mut bytes)?;
        anyhow::ensure!(bytes.len() <= MAX_BYTES, "snapshot supérieur à 4 Mio");
        bytes
    } else {
        let mut child = async_process::Command::new("docker")
            .args(["ps", "--all", "--no-trunc", "--format", "{{json .}}"])
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .kill_on_drop(true)
            .spawn()?;
        let (out, err) = future::zip(
            bounded(child.stdout.take().unwrap(), MAX_BYTES),
            bounded(child.stderr.take().unwrap(), 4096),
        )
        .await;
        let (out, err) = (out?, err?);
        let status = child.status().await?;
        anyhow::ensure!(
            status.success(),
            "Docker : {status} · {}",
            String::from_utf8_lossy(&err)
        );
        out
    };
    bytes
        .split(|b| *b == b'\n')
        .filter(|line| !line.is_empty())
        .map(|line| serde_json::from_slice(line).map_err(Into::into))
        .collect()
}

fn main() {
    gpui_platform::application().run(|cx| {
        cx.on_window_closed(|cx, _| {
            if cx.windows().is_empty() {
                cx.quit();
            }
        })
        .detach();
        cx.open_window(
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
            |window, cx| cx.new(|cx| Containers::new(window, cx)),
        )
        .expect("could not open GPUI window");
        cx.activate(true);
    });
}
