"""
Holds the points spent in a class's talents and enforces the rules:
point cap, row unlocking, and prerequisites. Has no web or UI dependencies.
A straight port of Services/TalentBuild.cs from the Blazor version.
"""
from __future__ import annotations

# "re" is Python's regular expression module (System.Text.RegularExpressions in C#).
import re

# Our own data classes from models.py.
from models import ClassData, TalentData, TreeData


# PYTHON BASICS USED IN THIS FILE
# - "self" is Python's "this". Every normal method lists it as its first parameter, and Python
#   fills it in automatically: build.add(talent) really calls TalentBuild.add(build, talent).
# - A name starting with "_" (like _ranks or _learn) means "private, for use inside this class".
#   Python doesn't enforce it; it's a convention everyone follows.
# - "and", "or", "not" are &&, ||, ! in C#.
# - "is" / "is not" check for the very same object (like ReferenceEquals); "==" compares values.
# - "None" is null.
# - A dict ({}) is a Dictionary, a list ([]) is a List.


# "class Name:" declares a class. Everything indented under it belongs to the class.
class TalentBuild:

    # METHOD: __init__ (the constructor)
    # Python's constructor is always named __init__. TalentBuild(class_data) calls it.
    # There are no field declarations in Python: assigning self.something = ... creates the field.
    def __init__(self, class_data: ClassData):
        self.class_data = class_data

        # "dict[TalentData, int]" is a type hint for Dictionary<TalentData, int>. "{}" is an empty dict.
        self._ranks: dict[TalentData, int] = {}
        self._by_id: dict[str, TalentData] = {}
        self._tree_of: dict[TalentData, TreeData] = {}
        self._order: list[TalentData] = []  # every point, in the order it was learned

        # LOOP inside a LOOP: for each tree, then for each talent in that tree.
        # Fills the two lookup dictionaries so we can find a talent by id, and a talent's tree.
        # dictionary[key] = value adds or overwrites an entry, same as C#.
        for tree in class_data.trees:
            for talent in tree.talents:
                self._by_id[talent.id] = talent
                self._tree_of[talent] = tree

    # ---------- Queries ----------
    # These methods only read the build; none of them change anything.

    # METHOD: rank_of
    # How many points are in this talent. .get(key, 0) returns 0 when the key isn't in the
    # dictionary, like C#'s GetValueOrDefault.
    def rank_of(self, talent: TalentData) -> int:
        return self._ranks.get(talent, 0)

    # PROPERTY: learn_order
    # "@property" turns a method into a read-only property, exactly like a C# getter:
    # you write build.learn_order, with no parentheses.
    # list(...) makes a copy so callers can't change our internal list.
    @property
    def learn_order(self) -> list[TalentData]:
        """Every point spent, in the order it was learned (a talent appears once per rank)."""
        return list(self._order)

    # PROPERTY: points_spent
    # sum() adds up every value in a collection. .values() is the dictionary's values,
    # so this adds every talent's rank together.
    @property
    def points_spent(self) -> int:
        return sum(self._ranks.values())

    # PROPERTY: points_remaining
    # A property can use another property: self.points_spent (again, no parentheses).
    @property
    def points_remaining(self) -> int:
        return self.class_data.total_points - self.points_spent

    # METHOD: points_in
    # Points spent in one tree. The part inside sum(...) is a "generator expression":
    #   rank_of(talent) for talent in tree.talents
    # Read it as "the rank of each talent in the tree". It's the Python form of the LINQ
    # tree.Talents.Sum(RankOf). The for here is not a loop statement; it's part of the expression.
    def points_in(self, tree: TreeData) -> int:
        return sum(self.rank_of(talent) for talent in tree.talents)

    # PROPERTY: required_level
    # CONDITIONAL: "if condition:" runs the indented line only when the condition is true.
    # "==" compares values. When the if returns, the rest of the method is skipped,
    # so the last line acts as the "else" without needing to write one.
    @property
    def required_level(self) -> int:
        if self.points_spent == 0:
            return 0
        return self.class_data.first_talent_level - 1 + self.points_spent

    # METHOD: points_needed_for_row
    # Row 0 needs 0 points, row 1 needs 5, row 2 needs 10, and so on.
    def points_needed_for_row(self, row: int) -> int:
        return row * self.class_data.points_per_row

    # METHOD: find
    # Looks up a talent by its id. "TalentData | None" means it returns a talent, or None if
    # there's no talent with that id (dictionary .get() returns None for a missing key).
    def find(self, talent_id: str) -> TalentData | None:
        return self._by_id.get(talent_id)

    # METHOD: tree_of
    # Which tree a talent belongs to. Square brackets require the key to exist (it always does here).
    def tree_of(self, talent: TalentData) -> TreeData:
        return self._tree_of[talent]

    # METHOD: prerequisite_of
    # The talent this one requires, or None if it has no requirement.
    # "is None" is the correct way to check for None in Python (rather than "== None").
    def prerequisite_of(self, talent: TalentData) -> TalentData | None:
        if talent.requires is None:
            return None
        return self.find(talent.requires.id)

    # METHOD: required_prerequisite_rank
    # How many points the prerequisite needs. Three outcomes, checked top to bottom:
    #   1. no prerequisite at all             -> 0
    #   2. the data names a specific rank      -> that rank
    #   3. otherwise                           -> the prerequisite must be maxed
    # Each "if" returns, so only one of the three return lines ever runs.
    def required_prerequisite_rank(self, talent: TalentData) -> int:
        prerequisite = self.prerequisite_of(talent)
        if prerequisite is None:
            return 0
        # "is not None" checks both levels: the talent has a requires section AND it names a rank.
        if talent.requires is not None and talent.requires.rank is not None:
            return talent.requires.rank
        return prerequisite.max_rank

    # METHOD: is_row_unlocked
    # Returns a bool directly from a comparison: True when enough points are in the tree.
    def is_row_unlocked(self, talent: TalentData) -> bool:
        return self.points_in(self.tree_of(talent)) >= self.points_needed_for_row(talent.row)

    # METHOD: is_prerequisite_met
    # "A or B" is True when either side is True. Python stops at the first True ("short-circuits"),
    # just like || in C#. So when there's no prerequisite, the second part never runs.
    def is_prerequisite_met(self, talent: TalentData) -> bool:
        prerequisite = self.prerequisite_of(talent)
        return prerequisite is None or self.rank_of(prerequisite) >= self.required_prerequisite_rank(talent)

    # METHOD: can_add
    # All four rules must be true, joined with "and" (C#'s &&).
    # The outer ( ) lets the expression run over several lines; Python ignores line breaks inside brackets.
    def can_add(self, talent: TalentData) -> bool:
        return (
                self.rank_of(talent) < talent.max_rank
                and self.points_remaining > 0
                and self.is_row_unlocked(talent)
                and self.is_prerequisite_met(talent))

    # METHOD: can_remove
    # Whether a point can be taken out of this talent without breaking the build.
    # The method returns False as soon as it finds any problem, and True only if it gets to the end.
    def can_remove(self, talent: TalentData) -> bool:
        # No points means nothing to remove.
        rank = self.rank_of(talent)
        if rank == 0:
            return False

        # A talent that something else depends on can't drop below the required rank.
        # LOOP: check every other talent in the same tree.
        # CONDITIONAL: the "if" has three conditions joined with "and"; all three must be true:
        #   the other talent has points, it requires THIS talent, and removing a point would put
        #   this talent below what the other one needs.
        tree = self.tree_of(talent)
        for other in tree.talents:
            if (
                    self.rank_of(other) > 0
                    and self.prerequisite_of(other) is talent
                    and rank - 1 < self.required_prerequisite_rank(other)):
                return False

        # Every row that has points must still be unlocked by the points spent in the rows above it.
        # deepest_row: the highest row number that has any points.
        # max(...) with a generator expression reads as:
        #   "the row of each talent in the tree, but only talents that have points"
        # The "if" at the end is a filter, like LINQ's .Where(). So in C#:
        #   tree.Talents.Where(t => RankOf(t) > 0).Max(t => t.Row)
        deepest_row = max(
                tree_talent.row
                for tree_talent in tree.talents
                if self.rank_of(tree_talent) > 0)

        # LOOP over numbers: range(start, stop) counts from start up to, but NOT including, stop.
        # range(3, 7) gives 3, 4, 5, 6. That's why it says deepest_row + 1: to include deepest_row.
        # This is C#'s: for (var row = talent.Row + 1; row <= deepestRow; row++)
        for row in range(talent.row + 1, deepest_row + 1):
            # any(...) is True if at least one item is True, like LINQ's .Any().
            # "Does any talent in this row have points?"
            row_has_points = any(
                    tree_talent.row == row and self.rank_of(tree_talent) > 0
                    for tree_talent in tree.talents)

            # "continue" skips the rest of this pass and jumps to the next row, same as C#.
            if not row_has_points:
                continue

            # Points in all rows above this one, minus the point we want to remove.
            # Same as: tree.Talents.Where(t => t.Row < row).Sum(RankOf) - 1
            points_above_after_removal = sum(
                    self.rank_of(tree_talent)
                    for tree_talent in tree.talents
                    if tree_talent.row < row) - 1

            # Not enough points left to keep this row unlocked: refuse.
            if points_above_after_removal < self.points_needed_for_row(row):
                return False

        # Survived every check.
        return True

    # ---------- Changes ----------
    # These methods change the build.

    # METHOD: add
    # "if not X:" means "if X is false". Returning early keeps the happy path unindented.
    # .append() adds to the end of the list.
    def add(self, talent: TalentData) -> bool:
        if not self.can_add(talent):
            return False
        self._ranks[talent] = self.rank_of(talent) + 1
        self._order.append(talent)
        return True

    # METHOD: remove
    # Takes one point out, then removes that talent's LAST entry from the learn order.
    # Python lists have no LastIndexOf, so:
    #   self._order[::-1]   is a reversed copy of the list ([start:stop:step] slice, step -1 = backwards)
    #   .index(talent)      finds the first match in that reversed copy
    #   len(...) - 1 - that converts the position back to an index in the original list
    # "del list[index]" removes the item at that index, like RemoveAt().
    def remove(self, talent: TalentData) -> bool:
        if not self.can_remove(talent):
            return False
        self._ranks[talent] = self.rank_of(talent) - 1
        last_index = len(self._order) - 1 - self._order[::-1].index(talent)
        del self._order[last_index]
        self._repair_order()
        return True

    # METHOD: reset
    # Clears one tree. "-> None" means it returns nothing, like void in C#.
    # .pop(key, None) removes a key from the dictionary; the None stops it erroring if the key isn't there.
    # The second statement is a "list comprehension": [item for item in list if condition]
    # builds a NEW list of only the items that pass the "if", like LINQ's .Where(...).ToList().
    # Here: keep every learned talent that is NOT in this tree.
    def reset(self, tree: TreeData) -> None:
        for talent in tree.talents:
            self._ranks.pop(talent, None)
        self._order = [
                learned_talent
                for learned_talent in self._order
                if self.tree_of(learned_talent) is not tree]

    # METHOD: reset_all
    # .clear() empties a dictionary or list in place.
    def reset_all(self) -> None:
        self._ranks.clear()
        self._order.clear()

    # ---------- Build code ----------

    # METHOD: to_code
    # Builds the "?build=" text, e.g. "301-1_0cA1a".
    def to_code(self) -> str:
        """
        Build code in the Wowhead style: "{build}_{order}".
        Build: one digit per talent (JSON order) per tree, trees separated by '-',
        trailing zeros and empty trailing trees dropped.
        Order: every point in the order it was learned. A digit switches tree, a lowercase letter
        is one point in that tree's talent (a = first talent), and an uppercase letter
        is a talent taken from 0 to max rank in one go. E.g. "0Ac1a".
        """
        tree_codes = []

        # LOOP: one piece of text per tree.
        for tree in self.class_data.trees:
            # "".join(...) glues strings together with nothing between them (string.Concat in C#).
            # str(number) turns a number into text. So ranks 3, 0, 1 become "301".
            rank_digits = "".join(str(self.rank_of(talent)) for talent in tree.talents)
            # .rstrip("0") removes zeros from the right end only, like TrimEnd('0').
            tree_codes.append(rank_digits.rstrip("0"))

        # "-".join(list) puts "-" between the pieces, like string.Join("-", list).
        build = "-".join(tree_codes).rstrip("-")
        if build == "":
            return ""
        # "+" joins strings.
        return build + "_" + self._order_code()

    # METHOD: _order_code (private)
    # Turns the learn order into letters. This uses a "while" loop instead of "for" because the
    # loop sometimes jumps ahead several items at once (a capital letter covers several points).
    def _order_code(self) -> str:
        code = []
        current_tree = None
        order_index = 0

        # LOOP: "while condition:" repeats as long as the condition stays true, same as C#.
        # len(list) is the list's length (.Count in C#).
        while order_index < len(self._order):
            talent = self._order[order_index]
            tree = self.tree_of(talent)

            # Write the tree's number whenever we move to a different tree.
            # .index(item) is IndexOf.
            if tree is not current_tree:
                code.append(str(self.class_data.trees.index(tree)))
                current_tree = tree

            # ord("a") is the character code of "a" (97); chr(number) turns a code back into a character.
            # So talent 0 -> "a", talent 1 -> "b", and so on. Same as (char)('a' + index) in C#.
            letter = chr(ord("a") + tree.talents.index(talent))

            # A run of picks that takes the talent from 0 to max becomes one capital letter.
            # "x not in list" is True when the list doesn't contain x (!list.Contains(x)).
            # self._order[:order_index] is every item before this position (a slice; [..orderIndex] in C#).
            is_first_rank = talent not in self._order[:order_index]

            # Count how many times in a row this same talent appears, starting here.
            # "+= 1" adds one. Python has no "++" operator.
            run_length = 1
            while (
                    order_index + run_length < len(self._order)
                    and self._order[order_index + run_length] is talent):
                run_length += 1

            # CONDITIONAL with else: if the whole run takes the talent from 0 to max,
            # write one capital letter and skip past the whole run; otherwise write one lowercase
            # letter and move on by one.
            if is_first_rank and talent.max_rank > 1 and run_length == talent.max_rank:
                code.append(letter.upper())
                order_index += run_length
            else:
                code.append(letter)
                order_index += 1

        return "".join(code)

    # METHOD: load_code
    # Reads a "?build=" text back into the build. "str | None" means the code may be missing.
    def load_code(self, code: str | None) -> None:
        """
        Loads a build code. The learn order is replayed when it's valid and matches the build;
        otherwise the build digits are applied top row first. Every point goes through the rules.
        """
        self.reset_all()

        # "not code" is True for None and for "". .strip() removes surrounding spaces.
        # A bare "return" in a method that returns None just leaves the method.
        if not code or not code.strip():
            return

        # .split("_", 1) splits on the first "_" only, giving at most 2 parts:
        #   "301-1_0cA1a" -> ["301-1", "0cA1a"]
        sections = code.split("_", 1)
        wanted = self._parse_build(sections[0])
        has_order = len(sections) == 2

        # Three things must all be true for the learn order to be trusted:
        #   there is an order section, replaying it worked, and the result matches the digits.
        # all(...) is True only if every item is True (LINQ's .All()).
        # The generator has two "for"s, which is a nested loop in one expression:
        #   for every tree, for every talent in that tree, check its rank against the digits.
        # In C#: Class.Trees.SelectMany(tree => tree.Talents).All(talent => ...)
        order_matches_build = (
                has_order
                and self._replay_order(sections[1])
                and all(
                        self.rank_of(talent) == wanted.get(talent, 0)
                        for tree in self.class_data.trees
                        for talent in tree.talents))
        if order_matches_build:
            return

        # Fallback: ignore the order and apply the digits, top row first.
        self.reset_all()
        for tree in self.class_data.trees:
            # sorted(list, key=...) returns a sorted copy. "lambda candidate: ..." is a small unnamed
            # function, like C#'s "candidate => ...". Returning a pair (row, col) sorts by row first,
            # then by column: the same as .OrderBy(c => c.Row).ThenBy(c => c.Col).
            top_row_first = sorted(tree.talents, key=lambda candidate: (candidate.row, candidate.col))
            for talent in top_row_first:
                # range(n) counts 0, 1, ..., n-1, so this loop runs n times.
                # The variable is named "_point" with a leading underscore because we never use it;
                # we only care about repeating the loop that many times.
                for _point in range(wanted.get(talent, 0)):
                    # "break" leaves the innermost loop only (this one), same as C#.
                    # If a point can't be learned, stop trying this talent and move to the next.
                    if not self._learn(talent):
                        break

    # METHOD: _parse_build (private)
    # Reads the digits part ("301-1") into a dictionary of talent -> wanted rank.
    def _parse_build(self, build: str) -> dict[TalentData, int]:
        wanted: dict[TalentData, int] = {}

        # enumerate(list) gives (index, item) pairs, so the loop gets both at once.
        # "for tree_index, digits in ..." unpacks each pair into two variables.
        # C# equivalent: for (var treeIndex = 0; treeIndex < parts.Length; treeIndex++) { var digits = parts[treeIndex]; ... }
        for tree_index, digits in enumerate(build.split("-")):
            # More parts than the class has trees: stop reading.
            if tree_index >= len(self.class_data.trees):
                break
            talents = self.class_data.trees[tree_index].talents

            # Looping over a string gives one character at a time.
            for talent_index, digit in enumerate(digits):
                if talent_index >= len(talents):
                    break
                # .isdigit() checks the character is 0-9; int("3") turns text into the number 3.
                if digit.isdigit():
                    wanted[talents[talent_index]] = int(digit)
        return wanted

    # METHOD: _replay_order (private)
    # Re-learns each point from the letters part ("0cA1a"). Returns False if anything is invalid.
    def _replay_order(self, order: str) -> bool:
        tree = None

        # LOOP over each character of the string.
        for symbol in order:
            # A digit switches to that tree. "continue" then skips to the next character.
            if symbol.isdigit():
                tree_index = int(symbol)
                if tree_index >= len(self.class_data.trees):
                    return False
                tree = self.class_data.trees[tree_index]
                continue

            # A letter is a talent: "a" -> 0, "b" -> 1, ...
            talent_index = ord(symbol.lower()) - ord("a")
            # "or" chain: invalid if ANY of these is true.
            if tree is None or talent_index < 0 or talent_index >= len(tree.talents):
                return False
            talent = tree.talents[talent_index]

            # Python's one-line conditional ("ternary"): value_if_true if condition else value_if_false.
            # Same as C#'s: symbol is upper ? talent.MaxRank : 1. Note the order is different from C#.
            points_to_learn = talent.max_rank if symbol.isupper() else 1
            for _point in range(points_to_learn):
                if not self._learn(talent):
                    return False
        return True

    # METHOD: _learn (private)
    # Adds a point while loading (same rules as add).
    def _learn(self, talent: TalentData) -> bool:
        """Adds a point while loading (same as add, kept separate to mirror the C# version)."""
        if not self.can_add(talent):
            return False
        self._ranks[talent] = self.rank_of(talent) + 1
        self._order.append(talent)
        return True

    # METHOD: _repair_order (private)
    def _repair_order(self) -> None:
        """
        After a point is removed, an earlier pick may no longer have been legal at the time
        (e.g. its row was unlocked by the removed point). Re-learn the same points, always taking
        the earliest one in the old order that is allowed, so the order stays replayable.
        """
        # list(...) copies the list before we clear the build.
        remaining = list(self._order)
        self.reset_all()

        # "while remaining:" loops as long as the list isn't empty (an empty list counts as false).
        while remaining:
            # next(generator, None) returns the FIRST item the generator produces, or None if it
            # produces nothing. Combined with the filter, this reads:
            #   "the index of the first remaining talent that can be added, or None"
            # In C#: remaining.FindIndex(CanAdd), which returns -1 instead of None.
            next_index = next(
                    (index
                     for index, talent in enumerate(remaining)
                     if self.can_add(talent)),
                    None)
            if next_index is None:
                break  # can't happen for a valid build, but never loop forever
            # .pop(index) removes the item at that index AND returns it, so we can learn it.
            self._learn(remaining.pop(next_index))

    # METHOD: describe_rank (static)
    # Turns "by {5|10|15}%" into "by 10%" for rank 2.
    @staticmethod
    def describe_rank(talent: TalentData, rank: int) -> str:
        """Resolves {a|b|c} placeholders in a description for the given rank (1-based)."""

        # A function defined INSIDE another function. It can read "rank" from the outer function.
        # re.sub calls it once for every {...} it finds and uses the returned text as the replacement.
        def pick_value(placeholder: re.Match[str]) -> str:
            # group(1) is the text between the braces: "5|10|15" -> ["5", "10", "15"].
            values = placeholder.group(1).split("|")
            # Clamp the index between 0 and the last value (Math.Clamp in C#), then pick it.
            return values[min(max(rank - 1, 0), len(values) - 1)]

        # re.sub(pattern, replacement, text) is Regex.Replace. The r"..." prefix makes a "raw" string,
        # so backslashes are kept as-is (like @"..." in C#).
        return re.sub(r"\{([^{}]*)\}", pick_value, talent.description)
