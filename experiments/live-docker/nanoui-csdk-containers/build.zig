const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});
    const nano = b.dependency("nanoui", .{ .target = target, .optimize = optimize });
    const bindings = b.addTranslateC(.{ .root_source_file = b.path("src/docker_bridge.h"), .target = target, .optimize = optimize });
    const exe = b.addExecutable(.{
        .name = "nanoui-csdk-containers",
        .root_module = b.createModule(.{
            .root_source_file = b.path("src/main.zig"),
            .target = target,
            .optimize = optimize,
            .strip = true,
            .link_libc = true,
            .imports = &.{
                .{ .name = "nanoui", .module = nano.module("nanoui") },
                .{ .name = "docker_c", .module = bindings.createModule() },
            },
        }),
    });
    exe.root_module.addIncludePath(b.path("src"));
    exe.root_module.addIncludePath(b.path("../../../.verification/gui-live-comparison/deps/libdocker/inc"));
    exe.root_module.addCSourceFile(.{ .file = b.path("src/docker_bridge.c"), .flags = &.{"-std=c11"} });
    exe.root_module.addCSourceFile(.{ .file = b.path("../../../.verification/gui-live-comparison/deps/libdocker/src/docker.c"), .flags = &.{"-std=c11"} });
    exe.root_module.linkSystemLibrary("curl", .{});
    b.installArtifact(exe);
    const run = b.addRunArtifact(exe);
    run.addPassthruArgs();
    b.step("run", "Open the C SDK container list").dependOn(&run.step);
}
