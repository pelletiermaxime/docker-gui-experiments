mod search;

use bollard::{Docker, query_parameters::ListContainersOptionsBuilder};
use gpui::{prelude::*, *};
use search::Search;
use std::time::{Duration, Instant};

const MAX_ROWS: usize = 20_000;
const BACKGROUND: u32 = 0x171d21;
const MUTED: u32 = 0x9eb2a8;

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
        let task = cx
            .background_executor()
            .spawn(async move { load_containers() });
        cx.spawn_in(window, async move |this, cx| {
            let result = task.await;
            let _ = this.update_in(cx, |this, window, cx| {
                this.busy = false;
                match result {
                    Ok(rows) => {
                        this.rows = rows;
                        this.filter(cx);
                    }
                    Err(err) => this.error = Some(format!("Cannot load containers: {err:#}")),
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
            "Loading…".into()
        } else {
            format!(
                "{} / {} containers · all states · live Bollard API",
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
                    .child(
                        div()
                            .text_color(rgb(MUTED))
                            .child("Rust · gpui-pre · Bollard"),
                    ),
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
            .child(cells(["Name", "Image", "State", "Status"], true).bg(rgb(0x1e272c)))
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
                summaries.len() <= MAX_ROWS,
                "Docker returned more than {MAX_ROWS} containers"
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
                        .map(|name| name.trim_start_matches('/'))
                        .collect::<Vec<_>>()
                        .join(", "),
                    image: item.image.unwrap_or_default(),
                    state: item
                        .state
                        .map(|state| state.to_string())
                        .unwrap_or_default(),
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
                    title: Some("FerryDock · Live GPUI".into()),
                    ..Default::default()
                }),
                app_id: Some("dev.ferrydock.GpuiLiveContainers".into()),
                ..Default::default()
            },
            |window, cx| cx.new(|cx| Containers::new(window, cx)),
        )
        .expect("could not open GPUI window");
        cx.activate(true);
    });
}
