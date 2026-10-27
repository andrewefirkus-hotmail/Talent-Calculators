"""Plain data classes that mirror the JSON files in static/data. No logic lives here."""
# ^ A string on the first line of a file (or a class or function) is a "docstring":
#   documentation that tools and editors show on hover, like /// <summary> in C#.

# PYTHON BASICS USED IN THIS FILE
# - "import" is Python's "using". "from X import Y" pulls in just Y from module X.
# - A "module" is simply a .py file. This file is the module "models".
# - Indentation (4 spaces) replaces { }. A line ending in ":" starts a block,
#   and the block is every line indented under it.

# Lets type hints mention a class before it's defined (ClassData uses itself below).
from __future__ import annotations

# dataclass: writes the constructor (__init__) and a readable print-out for us.
# field: used for default values that are lists (see TreeData.talents).
from dataclasses import dataclass, field
from typing import Any


# "@dataclass" is a decorator: a line starting with "@" that wraps the thing below it and adds
# behavior, similar to an attribute like [Parameter] in C#, but it actually changes the class.
# Here it generates a constructor from the fields, so you can write Prerequisite(id="x", rank=2).
@dataclass
class Prerequisite:
    # Fields are written as "name: type". The type is a hint for the editor; Python doesn't enforce it.
    id: str
    # "int | None" means "an int or None". None is Python's null.
    # "= None" gives a default, so callers may leave it out, like an optional parameter in C#.
    # Ranks needed in the prerequisite talent. None means its max rank.
    rank: int | None = None


# eq=False keeps Python's default "same object" comparison instead of comparing field by field.
# That matters because talents are used as dictionary keys in TalentBuild, like C# reference types.
@dataclass(eq=False)  # compared by identity, so a talent can be a dictionary key like in C#
class TalentData:
    id: str
    name: str
    row: int  # 0-based. Row N needs N * points_per_row points spent in the tree.
    col: int  # 0-based column (0-3)
    max_rank: int = 1
    icon: str | None = None
    # Tooltip text. {a|b|c} gives a value per rank, e.g. "Increases damage by {2|4|6}%."
    description: str = ""
    requires: Prerequisite | None = None


@dataclass(eq=False)
class TreeData:
    name: str
    icon: str | None = None
    background: str | None = None  # any CSS background value
    # "list[TalentData]" is a List<TalentData>.
    # field(default_factory=list) means "start each tree with its own new empty list".
    # Writing "= []" directly isn't allowed, because every tree would share the same list object.
    talents: list[TalentData] = field(default_factory=list)


@dataclass(eq=False)
class ClassData:
    name: str
    color: str | None = None
    total_points: int = 51
    first_talent_level: int = 10
    points_per_row: int = 5
    trees: list[TreeData] = field(default_factory=list)

    # METHOD: from_json
    # Turns the dictionary that json.load() produces into ClassData / TreeData / TalentData objects.
    # C# did this automatically with GetFromJsonAsync<ClassData>; Python's json module only gives
    # back plain dictionaries and lists, so we copy the values across by hand.
    #
    # "def" defines a function. "-> ClassData" is the return type hint.
    # "@staticmethod" means it belongs to the class but doesn't need an instance (no "self"),
    # exactly like a static method in C#. Called as ClassData.from_json(document).
    # "document: dict" is a parameter with a type hint: a dictionary (Dictionary<string, object>).
    @staticmethod
    def from_json(document: dict[str, Any]) -> ClassData:
        # An empty list, like new List<TreeData>().
        trees = []

        # LOOP: "for item in collection:" is C#'s "foreach (var item in collection)".
        # document.get("trees", []) reads the "trees" key, or gives [] if the key is missing,
        # so the loop simply runs zero times instead of crashing.
        for tree_document in document.get("trees", []):
            talents = []

            # A loop inside a loop: for every tree, go through each of its talents.
            for talent_document in tree_document.get("talents", []):
                requires_document = talent_document.get("requires")
                requires = None

                # CONDITIONAL: "if value:" is true when the value is "truthy".
                # None, 0, "" and empty lists/dictionaries count as false; anything else is true.
                # So this reads: "if the talent has a requires section".
                if requires_document:
                    # Square brackets read a key that must exist: document["id"].
                    # .get("rank") reads a key that may be missing and gives None if so.
                    requires = Prerequisite(id=requires_document["id"], rank=requires_document.get("rank"))

                # .append() adds to the end of a list, like List.Add() in C#.
                # "name=value" inside the call are named arguments, the same as C#'s name: value.
                talents.append(TalentData(
                        id=talent_document["id"],
                        name=talent_document["name"],
                        row=talent_document["row"],
                        col=talent_document["col"],
                        max_rank=talent_document.get("maxRank", 1),
                        icon=talent_document.get("icon"),
                        description=talent_document.get("description", ""),
                        requires=requires))

            # Back at the tree level (note the indentation): the talent loop has finished,
            # so build the tree with the talents we collected.
            trees.append(TreeData(
                    name=tree_document["name"],
                    icon=tree_document.get("icon"),
                    background=tree_document.get("background"),
                    talents=talents))

        # Both loops are done; build and return the class.
        return ClassData(
                name=document["name"],
                color=document.get("color"),
                total_points=document.get("totalPoints", 51),
                first_talent_level=document.get("firstTalentLevel", 10),
                points_per_row=document.get("pointsPerRow", 5),
                trees=trees)
