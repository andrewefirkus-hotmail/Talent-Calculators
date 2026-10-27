using System.IO.Compression;

const string Address = "http://localhost:5080";

// The share build (SingleFileProfile) packs the published Blazor app into the .exe as "blazor-app.zip".
// The normal build (FolderProfile, or F5 in Visual Studio) has no such resource and serves wwwroot from disk.
string? embeddedAppFolder = ExtractEmbeddedApp();

var options = new WebApplicationOptions
{
    Args = args,
    WebRootPath = embeddedAppFolder is null ? null : Path.Combine(embeddedAppFolder, "wwwroot"),
};
var app = WebApplication.CreateBuilder(options).Build();
app.Urls.Add(Address);

if (embeddedAppFolder is null)
{
    app.MapStaticAssets();
}
else
{
    // The manifest maps friendly URLs (blazor.webassembly.js) to the real fingerprinted files.
    app.MapStaticAssets(Path.Combine(embeddedAppFolder, "TalentCalculator.staticwebassets.endpoints.json"));
}

app.MapFallbackToFile("index.html");
app.Lifetime.ApplicationStarted.Register(() =>
    System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(Address) { UseShellExecute = true }));
app.Run();

// Unzips the embedded Blazor app into a temp folder and returns that folder,
// or returns null when this build has no embedded app.
static string? ExtractEmbeddedApp()
{
    var assembly = typeof(Program).Assembly;
    using Stream? zipStream = assembly.GetManifestResourceStream("blazor-app.zip");
    if (zipStream is null)
    {
        return null;
    }

    // One folder per build, so a newer .exe never serves an older copy's files.
    string buildStamp = File.GetLastWriteTimeUtc(Environment.ProcessPath ?? assembly.Location).Ticks.ToString();
    string targetFolder = Path.Combine(Path.GetTempPath(), "TalentCalculator", buildStamp);
    if (!File.Exists(Path.Combine(targetFolder, "wwwroot", "index.html")))
    {
        ZipFile.ExtractToDirectory(zipStream, targetFolder, overwriteFiles: true);
    }

    return targetFolder;
}
