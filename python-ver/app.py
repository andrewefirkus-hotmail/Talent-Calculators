"""
Flask version of the talent calculator. Run with:  python app.py   then open http://localhost:5080

The server keeps no state. Every request rebuilds the TalentBuild from the ?build= code in the URL,
applies the click, renders the page (or just the part that changed), and hands back the new URL.
"""
# HOW A REQUEST FLOWS THROUGH THIS FILE
# 1. The browser asks for a URL, e.g. GET /rogue?build=301-1_0cA1a
# 2. Flask finds the function whose @app.route(...) pattern matches, and calls it.
#    "<class_slug>" in the pattern becomes the function's class_slug parameter ("rogue").
# 3. The function builds a TalentBuild from the ?build= code, then returns HTML from a template.
# 4. Clicking a talent makes HTMX send a POST to /rogue/talent/<id>?build=..., which applies the
#    click and returns only the summary and trees (_content.html), plus the new URL in a header.
# This is the same job Program.cs, App.razor and Calculator.razor.cs do in the Blazor version.

# Standard library modules (they come with Python, nothing to install):
import json                       # reads .json files into dicts and lists
import webbrowser                 # opens the default browser
from typing import Any            # "Any" is the type hint for "could be anything" (like object/dynamic)
from functools import lru_cache   # remembers a function's results (see load_class)
from pathlib import Path          # file paths; the "/" operator joins path pieces

# Flask, installed from requirements.txt:
from flask import Flask, abort, redirect, render_template, request, url_for
from werkzeug.wrappers import Response  # the type Flask's redirect() returns

# Our own modules (models.py and talent_build.py in this folder):
# beartype checks type hints WHILE the program runs: a call with the wrong type raises an error
# right at the call, instead of crashing somewhere deeper later (or not at all).
# beartype_packages(...) must run BEFORE the import lines below: it hooks the import so every
# function and class in models.py and talent_build.py gets checked automatically.
from beartype import beartype
from beartype.claw import beartype_packages

beartype_packages(("models", "talent_build"))

from models import ClassData, TalentData, TreeData
from talent_build import TalentBuild

# Module-level constants. ALL_CAPS is the naming convention for "don't change this".
# __file__ is the path of this .py file, so APP_FOLDER is the python-ver folder.
# This file is run directly, so the hook above can't reach it. Instead each function here is
# marked with @beartype, which does the same check for that one function.
APP_FOLDER = Path(__file__).parent
DATA_FOLDER = APP_FOLDER / "static" / "data"
DEFAULT_CLASS = "rogue"

# The web application object. __name__ tells Flask where to look for templates/ and static/.
# Every "@app.something" decorator below registers a function with this object.
app = Flask(__name__)


# FUNCTION: load_classes
# Reads classes.json (the list of classes for the header links).
# Functions outside a class don't take "self"; they're like static methods in C#.
# "@lru_cache" remembers the result after the first call, so the file is read only once
# while the server runs instead of on every request.
# "with open(...) as classes_file:" opens the file and guarantees it's closed when the block ends,
# even if an error happens. It's C#'s "using (var file = File.OpenRead(...)) { ... }".
@lru_cache
@beartype
def load_classes() -> list[dict[str, Any]]:
    with open(DATA_FOLDER / "classes.json", encoding="utf8") as classes_file:
        # json.load can return anything, so we state what we expect by annotating the variable.
        classes: list[dict[str, Any]] = json.load(classes_file)
        return classes


# FUNCTION: load_class
# Reads one class file, e.g. static/data/rogue.json, into a ClassData object.
# f"{class_slug}.json" is an "f-string": values inside { } are inserted, like C#'s $"{classSlug}.json".
# CONDITIONAL: if the file doesn't exist, abort(404) stops the request with "404 Not Found".
# abort() raises an error that Flask turns into the 404 page, so nothing after it runs.
# lru_cache keeps one result per different class_slug, so each class file is read once.
@lru_cache
@beartype
def load_class(class_slug: str) -> ClassData:
    class_path = DATA_FOLDER / f"{class_slug}.json"
    if not class_path.is_file():
        abort(404)
    with open(class_path, encoding="utf8") as class_file:
        return ClassData.from_json(json.load(class_file))


# FUNCTION: build_from_request
# Creates a fresh TalentBuild and loads the ?build= code from the current request's URL.
# "request" is Flask's object for the request being handled right now (like HttpContext.Request).
# request.args is the query string; .get("build") returns None when there is no ?build=.
@beartype
def build_from_request(class_slug: str) -> TalentBuild:
    build = TalentBuild(load_class(class_slug.lower()))
    build.load_code(request.args.get("build"))
    return build


# FUNCTION: page_url
# The address the browser should show for this build.
# url_for("calculator", ...) builds a URL for the function named "calculator" below, so URLs are
# never typed by hand. Extra named arguments that aren't part of the route become the query string:
#   url_for("calculator", class_slug="rogue", build="301") -> "/rogue?build=301"
# CONDITIONAL: with no points spent, leave ?build= off entirely.
@beartype
def page_url(class_slug: str, build: TalentBuild) -> str:
    code = build.to_code()
    if code == "":
        return url_for("calculator", class_slug=class_slug)
    return url_for("calculator", class_slug=class_slug, build=code)


# ---------- Inline styles ----------
# The templates only write style="{{ ... }}"; the CSS text is built here. Keeping CSS out of the
# templates means editors that read them as plain HTML don't report errors for {{ }} inside CSS.
# Positions are passed as CSS variables (--row, --col, ...); the SCSS turns them into pixels.
#
# "@app.template_global()" makes the function callable from any template, e.g.
# {{ talent_style(talent) }}. Without it, templates can only see the values passed to render_template.

# FUNCTION: asset_url
# Data files point at "icons/rogue/x.png"; this makes it "/static/icons/rogue/x.png".
@beartype
def asset_url(path: str) -> str:
    """Data files point at "icons/..." relative to the static folder; make that a real URL."""
    return url_for("static", filename=path)


# FUNCTION: class_name_style
# "a or b" returns a if a is truthy, otherwise b. So a missing color falls back to "inherit".
# It's C#'s null-coalescing ?? (it also treats an empty string as missing).
@app.template_global()
@beartype
def class_name_style(class_data: ClassData) -> str:
    return f"color:{class_data.color or 'inherit'}"


# FUNCTION: tree_icon_style
# CONDITIONAL: no icon means no style at all (an empty string).
@app.template_global()
@beartype
def tree_icon_style(tree: TreeData) -> str:
    if not tree.icon:
        return ""
    return f"background-image:url('{asset_url(tree.icon)}')"


# FUNCTION: tree_grid_style
# rows: max(..., default=0) finds the deepest row, or 0 if the tree has no talents (an empty
#   tree would otherwise raise an error). +1 turns "deepest row index" into "number of rows".
# background: the JSON value, or a plain dark color if there isn't one ("or" fallback again).
#   .replace() points any url('icons/...') at the static folder.
@app.template_global()
@beartype
def tree_grid_style(tree: TreeData) -> str:
    rows = max((talent.row for talent in tree.talents), default=0) + 1
    background = tree.background or "#1b1b1b"
    background = background.replace("url('", "url('" + url_for("static", filename=""))
    return f"--rows:{rows}; background:{background};"


# FUNCTION: arrow_style
# Two f-strings placed next to each other inside ( ) are joined into one string automatically.
@app.template_global()
@beartype
def arrow_style(prerequisite: TalentData, talent: TalentData) -> str:
    return (
            f"--from-row:{prerequisite.row}; --from-col:{prerequisite.col}; "
            f"--to-row:{talent.row}; --to-col:{talent.col};")


# FUNCTION: talent_style
@app.template_global()
@beartype
def talent_style(talent: TalentData) -> str:
    return f"--row:{talent.row}; --col:{talent.col};"


# FUNCTION: talent_icon_style
@app.template_global()
@beartype
def talent_icon_style(talent: TalentData) -> str:
    if not talent.icon:
        return ""
    return f"background-image:url('{asset_url(talent.icon)}');"


# ---------- Routes ----------
# "@app.route(pattern)" says "call this function when the browser visits this URL" (GET by default).
# "@app.post(pattern)" is the same for POST requests, which HTMX sends on clicks.
# Whatever the function returns is sent back to the browser.

# ROUTE: /  ->  redirect to the default class.
@app.route("/")
@beartype
def home() -> Response:
    return redirect(url_for("calculator", class_slug=DEFAULT_CLASS))


# ROUTE: /rogue, /warrior, ...  ->  the full page.
# CONDITIONAL: if the URL's code differs from what the rules allow (an old or hand-edited link),
# redirect to the corrected URL instead of showing the page.
# (a or "") turns None into "" so the comparison works when there's no ?build= at all.
# render_template(file, name=value, ...) fills the template; each name becomes a template variable.
@app.route("/<class_slug>")
@beartype
def calculator(class_slug: str) -> str | Response:
    build = build_from_request(class_slug)
    # Normalize the URL when the rules dropped points from a hand-edited or old link.
    if (request.args.get("build") or "") != build.to_code():
        return redirect(page_url(class_slug, build))
    return render_template("calculator.html", build=build, class_slug=class_slug, classes=load_classes())


# ROUTE: POST /rogue/talent/<talent_id>  ->  a click on a talent.
# CONDITIONALS:
#   - unknown talent id -> 404
#   - if/else: the template sends remove=true for right-click or shift-click. request.form holds
#     the posted values; they always arrive as text, so it's compared with the string "true".
@app.post("/<class_slug>/talent/<talent_id>")
@beartype
def click_talent(class_slug: str, talent_id: str) -> tuple[str, dict[str, str]]:
    build = build_from_request(class_slug)
    talent = build.find(talent_id)
    if talent is None:
        abort(404)
    if request.form.get("remove") == "true":
        build.remove(talent)
    else:
        build.add(talent)
    return render_content(class_slug, build)


# ROUTE: POST /rogue/reset/0  ->  a tree's Reset button.
# "<int:tree_index>" makes Flask convert that part of the URL to an int (and 404 if it isn't a number).
@app.post("/<class_slug>/reset/<int:tree_index>")
@beartype
def reset_tree(class_slug: str, tree_index: int) -> tuple[str, dict[str, str]]:
    build = build_from_request(class_slug)
    if tree_index >= len(build.class_data.trees):
        abort(404)
    build.reset(build.class_data.trees[tree_index])
    return render_content(class_slug, build)


# ROUTE: POST /rogue/reset  ->  the Reset all button.
@app.post("/<class_slug>/reset")
@beartype
def reset_all(class_slug: str) -> tuple[str, dict[str, str]]:
    build = build_from_request(class_slug)
    build.reset_all()
    return render_content(class_slug, build)


# FUNCTION: render_content
# Returning two values separated by a comma returns a "tuple" (a fixed pair). Flask reads it as
# (body, headers). HTMX sees the HX-Replace-Url header and updates the address bar.
@beartype
def render_content(class_slug: str, build: TalentBuild) -> tuple[str, dict[str, str]]:
    """Returns just the summary and trees. HX-Replace-Url updates the address bar, like replace: true in Blazor."""
    html = render_template("_content.html", build=build, class_slug=class_slug)
    return html, {"HX-Replace-Url": page_url(class_slug, build)}


# PROGRAM START
# This block runs only when you start this file directly ("python app.py"), not when another file
# imports it. It's the Python equivalent of Main() / the top of Program.cs.
if __name__ == "__main__":
    port = 5080
    webbrowser.open(f"http://localhost:{port}")
    app.run(port=port, debug=False)
