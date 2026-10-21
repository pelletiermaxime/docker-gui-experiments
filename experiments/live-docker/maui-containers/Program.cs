using Microsoft.Maui.Hosting;
using Microsoft.Maui.Platforms.Linux.Gtk4.Hosting;
using Microsoft.Maui.Platforms.Linux.Gtk4.Platform;
using System.Runtime.Versioning;

namespace MauiContainers;

[SupportedOSPlatform("linux")]
public sealed class Program : GtkMauiApplication
{
    protected override MauiApp CreateMauiApp() => MauiApp.CreateBuilder()
        .UseMauiAppLinuxGtk4<App>().Build();

    public static void Main(string[] args) => new Program().Run(args);
}
