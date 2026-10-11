using Microsoft.AspNetCore.Components;
using Microsoft.AspNetCore.Components.Web;
using TalentCalculator.Models;
using TalentCalculator.Services;

namespace TalentCalculator.Components;

public partial class TalentNode
{
    [Parameter, EditorRequired] 
    public TalentData Talent { get; set; } = default!;

    [Parameter, EditorRequired] 
    public TreeData Tree { get; set; } = default!;

    [Parameter, EditorRequired] 
    public TalentBuild Build { get; set; } = default!;

    private int Rank => Build.RankOf(Talent);

    private string StateClass =>
        Rank >= Talent.MaxRank ? "maxed"
        : Build.CanAdd(Talent) ? "available"
        : Rank > 0 ? "partial"
        : "locked";

    // Up to three capital letters from the talent's name, skipping short words like "of" and "and".
    private string Initials
    {
        get
        {
            var words = Talent.Name.Split(' ', StringSplitOptions.RemoveEmptyEntries);
            var significantWords = words.Where(word => word.Length > 2 || words.Length == 1);
            var initials = string.Concat(significantWords
                                       .Select(word => word[0]))
                                       .ToUpperInvariant();

            if (initials.Length == 0)
            {
                return Talent.Name[..1];
            }
            return initials[..Math.Min(3, initials.Length)];
        }
    }

    // Image if the data gives one, otherwise a colored tile derived from the talent name.
    private string IconStyle
    {
        get
        {
            if (!string.IsNullOrEmpty(Talent.Icon))
            {
                return $"background-image:url('{Talent.Icon}');";
            }
            // A simple hash of the id, so each talent always gets the same color.
            var hash = Talent.Id.Aggregate(17, (runningHash, character) => runningHash * 31 + character);
            var hue = Math.Abs(hash) % 360;
            return $"background: linear-gradient(135deg, hsl({hue},45%,42%), hsl({(hue + 40) % 360},50%,18%));";
        }
    }

    private void OnClick(MouseEventArgs mouseEvent)
    {
        if (mouseEvent.ShiftKey)
        {
            Build.Remove(Talent);
        }
        else
        {
            Build.Add(Talent);
        }
    }
}
