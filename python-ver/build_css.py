"""Compiles styles/site.scss into static/css/site.css. Needs:  pip install libsass"""
# A plain script: no functions, it just runs top to bottom when you start it with "python build_css.py".
from pathlib import Path

# "sass" is the libsass package. It does the same job as the AspNetCore.SassCompiler package in the C# project.
import sass

APP_FOLDER = Path(__file__).parent
# Compile the main .scss file (it @imports the others) into one CSS string.
css = sass.compile(filename=str(APP_FOLDER / "styles" / "site.scss"), output_style="expanded")
# Save that string to static/css/site.css, the file the page links to.
(APP_FOLDER / "static" / "css" / "site.css").write_text(css, encoding="utf8")
print("Wrote static/css/site.css")
