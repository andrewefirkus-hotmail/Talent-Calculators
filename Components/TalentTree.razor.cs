using Microsoft.AspNetCore.Components;
using TalentCalculator.Models;
using TalentCalculator.Services;

namespace TalentCalculator.Components;

public partial class TalentTree
{
    [Parameter, EditorRequired]
    public TreeData Tree { get; set; } = default!;

    [Parameter, EditorRequired]
    public TalentBuild Build { get; set; } = default!;

    private int Rows =>
        Tree.Talents.Count == 0 ? 1 : Tree.Talents.Max(talent => talent.Row) + 1;

    private string HeaderIconStyle =>
        string.IsNullOrEmpty(Tree.Icon) ? ""
        : $"background-image:url('{Tree.Icon}')";
}
