using Microsoft.Maui;
using Microsoft.Maui.Controls;

namespace MauiContainers;

public sealed class App : Application
{
    public App() => UserAppTheme = AppTheme.Dark;

    protected override Window CreateWindow(IActivationState? activationState) => new(new MainPage())
    {
        Title = "Docker GUI · Live MAUI",
        Width = 1000,
        Height = 680,
        MinimumWidth = 640,
        MinimumHeight = 400
    };
}
