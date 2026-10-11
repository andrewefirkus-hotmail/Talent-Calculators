"""
Builds wwwroot/data/<class>.json and wwwroot/icons/<class>/*.png from a WoW 1.12 client.
Usage: python3 tools/extract_talents.py "<path to WoW Data folder>" rogue warrior ...
Reads the client's MPQ archives only; nothing in the game folder is changed.
"""
import json, os, re, struct, sys, io
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mpq

CLASS_INFO = {  # slug: (class mask, display name, color)
    "warrior": (1, "Warrior", "#c79c6e"), "paladin": (2, "Paladin", "#f58cba"), "hunter": (4, "Hunter", "#abd473"),
    "rogue": (8, "Rogue", "#fff569"), "priest": (16, "Priest", "#ffffff"), "shaman": (64, "Shaman", "#0070de"),
    "mage": (128, "Mage", "#69ccf0"), "warlock": (256, "Warlock", "#9482c9"), "druid": (1024, "Druid", "#ff7d0a"),
}
ARCHIVE_ORDER = ["patch-2.MPQ", "patch.MPQ", "dbc.MPQ", "interface.MPQ", "texture.MPQ", "misc.MPQ", "base.MPQ"]

# Spell.dbc column indices for 1.12
SPELL_PROC_CHANCE, SPELL_PROC_CHARGES, SPELL_DURATION, SPELL_STACK = 25, 26, 30, 39
SPELL_DIE_SIDES, SPELL_BASE_POINTS, SPELL_RADIUS, SPELL_AMPLITUDE, SPELL_CHAIN = 64, 76, 88, 94, 100
SPELL_POINTS_PER_COMBO = 112
SPELL_MAX_LEVEL, SPELL_LEVEL, SPELL_POINTS_PER_LEVEL = 27, 29, 73
MAX_PLAYER_LEVEL = 60
SPELL_ICON, SPELL_NAME, SPELL_DESCRIPTION = 117, 120, 138


class GameData:
    def __init__(self, dataFolder):
        self.archives = [mpq.Archive(os.path.join(dataFolder, name))
                         for name in ARCHIVE_ORDER if os.path.exists(os.path.join(dataFolder, name))]

    def read(self, name):
        for archive in self.archives:
            data = archive.read(name)
            if data is not None:
                return data
        return None

    def table(self, name):
        data = self.read("DBFilesClient\\" + name)
        _, count, fieldCount, recordSize, _ = struct.unpack_from('<4sIIII', data)
        strings = data[20 + count * recordSize:]
        rows = {}
        for index in range(count):
            row = struct.unpack_from('<%dI' % fieldCount, data, 20 + index * recordSize)
            rows[row[0]] = row
        def text(offset):
            return strings[offset:strings.index(b'\0', offset)].decode('utf8', 'replace')
        return rows, text


def signed(value):
    return value - (1 << 32) if value >= 1 << 31 else value


def format_number(value):
    value = round(value, 1)
    return str(int(value)) if value == int(value) else str(value)


class Describer:
    def __init__(self, game):
        self.spells, self.text = game.table("Spell.dbc")
        self.durations, _ = game.table("SpellDuration.dbc")
        self.radii, _ = game.table("SpellRadius.dbc")

    def points(self, spell, effect):
        base = signed(spell[SPELL_BASE_POINTS + effect]) + 1
        # Some values grow with level; show them at max level (capped where the spell stops scaling).
        perLevel = struct.unpack('<f', struct.pack('<I', spell[SPELL_POINTS_PER_LEVEL + effect]))[0]
        if perLevel:
            level = min(MAX_PLAYER_LEVEL, spell[SPELL_MAX_LEVEL] or MAX_PLAYER_LEVEL) - spell[SPELL_LEVEL]
            base += int(perLevel * level)
        dieSides = spell[SPELL_DIE_SIDES + effect]
        return abs(base), (abs(base + dieSides - 1) if dieSides > 1 else None)

    def duration_ms(self, spell):
        row = self.durations.get(spell[SPELL_DURATION])
        return signed(row[1]) if row else 0

    def value(self, spell, code, effect):
        effect = max(effect - 1, 0)
        if code in "sm":
            low, high = self.points(spell, effect)
            return low if high is None else (low, high)
        if code == "o":
            amplitude = spell[SPELL_AMPLITUDE + effect] or 1
            return self.points(spell, effect)[0] * (self.duration_ms(spell) // amplitude)
        if code == "t": return spell[SPELL_AMPLITUDE + effect] / 1000
        if code == "b":
            return struct.unpack('<f', struct.pack('<I', spell[SPELL_POINTS_PER_COMBO + effect]))[0]
        if code == "h": return spell[SPELL_PROC_CHANCE]
        if code == "n": return spell[SPELL_PROC_CHARGES]
        if code == "u": return spell[SPELL_STACK]
        if code == "x": return spell[SPELL_CHAIN + effect]
        if code == "a":
            row = self.radii.get(spell[SPELL_RADIUS + effect])
            return struct.unpack('<f', struct.pack('<I', row[1]))[0] if row else 0
        if code == "d":
            seconds = self.duration_ms(spell) / 1000
            if seconds >= 60 and seconds % 60 == 0: return "%d min" % (seconds // 60)
            return format_number(seconds) + " sec"
        return None

    def describe(self, spellId):
        spell = self.spells[spellId]
        description = self.text(spell[SPELL_DESCRIPTION])
        # Higher ranks sometimes say "1.5 min" where lower ranks say "45 sec"; use seconds throughout.
        description = re.sub(r'\$/60000;([sS]\d) min', r'$/1000;\1 sec', description)
        description = re.sub(r'\s*More effective than [^(]*\(Rank \d+\)\.', '', description)
        pattern = re.compile(r'\$(?:/(\d+);|\*(\d+);)?(\d*)([smothnuxadbSMOTHNUXADB])([1-3]?)')
        def replace(match):
            divisor, multiplier, otherSpell, code, effect = match.groups()
            source = self.spells.get(int(otherSpell)) if otherSpell else spell
            if source is None: return match.group(0)
            result = self.value(source, code.lower(), int(effect or 1))
            if result is None: return match.group(0)
            if isinstance(result, str): return result
            if isinstance(result, tuple): return "%s to %s" % tuple(format_number(part) for part in result)
            if divisor: result = result / int(divisor)
            if multiplier: result = result * int(multiplier)
            return format_number(result)
        description = pattern.sub(replace, description)
        description = re.sub(r'\$[lL]([^:;]*):([^;]*);', r'\2', description)
        description = re.sub(r'\$[gG]([^:;]*):([^;]*);', r'\1', description)
        return re.sub(r'\s+', ' ', description).strip()


def merge_ranks(descriptions):
    """Turns one description per rank into a single text with {a|b|c} where the numbers differ."""
    numberPattern = re.compile(r'\d+(?:\.\d+)?')
    numbersPerRank = [numberPattern.findall(description) for description in descriptions]
    if len(set(len(numbers) for numbers in numbersPerRank)) != 1:
        return descriptions[-1]
    # The words around the numbers come from the last rank (it has the plural forms, e.g. "points").
    pieces = numberPattern.sub('#', descriptions[-1]).split('#')
    merged = pieces[0]
    for position, piece in enumerate(pieces[1:]):
        values = [numbers[position] for numbers in numbersPerRank]
        merged += values[0] if len(set(values)) == 1 else "{" + "|".join(values) + "}"
        merged += piece
    return merged


def slug(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def save_icon(game, iconPath, iconFolder):
    fileName = iconPath.split("\\")[-1].lower() + ".png"
    target = os.path.join(iconFolder, fileName)
    if not os.path.exists(target):
        data = game.read(iconPath + ".blp")
        if data is None:
            print("  missing icon", iconPath)
            return None
        Image.open(io.BytesIO(data)).convert("RGBA").save(target)
    return fileName


def save_background(game, backgroundName, iconFolder):
    """Stitches the four TalentFrame pieces (256+64 wide, 256+128 tall) into one image."""
    fileName = "background-" + backgroundName.lower() + ".jpg"
    target = os.path.join(iconFolder, fileName)
    if os.path.exists(target):
        return fileName
    canvas = Image.new("RGB", (320, 384))
    pieces = {"TopLeft": (0, 0), "TopRight": (256, 0), "BottomLeft": (0, 256), "BottomRight": (256, 256)}
    for pieceName, corner in pieces.items():
        data = game.read("Interface\\TalentFrame\\%s-%s.blp" % (backgroundName, pieceName))
        if data is None:
            print("  missing background", backgroundName, pieceName)
            return None
        canvas.paste(Image.open(io.BytesIO(data)).convert("RGB"), corner)
    # The game only shows the left 296 x 335 of the stitched art; the rest is padding.
    canvas.crop((0, 0, 296, 335)).save(target, quality=90)
    return fileName


def build_class(game, describer, classSlug, projectRoot):
    classMask, className, color = CLASS_INFO[classSlug]
    tabs, tabText = game.table("TalentTab.dbc")
    talents, _ = game.table("Talent.dbc")
    icons, iconText = game.table("SpellIcon.dbc")
    iconFolder = os.path.join(projectRoot, "wwwroot", "icons", classSlug)
    os.makedirs(iconFolder, exist_ok=True)

    dataPath = os.path.join(projectRoot, "wwwroot", "data", classSlug + ".json")
    oldBackgrounds = {}
    if os.path.exists(dataPath):
        with open(dataPath) as oldFile:
            oldBackgrounds = {tree["name"]: tree.get("background") for tree in json.load(oldFile)["trees"]}

    classTabs = sorted((tab for tab in tabs.values() if tab[12] == classMask), key=lambda tab: tab[13])
    trees = []
    for tab in classTabs:
        treeName = tabText(tab[1])
        treeIcon = save_icon(game, iconText(icons[tab[10]][1]), iconFolder)
        tabTalents = sorted((talent for talent in talents.values() if talent[1] == tab[0]),
                            key=lambda talent: (talent[2], talent[3]))
        idOfTalent = {}
        entries = []
        for talent in tabTalents:
            rankSpells = [spellId for spellId in talent[4:9] if spellId]
            firstSpell = describer.spells[rankSpells[0]]
            name = describer.text(firstSpell[SPELL_NAME])
            idOfTalent[talent[0]] = slug(name)
            entries.append((talent, name, rankSpells, firstSpell))
        treeTalents = []
        for talent, name, rankSpells, firstSpell in entries:
            entry = {"id": slug(name), "name": name, "row": talent[2], "col": talent[3], "maxRank": len(rankSpells)}
            iconFile = save_icon(game, iconText(icons[firstSpell[SPELL_ICON]][1]), iconFolder)
            if iconFile: entry["icon"] = "icons/%s/%s" % (classSlug, iconFile)
            if talent[13]:
                entry["requires"] = {"id": idOfTalent[talent[13]]}
                requiredRank = talent[16] + 1
                prerequisite = next(other for other in entries if other[0][0] == talent[13])
                if requiredRank < len(prerequisite[2]): entry["requires"]["rank"] = requiredRank
            entry["description"] = merge_ranks([describer.describe(spellId) for spellId in rankSpells])
            treeTalents.append(entry)
        tree = {"name": treeName}
        if treeIcon: tree["icon"] = "icons/%s/%s" % (classSlug, treeIcon)
        backgroundFile = save_background(game, tabText(tab[14]), iconFolder)
        if backgroundFile:
            tree["background"] = "url('icons/%s/%s') center / cover" % (classSlug, backgroundFile)
        elif oldBackgrounds.get(treeName):
            tree["background"] = oldBackgrounds[treeName]
        tree["talents"] = treeTalents
        trees.append(tree)

    write_class(dataPath, {"name": className, "color": color, "totalPoints": 51, "firstTalentLevel": 10,
                           "pointsPerRow": 5, "trees": trees})
    print(classSlug, [(tree["name"], len(tree["talents"])) for tree in trees])


def write_class(path, classData):
    """Same layout as the hand-written files: one talent per line, description on the next."""
    dump = lambda value: json.dumps(value, ensure_ascii=False)
    lines = ['{']
    for key in ("name", "color", "totalPoints", "firstTalentLevel", "pointsPerRow"):
        lines.append('  "%s": %s,' % (key, dump(classData[key])))
    lines.append('  "trees": [')
    treeBlocks = []
    for tree in classData["trees"]:
        block = ['    {']
        for key in ("name", "icon", "background"):
            if key in tree: block.append('      "%s": %s,' % (key, dump(tree[key])))
        block.append('      "talents": [')
        talentLines = []
        for talent in tree["talents"]:
            head = ", ".join('"%s": %s' % (key, dump(talent[key]))
                             for key in ("id", "name", "row", "col", "maxRank", "icon") if key in talent)
            line = '        { ' + head + ','
            if "requires" in talent: line += '\n          "requires": ' + dump(talent["requires"]).replace('{', '{ ').replace('}', ' }') + ','
            line += '\n          "description": ' + dump(talent["description"]) + ' }'
            talentLines.append(line)
        block.append(",\n".join(talentLines))
        block += ['      ]', '    }']
        treeBlocks.append("\n".join(block))
    lines.append(",\n".join(treeBlocks))
    lines += ['  ]', '}']
    with open(path, "w", encoding="utf8") as output:
        output.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    projectRoot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    game = GameData(sys.argv[1])
    describer = Describer(game)
    for classSlug in sys.argv[2:]:
        build_class(game, describer, classSlug, projectRoot)
