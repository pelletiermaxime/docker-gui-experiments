const std = @import("std");
const nanoui = @import("nanoui");
const csdk = @import("docker_c");
const ui = nanoui.ui;
const alloc = std.heap.smp_allocator;
const max_rows = 20_000;

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

    fn get(io: std.Io, started: std.Io.Timestamp, url: [:0]const u8) !csdk.struct_fd_response {
        const elapsed = started.durationTo(std.Io.Clock.awake.now(io)).toMilliseconds();
        if (elapsed >= 10_000) return error.DockerTimeout;
        var response: csdk.struct_fd_response = undefined;
        if (csdk.fd_docker_get(url.ptr, @intCast(10_000 - elapsed), &response) != 0) return error.CSdkAllocationFailed;
        errdefer csdk.fd_docker_response_free(&response);
        if (response.transport != 0) return error.CSdkTransportFailed;
        if (response.status != 200) return error.DockerHttpError;
        return response;
    }

    fn loadTimed(self: *Snapshot, io: std.Io, environment: *const std.process.Environ.Map) !void {
        if (environment.get("DOCKER_HOST")) |host| {
            if (!std.mem.startsWith(u8, host, "unix:///")) return error.OnlyUnixDockerHostSupported;
        }
        const a = self.arena.allocator();
        const started = std.Io.Clock.awake.now(io);
        var version_response = try get(io, started, "http://localhost/version");
        defer csdk.fd_docker_response_free(&version_response);
        const Version = struct { ApiVersion: []const u8, MinAPIVersion: ?[]const u8 = null };
        const version = try std.json.parseFromSlice(Version, a, version_response.data[0..version_response.size], .{ .ignore_unknown_fields = true });
        const prefix = "1.";
        if (!std.mem.startsWith(u8, version.value.ApiVersion, prefix)) return error.UnsupportedDockerApi;
        const minor = @min(@as(u16, 55), try std.fmt.parseInt(u16, version.value.ApiVersion[prefix.len..], 10));
        if (version.value.MinAPIVersion) |minimum| {
            if (!std.mem.startsWith(u8, minimum, prefix) or minor < try std.fmt.parseInt(u16, minimum[prefix.len..], 10)) return error.UnsupportedDockerApi;
        }
        const url = try std.fmt.allocPrintSentinel(a, "http://localhost/v1.{d}/containers/json?all=true", .{minor}, 0);
        var response = try get(io, started, url);
        defer csdk.fd_docker_response_free(&response);
        const Item = struct { Id: []const u8, Names: []const []const u8, Image: []const u8, State: []const u8, Status: []const u8 };
        const parsed = try std.json.parseFromSlice([]Item, a, response.data[0..response.size], .{ .ignore_unknown_fields = true, .allocate = .alloc_always });
        if (parsed.value.len > max_rows) return error.TooManyContainers;
        self.rows = try a.alloc(Container, parsed.value.len);
        const ids = try a.alloc([]const u8, parsed.value.len);
        for (parsed.value, self.rows, ids) |item, *row, *id| {
            const names = try a.alloc([]const u8, item.Names.len);
            for (item.Names, names) |name, *out| out.* = std.mem.trimStart(u8, name, "/");
            row.* = .{ .ID = item.Id, .Names = try std.mem.join(a, ", ", names), .Image = item.Image, .State = item.State, .Status = item.Status };
            id.* = row.ID;
        }
        std.mem.sort([]const u8, ids, {}, struct {
            fn less(_: void, left: []const u8, right: []const u8) bool {
                return std.mem.lessThan(u8, left, right);
            }
        }.less);
        var digest: [32]u8 = undefined;
        std.crypto.hash.sha2.Sha256.hash(try std.mem.join(a, "\n", ids), &digest, .{});
        std.log.info("source=libdocker-c-api containers={d} ids_sha256={s} elapsed_ms={d}", .{ self.rows.len, std.fmt.bytesToHex(digest, .lower), started.durationTo(std.Io.Clock.awake.now(io)).toMilliseconds() });
    }
};

const State = struct {
    io: std.Io,
    environment: *const std.process.Environ.Map,
    window: ?*nanoui.Window = null,
    thread: ?std.Thread = null,
    pending: ?*Snapshot = null,
    current: Snapshot = .{},
    search: ui.TextBuffer = .{},
    visible: std.ArrayList(usize) = .empty,
    loading: bool = false,
    error_message: ?[]const u8 = null,
    scroll_reset: bool = false,

    fn refresh(s: *State) void {
        if (s.loading) return;
        if (s.error_message) |message| alloc.free(message);
        s.error_message = null;
        s.current.message = "";
        const snapshot = alloc.create(Snapshot) catch return;
        snapshot.* = .{};
        s.pending = snapshot;
        s.loading = true;
        s.thread = std.Thread.spawn(.{}, worker, .{s}) catch {
            s.loading = false;
            s.pending = null;
            alloc.destroy(snapshot);
            s.current.message = "Could not start loader";
            return;
        };
    }

    fn worker(s: *State) void {
        const snapshot = s.pending.?;
        snapshot.loadTimed(s.io, s.environment) catch |err| {
            snapshot.message = std.fmt.allocPrint(snapshot.arena.allocator(), "Load failed: {s}", .{@errorName(err)}) catch "Out of memory";
        };
        nanoui.App.after(0, s, ready);
    }

    fn ready(ptr: ?*anyopaque) callconv(.c) void {
        const s: *State = @ptrCast(@alignCast(ptr.?));
        s.thread.?.join();
        s.thread = null;
        if (s.pending.?.message.len == 0) {
            s.current.arena.deinit();
            s.current = s.pending.?.*;
        } else {
            s.error_message = alloc.dupe(u8, s.pending.?.message) catch null;
            s.current.message = s.error_message orelse "Out of memory";
            s.pending.?.arena.deinit();
        }
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
            ui.label(c, "Zig · NanoUI · C libdocker");
        }
        {
            const toolbar = ui.div(c).row().wFull().itemsCenter().gap(12);
            defer toolbar.end();
            if (ui.textField(c, &s.search, .{ .placeholder = "Search name, image, state…", .width = .fill }).changed) s.filter();
            if (ui.button(c, "Refresh", .{ .variant = .primary, .disabled = s.loading }).clicked) s.refresh();
        }
        ui.textf(c, .{ .size = 12, .color = c.theme.muted }, "{d} / {d} containers · {s}", .{ s.visible.items.len, s.current.rows.len, if (s.loading) "Loading…" else "Live Docker API · all states" });
        if (s.current.message.len != 0) ui.text(c, s.current.message, .{ .size = 13, .color = c.theme.danger, .wrap = true });
        {
            const head = ui.div(c).row().wFull().h(32).itemsCenter().px(12).gap(12).bg(c.theme.surface).rounded(6);
            defer head.end();
            cell(c, "Name", 220, c.theme.muted, true);
            cell(c, "Image", 300, c.theme.muted, true);
            cell(c, "State", 100, c.theme.muted, true);
            cell(c, "Status", 250, c.theme.muted, true);
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
        if (s.error_message) |message| alloc.free(message);
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
    if (csdk.fd_docker_init() != 0) return error.CurlInitializationFailed;
    defer csdk.fd_docker_cleanup();
    const app = try nanoui.App.create(init, .{ .name = "FerryDock NanoUI C SDK" });
    defer app.destroy();
    var state: State = .{ .io = init.io, .environment = init.environ_map };
    defer state.deinit();
    state.window = try app.newWindow(.{
        .title = "FerryDock · NanoUI C SDK",
        .width = 1000,
        .height = 680,
        .theme = ui.Theme.dark_theme,
        .content = .{ .view = .init(&state, State.view) },
        .on_close = .{ .ctx = &state, .func = State.closed },
    });
    state.refresh();
    try app.run();
}
