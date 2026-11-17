from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_it_saves_each_screen_the_docs_show(tmp_path: Path) -> None:
    script = ROOT / "scripts" / "tui_screenshots.py"
    subprocess.run([sys.executable, str(script), str(tmp_path)], check=True, cwd=ROOT)
    shown = {path.name: path.read_text() for path in tmp_path.iterdir()}
    assert sorted(shown) == ["tui-changelist.svg", "tui-form.svg", "tui-specs.svg"]
    assert "list-books" in shown["tui-specs.svg"]
    assert "Dune" in shown["tui-changelist.svg"]
    assert "retitle-book&#160;writes:&#160;ctrl+s&#160;again" in shown["tui-form.svg"]
