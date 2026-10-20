// Native input pattern adapted from GPUI 0.2.2 examples/input.rs (Zed, Apache-2.0).
use gpui::{prelude::*, *};
use std::ops::Range;

pub struct Search {
    focus: FocusHandle,
    text: String,
    anchor: usize,
    cursor: usize,
    marked: Option<Range<usize>>,
    line: Option<ShapedLine>,
    bounds: Option<Bounds<Pixels>>,
}

impl EventEmitter<()> for Search {}

impl Search {
    pub fn new(cx: &mut Context<Self>) -> Self {
        Self {
            focus: cx.focus_handle(),
            text: String::new(),
            anchor: 0,
            cursor: 0,
            marked: None,
            line: None,
            bounds: None,
        }
    }
    pub fn value(&self) -> &str {
        &self.text
    }
    fn selection(&self) -> Range<usize> {
        self.anchor.min(self.cursor)..self.anchor.max(self.cursor)
    }
    fn utf16(&self, byte: usize) -> usize {
        self.text[..byte].encode_utf16().count()
    }
    fn byte(&self, utf16: usize) -> usize {
        let mut offset = 0;
        for (i, ch) in self.text.char_indices() {
            if offset >= utf16 {
                return i;
            }
            offset += ch.len_utf16();
        }
        self.text.len()
    }
    fn bytes(&self, range: Range<usize>) -> Range<usize> {
        self.byte(range.start)..self.byte(range.end)
    }
    fn replace(&mut self, range: Range<usize>, text: &str, cx: &mut Context<Self>) {
        let text = text.replace(['\n', '\r'], " ");
        self.text.replace_range(range.clone(), &text);
        self.cursor = range.start + text.len();
        self.anchor = self.cursor;
        self.marked = None;
        self.line = None;
        cx.emit(());
        cx.notify();
    }
    fn key(&mut self, event: &KeyDownEvent, window: &mut Window, cx: &mut Context<Self>) {
        let key = event.keystroke.key.as_str();
        let selection = self.selection();
        let previous = self.text[..self.cursor]
            .char_indices()
            .last()
            .map_or(0, |(i, _)| i);
        let next = self.text[self.cursor..]
            .chars()
            .next()
            .map_or(self.cursor, |ch| self.cursor + ch.len_utf8());
        if event.keystroke.modifiers.control {
            match key {
                "a" => {
                    self.anchor = 0;
                    self.cursor = self.text.len();
                }
                "v" => {
                    if let Some(text) = cx.read_from_clipboard().and_then(|item| item.text()) {
                        self.replace(selection, &text, cx);
                    }
                }
                "c" | "x" => {
                    cx.write_to_clipboard(ClipboardItem::new_string(
                        self.text[selection.clone()].to_owned(),
                    ));
                    if key == "x" {
                        self.replace(selection, "", cx);
                    }
                }
                _ => return,
            }
        } else {
            match key {
                "backspace" => self.replace(
                    if selection.is_empty() {
                        previous..self.cursor
                    } else {
                        selection
                    },
                    "",
                    cx,
                ),
                "delete" => self.replace(
                    if selection.is_empty() {
                        self.cursor..next
                    } else {
                        selection
                    },
                    "",
                    cx,
                ),
                "left" | "right" | "home" | "end" => {
                    self.cursor = match key {
                        "home" => 0,
                        "end" => self.text.len(),
                        "left" if !event.keystroke.modifiers.shift && !selection.is_empty() => {
                            selection.start
                        }
                        "right" if !event.keystroke.modifiers.shift && !selection.is_empty() => {
                            selection.end
                        }
                        "left" => previous,
                        _ => next,
                    };
                    if !event.keystroke.modifiers.shift {
                        self.anchor = self.cursor;
                    }
                }
                _ => return,
            }
        }
        window.prevent_default();
        cx.stop_propagation();
        cx.notify();
    }
}

impl EntityInputHandler for Search {
    fn text_for_range(
        &mut self,
        range: Range<usize>,
        actual: &mut Option<Range<usize>>,
        _: &mut Window,
        _: &mut Context<Self>,
    ) -> Option<String> {
        let range = self.bytes(range);
        *actual = Some(self.utf16(range.start)..self.utf16(range.end));
        Some(self.text[range].to_owned())
    }
    fn selected_text_range(
        &mut self,
        _: bool,
        _: &mut Window,
        _: &mut Context<Self>,
    ) -> Option<UTF16Selection> {
        let range = self.selection();
        Some(UTF16Selection {
            range: self.utf16(range.start)..self.utf16(range.end),
            reversed: self.anchor > self.cursor,
        })
    }
    fn marked_text_range(&self, _: &mut Window, _: &mut Context<Self>) -> Option<Range<usize>> {
        self.marked
            .as_ref()
            .map(|range| self.utf16(range.start)..self.utf16(range.end))
    }
    fn unmark_text(&mut self, _: &mut Window, _: &mut Context<Self>) {
        self.marked = None;
    }
    fn replace_text_in_range(
        &mut self,
        range: Option<Range<usize>>,
        text: &str,
        _: &mut Window,
        cx: &mut Context<Self>,
    ) {
        let range = range
            .map(|r| self.bytes(r))
            .or(self.marked.clone())
            .unwrap_or(self.selection());
        self.replace(range, text, cx);
    }
    fn replace_and_mark_text_in_range(
        &mut self,
        range: Option<Range<usize>>,
        text: &str,
        selection: Option<Range<usize>>,
        _: &mut Window,
        cx: &mut Context<Self>,
    ) {
        let range = range
            .map(|r| self.bytes(r))
            .or(self.marked.clone())
            .unwrap_or(self.selection());
        let start = range.start;
        self.replace(range, text, cx);
        self.marked = Some(start..self.cursor);
        if let Some(range) = selection {
            let prefix = self.utf16(start);
            self.anchor = self.byte(prefix + range.start);
            self.cursor = self.byte(prefix + range.end);
        }
    }
    fn bounds_for_range(
        &mut self,
        range: Range<usize>,
        bounds: Bounds<Pixels>,
        _: &mut Window,
        _: &mut Context<Self>,
    ) -> Option<Bounds<Pixels>> {
        let range = self.bytes(range);
        let line = self.line.as_ref()?;
        Some(Bounds::from_corners(
            point(bounds.left() + line.x_for_index(range.start), bounds.top()),
            point(bounds.left() + line.x_for_index(range.end), bounds.bottom()),
        ))
    }
    fn character_index_for_point(
        &mut self,
        position: Point<Pixels>,
        _: &mut Window,
        _: &mut Context<Self>,
    ) -> Option<usize> {
        Some(
            self.utf16(
                self.line
                    .as_ref()?
                    .closest_index_for_x(position.x - self.bounds?.left())
                    .min(self.text.len()),
            ),
        )
    }
}

impl Render for Search {
    fn render(&mut self, _: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        let input = cx.entity();
        let paint_input = input.clone();
        div()
            .id("search")
            .track_focus(&self.focus)
            .cursor(CursorStyle::IBeam)
            .overflow_hidden()
            .px_3()
            .py_2()
            .rounded_md()
            .border_1()
            .border_color(rgb(0x34433c))
            .bg(rgb(0x1e272c))
            .on_key_down(cx.listener(Self::key))
            .on_mouse_down(
                MouseButton::Left,
                cx.listener(|this, event: &MouseDownEvent, window, cx| {
                    this.focus.focus(window, cx);
                    this.cursor = this.line.as_ref().zip(this.bounds).map_or(
                        this.text.len(),
                        |(line, bounds)| {
                            line.closest_index_for_x(event.position.x - bounds.left())
                                .min(this.text.len())
                        },
                    );
                    if !event.modifiers.shift {
                        this.anchor = this.cursor;
                    }
                    cx.notify();
                }),
            )
            .child(
                canvas(
                    move |_, window, cx| {
                        let s = input.read(cx);
                        let text: SharedString = if s.text.is_empty() {
                            "Rechercher nom, image ou état…".into()
                        } else {
                            s.text.clone().into()
                        };
                        let style = window.text_style();
                        window.text_system().shape_line(
                            text.clone(),
                            px(13.),
                            &[TextRun {
                                len: text.len(),
                                font: style.font(),
                                color: rgb(if s.text.is_empty() {
                                    0x9eb2a8
                                } else {
                                    0xe0ece7
                                })
                                .into(),
                                background_color: None,
                                underline: None,
                                strikethrough: None,
                            }],
                            None,
                        )
                    },
                    move |bounds, line, window, cx| {
                        let s = paint_input.read(cx);
                        let focus = s.focus.clone();
                        let range = s.selection();
                        window.handle_input(
                            &focus,
                            ElementInputHandler::new(bounds, paint_input.clone()),
                            cx,
                        );
                        if focus.is_focused(window) {
                            let start = line.x_for_index(range.start);
                            let end = if range.is_empty() {
                                start + px(1.)
                            } else {
                                line.x_for_index(range.end)
                            };
                            window.paint_quad(fill(
                                Bounds::new(
                                    point(bounds.left() + start, bounds.top()),
                                    size(end - start, bounds.size.height),
                                ),
                                rgba(if range.is_empty() {
                                    0x74d7b1ff
                                } else {
                                    0x74d7b150
                                }),
                            ));
                        }
                        let _ = line.paint(
                            bounds.origin,
                            px(20.),
                            TextAlign::Left,
                            Some(bounds.size.width),
                            window,
                            cx,
                        );
                        paint_input.update(cx, |s, _| {
                            s.line = Some(line);
                            s.bounds = Some(bounds);
                        });
                    },
                )
                .w_full()
                .h(px(20.)),
            )
    }
}
