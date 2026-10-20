const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});
    const nano = b.dependency("nanoui", .{ .target = target, .optimize = optimize });
    const exe = b.addExecutable(.{
        .name = "nanoui-containers",
        .root_module = b.createModule(.{
            .root_source_file = b.path("src/main.zig"),
            .target = target,
            .optimize = optimize,
            .strip = true,
            .link_libc = true,
            .imports = &.{.{ .name = "nanoui", .module = nano.module("nanoui") }},
        }),
    });
    b.installArtifact(exe);
    const run = b.addRunArtifact(exe);
    run.addPassthruArgs();
    b.step("run", "Open the container list").dependOn(&run.step);
}
