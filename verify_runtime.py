"""Single runtime entry: preserve all regressions and verify insert-card HTTP flow."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import check_project
from tests.insert_flow import verify_all


def main():
    regression_status = check_project.main()
    if regression_status != 0:
        return regression_status
    verify_all()
    print('RUNTIME VERIFY PASS: regression suite and insert request flow')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
