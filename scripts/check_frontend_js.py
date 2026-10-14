"""Run Node's syntax checker against inline scripts in the HTML templates."""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    ROOT / "index.html",
    ROOT / "templates/staff/login.html",
    ROOT / "templates/staff/dashboard.html",
)
TEMPLATE_BOOL = re.compile(
    r'\{\{\s*(is_admin|is_provider|is_superuser|is_field_team|is_dispatcher|is_mfa_recovery_owner)'
    r'\|yesno:"true,false"\s*\}\}'
)
INLINE_SCRIPT = re.compile(r"(?is)<script(?:\s[^>]*)?>(.*?)</script\s*>")


def main() -> None:
    checked = 0
    with tempfile.TemporaryDirectory(prefix="mauzosheet-js-") as temp_dir:
        temp_root = Path(temp_dir)
        for html_path in FILES:
            html = html_path.read_text(encoding="utf-8")
            scripts = INLINE_SCRIPT.findall(html)
            for index, script in enumerate(scripts):
                if not script.strip():
                    continue
                rendered = TEMPLATE_BOOL.sub("false", script)
                script_path = temp_root / f"{html_path.stem}-{index}.js"
                script_path.write_text(rendered, encoding="utf-8")
                subprocess.run(["node", "--check", str(script_path)], check=True)
                checked += 1
    if checked == 0:
        raise SystemExit("No inline scripts were checked.")
    print(f"Checked JavaScript syntax in {checked} inline script blocks.")


if __name__ == "__main__":
    main()
