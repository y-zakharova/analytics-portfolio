"""Embed data/dashboard_data.json into template.html -> index.html (one self-contained file)."""
t = open("template.html").read()
d = open("data/dashboard_data.json").read()
open("index.html", "w").write(t.replace("__DATA__", d))
