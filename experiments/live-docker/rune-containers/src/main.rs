use std::borrow::Cow;
use std::time::{Duration, Instant};

use bollard::{Docker, query_parameters::ListContainersOptionsBuilder};
use rune::{App, AppHandle, AppSpec, Cx, El, TextEdit, col, row, text};
use rune_kit::{Button, Cell, ControlSize, Kit, Table, TableColumn, TableState, TextInput};

#[derive(Default)]
struct State {
    rows: Vec<Container>,
    visible: Vec<usize>,
    query: TextEdit,
    table: TableState,
    busy: bool,
    error: String,
    handle: Option<AppHandle<State>>,
}

struct Container {
    id: String,
    names: String,
    image: String,
    state: String,
    status: String,
}

impl State {
    fn filter(&mut self) {
        let query = self.query.text.trim().to_lowercase();
        self.visible = self
            .rows
            .iter()
            .enumerate()
            .filter(|(_, row)| {
                [&row.names, &row.image, &row.state]
                    .iter()
                    .any(|cell| cell.to_lowercase().contains(&query))
            })
            .map(|(i, _)| i)
            .collect();
    }

    fn refresh(&mut self) {
        if self.busy {
            return;
        }
        let Some(handle) = self.handle.clone() else {
            return;
        };
        self.busy = true;
        self.error.clear();
        std::thread::spawn(move || {
            let result = load_containers();
            handle.update(move |s, tx| {
                tx.instant();
                s.busy = false;
                match result {
                    Ok(rows) => {
                        s.rows = rows;
                        s.filter();
                    }
                    Err(error) => s.error = format!("Cannot load containers: {error:#}"),
                }
            });
        });
    }
}

fn view(s: &State, _: &mut Cx<State>) -> El {
    let k = Kit::neutral(true);
    let table = Table::new(
        |s: &State| &s.table,
        |s: &mut State| &mut s.table,
        |s: &State| s.visible.len(),
        |s: &State, i| Cow::Borrowed(s.rows[s.visible[i]].id.as_str()),
    )
    .name("Containers")
    .column(TableColumn::new("name", "Name").width(220.0).min(100.0))
    .column(TableColumn::new("image", "Image").flex(1.2).min(120.0))
    .column(TableColumn::new("state", "State").width(100.0).min(70.0))
    .column(TableColumn::new("status", "Status").flex(1.0).min(110.0))
    .cell(|s: &State, i, column| {
        let item = &s.rows[s.visible[i]];
        Cell::text(match column {
            "name" => &item.names,
            "image" => &item.image,
            "state" => &item.state,
            _ => &item.status,
        })
    })
    .zebra(true)
    .build(s, &k)
    .key("containers")
    .grow(1.0)
    .min_h(0.0);

    let search = TextInput::new(&s.query)
        .label("Search containers")
        .placeholder("Search name, image, state…")
        .width(None)
        .height(32.0)
        .on_edit(|s: &mut State| &mut s.query)
        .on_change(|s: &mut State, tx| {
            tx.instant();
            s.filter();
        })
        .build(&k)
        .key("search")
        .grow(1.0);
    let refresh = Button::new("Refresh")
        .control_size(ControlSize::Large)
        .disabled(s.busy)
        .on_press(State::refresh)
        .build(&k)
        .key("refresh");
    let status = if s.busy {
        "Loading…".to_owned()
    } else {
        format!(
            "{} / {} containers · all states · live Bollard API",
            s.visible.len(),
            s.rows.len()
        )
    };
    let mut body = col()
        .w_full()
        .h_full()
        .min_h(0.0)
        .padding(24.0)
        .gap(16.0)
        .fill(k.c.page)
        .child(
            row()
                .w_full()
                .center_y()
                .gap(12.0)
                .child(
                    text("Containers")
                        .font(rune::TextStyle::new(26.0, 600.0))
                        .color(k.c.text_base)
                        .grow(1.0),
                )
                .child(
                    text("Rust · Rune · Bollard")
                        .font(k.ty.ui)
                        .color(k.c.text_muted),
                ),
        )
        .child(
            row()
                .w_full()
                .center_y()
                .gap(12.0)
                .child(search)
                .child(refresh),
        )
        .child(
            text(status)
                .key("status")
                .font(k.ty.ui)
                .color(k.c.text_muted),
        );
    if !s.error.is_empty() {
        body = body.child(
            text(&s.error)
                .key("error")
                .font(k.ty.ui)
                .color(k.c.danger.fg),
        );
    }
    body.child(table)
}

fn load_containers() -> anyhow::Result<Vec<Container>> {
    let started = Instant::now();
    let runtime = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()?;
    let rows = runtime.block_on(async {
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
            Ok::<_, anyhow::Error>(
                summaries
                    .into_iter()
                    .map(|item| Container {
                        id: item.id.unwrap_or_default(),
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
                    })
                    .collect::<Vec<_>>(),
            )
        })
        .await
        .map_err(|_| anyhow::anyhow!("Docker request exceeded 10 seconds"))?
    })?;
    let mut ids: Vec<_> = rows.iter().map(|row| row.id.as_str()).collect();
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
    rune::set_app_id("dev.ferrydock.RuneLiveContainers");
    let app = App::new(AppSpec::new(
        "FerryDock · Live Rune",
        (1000.0, 680.0),
        State::default,
        view,
    ));
    let handle = app.handle();
    let ready = handle.clone();
    app.init(move || State {
        handle: Some(handle),
        ..State::default()
    })
    .on_window(|window| {
        if let Ok(native) = window.with_raw_handle(|handle| format!("{:?}", handle.as_raw())) {
            eprintln!(
                "Window backend: {}",
                native.split('(').next().unwrap_or("unknown")
            );
        }
    })
    .on_ready(move |_| ready.update(|s, _| s.refresh()))
    .run();
}
