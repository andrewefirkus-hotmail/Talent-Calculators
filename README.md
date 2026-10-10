# Talent Calculator (Blazor WebAssembly)

A homemade Classic WoW-style talent calculator, modeled on Wowhead's Classic Rogue calculator.
No database and no server code: everything runs in the browser and the talent data is a JSON file.

## Run it

Requires the [.NET 10 SDK](https://dotnet.microsoft.com/download).

```
dotnet run
```

Then open the URL it prints (http://localhost:5074 by default). `dotnet watch` gives you hot reload while you tinker.

## How to use

- **Click** a talent to add a point, **right-click** (or shift-click) to remove one.
- Each row unlocks after 5 points in that tree; arrows show prerequisites, which must be maxed.
- 51 points total; the header shows points left and the character level the build needs.
- The build is saved in the address bar (`?build=...`), so you can bookmark or share it.

## Project layout

| Path | What it is |
| --- | --- |
| `wwwroot/data/rogue.json` | The Rogue talent data. Edit this to fix names, ranks, positions and text. |
| `wwwroot/data/classes.json` | List of classes. Add an entry plus a `{slug}.json` file to add a class; it appears at `/{slug}`. |
| `wwwroot/icons/` | Put talent icons here and reference them with `"icon": "icons/name.jpg"`. |
| `Models/TalentModels.cs` | Shapes of the JSON data. |
| `Services/TalentBuild.cs` | All the rules (point cap, row unlocking, prerequisites, safe removal, build code). No UI code. |
| `Components/TalentTree.razor` | One tree: header, grid, prerequisite arrows, reset button. Layout sizes are constants at the bottom. |
| `Components/TalentNode.razor` | One talent icon with its rank badge and tooltip. |
| `Pages/Calculator.razor` | The page: loads the data, shows the summary bar and the three trees. |
| `wwwroot/css/app.css` | All styling (bottom half of the file). |

## Talent data format

```json
{
  "id": "lethality",              // unique within the class
  "name": "Lethality",
  "row": 2, "col": 2,             // 0-based; 4 columns, row N needs N*5 points in the tree
  "maxRank": 5,
  "icon": "icons/lethality.jpg",  // optional; initials on a colored tile if omitted
  "requires": { "id": "malice" }, // optional; add "rank": 3 if it doesn't need the max rank
  "description": "Increases crit damage by {6|12|18|24|30}%."   // {a|b|c} = value per rank
}
```

Trees take an optional `"background"` (any CSS background, e.g. `"url('images/assassination.jpg') center/cover"`)
and an optional `"icon"`.

The bundled Rogue data matches the layout and max ranks from the Wowhead screenshots. Most names and
descriptions are from memory of Classic and a few are placeholders, so treat it as sample data to replace.

## Build code format

Modeled on Wowhead's: `?build=3053-32-5_0Ac1a`. The part before `_` is the build, and the part after is the order the points were learned.

- **Build:** one digit per talent (in the order they appear in the JSON) per tree, trees separated by `-`
  in JSON order (Assassination-Combat-Subtlety). Trailing zeros are dropped, so taking only the third
  talent in a tree gives `003`.
- **Order:** a digit switches to that tree, a lowercase letter is one point in that tree's talent
  (`a` = first talent in the JSON), and an uppercase letter means the talent was taken from 0 to max in one go.
  `0Ac1a` = max the first Assassination talent, one point in its third, then one point in Combat's first.

When a link loads, the order is replayed if it is valid and matches the build; otherwise the build digits are
used on their own. Reordering talents in the JSON changes what old codes mean.
