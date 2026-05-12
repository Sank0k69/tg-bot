"""Hot-reload entry point — cleans sys.modules and imports all handlers."""
from __future__ import annotations

import sys
import os

_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _dir)

for _m in list(sys.modules):
    if _m in (
        "app", "params", "api_client",
        "handlers_bots", "handlers_schedules", "handlers_notify", "handlers_settings",
        "panels_side", "panels_main", "skeleton",
    ):
        del sys.modules[_m]

from app import ext, chat  # noqa: F401, E402
import handlers_bots        # noqa: F401, E402
import handlers_schedules   # noqa: F401, E402
import handlers_notify      # noqa: F401, E402
import handlers_settings    # noqa: F401, E402
import skeleton             # noqa: F401, E402
import panels_side          # noqa: F401, E402
import panels_main          # noqa: F401, E402
