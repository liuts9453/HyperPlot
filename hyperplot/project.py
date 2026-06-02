import copy
import json
import math
import os
import warnings
from datetime import datetime
from itertools import cycle

from .models import PlotElement
from .settings import (
    DEFAULT_SETTINGS,
    DEFAULT_SHORT_COLOR_PALETTE,
    KNOWN_PREFERENCES,
    PLOT_RC_PARAMS,
    SERIALIZABLE_PREFERENCES,
    SHORT_COLOR_CODES,
    USER_PREFERENCES,
    configure_matplotlib_cache,
    parse_bool,
    parse_optional_float,
    parse_positive_int,
    validate_preference,
)
from .state_io import (
    SVG_STATE_ENCODING,
    SVG_STATE_VERSION,
    decode_state,
    encode_state,
    png_metadata,
    read_png_state,
    read_svg_state,
    write_svg_state,
)
from .templates import (
    DEFAULT_TEMPLATE_NAMES,
    TEMPLATE_EXTENSION,
    default_template_path,
    is_template_path,
    read_template_state,
    save_template,
    template_dir,
    template_state,
)

configure_matplotlib_cache()

import matplotlib as mpl
from matplotlib.figure import Figure
import numpy as np

PACKAGE_ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(PACKAGE_ROOT)
PROJECT_ENTRY_FILE = os.path.join(PROJECT_ROOT, "HyperPlot.py")


def compute_figsize(fig, target_ax_width, target_ax_height):
    """
    根据目标绘图区域大小，计算 Figure 尺寸，不使用 twinx。

    Parameters:
        fig: matplotlib.figure.Figure - 当前 Figure 对象。
        target_ax_width: float - 目标绘图区域宽度（单位：英寸）。
        target_ax_height: float - 目标绘图区域高度（单位：英寸）。
        dpi: int - 图像分辨率。

    Returns:
        tuple - 调整后的 Figure 宽度和高度（单位：英寸）。
    """
    # 获取 figure 的 subplot 参数
    subplot_params = fig.subplotpars

    # 左右边距和上下边距占用比例
    left_margin = subplot_params.left
    right_margin = 1 - subplot_params.right
    top_margin = 1 - subplot_params.top
    bottom_margin = subplot_params.bottom
    # 计算绘图区占 Figure 的比例
    drawing_area_width_ratio = 1 - left_margin - right_margin
    drawing_area_height_ratio = 1 - top_margin - bottom_margin

    # 根据目标宽高反推出 Figure 的宽高
    fig_width = target_ax_width / drawing_area_width_ratio
    fig_height = target_ax_height / drawing_area_height_ratio

    return fig_width, fig_height


def compute_figsize_twinx(fig, target_ax_width, target_ax_height):
    """
    根据目标绘图区域大小，计算 Figure 尺寸，不使用 twinx。

    Parameters:
        fig: matplotlib.figure.Figure - 当前 Figure 对象。
        target_ax_width: float - 目标绘图区域宽度（单位：英寸）。
        target_ax_height: float - 目标绘图区域高度（单位：英寸）。
        dpi: int - 图像分辨率。

    Returns:
        tuple - 调整后的 Figure 宽度和高度（单位：英寸）。
    """
    # 获取 figure 的 subplot 参数
    subplot_params = fig.subplotpars

    # 左右边距和上下边距占用比例
    left_margin = subplot_params.left
    right_margin = 2 * (1 - subplot_params.right)
    top_margin = 1 - subplot_params.top
    bottom_margin = subplot_params.bottom
    # 计算绘图区占 Figure 的比例
    drawing_area_width_ratio = 1 - left_margin - right_margin
    drawing_area_height_ratio = 1 - top_margin - bottom_margin

    # 根据目标宽高反推出 Figure 的宽高
    fig_width = target_ax_width / drawing_area_width_ratio
    fig_height = target_ax_height / drawing_area_height_ratio

    return fig_width, fig_height



class HyperPlot:
    def __init__(self, **kwargs):
        """
        Initializes the HyperPlot class, providing flexible options for x and y axis labels.

        Parameters:
        - plot_type: A string specifying the type of plot by combining x-axis and y-axis labels,
                     formatted as 'x_axis_label_y_axis_label' (e.g., 'time_stress').
        - plot_dpi: Resolution in dots per inch for saving plots (default is 300 dpi).
        - plot_format: Format in which the plot will be saved (default is 'svg').
        - loc: Legend location in the plot, accepts Matplotlib location strings like 'best', 'upper right', etc.
        """
        self.set_plot_preferences(**copy.deepcopy(DEFAULT_SETTINGS))
        self._last_catch = []
        self.set_plot_preferences(**kwargs)

    def set_axis_labels_from_plot_type(self, plot_type):

        self.xlabel, self.ylabel, self.right_axis_label = (
            self.get_labels_from_plot_type(plot_type)
        )

    def get_labels_from_plot_type(self, plot_type):
        """
        Generates x and y axis labels based on the plot_type string.

        Parameters:
        - plot_type: A string formatted as 'x_axis_label_y_axis_label',
                     where x_axis_label and y_axis_label are keys from the axis_labels dictionary.

        Returns:
        - A tuple containing the formatted x-axis and y-axis labels as strings.
        """
        foo = plot_type.split("_")
        x_key, y_key = foo if len(foo) == 2 else foo[:-1]
        xlabel = self.axis_labels.get(x_key, "x")
        ylabel = self.axis_labels.get(y_key, "y")
        rlabel = self.axis_labels.get(foo[-1])
        return xlabel, ylabel, rlabel

    def _has_supported_format(self, file_name):
        file_name = file_name.lower()
        return any(file_name.endswith(f".{ext}") for ext in self.supported_formats)

    def _parse_args(self, *args):
        """
        Parses and processes input arguments for element indices, legends, and output file name.

        Parameters:
        - args: Arguments that may include element indices (list or tuple),
                legends (string with '|' separating multiple legends), and out_name (output file name).

        Returns:
        - element_indices: List of indices corresponding to the elements to plot, or None to plot all elements.
        - legends: A string containing custom legends and line styles for each plot, separated by '|'.
        - out_name: A string specifying the output file name for saving the plot.
        """
        element_indices = None
        legends = ""
        out_name = ""
        # Determine which argument corresponds to indices, legends, or output file name
        for arg in args:
            if isinstance(arg, (list, tuple)):
                element_indices = arg  # Treat lists or tuples as element indices
            elif isinstance(arg, str):
                if self._has_supported_format(arg):
                    out_name = arg  # Identify file name by '.svg' extension
                elif not legends:
                    legends = arg

        return element_indices, legends, out_name

    def set_plot_preferences(self, **kwargs):
        for key, value in kwargs.items():
            if key not in KNOWN_PREFERENCES:
                warnings.warn(
                    f"Unknown HyperPlot preference ignored: {key}",
                    RuntimeWarning,
                    stacklevel=2,
                )
                continue
            if key in USER_PREFERENCES:
                value = validate_preference(key, value)
            setattr(self, key, value)

    def get_plot_preferences(self, *props):
        return {prop: getattr(self, prop, None) for prop in props}

    @staticmethod
    def _values_to_list(values):
        if hasattr(values, "to_numpy"):
            values = values.to_numpy()
        return np.asarray(values).tolist()

    def _preferences_to_state(self):
        return {
            prop: copy.deepcopy(getattr(self, prop, None))
            for prop in SERIALIZABLE_PREFERENCES
        }

    def apply_preferences(self, preferences):
        clean_preferences = {
            key: value
            for key, value in preferences.items()
            if key in SERIALIZABLE_PREFERENCES
        }
        self.set_plot_preferences(**clean_preferences)
        return clean_preferences

    @staticmethod
    def _parse_palette_string(palette):
        palette = palette.strip()
        if not palette:
            return {}
        if palette.startswith("{"):
            return json.loads(palette)

        parsed = {}
        for item in palette.replace(";", ",").split(","):
            if not item.strip():
                continue
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            parsed[key.strip()] = value.strip()
        return parsed

    def _custom_color_palette(self):
        palette = getattr(self, "color_palette", {}) or {}
        if isinstance(palette, str):
            try:
                palette = self._parse_palette_string(palette)
            except json.JSONDecodeError:
                return {}
        if not isinstance(palette, dict):
            return {}
        return {
            str(key).strip(): str(value).strip()
            for key, value in palette.items()
            if str(key).strip() and str(value).strip()
        }

    def resolved_color_palette(self):
        palette = copy.deepcopy(DEFAULT_SHORT_COLOR_PALETTE)
        palette.update(self._custom_color_palette())
        return palette

    @staticmethod
    def template_dir():
        return template_dir(PROJECT_ENTRY_FILE)

    @staticmethod
    def default_template_path():
        return default_template_path(PROJECT_ENTRY_FILE)

    @staticmethod
    def is_template_path(file_path):
        return is_template_path(file_path)

    def to_template_state(self):
        return template_state(self._preferences_to_state())

    def save_template(self, template_path=None):
        if template_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            template_path = os.path.join(
                self.template_dir(), f"{timestamp}{TEMPLATE_EXTENSION}"
            )

        return save_template(template_path, self.to_template_state())

    @staticmethod
    def read_template_state(template_path):
        return read_template_state(template_path)

    def load_template(self, template_path):
        state = self.read_template_state(template_path)
        self.apply_preferences(state.get("preferences", {}))
        return template_path

    def load_default_template(self):
        template_path = self.default_template_path()
        if template_path is None:
            return None
        return self.load_template(template_path)

    def _element_to_state(self, element):
        return {
            "x": self._values_to_list(element.x),
            "y": self._values_to_list(element.y),
            "label": getattr(element, "label", ""),
            "ls": getattr(element, "ls", "-"),
            "axis": getattr(element, "axis", "left"),
            "is_background": getattr(element, "is_background", False),
            "background_group": getattr(element, "background_group", None),
            "background_label": getattr(element, "background_label", None),
            "file_name": getattr(element, "file_name", ""),
            "x_label": getattr(element, "x_label", ""),
            "y_label": getattr(element, "y_label", getattr(element, "label", "")),
            "signature": getattr(element, "signature", ""),
        }

    def to_state(self, elements=None):
        if elements is None:
            elements = self._elements
        return {
            "app": "HyperPlot",
            "version": SVG_STATE_VERSION,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "preferences": self._preferences_to_state(),
            "elements": [self._element_to_state(element) for element in elements],
        }

    @staticmethod
    def _encode_state(state):
        return encode_state(state)

    @staticmethod
    def _decode_state(encoded_state):
        return decode_state(encoded_state)

    @staticmethod
    def _svg_namespace(root):
        if root.tag.startswith("{"):
            return root.tag[1:].split("}", 1)[0]
        return ""

    def _write_svg_state(self, svg_path, state):
        write_svg_state(svg_path, state)

    def _png_metadata(self, state):
        return png_metadata(state)

    @staticmethod
    def read_svg_state(svg_path):
        return read_svg_state(svg_path)

    @staticmethod
    def read_png_state(png_path):
        return read_png_state(png_path)

    def _element_from_state(self, element_state):
        x = np.asarray(element_state.get("x", []))
        y = np.asarray(element_state.get("y", []))
        if len(x) != len(y):
            raise ValueError("SVG element state has mismatched x/y lengths.")

        file_name = element_state.get("file_name", "")
        x_label = element_state.get("x_label", "")
        y_label = element_state.get("y_label", element_state.get("label", ""))
        signature = element_state.get("signature") or (
            f"{file_name}_{x_label}_{y_label}".replace(" ", "")
        )
        element = PlotElement(
            x=x,
            y=y,
            label=element_state.get("label", ""),
            ls=element_state.get("ls", "-"),
            axis=element_state.get("axis", "left"),
            file_name=file_name,
            x_label=x_label,
            y_label=y_label,
            signature=signature,
            is_background=element_state.get("is_background", False),
            background_group=element_state.get("background_group"),
            background_label=element_state.get("background_label"),
        )
        return element

    def _upsert_element(self, element):
        existing_element = next(
            (
                existing
                for existing in self._elements
                if getattr(existing, "signature", None) == element.signature
            ),
            None,
        )
        if existing_element:
            for attr in (
                "x",
                "y",
                "label",
                "ls",
                "axis",
                "is_background",
                "background_group",
                "background_label",
                "file_name",
                "x_label",
                "y_label",
                "signature",
            ):
                setattr(existing_element, attr, getattr(element, attr))
            self._last_catch.append(existing_element)
        else:
            self._elements.append(element)
            self._last_catch.append(element)
            self._element_counter += 1

    def restore_state(self, state, merge=True):
        if state.get("app") != "HyperPlot":
            raise ValueError("SVG state is not a HyperPlot state.")

        self.apply_preferences(state.get("preferences", {}))

        if not merge:
            self._elements = []
            self._element_counter = 0

        self._last_catch = []
        for element_state in state.get("elements", []):
            self._upsert_element(self._element_from_state(element_state))
        return len(self._last_catch)

    def catch_svg(self, file_path):
        state = self.read_svg_state(file_path)
        return self.restore_state(state, merge=True)

    def catch_png(self, file_path):
        state = self.read_png_state(file_path)
        return self.restore_state(state, merge=True)

    def _create_elements_from_csv(self, file_path, df):
        """
        Converts CSV data into PlotElement objects and stores them in _elements with unique labels.
        If an element with the same label already exists, it will be overwritten.
        Tracks the original file name, x label, and y label.

        Parameters:
        - file_path: The file path to the CSV being processed.
        - df: A pandas DataFrame containing the CSV data.
        """
        x_label = df.columns[0]  # First column is x-axis label
        for i in range(1, df.shape[1]):
            y_label = df.columns[i]  # Remaining columns are y-axis labels
            y = df.iloc[:, i]
            x = df.iloc[:, 0]

            # Generate the label for the PlotElement (unique for each file and column)
            signature = f"{os.path.basename(file_path).replace('.csv', '')}_{x_label}_{y_label}".replace(
                " ", ""
            )

            # Check if an element with the same label already exists
            existing_element = next(
                (el for el in self._elements if el.signature == signature), None
            )

            if existing_element:
                print(
                    f"Warning: Element with signature label '{signature}' already exists. Overwriting it."
                )
                existing_element.x = x
                existing_element.y = y
                existing_element.file_name = os.path.basename(file_path)
                existing_element.x_label = x_label
                existing_element.y_label = y_label
                existing_element.is_background = getattr(
                    existing_element, "is_background", False
                )
                existing_element.background_group = getattr(
                    existing_element, "background_group", None
                )
                existing_element.background_label = getattr(
                    existing_element, "background_label", None
                )
                self._last_catch.append(existing_element)
            else:
                new_element = PlotElement(
                    x=x,
                    y=y,
                    label=y_label,
                    ls="-",
                    file_name=os.path.basename(file_path),
                    x_label=x_label,
                    y_label=y_label,
                    signature=signature,
                    is_background=False,
                    background_group=None,
                    background_label=None,
                )
                self._elements.append(new_element)
                self._last_catch.append(new_element)
                self._element_counter += 1

    def catch(self, path_or_files):
        """
        Loads and processes one or more CSV files, converting each into PlotElement objects.

        Parameters:
        - path_or_files: Either a directory path (string) or a list of file paths (strings).
                         If a directory is provided, all CSV files in the directory will be processed.
        """
        import pandas as pd

        self._last_catch = []
        if isinstance(path_or_files, str) and os.path.isdir(path_or_files):
            # Process all CSV files in the directory
            for file in os.listdir(path_or_files):
                if file.endswith(".csv"):
                    file_path = os.path.join(path_or_files, file)
                    df = pd.read_csv(file_path, sep=self.seperator, engine="python")
                    self._create_elements_from_csv(file_path, df)
        elif isinstance(path_or_files, list):
            # Process multiple specified CSV files
            for file_path in path_or_files:
                if file_path.endswith(".csv"):
                    df = pd.read_csv(file_path, sep=self.seperator, engine="python")
                    self._create_elements_from_csv(file_path, df)
        elif isinstance(path_or_files, str) and path_or_files.endswith(".csv"):
            # Process a single CSV file
            df = pd.read_csv(path_or_files, sep=self.seperator, engine="python")
            self._create_elements_from_csv(path_or_files, df)
        return self

    def _valid_indices(self, indices):
        return sorted(
            {
                int(index)
                for index in indices
                if 0 <= int(index) < len(self._elements)
            }
        )

    def delete_elements(self, indices):
        valid_indices = self._valid_indices(indices)
        for index in reversed(valid_indices):
            self._elements.pop(index)
        self._element_counter = len(self._elements)
        return len(valid_indices)

    @staticmethod
    def _background_label(elements):
        file_names = {
            getattr(element, "file_name", "")
            for element in elements
            if getattr(element, "file_name", "")
        }
        if len(file_names) == 1:
            return f"{next(iter(file_names))} Experimental Range"
        return "Experimental Range"

    def set_background(self, indices):
        valid_indices = self._valid_indices(indices)
        if not valid_indices:
            return 0

        elements = [self._elements[index] for index in valid_indices]
        group_id = f"background_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        group_label = self._background_label(elements)
        for element in elements:
            element.is_background = True
            element.background_group = group_id
            element.background_label = group_label
        return len(elements)

    def unset_background(self, indices):
        valid_indices = self._valid_indices(indices)
        for index in valid_indices:
            element = self._elements[index]
            element.is_background = False
            element.background_group = None
            element.background_label = None
        return len(valid_indices)

    def toggle_axis(self, indices):
        valid_indices = self._valid_indices(indices)
        for index in valid_indices:
            element = self._elements[index]
            element.axis = "right" if element.axis == "left" else "left"
        return [
            (self._elements[index].label, self._elements[index].axis)
            for index in valid_indices
        ]

    def element_detail(self, index):
        index = int(index)
        if not 0 <= index < len(self._elements):
            raise IndexError("PlotElement index out of range.")

        element = self._elements[index]
        is_background = getattr(element, "is_background", False)
        return {
            "index": index,
            "label": (
                getattr(element, "background_label", None)
                if is_background
                else getattr(element, "label", "")
            )
            or "",
            "ls": getattr(element, "ls", "-"),
            "axis": getattr(element, "axis", "left"),
            "is_background": is_background,
            "background_group": getattr(element, "background_group", None),
        }

    def update_element_style(self, index, label=None, ls=None, axis=None):
        detail = self.element_detail(index)
        element = self._elements[detail["index"]]

        if detail["is_background"]:
            group_id = detail["background_group"] or getattr(
                element, "signature", id(element)
            )
            targets = [
                candidate
                for candidate in self._elements
                if getattr(candidate, "is_background", False)
                and (
                    getattr(candidate, "background_group", None)
                    or getattr(candidate, "signature", id(candidate))
                )
                == group_id
            ]
            for target in targets:
                if label is not None:
                    target.background_label = label
                if ls is not None:
                    target.ls = ls
                if axis in ("left", "right"):
                    target.axis = axis
            return len(targets)

        if label is not None:
            element.label = label
        if ls is not None:
            element.ls = ls
        if axis in ("left", "right"):
            element.axis = axis
        return 1

    def element_rows(self):
        rows = []
        for idx, element in enumerate(self._elements):
            rows.append(
                {
                    "index": idx,
                    "file_name": getattr(element, "file_name", ""),
                    "x_label": getattr(element, "x_label", ""),
                    "label": getattr(element, "label", ""),
                    "ls": getattr(element, "ls", "-"),
                    "axis": getattr(element, "axis", "left"),
                    "is_background": getattr(element, "is_background", False),
                }
            )
        return rows

    def _ensure_folder_exist(self, folder):
        """
        Ensure that the 'plots' directory exists; if not, create it.
        """
        if not os.path.exists(folder):
            os.makedirs(folder)
            print(f"Created directory: {folder}")

    def _build_plot(self, element_indices, legends):
        if element_indices is None:
            element_indices = list(range(len(self._elements)))

        selected_elements = [self._elements[i] for i in element_indices]
        self._apply_styles(selected_elements, legends)
        with mpl.rc_context(PLOT_RC_PARAMS):
            fig, _ = self._routine(selected_elements)
        return fig, selected_elements

    def get_plot(self, element_indices, legends):
        fig, _ = self._build_plot(element_indices, legends)
        return fig

    def get_plot_with_elements(self, element_indices, legends):
        return self._build_plot(element_indices, legends)

    def _default_output_name(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{timestamp}.svg"

    def _save_figure_with_state(self, fig, out_path, elements):
        state = self.to_state(elements)
        if out_path.lower().endswith(".png"):
            fig.savefig(
                out_path,
                dpi=int(self.plot_dpi),
                bbox_inches="tight",
                metadata=self._png_metadata(state),
            )
            return

        fig.savefig(out_path, dpi=int(self.plot_dpi), bbox_inches="tight")
        if out_path.lower().endswith(".svg"):
            self._write_svg_state(out_path, state)

    def save_plot(self, fig, elements, out_name=None):
        if not out_name:
            out_name = self._default_output_name()
        elif not self._has_supported_format(out_name):
            out_name = f"{out_name}.svg"

        self._ensure_folder_exist(self.outpath)
        out_path = os.path.join(self.outpath, out_name)
        self._save_figure_with_state(fig, out_path, elements)
        print(f"Saved plot as {out_name}")
        return out_path

    def out(self, *args):
        """
        Generates and displays a plot based on the selected PlotElements.

        Parameters:
        - args: May include element indices (list or tuple), legends (string with '|' separator),
                and an optional output file name ending in '.svg'.
        """
        element_indices, legends, out_name = self._parse_args(*args)
        # Plot and save the figure
        fig, selected_elements = self._build_plot(element_indices, legends)
        self.save_plot(fig, selected_elements, out_name)
        # fig.canvas.manager.set_window_title(out_name)
        fig.clear()

    def fastCSV(self, file_path, legends=""):
        """
        Quickly reads a CSV file and generates a plot using the data.

        Parameters:
        - file_path: The path to the CSV file being processed.
        - legends: Optional string for specifying custom legends and line styles, using '|' to separate entries.
        """
        self.catch(file_path)
        selected_elements = self._last_catch

        # Apply custom legends and line styles, if provided
        self._apply_styles(selected_elements, legends)

        # Generate and save the plot
        output_file = file_path[:-3] + self.plot_format
        with mpl.rc_context(PLOT_RC_PARAMS):
            fig, _ = self._routine(selected_elements)
        self._save_figure_with_state(fig, output_file, selected_elements)
        print(f"Dump {file_path} to {output_file}")
        fig.clear()

    @staticmethod
    def _parse_style_item(style_item):
        parts = style_item.split("==", 1)
        label = parts[0].strip()
        line_style = parts[1].strip() if len(parts) > 1 else None
        return label, line_style

    def _style_targets(self, selected_elements):
        targets = []
        seen_background_groups = set()

        for element in selected_elements:
            if getattr(element, "is_background", False):
                group_id = getattr(element, "background_group", None) or getattr(
                    element, "signature", id(element)
                )
                if group_id in seen_background_groups:
                    continue
                group_elements = [
                    candidate
                    for candidate in selected_elements
                    if getattr(candidate, "is_background", False)
                    and (
                        getattr(candidate, "background_group", None)
                        or getattr(candidate, "signature", id(candidate))
                    )
                    == group_id
                ]
                targets.append(group_elements)
                seen_background_groups.add(group_id)
            else:
                targets.append(element)
        return targets

    def _apply_styles(self, selected_elements, legends):
        """
        Apply custom legends and linestyles (and potentially other styles) to the selected PlotElement objects.

        Parameters:
        - selected_elements: List of PlotElement objects to be plotted.
        - legends: A string specifying custom legends and line styles, with '==' separating the label and style.
                   The styles can include line style, color, and marker.
                   Multiple entries should be separated by '|'.

        The styles use Matplotlib conventions for specifying:
        - Line style (e.g., '-', '--', '-.', ':')
        - Line color (e.g., 'r', 'g', 'b' for red, green, blue, etc.)
        - Marker style (e.g., 'o', '^', 's' for circle, triangle, square, etc.)

        Background groups consume one Batch Style item, because they are rendered as
        one envelope in the final plot.

        Example:
        --------------
        legends = "Label1==--r-o|Label2==-.g^|Label3==-b"
        self._apply_styles(selected_elements, legends)

        This example assigns:
        - Label1 a red dashed line with circle markers (--r-o)
        - Label2 a green dash-dot line with triangle markers (-.g^)
        - Label3 a solid blue line (-b)
        """
        legend_items = legends.split("|") if legends else []

        for i, target in enumerate(self._style_targets(selected_elements)):
            if i < len(legend_items):
                label, line_style = self._parse_style_item(legend_items[i])

                if isinstance(target, list):
                    for element in target:
                        element.background_label = label
                        if line_style is not None:
                            element.ls = line_style
                    continue

                target.label = label
                if line_style is not None:
                    target.ls = line_style

    def _plot_box_aspect(self):
        return float(self.fig_height_cm) / float(self.fig_width_cm)

    def _target_plot_box_inches(self):
        return float(self.fig_width_cm) / 2.54, float(self.fig_height_cm) / 2.54

    def _apply_plot_box_aspect(self, *axes):
        aspect = self._plot_box_aspect()
        for axis in axes:
            if hasattr(axis, "set_box_aspect"):
                axis.set_box_aspect(aspect)
            else:
                warnings.warn(
                    "This matplotlib version does not support precise axes box aspect control.",
                    RuntimeWarning,
                    stacklevel=2,
                )

    def _fit_figure_to_plot_box(self, fig, ax, max_iterations=8, tolerance=0.001):
        target_width, target_height = self._target_plot_box_inches()

        for _ in range(max_iterations):
            fig.canvas.draw()
            bbox = ax.get_window_extent()
            current_width = bbox.width / fig.dpi
            current_height = bbox.height / fig.dpi
            if current_width <= 0 or current_height <= 0:
                return

            delta_width = target_width - current_width
            delta_height = target_height - current_height
            if abs(delta_width) <= tolerance and abs(delta_height) <= tolerance:
                break

            fig_width, fig_height = fig.get_size_inches()
            fig.set_size_inches(
                max(fig_width + delta_width, target_width),
                max(fig_height + delta_height, target_height),
                forward=True,
            )

        fig.canvas.draw()

    @staticmethod
    def _visible_y_ticks(axis):
        lower, upper = sorted(axis.get_ylim())
        span = upper - lower
        if span <= 0:
            return np.array([])
        tolerance = span * 1e-9
        ticks = np.asarray(axis.get_yticks(), dtype=float)
        return ticks[
            np.isfinite(ticks)
            & (ticks >= lower - tolerance)
            & (ticks <= upper + tolerance)
        ]

    def _axis_y_range(self, elements):
        y_values = []
        for element in elements:
            _, y = self._limited_xy(element)
            if len(y):
                y_values.append(y)
        if not y_values:
            return None

        values = np.concatenate(y_values)
        values = values[np.isfinite(values)]
        if not len(values):
            return None
        return float(np.nanmin(values)), float(np.nanmax(values))

    @staticmethod
    def _nice_tick_step_candidates(raw_step):
        if not np.isfinite(raw_step) or raw_step <= 0:
            raw_step = 1.0

        exponent = math.floor(math.log10(raw_step))
        steps = []
        for power in range(exponent - 1, exponent + 4):
            scale = 10**power
            for multiplier in (1, 2, 2.5, 5, 10):
                step = multiplier * scale
                if step >= raw_step * (1 - 1e-12):
                    steps.append(step)
        return sorted(set(steps))

    @staticmethod
    def _round_tick_value(value, step):
        if not np.isfinite(value):
            return value
        if step <= 0:
            return value
        decimals = max(0, int(math.ceil(-math.log10(abs(step)))) + 3)
        value = round(float(value), decimals)
        return 0.0 if value == -0.0 else value

    def _right_axis_nice_ticks(self, data_min, data_max, count, lower_margin, upper_margin):
        if count < 2:
            return None

        if data_min > data_max:
            data_min, data_max = data_max, data_min
        data_span = data_max - data_min
        raw_step = data_span / max(count - 1, 1) if data_span > 0 else 1.0

        for step in self._nice_tick_step_candidates(raw_step):
            lower_first = data_max - (count - 1 + upper_margin) * step
            upper_first = data_min + lower_margin * step
            if lower_first > upper_first + abs(step) * 1e-9:
                continue

            data_center = (data_min + data_max) / 2
            center_offset = (count - 1 + upper_margin - lower_margin) * step / 2
            ideal_first = data_center - center_offset
            first = round(ideal_first / step) * step
            first = max(first, math.ceil((lower_first / step) - 1e-12) * step)
            first = min(first, math.floor((upper_first / step) + 1e-12) * step)

            ticks = np.array(
                [
                    self._round_tick_value(first + index * step, step)
                    for index in range(count)
                ],
                dtype=float,
            )
            lower = self._round_tick_value(first - lower_margin * step, step)
            upper = self._round_tick_value(
                first + (count - 1 + upper_margin) * step,
                step,
            )
            if lower <= data_min + abs(step) * 1e-9 and upper >= data_max - abs(step) * 1e-9:
                return ticks, lower, upper
        return None

    def _align_right_axis_ticks(self, fig, ax, ax_right, right_axis_elements):
        fig.canvas.draw()
        left_ticks = self._visible_y_ticks(ax)
        if len(left_ticks) < 2:
            return

        left_ylim = ax.get_ylim()
        left_span = left_ylim[1] - left_ylim[0]
        if left_span == 0:
            return

        relative_positions = (left_ticks - left_ylim[0]) / left_span
        relative_steps = np.diff(relative_positions)
        relative_steps = relative_steps[np.isfinite(relative_steps) & (relative_steps > 0)]
        if not len(relative_steps):
            return

        relative_step = float(np.median(relative_steps))
        lower_margin = float(relative_positions[0] / relative_step)
        upper_margin = float((1 - relative_positions[-1]) / relative_step)

        y_range = self._axis_y_range(right_axis_elements)
        if y_range is None or y_range[0] == y_range[1]:
            y_range = tuple(sorted(ax_right.get_ylim()))

        nice_ticks = self._right_axis_nice_ticks(
            y_range[0],
            y_range[1],
            len(left_ticks),
            lower_margin,
            upper_margin,
        )
        if nice_ticks is None:
            return

        ticks, _, _ = nice_ticks
        relative_span = relative_positions[-1] - relative_positions[0]
        if relative_span <= 0:
            return

        right_span = (ticks[-1] - ticks[0]) / relative_span
        lower = ticks[0] - relative_positions[0] * right_span
        upper = lower + right_span

        ax.set_yticks(left_ticks)
        ax.set_ylim(left_ylim)
        ax_right.set_ylim(lower, upper)
        ax_right.set_yticks(ticks)

    def _routine(self, elements):
        fig = Figure()
        ax = fig.add_subplot()
        # fig, ax = plt.subplots()

        fig.set_size_inches(
            compute_figsize(
                fig, float(self.fig_width_cm) / 2.54, float(self.fig_height_cm) / 2.54
            )
        )
        self.set_axis_labels_from_plot_type(self.plot_type)
        # 分离左右轴的元素
        left_axis_elements = [el for el in elements if el.axis == "left"]
        right_axis_elements = [el for el in elements if el.axis == "right"]

        self._axisroutine(ax, left_axis_elements)
        # 绘制左轴元素，使用颜色循环

        # 如果有右轴元素，则创建右轴并绘制
        if right_axis_elements:
            ax_right = ax.twinx()  # 创建右轴
            fig.set_size_inches(
                compute_figsize_twinx(
                    fig,
                    float(self.fig_width_cm) / 2.54,
                    float(self.fig_height_cm) / 2.54,
                )
            )
            self._axisroutine(ax_right, right_axis_elements)
            # 设置右轴标签和颜色
            ax_right.set_ylabel(self.right_axis_label, color=self.right_axis_color)
            ax_right.tick_params(axis="y", colors=self.right_axis_color)
            ax_right.spines["right"].set_color(self.right_axis_color)
            self._apply_plot_box_aspect(ax, ax_right)
        else:
            self._apply_plot_box_aspect(ax)
        # 设置主轴标签和其他参数
        ax.set_xlabel(self.xlabel)
        ax.set_ylabel(self.ylabel)

        ## 将左右轴的标签合并，生成一个共享的图例
        lines, labels = ax.get_legend_handles_labels()
        if right_axis_elements:
            right_lines, right_labels = ax_right.get_legend_handles_labels()
            lines += right_lines
            labels += right_labels
        if len(elements) > 1:
            ax.legend(
                lines,
                labels,
                loc=self.loc,
                borderaxespad=0.0,
                framealpha=1,
                edgecolor="black",
                fancybox=False,
                handlelength=float(self.legend_line_length),
            ).get_frame().set_linewidth(
                ax.spines["bottom"].get_linewidth()
            )  # 使用合并后的标签和句柄创建图例

        self._fit_figure_to_plot_box(fig, ax)

        if right_axis_elements:
            self._align_right_axis_ticks(fig, ax, ax_right, right_axis_elements)

        if parse_bool(self.grid):
            ax.grid(True)

        # Determine which plot has finer grid. Set pointers accordingly

        self._fit_figure_to_plot_box(fig, ax)
        return fig, ax
        # plt.tight_layout()

    @staticmethod
    def parse_limit(s: str):
        """
        把字符串 s 解析成 float 或 None
        - 空串、只含空白、'none' (大小写均可) → None
        - 其余尝试 float(s)，失败则抛 ValueError
        """
        return parse_optional_float(s, "plot limit")

    def _plot_limits(self):
        return self.parse_limit(self.xmin), self.parse_limit(self.xmax)

    def _markevery(self, point_count):
        marks = parse_positive_int(self.marks, "marks")
        return max(int(point_count / marks), 1)

    def _background_alpha(self):
        return validate_preference("background_alpha", self.background_alpha)

    def _background_points(self):
        return max(parse_positive_int(self.background_points, "background_points"), 2)

    @staticmethod
    def _short_color_code(style):
        for char in style:
            if char in SHORT_COLOR_CODES:
                return char
        return None

    def _resolve_plot_style(self, style):
        style = style or "-"
        color_code = self._short_color_code(style)
        if color_code is None:
            return style, None

        color = self.resolved_color_palette().get(color_code, color_code)
        fmt = style.replace(color_code, "", 1)
        if not fmt:
            fmt = "-"
        return fmt, color

    def _limited_xy(self, element, sort_for_interp=False):
        xmin, xmax = self._plot_limits()
        x_values = np.asarray(element.x, dtype=float)
        y_values = np.asarray(element.y, dtype=float)
        mask = np.isfinite(x_values) & np.isfinite(y_values)
        if xmin is not None:
            mask &= x_values >= xmin
        if xmax is not None:
            mask &= x_values <= xmax

        x_values = x_values[mask]
        y_values = y_values[mask]
        if sort_for_interp and len(x_values):
            order = np.argsort(x_values)
            x_values = x_values[order]
            y_values = y_values[order]
            x_values, unique_indices = np.unique(x_values, return_index=True)
            y_values = y_values[unique_indices]
        return x_values, y_values

    def _background_groups(self, elements):
        groups = {}
        for element in elements:
            if not getattr(element, "is_background", False):
                continue
            group_id = getattr(element, "background_group", None) or getattr(
                element, "signature", id(element)
            )
            groups.setdefault(group_id, []).append(element)
        return list(groups.values())

    def _plot_background_group(self, ax, elements, colors):
        first = elements[0]
        label = getattr(first, "background_label", None) or self._background_label(
            elements
        )
        _, color = self._resolve_plot_style(getattr(first, "ls", "-"))
        color = color or next(colors)
        alpha = self._background_alpha()

        cleaned = [
            self._limited_xy(element, sort_for_interp=True) for element in elements
        ]
        cleaned = [(x, y) for x, y in cleaned if len(x) >= 2]
        if not cleaned:
            return

        if len(cleaned) == 1:
            x_values, y_values = cleaned[0]
            ax.plot(
                x_values,
                y_values,
                color=color,
                alpha=alpha,
                linewidth=1.0,
                label=label,
            )
            return

        min_x = max(x_values[0] for x_values, _ in cleaned)
        max_x = min(x_values[-1] for x_values, _ in cleaned)
        if min_x >= max_x:
            for i, (x_values, y_values) in enumerate(cleaned):
                ax.plot(
                    x_values,
                    y_values,
                    color=color,
                    alpha=alpha,
                    linewidth=1.0,
                    label=label if i == 0 else "_nolegend_",
                )
            return

        common_x = np.linspace(min_x, max_x, self._background_points())
        interpolated = np.array(
            [
                np.interp(common_x, x_values, y_values)
                for x_values, y_values in cleaned
            ]
        )
        y_min = np.nanmin(interpolated, axis=0)
        y_max = np.nanmax(interpolated, axis=0)
        ax.fill_between(common_x, y_min, y_max, color=color, alpha=alpha, label=label)

    def _plot_curve(self, ax, element, colors):
        x_values, y_values = self._limited_xy(element)
        if not len(x_values):
            return

        fmt, color = self._resolve_plot_style(element.ls)
        if color:
            ax.plot(
                x_values,
                y_values,
                fmt,
                label=element.label,
                color=color,
                markevery=self._markevery(len(x_values)),
                fillstyle="none",
            )
        else:
            color = next(colors)
            ax.plot(
                x_values,
                y_values,
                fmt,
                label=element.label,
                color=color,
                markevery=self._markevery(len(x_values)),
                fillstyle="none",
            )

    def _axisroutine(self, ax, elements):
        """TODO: Docstring for _axisroutine.

        :arg1: TODO
        :returns: TODO

        """
        colors = cycle(mpl.rcParams["axes.prop_cycle"].by_key()["color"])
        for group in self._background_groups(elements):
            self._plot_background_group(ax, group, colors)
        for element in elements:
            if getattr(element, "is_background", False):
                continue
            self._plot_curve(ax, element, colors)

    def listElements(self):
        """
        Displays information about all PlotElements in the form of a table.

        The table includes the following columns:
        - Filename: The name of the file from which the element was loaded.
        - Element Index: The index of the element in the class for use in the 'out' method.
        - X-Label: The x-axis label from the original CSV file.
        - Y-Label: The y-axis label from the original CSV file.
        """
        import pandas as pd

        data = []
        current_file = None  # Track the current file to avoid repeating the filename

        # Iterate over all elements
        for idx, element in enumerate(self._elements):
            # Extract file name directly from the element (which we now store)
            file_name = element.file_name

            # Show the file name only if it's different from the previous one
            display_file_name = file_name if file_name != current_file else ""
            current_file = file_name  # Update the current file tracker

            # Add a row with file name, element index, x_label, and y_label from the element
            data.append([display_file_name, str(idx), element.x_label, element.y_label])

        # Convert the data to a pandas DataFrame for better display
        df = pd.DataFrame(data, columns=["Filename", "Idx", "X-Label", "Y-Label"])

        # Display the DataFrame as a table
        print(df.to_string(index=False, justify="left", col_space=20))
        return self


if __name__ == "__main__":
    pass
    # Example of how to use the class:
    # a = HyperPlot("time_heat")
    # a.fastCSV("UA_KH_Heat.csv")
    # a.fastCSV("UA_KH_Heat.csv")
    # a.fastCSV("UA_KH_Heat.csv", "$\mathrm{r}$|$\mathrm{r_e}$|$\mathrm{r_p}$")
    # a.catch(["UA_PF_Str.csv", "UA_KH_Str.csv"]).listElements().out(
    #    [0, 5], "Perfect elasto-plastic==--|With hardning"
    # )
    # import plotext as plt

    # y = plt.sin()
    # plt.plot(y)
    # plt.title("Line Plot")
    # plt.show()
    # a.set_plot_preferences(plot_type="strain_stress")
    # print(a.get_plot_preferences("plot_type","axis_labels"))
