using System.Diagnostics;
using System.Collections.ObjectModel;
using Docker.DotNet;
using Docker.DotNet.Models;
using Microsoft.Maui;
using Microsoft.Maui.Controls;
using Microsoft.Maui.Graphics;

namespace MauiContainers;

public sealed record ContainerRow(string Id, string Name, string Image, string State, string Status);

public sealed class MainPage : ContentPage
{
    private readonly Entry search = new() { Placeholder = "Search name, image, state…", FontSize = 13 };
    private readonly Button refresh = new() { Text = "Refresh", FontSize = 13 };
    private readonly Label count = Text("Loading…", muted: true);
    private readonly Label error = new() { TextColor = Color.FromArgb("#FFA4A4"), FontSize = 13, IsVisible = false };
    private readonly CollectionView list = new() { SelectionMode = SelectionMode.None, ItemSizingStrategy = ItemSizingStrategy.MeasureFirstItem };
    private ContainerRow[] rows = [];
    private readonly ObservableCollection<ContainerRow> visible = [];
    private CancellationTokenSource? request;
    private bool busy, loaded, closed;

    public MainPage()
    {
        BackgroundColor = Color.FromArgb("#171D21");
        search.TextColor = Color.FromArgb("#E0ECE7");
        search.PlaceholderColor = Color.FromArgb("#9FB2A8");
        search.BackgroundColor = Color.FromArgb("#242D34");
        search.TextChanged += (_, _) => Filter();
        refresh.Clicked += async (_, _) => await Load();
        list.ItemsSource = visible;
        var title = new Grid { ColumnDefinitions = Columns(GridLength.Star, GridLength.Auto) };
        title.Add(new Label { Text = "Containers", FontSize = 26, TextColor = Color.FromArgb("#E0ECE7") });
        title.Add(Text("C# · .NET MAUI · Docker SDK", muted: true), 1);
        var toolbar = new Grid { ColumnDefinitions = Columns(GridLength.Star, GridLength.Auto), ColumnSpacing = 12 };
        toolbar.Add(search);
        toolbar.Add(refresh, 1);
        list.ItemTemplate = new DataTemplate(() =>
        {
            var row = Row();
            string[] properties = [nameof(ContainerRow.Name), nameof(ContainerRow.Image), nameof(ContainerRow.State), nameof(ContainerRow.Status)];
            for (var i = 0; i < properties.Length; i++)
            {
                var label = Text("");
                label.SetBinding(Label.TextProperty, properties[i]);
                row.Add(label, i);
            }
            return row;
        });
        var header = Row();
        string[] headings = ["Name", "Image", "State", "Status"];
        for (var i = 0; i < headings.Length; i++) header.Add(Text(headings[i], muted: true), i);
        var layout = new Grid
        {
            RowDefinitions = new RowDefinitionCollection(
                new(GridLength.Auto), new(GridLength.Auto), new(GridLength.Auto),
                new(GridLength.Auto), new(GridLength.Auto), new(GridLength.Star)),
            RowSpacing = 12
        };
        layout.Add(title, 0, 0);
        layout.Add(toolbar, 0, 1);
        layout.Add(count, 0, 2);
        layout.Add(error, 0, 3);
        layout.Add(header, 0, 4);
        layout.Add(list, 0, 5);
        Content = layout;
        Loaded += async (_, _) =>
        {
            if (loaded) return;
            loaded = true;
            await Load();
        };
    }

    protected override void OnAppearing()
    {
        base.OnAppearing();
        if (Window is not null) Window.Destroying += (_, _) => { closed = true; request?.Cancel(); };
    }

    private async Task Load()
    {
        if (busy || closed) return;
        busy = true;
        refresh.Text = "Loading…";
        error.IsVisible = false;
        count.Text = "Loading…";
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
            request = null;
            busy = false;
            if (!closed) { refresh.Text = "Refresh"; Filter(); }
        }
    }

    private void Filter()
    {
        var query = search.Text?.Trim() ?? "";
        var matches = rows.Where(c => c.Name.Contains(query, StringComparison.OrdinalIgnoreCase)
            || c.Image.Contains(query, StringComparison.OrdinalIgnoreCase)
            || c.State.Contains(query, StringComparison.OrdinalIgnoreCase)).ToArray();
        visible.Clear();
        foreach (var row in matches) visible.Add(row);
        if (!busy) count.Text = $"{visible.Count} / {rows.Length} containers · all states · live Docker SDK";
    }

    private static Grid Row() => new()
    {
        ColumnDefinitions = Columns(new(2.3, GridUnitType.Star), new(3, GridUnitType.Star),
            new(1.2, GridUnitType.Star), new(2.5, GridUnitType.Star)),
        ColumnSpacing = 16,
        HeightRequest = 32
    };

    private static ColumnDefinitionCollection Columns(params GridLength[] widths) =>
        new(widths.Select(w => new ColumnDefinition(w)).ToArray());

    private static Label Text(string text, bool muted = false) => new()
    {
        Text = text, FontSize = 13, VerticalTextAlignment = TextAlignment.Center,
        TextColor = Color.FromArgb(muted ? "#9FB2A8" : "#E0ECE7"),
        LineBreakMode = LineBreakMode.TailTruncation, MaxLines = 1
    };
}
