"""A dict persisted as JSON."""

import json
import os
from typing import Any


class JsonCache:
    """Missing file -> empty cache. fresh=True ignores the file; the next flush overwrites it."""

    def __init__(self, path: str, fresh: bool = False) -> None:
        self.path = path
        self.data: dict[str, Any] = {}
        if not fresh and os.path.exists(path):
            with open(path) as f:
                self.data = json.load(f)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def __contains__(self, key: str) -> bool:
        return key in self.data

    def section(self, name: str) -> dict:
        """Return the (created on demand) sub-dict `name`, e.g. cache.section("artist")."""
        return self.data.setdefault(name, {})

    def flush(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.data, f, indent=2)
        os.replace(tmp, self.path)
