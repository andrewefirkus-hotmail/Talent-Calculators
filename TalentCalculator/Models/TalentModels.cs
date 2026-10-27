namespace TalentCalculator.Models;

/// <summary>A playable class and its talent trees. Loaded from wwwroot/data/{slug}.json.</summary>
public class ClassData
{
    public string Name { get; set; } = "";
    /// <summary>Total talent points available (51 at level 60 in Classic).</summary>
    public int TotalPoints { get; set; } = 51;
    /// <summary>Character level that grants the first talent point.</summary>
    public int FirstTalentLevel { get; set; } = 10;
    /// <summary>Points that must be spent in a tree to unlock each next row.</summary>
    public int PointsPerRow { get; set; } = 5;
    public string? Color { get; set; }
    public List<TreeData> Trees { get; set; } = new();
}

public class TreeData
{
    public string Name { get; set; } = "";
    /// <summary>Optional image path (relative to wwwroot) shown next to the tree name.</summary>
    public string? Icon { get; set; }
    /// <summary>Any CSS background value, e.g. a gradient or url('images/bg.jpg').</summary>
    public string? Background { get; set; }
    public List<TalentData> Talents { get; set; } = new();
}

public class TalentData
{
    /// <summary>Unique id within the class, used for prerequisites.</summary>
    public string Id { get; set; } = "";
    public string Name { get; set; } = "";
    /// <summary>0-based row. Row N needs N * PointsPerRow points spent in the tree.</summary>
    public int Row { get; set; }
    /// <summary>0-based column (0-3).</summary>
    public int Col { get; set; }
    public int MaxRank { get; set; } = 1;
    /// <summary>Optional image path (relative to wwwroot). Falls back to the talent's initials.</summary>
    public string? Icon { get; set; }
    /// <summary>
    /// Tooltip text. Use {a|b|c} to give a value per rank, e.g. "Increases damage by {2|4|6}%."
    /// </summary>
    public string Description { get; set; } = "";
    public Prerequisite? Requires { get; set; }
}

public class Prerequisite
{
    public string Id { get; set; } = "";
    /// <summary>Ranks needed in the prerequisite talent. Defaults to its max rank.</summary>
    public int? Rank { get; set; }
}
