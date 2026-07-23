from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.diagnostics import diagnostics_exit_code, diagnostics_summary, run_diagnostics


def main() -> int:
    checks = run_diagnostics()
    print(diagnostics_summary(checks))
    return diagnostics_exit_code(checks)


if __name__ == "__main__":
    raise SystemExit(main())
