#!/usr/bin/env python3
"""Line-oriented JSON bridge between the Electron UI and HyperPlot."""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLBACKEND", "Agg")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import HyperPlot  # noqa: E402
from hyperplot.settings import SERIALIZABLE_PREFERENCES  # noqa: E402


class HyperPlotBridge:
    """Stateful request dispatcher used by the Electron process."""

    def __init__(self):
        self.plotter = HyperPlot.HyperPlot()
        self.startup_messages: list[str] = []
        try:
            template = self.plotter.load_default_template()
            if template:
                self.startup_messages.append(f"Default template loaded: {template}")
        except Exception as exc:  # A bad user template should not stop the app.
            self.startup_messages.append(
                f"Default template could not be loaded: {exc}"
            )

    def snapshot(self) -> dict[str, Any]:
        return {
            "elements": self.plotter.element_rows(),
            "preferences": self.plotter.get_plot_preferences(
                *SERIALIZABLE_PREFERENCES
            ),
            "palette": self.plotter.resolved_color_palette(),
        }

    @staticmethod
    def _indices(payload: dict[str, Any]) -> list[int]:
        return [int(index) for index in payload.get("indices", [])]

    @staticmethod
    def _preview_data(fig) -> str:
        output = io.BytesIO()
        fig.savefig(output, format="svg", bbox_inches="tight")
        fig.clear()
        encoded = base64.b64encode(output.getvalue()).decode("ascii")
        return f"data:image/svg+xml;base64,{encoded}"

    def dispatch(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        handlers = {
            "initialize": self.initialize,
            "import_files": self.import_files,
            "preview": self.preview,
            "save_plot": self.save_plot,
            "set_preferences": self.set_preferences,
            "toggle_axis": self.toggle_axis,
            "set_background": self.set_background,
            "unset_background": self.unset_background,
            "delete_elements": self.delete_elements,
            "set_x_axis": self.set_x_axis,
            "element_detail": self.element_detail,
            "update_element_style": self.update_element_style,
            "reload": self.reload,
            "export_csv": self.export_csv,
            "save_template": self.save_template,
        }
        if action not in handlers:
            raise ValueError(f"Unknown backend action: {action}")
        return handlers[action](payload)

    def initialize(self, _payload: dict[str, Any]) -> dict[str, Any]:
        messages, self.startup_messages = self.startup_messages, []
        return {"state": self.snapshot(), "messages": messages}

    def import_files(self, payload: dict[str, Any]) -> dict[str, Any]:
        paths = [
            str(Path(path).expanduser().resolve())
            for path in payload.get("paths", [])
            if path
        ]
        fast_csv = bool(payload.get("fastCsv", False))
        legends = str(payload.get("legends", ""))
        messages: list[str] = []
        suggested_output = None

        templates = [
            path for path in paths if self.plotter.is_template_path(path)
        ]
        csv_paths = [path for path in paths if path.lower().endswith(".csv")]
        svg_paths = [path for path in paths if path.lower().endswith(".svg")]
        png_paths = [path for path in paths if path.lower().endswith(".png")]

        for path in templates:
            try:
                self.plotter.load_template(path)
                messages.append(f"Template loaded: {path}")
            except Exception as exc:
                messages.append(f"Template import skipped: {exc}")

        for path, loader, kind in (
            *((path, self.plotter.catch_svg, "SVG") for path in svg_paths),
            *((path, self.plotter.catch_png, "PNG") for path in png_paths),
        ):
            try:
                count = loader(path)
                suggested_output = os.path.basename(path)
                messages.append(
                    f"{kind} state loaded from {path}: {count} element(s)."
                )
            except Exception as exc:
                messages.append(f"{kind} import skipped: {exc}")

        if csv_paths and fast_csv:
            for path in csv_paths:
                self.plotter.fastCSV(path, legends)
                messages.append(f"FastCSV exported: {Path(path).with_suffix('.svg')}")
        elif csv_paths:
            self.plotter.catch(csv_paths)
            messages.append(f"Imported {len(csv_paths)} CSV file(s).")

        if not templates and not csv_paths and not svg_paths and not png_paths:
            messages.append("No supported HyperPlot files were selected.")
        return {
            "state": self.snapshot(),
            "messages": messages,
            "suggestedOutput": suggested_output,
        }

    def preview(self, payload: dict[str, Any]) -> dict[str, Any]:
        fig = self.plotter.get_plot(
            self._indices(payload),
            str(payload.get("legends", "")),
        )
        return {"preview": self._preview_data(fig), "state": self.snapshot()}

    def save_plot(self, payload: dict[str, Any]) -> dict[str, Any]:
        output_path = str(Path(payload["path"]).expanduser().resolve())
        if not self.plotter._has_supported_format(output_path):
            output_path += ".svg"
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        fig, elements = self.plotter.get_plot_with_elements(
            self._indices(payload),
            str(payload.get("legends", "")),
        )
        try:
            self.plotter._save_figure_with_state(fig, output_path, elements)
        finally:
            fig.clear()
        return {"path": output_path, "state": self.snapshot()}

    def set_preferences(self, payload: dict[str, Any]) -> dict[str, Any]:
        preferences = payload.get("preferences", {})
        self.plotter.set_plot_preferences(**preferences)
        return {"state": self.snapshot()}

    def toggle_axis(self, payload: dict[str, Any]) -> dict[str, Any]:
        changed = self.plotter.toggle_axis(self._indices(payload))
        return {"changed": changed, "state": self.snapshot()}

    def set_background(self, payload: dict[str, Any]) -> dict[str, Any]:
        count = self.plotter.set_background(self._indices(payload))
        return {"count": count, "state": self.snapshot()}

    def unset_background(self, payload: dict[str, Any]) -> dict[str, Any]:
        count = self.plotter.unset_background(self._indices(payload))
        return {"count": count, "state": self.snapshot()}

    def delete_elements(self, payload: dict[str, Any]) -> dict[str, Any]:
        count = self.plotter.delete_elements(self._indices(payload))
        return {"count": count, "state": self.snapshot()}

    def set_x_axis(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = self.plotter.set_x_axis(int(payload["index"]))
        return {"change": result, "state": self.snapshot()}

    def element_detail(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"detail": self.plotter.element_detail(int(payload["index"]))}

    def update_element_style(self, payload: dict[str, Any]) -> dict[str, Any]:
        count = self.plotter.update_element_style(
            int(payload["index"]),
            label=payload.get("label"),
            ls=payload.get("ls"),
            axis=payload.get("axis"),
        )
        return {"count": count, "state": self.snapshot()}

    def reload(self, _payload: dict[str, Any]) -> dict[str, Any]:
        result = self.plotter.reload_all()
        return {"reload": result, "state": self.snapshot()}

    def export_csv(self, payload: dict[str, Any]) -> dict[str, Any]:
        output_path = self.plotter.export_elements_csv(
            self._indices(payload),
            str(Path(payload["path"]).expanduser().resolve()),
        )
        return {"path": output_path}

    def save_template(self, payload: dict[str, Any]) -> dict[str, Any]:
        path = payload.get("path")
        output_path = self.plotter.save_template(path)
        return {"path": output_path}


def serve_stdio() -> None:
    bridge = HyperPlotBridge()
    for raw_line in sys.stdin:
        try:
            request = json.loads(raw_line)
            request_id = request.get("id")
            action = request.get("action", "")
            payload = request.get("payload") or {}
            logs = io.StringIO()
            with redirect_stdout(logs), redirect_stderr(logs):
                result = bridge.dispatch(action, payload)
            response = {
                "id": request_id,
                "ok": True,
                "result": result,
                "logs": [
                    line for line in logs.getvalue().splitlines() if line.strip()
                ],
            }
        except Exception as exc:
            response = {
                "id": locals().get("request_id"),
                "ok": False,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stdio", action="store_true", help="serve JSON over stdio")
    args = parser.parse_args()
    if args.stdio:
        serve_stdio()
    else:
        parser.error("--stdio is required")


if __name__ == "__main__":
    main()
