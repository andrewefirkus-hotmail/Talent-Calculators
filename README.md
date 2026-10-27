# Talent Calculators

A Classic WoW talent calculator, written twice.

| Folder | What it is |
| --- | --- |
| `TalentCalculator/` | The .NET version: a Blazor WebAssembly app. Its own README covers running it and how the code is laid out. |
| `TalentCalculator.Launcher/` | A tiny ASP.NET Core server that hosts the Blazor app on http://localhost:5080 and opens the browser. This is the project you publish into an .exe. |
| `python-ver/` | The Python version (Flask + HTMX). See its README for setup. |

## Publishing the .NET version

There are two publish profiles in `TalentCalculator.Launcher/Properties/PublishProfiles`.
Both are Release, self-contained and Windows x64, so the PC that runs them doesn't need .NET installed.

| Profile | What you get | Use it for |
| --- | --- | --- |
| **FolderProfile** | A folder of files: `TalentCalculator.Launcher.exe` plus the runtime and a `wwwroot` folder. | Checking that a build works. |
| **SingleFileProfile** | One file: `TalentCalculator.exe` (about 65 MB) with everything packed inside. | Sharing with other people. |

**From Visual Studio:**
1. Open `TalentCalculator/TalentCalculator.slnx`.
2. Right-click **TalentCalculator.Launcher** in Solution Explorer and choose **Publish**.
3. Pick the profile you want and click **Publish**.

**From a terminal** (in this folder):

```
dotnet publish TalentCalculator.Launcher -p:PublishProfile=FolderProfile
dotnet publish TalentCalculator.Launcher -p:PublishProfile=SingleFileProfile
```

**Where the output lands:**
- FolderProfile: `TalentCalculator.Launcher/bin/Release/net10.0/publish/`. Run `TalentCalculator.Launcher.exe` from there. If you copy it elsewhere, copy the whole folder.
- SingleFileProfile: `TalentCalculator.Launcher/bin/Release/net10.0/share/TalentCalculator.exe`. That one file is all anyone needs.
  (The `share-build` folder next to it is a by-product of the build and can be ignored.)

Either way, running the .exe starts a small web server and opens your browser at http://localhost:5080.
The single .exe unpacks the app into your temp folder (`%TEMP%\TalentCalculator`) on its first run.

Windows SmartScreen may warn about the single .exe the first time someone runs it, because it isn't code-signed.
They can click **More info**, then **Run anyway**.

## Publishing to GitHub Pages

`.github/workflows/deploy-pages.yml` builds only the Blazor project and publishes it to
https://andrewefirkus-hotmail.github.io/Talent-Calculators/ on every push to `main` that changes `TalentCalculator/`.
Python-only changes don't trigger it. You can also run it by hand from the Actions tab ("Run workflow").

One-time setup: on GitHub, go to Settings > Pages > Build and deployment, and set Source to **GitHub Actions**.
