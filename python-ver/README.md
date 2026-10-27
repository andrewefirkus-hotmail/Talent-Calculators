# Talent Calculator (Python version)

The same calculator as the Blazor project, built with Flask and HTMX.

## Run it

```
pip install -r requirements.txt
python app.py
```

That opens http://localhost:5080. Stop it with Ctrl+C.

## How it's built

| Blazor version | Python version | What it does |
|---|---|---|
| `Models/TalentModels.cs` | `models.py` | Data classes the JSON loads into |
| `Services/TalentBuild.cs` | `talent_build.py` | All rules and the build code (a line-for-line port) |
| `Program.cs`, `App.razor`, `Pages/Calculator.razor.cs` | `app.py` | Routes: the page, and one endpoint per click |
| `Pages/Calculator.razor` | `templates/calculator.html`, `templates/_content.html` | Page, header, summary bar |
| `Components/TalentTree.razor` | `templates/_tree.html` | One tree with its arrows |
| `Components/TalentNode.razor` | `templates/_talent.html` | One talent and its tooltip |
| `Styles/*.scss`, `*.razor.scss` | `styles/*.scss` → `static/css/site.css` | Same SCSS, compiled into one file |
| `wwwroot/data`, `wwwroot/icons` | `static/data`, `static/icons` | Same files |

The biggest difference: in Blazor the C# runs in the browser and keeps the build in memory.
Here the server keeps nothing. Each click sends the current `?build=` code to the server,
which rebuilds the `TalentBuild` from it, applies the click, and sends back the new HTML for
the summary and trees. HTMX swaps that in and updates the address bar, so links still share builds.

## Changing styles

Edit the files in `styles/`, then run `python build_css.py` to regenerate `static/css/site.css`.

## Adding classes

Same data as the Blazor version. Regenerate with the extractor in the C# project's `tools` folder,
then copy `wwwroot/data` and `wwwroot/icons` into `static/`.

## Type checking

Type hints are checked twice:

- **Before running:** `python -m mypy` reads every hint and reports mismatches, like the C# compiler.
  Settings are in `mypy.ini` (strict mode).
- **While running:** beartype checks every call in `models.py`, `talent_build.py` and `app.py`.
  A wrong type raises an error at the call itself.
