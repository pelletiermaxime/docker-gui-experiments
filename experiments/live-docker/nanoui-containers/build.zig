const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});
    const nano = b.dependency("nanoui", .{ .target = target, .optimize = optimize });
    const sdk = b.dependency("container_zig", .{ .target = target, .optimize = optimize });
    const endpoint = b.createModule(.{
        .root_source_file = sdk.path("examples/demo_transport.zig"),
        .target = target,
        .optimize = optimize,
        .imports = &.{.{ .name = "container_zig", .module = sdk.module("container_zig") }},
    });
    const exe = b.addExecutable(.{
        .name = "nanoui-live-containers",
        .root_module = b.createModule(.{
            .root_source_file = b.path("src/main.zig"),
            .target = target,
            .optimize = optimize,
            .strip = true,
            .link_libc = true,
            .imports = &.{
                .{ .name = "nanoui", .module = nano.module("nanoui") },
                .{ .name = "container_zig", .module = sdk.module("container_zig") },
                .{ .name = "docker_endpoint", .module = endpoint },
            },
        }),
    });
    b.installArtifact(exe);
    const run = b.addRunArtifact(exe);
    run.addPassthruArgs();
    b.step("run", "Open the container list").dependOn(&run.step);
}
