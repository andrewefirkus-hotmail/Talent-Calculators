using System.Text.RegularExpressions;
using TalentCalculator.Models;

namespace TalentCalculator.Services;

/// <summary>
/// Holds the points spent in a class's talents and enforces the rules:
/// point cap, row unlocking, and prerequisites. Has no UI dependencies.
/// </summary>
public class TalentBuild
{
    private readonly Dictionary<TalentData, int> _ranks = new();
    private readonly Dictionary<string, TalentData> _byId;
    private readonly Dictionary<TalentData, TreeData> _treeOf = new();
    private readonly List<TalentData> _order = new(); // every point, in the order it was learned

    public ClassData Class { get; }

    public event Action? Changed;

    public TalentBuild(ClassData classData)
    {
        Class = classData;
        _byId = new();
        foreach (var tree in classData.Trees)
            foreach (var talent in tree.Talents)
            {
                _byId[talent.Id] = talent;
                _treeOf[talent] = tree;
            }
    }

    public int RankOf(TalentData talent) => _ranks.GetValueOrDefault(talent);

    /// <summary>Every point spent, in the order it was learned (a talent appears once per rank).</summary>
    public IReadOnlyList<TalentData> LearnOrder => _order;
    public int PointsSpent => _ranks.Values.Sum();
    public int PointsRemaining => Class.TotalPoints - PointsSpent;
    public int PointsIn(TreeData tree) => tree.Talents.Sum(RankOf);
    public int RequiredLevel => PointsSpent == 0 ? 0 : Class.FirstTalentLevel - 1 + PointsSpent;
    public int PointsNeededForRow(int row) => row * Class.PointsPerRow;

    public TalentData? Find(string id) => _byId.GetValueOrDefault(id);
    public TreeData TreeOf(TalentData talent) => _treeOf[talent];

    public TalentData? PrerequisiteOf(TalentData talent) =>
        talent.Requires is null ? null : Find(talent.Requires.Id);

    public int RequiredPrerequisiteRank(TalentData talent)
    {
        var pre = PrerequisiteOf(talent);
        return pre is null ? 0 : talent.Requires!.Rank ?? pre.MaxRank;
    }

    public bool IsRowUnlocked(TalentData talent) =>
        PointsIn(TreeOf(talent)) >= PointsNeededForRow(talent.Row);

    public bool IsPrerequisiteMet(TalentData talent)
    {
        var pre = PrerequisiteOf(talent);
        return pre is null || RankOf(pre) >= RequiredPrerequisiteRank(talent);
    }

    /// <summary>True when the talent could take points right now (ignoring whether it's maxed).</summary>
    public bool IsAvailable(TalentData talent) =>
        IsRowUnlocked(talent) && IsPrerequisiteMet(talent) && (PointsRemaining > 0 || RankOf(talent) > 0);

    public bool CanAdd(TalentData talent) =>
        RankOf(talent) < talent.MaxRank && PointsRemaining > 0 && IsRowUnlocked(talent) && IsPrerequisiteMet(talent);

    public bool CanRemove(TalentData talent)
    {
        var rank = RankOf(talent);
        if (rank == 0) return false;

        // A talent that something else depends on can't drop below the required rank.
        foreach (var other in TreeOf(talent).Talents)
            if (RankOf(other) > 0 && PrerequisiteOf(other) == talent && rank - 1 < RequiredPrerequisiteRank(other))
                return false;

        // Every row that has points must still be unlocked by the points spent in the rows above it.
        var tree = TreeOf(talent);
        var deepestRow = tree.Talents.Where(t => RankOf(t) > 0).Max(t => t.Row);
        for (var row = talent.Row + 1; row <= deepestRow; row++)
        {
            if (!tree.Talents.Any(t => t.Row == row && RankOf(t) > 0)) continue;
            var above = tree.Talents.Where(t => t.Row < row).Sum(RankOf) - 1;
            if (above < PointsNeededForRow(row)) return false;
        }
        return true;
    }

    public bool Add(TalentData talent)
    {
        if (!CanAdd(talent)) return false;
        _ranks[talent] = RankOf(talent) + 1;
        _order.Add(talent);
        Changed?.Invoke();
        return true;
    }

    public bool Remove(TalentData talent)
    {
        if (!CanRemove(talent)) return false;
        _ranks[talent] = RankOf(talent) - 1;
        _order.RemoveAt(_order.LastIndexOf(talent));
        RepairOrder();
        Changed?.Invoke();
        return true;
    }

    public void Reset(TreeData tree)
    {
        foreach (var talent in tree.Talents) _ranks.Remove(talent);
        _order.RemoveAll(t => TreeOf(t) == tree);
        Changed?.Invoke();
    }

    public void ResetAll()
    {
        _ranks.Clear();
        _order.Clear();
        Changed?.Invoke();
    }

    /// <summary>
    /// Build code in the Wowhead style: "{build}_{order}".
    /// Build: one digit per talent (JSON order) per tree, trees separated by '-' in JSON order
    /// (Assassination-Combat-Subtlety), trailing zeros and empty trailing trees dropped.
    /// Order: every point in the order it was learned. A digit switches tree, a lowercase letter
    /// is one point in that tree's talent (a = first talent in the JSON), and an uppercase letter
    /// is a talent taken from 0 to max rank in one go. E.g. "0Ac1a".
    /// </summary>
    public string ToCode()
    {
        var build = string.Join("-", Class.Trees.Select(tree =>
            new string(tree.Talents.Select(t => (char)('0' + RankOf(t))).ToArray()).TrimEnd('0'))).TrimEnd('-');
        return build.Length == 0 ? "" : build + "_" + OrderCode();
    }

    private string OrderCode()
    {
        var code = new System.Text.StringBuilder();
        TreeData? currentTree = null;
        for (var i = 0; i < _order.Count; i++)
        {
            var talent = _order[i];
            var tree = TreeOf(talent);
            if (tree != currentTree)
            {
                code.Append((char)('0' + Class.Trees.IndexOf(tree)));
                currentTree = tree;
            }
            var letter = (char)('a' + tree.Talents.IndexOf(talent));

            // A run of picks that takes the talent from 0 to max becomes one capital letter.
            var isFirstRank = _order.Take(i).All(t => t != talent);
            var run = 1;
            while (i + run < _order.Count && _order[i + run] == talent) run++;
            if (isFirstRank && talent.MaxRank > 1 && run == talent.MaxRank)
            {
                code.Append(char.ToUpperInvariant(letter));
                i += run - 1;
            }
            else
            {
                code.Append(letter);
            }
        }
        return code.ToString();
    }

    /// <summary>
    /// Loads a build code. The learn order is replayed when it's valid and matches the build;
    /// otherwise the build digits are applied top row first. Every point goes through the rules.
    /// </summary>
    public void LoadCode(string? code)
    {
        _ranks.Clear();
        _order.Clear();
        if (!string.IsNullOrWhiteSpace(code))
        {
            var split = code.Split('_', 2);
            var wanted = ParseBuild(split[0]);
            if (split.Length < 2 || !ReplayOrder(split[1]) || !Class.Trees.SelectMany(t => t.Talents).All(t => RankOf(t) == wanted.GetValueOrDefault(t)))
            {
                _ranks.Clear();
                _order.Clear();
                foreach (var tree in Class.Trees)
                    foreach (var talent in tree.Talents.OrderBy(t => t.Row).ThenBy(t => t.Col))
                        for (var r = 0; r < wanted.GetValueOrDefault(talent); r++)
                            if (!Learn(talent)) break;
            }
        }
        Changed?.Invoke();
    }

    private Dictionary<TalentData, int> ParseBuild(string build)
    {
        var wanted = new Dictionary<TalentData, int>();
        var parts = build.Split('-');
        for (var i = 0; i < parts.Length && i < Class.Trees.Count; i++)
        {
            var talents = Class.Trees[i].Talents;
            for (var j = 0; j < parts[i].Length && j < talents.Count; j++)
                if (char.IsDigit(parts[i][j])) wanted[talents[j]] = parts[i][j] - '0';
        }
        return wanted;
    }

    private bool ReplayOrder(string order)
    {
        TreeData? tree = null;
        foreach (var c in order)
        {
            if (char.IsDigit(c))
            {
                var index = c - '0';
                if (index >= Class.Trees.Count) return false;
                tree = Class.Trees[index];
                continue;
            }
            var talentIndex = char.ToLowerInvariant(c) - 'a';
            if (tree is null || talentIndex < 0 || talentIndex >= tree.Talents.Count) return false;
            var talent = tree.Talents[talentIndex];
            var times = char.IsUpper(c) ? talent.MaxRank : 1;
            for (var r = 0; r < times; r++)
                if (!Learn(talent)) return false;
        }
        return true;
    }

    // Adds a point without raising Changed (used while loading).
    private bool Learn(TalentData talent)
    {
        if (!CanAdd(talent)) return false;
        _ranks[talent] = RankOf(talent) + 1;
        _order.Add(talent);
        return true;
    }

    /// <summary>
    /// After a point is removed, an earlier pick may no longer have been legal at the time
    /// (e.g. its row was unlocked by the removed point). Re-learn the same points, always taking
    /// the earliest one in the old order that is allowed, so the order stays replayable.
    /// </summary>
    private void RepairOrder()
    {
        var remaining = _order.ToList();
        _ranks.Clear();
        _order.Clear();
        while (remaining.Count > 0)
        {
            var next = remaining.FindIndex(CanAdd);
            if (next < 0) break; // can't happen for a valid build, but never loop forever
            Learn(remaining[next]);
            remaining.RemoveAt(next);
        }
    }

    /// <summary>
    /// Resolves {a|b|c} placeholders in a description for the given rank (1-based).
    /// </summary>
    public static string DescribeRank(TalentData talent, int rank) =>
        Regex.Replace(talent.Description, @"\{([^{}]*)\}", m =>
        {
            var values = m.Groups[1].Value.Split('|');
            return values[Math.Clamp(rank - 1, 0, values.Length - 1)];
        });
}
