const std = @import("std");
const nanoui = @import("nanoui");
const ui = nanoui.ui;
const alloc = std.heap.smp_allocator;
const max_bytes = 4 * 1024 * 1024;

const Container = struct {
    ID: []const u8 = "",
    Names: []const u8 = "",
    Image: []const u8 = "",
    State: []const u8 = "",
    Status: []const u8 = "",
};

const Snapshot = struct {
    arena: std.heap.ArenaAllocator = .init(alloc),
    rows: []Container = &.{},
    message: []const u8 = "",

    fn load(self: *Snapshot, io: std.Io, fixture: ?[]const u8) !void {
        const a = self.arena.allocator();
        const bytes = if (fixture) |path|
            try std.Io.Dir.cwd().readFileAlloc(io, path, a, .limited(max_bytes))
        else docker: {
            const result = try std.process.run(a, io, .{
                .argv = &.{ "docker", "ps", "--all", "--no-trunc", "--format", "{{json .}}" },
                .stdout_limit = .limited(max_bytes),
                .stderr_limit = .limited(4096),
                .timeout = (std.Io.Timeout{ .duration = .{ .raw = .fromSeconds(10), .clock = .awake } }).toDeadline(io),
            });
            if (!result.term.success()) {
                self.message = try std.fmt.allocPrint(a, "Docker indisponible : {s}", .{std.mem.trim(u8, result.stderr, "\r\n")});
                return;
            }
            break :docker result.stdout;
        };
        var rows: std.ArrayList(Container) = .empty;
        var lines = std.mem.tokenizeScalar(u8, bytes, '\n');
        while (lines.next()) |line| {
            const parsed = try std.json.parseFromSlice(Container, a, line, .{ .ignore_unknown_fields = true, .allocate = .alloc_always });
            try rows.append(a, parsed.value);
        }
        self.rows = try rows.toOwnedSlice(a);
    }
};

const State = struct {
    io: std.Io,
    fixture: ?[]const u8 = null,
    window: ?*nanoui.Window = null,
    thread: ?std.Thread = null,
    pending: ?*Snapshot = null,
    current: Snapshot = .{},
    search: ui.TextBuffer = .{},
    visible: std.ArrayList(usize) = .empty,
    loading: bool = false,
    scroll_reset: bool = false,

    fn refresh(s: *State) void {
        if (s.loading) return;
        const snapshot = alloc.create(Snapshot) catch return;
        snapshot.* = .{};
        s.pending = snapshot;
        s.loading = true;
        s.thread = std.Thread.spawn(.{}, worker, .{s}) catch {
            s.loading = false;
            s.pending = null;
            alloc.destroy(snapshot);
            s.current.message = "Impossible de démarrer le worker";
            return;
        };
    }

    fn worker(s: *State) void {
        const snapshot = s.pending.?;
        snapshot.load(s.io, s.fixture) catch |err| {
            snapshot.message = std.fmt.allocPrint(snapshot.arena.allocator(), "Lecture impossible : {s}", .{@errorName(err)}) catch "Mémoire insuffisante";
        };
        nanoui.App.after(0, s, ready);
    }

    fn ready(ptr: ?*anyopaque) callconv(.c) void {
        const s: *State = @ptrCast(@alignCast(ptr.?));
        s.thread.?.join();
        s.thread = null;
        s.current.arena.deinit();
        s.current = s.pending.?.*;
        alloc.destroy(s.pending.?);
        s.pending = null;
        s.loading = false;
        s.filter();
        if (s.window) |w| w.redraw();
    }

    fn filter(s: *State) void {
        s.visible.clearRetainingCapacity();
        const query = std.mem.trim(u8, s.search.text(), " \t\r\n");
        for (s.current.rows, 0..) |row, i| {
            if (contains(row.Names, query) or contains(row.Image, query) or contains(row.State, query))
                s.visible.append(alloc, i) catch break;
        }
        s.scroll_reset = true;
    }

    fn cell(c: *ui.Context, text: []const u8, width: f32, color: ui.Color, heading: bool) void {
        const box = ui.div(c).w(width).clip();
        defer box.end();
        ui.text(c, text, .{ .size = 13, .weight = if (heading) .semibold else .regular, .color = color });
    }

    fn view(s: *State, c: *ui.Context) void {
        const root = ui.div(c).column().sizeFull().p(24).gap(16).bg(c.theme.background);
        defer root.end();
        {
            const header = ui.div(c).row().wFull().itemsCenter().gap(16);
            defer header.end();
            ui.heading(c, "Containers");
            ui.spacer(c);
            ui.label(c, "Zig · NanoUI");
        }
        {
            const toolbar = ui.div(c).row().wFull().itemsCenter().gap(12);
            defer toolbar.end();
            if (ui.textField(c, &s.search, .{ .placeholder = "Rechercher nom, image, état…", .width = .fill }).changed) s.filter();
            if (ui.button(c, "Refresh", .{ .variant = .primary, .disabled = s.loading }).clicked) s.refresh();
        }
        ui.textf(c, .{ .size = 12, .color = c.theme.muted }, "{d} / {d} containers · {s}", .{ s.visible.items.len, s.current.rows.len, if (s.loading) "Chargement…" else if (s.fixture != null) "Snapshot local" else "Docker · tous les états" });
        if (s.current.message.len != 0) ui.text(c, s.current.message, .{ .size = 13, .color = c.theme.danger, .wrap = true });
        {
            const head = ui.div(c).row().wFull().h(32).itemsCenter().px(12).gap(12).bg(c.theme.surface).rounded(6);
            defer head.end();
            cell(c, "Nom", 220, c.theme.muted, true);
            cell(c, "Image", 300, c.theme.muted, true);
            cell(c, "État", 100, c.theme.muted, true);
            cell(c, "Statut", 250, c.theme.muted, true);
        }
        var rows = ui.list(c, .{ .count = s.visible.items.len, .row_height = 38, .scroll_to = if (s.scroll_reset) 0 else null });
        s.scroll_reset = false;
        while (rows.next()) |i| {
            const item = s.current.rows[s.visible.items[i]];
            const row = ui.div(c).row().wFull().h(38).itemsCenter().px(12).gap(12).clip().bg(if (i % 2 == 0) c.theme.surface.alpha(0.5) else c.theme.background);
            defer row.end();
            cell(c, item.Names, 220, c.theme.text, false);
            cell(c, item.Image, 300, c.theme.muted, false);
            cell(c, item.State, 100, if (std.mem.eql(u8, item.State, "running")) c.theme.success else c.theme.muted, false);
            cell(c, item.Status, 250, c.theme.muted, false);
        }
        rows.end();
    }

    fn closed(ptr: *anyopaque, _: *nanoui.Window) void {
        const s: *State = @ptrCast(@alignCast(ptr));
        s.window = null;
    }

    fn deinit(s: *State) void {
        if (s.thread) |thread| thread.join();
        if (s.pending) |p| {
            p.arena.deinit();
            alloc.destroy(p);
        }
        s.current.arena.deinit();
        s.visible.deinit(alloc);
        if (s.fixture) |path| alloc.free(path);
    }
};

fn contains(haystack: []const u8, needle: []const u8) bool {
    if (needle.len == 0) return true;
    if (needle.len > haystack.len) return false;
    for (0..haystack.len - needle.len + 1) |i| {
        if (std.ascii.eqlIgnoreCase(haystack[i .. i + needle.len], needle)) return true;
    }
    return false;
}

pub fn main(init: std.process.Init) !void {
    const app = try nanoui.App.create(init, .{ .name = "FerryDock NanoUI" });
    defer app.destroy();
    var state: State = .{ .io = init.io };
    defer state.deinit();
    if (init.environ_map.get("CONTAINER_SNAPSHOT")) |path| {
        state.fixture = try alloc.dupe(u8, path);
    }
    state.window = try app.newWindow(.{
        .title = "FerryDock · NanoUI",
        .width = 1000,
        .height = 680,
        .theme = ui.Theme.dark_theme,
        .content = .{ .view = .init(&state, State.view) },
        .on_close = .{ .ctx = &state, .func = State.closed },
    });
    state.refresh();
    try app.run();
}

// Application edit for compile timing: 1792466588041984663
