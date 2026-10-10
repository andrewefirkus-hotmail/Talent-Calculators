using System.Net.Http.Json;
using Microsoft.AspNetCore.Components;
using TalentCalculator.Models;
using TalentCalculator.Services;

namespace TalentCalculator.Pages;

public partial class Calculator : IDisposable
{
    [Inject]
    private HttpClient Http { get; set; } = default!;

    [Inject]
    private NavigationManager Nav { get; set; } = default!;

    [Parameter]
    public string? ClassSlug { get; set; }

    [SupplyParameterFromQuery(Name = "build")]
    public string? BuildCode { get; set; }

    private record ClassEntry(string Slug, string Name);

    private List<ClassEntry> Classes = new();
    private ClassData? Data;
    private TalentBuild? Build;
    private string? LoadedSlug;
    private string? Error;

    private string Slug =>
        string.IsNullOrEmpty(ClassSlug) ? "rogue": ClassSlug.ToLowerInvariant();

    protected override async Task OnInitializedAsync()
    {
        Classes = await Http.GetFromJsonAsync<List<ClassEntry>>("data/classes.json") ?? new();
    }

    protected override async Task OnParametersSetAsync()
    {
        if (Slug != LoadedSlug)
        {
            LoadedSlug = Slug;
            Error = null;
            if (Build is not null) Build.Changed -= OnBuildChanged;
            Build = null;
            try
            {
                Data = await Http.GetFromJsonAsync<ClassData>($"data/{Slug}.json");
                Build = new TalentBuild(Data!);
            }
            catch (Exception ex)
            {
                Error = $"Couldn't load data/{Slug}.json: {ex.Message}";
                return;
            }
            Build.LoadCode(BuildCode);
            Build.Changed += OnBuildChanged;
            if ((BuildCode ?? "") != Build.ToCode()) OnBuildChanged(); // drop points the rules rejected
        }
        else if (Build is not null && (BuildCode ?? "") != Build.ToCode())
        {
            // Back/forward navigation or a pasted link.
            Build.Changed -= OnBuildChanged;
            Build.LoadCode(BuildCode);
            Build.Changed += OnBuildChanged;
            if ((BuildCode ?? "") != Build.ToCode()) OnBuildChanged();
        }
    }

    private void OnBuildChanged()
    {
        var code = Build!.ToCode();
        var buildParameter = code.Length == 0 ? null : code;
        Nav.NavigateTo(Nav.GetUriWithQueryParameter("build", buildParameter), replace: true);
        StateHasChanged();
    }

    public void Dispose()
    {
        if (Build is not null) Build.Changed -= OnBuildChanged;
    }
}
