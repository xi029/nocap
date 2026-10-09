from importlib.resources import files


def test_installed_package_has_workbench_assets():
    root = files("nocap") / "static"
    for name in ("index.html", "app.js", "style.css", "logo.svg"):
        assert (root / name).is_file()
