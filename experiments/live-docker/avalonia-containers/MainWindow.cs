using System.Diagnostics;
using Avalonia.Controls;
using Avalonia.Data;
using Avalonia.Layout;
using Avalonia.Media;
using Docker.DotNet;
using Docker.DotNet.Models;

namespace AvaloniaContainers;

public sealed record ContainerRow(string Id, string Name, string Image, string State, string Status);

public sealed class MainWindow : Window
{
    private readonly TextBox search = new() { Watermark = "Search name, image, state…", FontSize = 13 };
    private readonly Button refresh = new() { Content = "Refresh", Margin = new(12, 0, 0, 0) };
    private readonly TextBlock count = Text("Loading…", true);
    private readonly TextBlock error = new() { Foreground = Brush.Parse("#FFA4A4"), IsVisible = false, TextWrapping = TextWrapping.Wrap };
    private readonly DataGrid table = new()
    {
        AutoGenerateColumns = false, IsReadOnly = true, RowHeight = 32,
        CanUserSortColumns = false, CanUserReorderColumns = false, CanUserResizeColumns = false,
        GridLinesVisibility = DataGridGridLinesVisibility.None,
        HeadersVisibility = DataGridHeadersVisibility.Column, FontSize = 13
    };
    private ContainerRow[] rows = [];
    private CancellationTokenSource? request;
    private bool busy, closed;

    public MainWindow()
    {
        Title = "Docker GUI · Live Avalonia";
        Width = 1000; Height = 680; MinWidth = 640; MinHeight = 400;
        Background = Brush.Parse("#171D21");
        search.TextChanged += (_, _) => Filter();
        refresh.Click += async (_, _) => await Load();
        var title = new Grid { ColumnDefinitions = new("*,Auto"), Margin = new(0, 0, 0, 16) };
        title.Children.Add(new TextBlock { Text = "Containers", FontSize = 26, Foreground = Brush.Parse("#E0ECE7") });
        var subtitle = Text("C# · Avalonia · Docker SDK", true);
        Grid.SetColumn(subtitle, 1); title.Children.Add(subtitle);
        var toolbar = new Grid { ColumnDefinitions = new("*,Auto"), Margin = new(0, 0, 0, 12) };
        toolbar.Children.Add(search);
        Grid.SetColumn(refresh, 1); toolbar.Children.Add(refresh);
        string[] properties = [nameof(ContainerRow.Name), nameof(ContainerRow.Image), nameof(ContainerRow.State), nameof(ContainerRow.Status)];
        string[] headings = ["Name", "Image", "State", "Status"];
        double[] weights = [2.3, 3, 1.2, 2.5];
        for (var i = 0; i < properties.Length; i++)
            table.Columns.Add(new DataGridTextColumn { Header = headings[i], Binding = new Binding(properties[i]),
                Width = new DataGridLength(weights[i], DataGridLengthUnitType.Star) });
        var layout = new Grid { RowDefinitions = new("Auto,Auto,Auto,Auto,*"), Margin = new(24) };
        Control[] controls = [title, toolbar, count, error, table];
        for (var i = 0; i < controls.Length; i++) { Grid.SetRow(controls[i], i); layout.Children.Add(controls[i]); }
        count.Margin = new(0, 0, 0, 12);
        error.Margin = new(0, 0, 0, 12);
        Content = layout;
        Opened += async (_, _) => { search.Focus(); await Load(); };
        Closed += (_, _) => { closed = true; request?.Cancel(); };
    }

    private async Task Load()
    {
        if (busy || closed) return;
        busy = true; refresh.IsEnabled = false; error.IsVisible = false; count.Text = "Loading…";
        using var cancellation = new CancellationTokenSource(TimeSpan.FromSeconds(10));
        request = cancellation;
        try
        {
            var fresh = await Task.Run(async () =>
            {
                var started = Stopwatch.StartNew();
                var endpoint = Environment.GetEnvironmentVariable("DOCKER_HOST");
                endpoint = string.IsNullOrWhiteSpace(endpoint)
                    ? OperatingSystem.IsWindows() ? "npipe://./pipe/docker_engine" : "unix:///var/run/docker.sock"
                    : endpoint;
                if (endpoint.StartsWith("tcp://", StringComparison.OrdinalIgnoreCase)) endpoint = "http://" + endpoint[6..];
                using var client = new DockerClientBuilder().WithEndpoint(new Uri(endpoint))
                    .WithTimeout(TimeSpan.FromSeconds(10)).Build();
                var containers = await client.Containers.ListContainersAsync(new ContainersListParameters { All = true }, cancellation.Token);
                if (containers.Count > 20_000) throw new InvalidOperationException("Docker returned more than 20,000 containers.");
                var result = containers.Select(c => new ContainerRow(c.ID,
                    c.Names?.FirstOrDefault()?.TrimStart('/') ?? c.ID[..Math.Min(12, c.ID.Length)],
                    c.Image ?? "", c.State ?? "", c.Status ?? ""))
                    .OrderBy(c => c.Name, StringComparer.OrdinalIgnoreCase).ToArray();
                Console.WriteLine($"Docker load: count={result.Length} elapsed_ms={started.ElapsedMilliseconds} ids={string.Join(',', result.Select(c => c.Id).Order(StringComparer.Ordinal))}");
                return result;
            }, cancellation.Token);
            if (!closed) rows = fresh;
        }
        catch (OperationCanceledException) when (!closed) { error.Text = "Docker request timed out after 10 seconds."; error.IsVisible = true; }
        catch (Exception ex) when (!closed) { error.Text = ex.Message; error.IsVisible = true; }
        catch (Exception) when (closed) { }
        finally
        {
            request = null; busy = false;
            if (!closed) { refresh.IsEnabled = true; Filter(); }
        }
    }

    private void Filter()
    {
        var query = search.Text?.Trim() ?? "";
        var visible = rows.Where(c => c.Name.Contains(query, StringComparison.OrdinalIgnoreCase)
            || c.Image.Contains(query, StringComparison.OrdinalIgnoreCase)
            || c.State.Contains(query, StringComparison.OrdinalIgnoreCase)).ToArray();
        table.ItemsSource = visible;
        if (!busy) count.Text = $"{visible.Length} / {rows.Length} containers · all states · live Docker SDK";
    }

    private static TextBlock Text(string text, bool muted = false) => new()
    {
        Text = text, FontSize = 13, VerticalAlignment = VerticalAlignment.Center,
        Foreground = Brush.Parse(muted ? "#9FB2A8" : "#E0ECE7")
    };
}
