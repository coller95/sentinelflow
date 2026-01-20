from typing import Any, Optional

class StaticFiles:
    def __init__(self, directory: Optional[str] = None, packages: Optional[list[str]] = None, html: bool = False, check_dir: bool = True, follow_symlink: bool = False) -> None: ...
