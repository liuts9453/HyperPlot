from dataclasses import dataclass
from typing import Any


@dataclass
class PlotElement:
    x: Any
    y: Any
    label: str = ""
    ls: str = "-"
    axis: str = "left"
    file_name: str = ""
    x_label: str = ""
    y_label: str = ""
    signature: str = ""
    is_background: bool = False
    background_group: str | None = None
    background_label: str | None = None
