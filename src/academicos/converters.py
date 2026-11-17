from importlib.metadata import version
from pathlib import Path


class MarkItDownConverter:
    """Adaptador reemplazable; el pipeline no depende del motor de conversión."""

    def __init__(self):
        from markitdown import MarkItDown
        self.engine = MarkItDown()
        self.cache_key = "markitdown:" + version("markitdown") + ":basic-local-v1"

    def convert(self, path: Path) -> str:
        return self.engine.convert(str(path)).text_content
