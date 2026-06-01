import copy
import os
import tempfile


def configure_matplotlib_cache():
    os.environ.setdefault(
        "MPLCONFIGDIR",
        os.path.join(
            os.path.expanduser("~/.cache/hyperplot")
            if os.access(os.path.expanduser("~"), os.W_OK)
            else tempfile.gettempdir(),
            "matplotlib",
        ),
    )
    os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)


SHORT_COLOR_CODES = "bgrcmykw"
DEFAULT_SHORT_COLOR_PALETTE = {
    "b": "#4dbbd5",
    "g": "#00a087",
    "r": "#e64b35",
    "c": "#3c5488",
    "m": "#cc79a7",
    "y": "#f39b7f",
    "k": "black",
    "w": "white",
}

SUPPORTED_FORMATS = {
    "eps",
    "jpeg",
    "jpg",
    "pdf",
    "pgf",
    "png",
    "ps",
    "raw",
    "rgba",
    "svg",
    "svgz",
    "tif",
    "tiff",
    "webp",
}

DEFAULT_SETTINGS = {
    "axis_labels": {
        "time": r"Time t [s]",
        "E-1time": r"Time t [$10^{-1}$s]",
        "strain": "Engineering Strain  $\\varepsilon$  [-]",
        "Truestrain": "True Strain  ln$\\lambda$  [-]",
        "Stretch": "Stretch  $\\lambda$  [-]",
        "stress": "True stress  $\\sigma$  [MPa]",
        "heat": "Heat Generation  r  [mW]",
        "tempK": "Temperature  $\\theta$  [K]",
        "tempD": "Temperature  $\\theta$  [$^\\circ$C]",
    },
    "plot_type": "strain_stress_tempD",
    "plot_dpi": 300,
    "plot_format": "svg",
    "loc": "best",
    "_elements": [],
    "_element_counter": 0,
    "right_axis_color": "red",
    "outpath": "./plots/",
    "supported_formats": copy.deepcopy(SUPPORTED_FORMATS),
    "label_decimal": 0,
    "fig_width_cm": 9,
    "fig_height_cm": 9,
    "legend_line_length": 1.5,
    "marks": 10,
    "background_alpha": 0.25,
    "background_points": 1000,
    "color_palette": copy.deepcopy(DEFAULT_SHORT_COLOR_PALETTE),
    "fill": "none",
    "seperator": ",",
    "xmin": "None",
    "xmax": "None",
    "grid": "True",
}

USER_PREFERENCES = {
    "axis_labels",
    "plot_type",
    "plot_dpi",
    "plot_format",
    "loc",
    "right_axis_color",
    "label_decimal",
    "fig_width_cm",
    "fig_height_cm",
    "legend_line_length",
    "marks",
    "background_alpha",
    "background_points",
    "color_palette",
    "fill",
    "seperator",
    "xmin",
    "xmax",
    "grid",
}

INTERNAL_PREFERENCES = {
    "_elements",
    "_element_counter",
    "outpath",
    "supported_formats",
}

KNOWN_PREFERENCES = USER_PREFERENCES | INTERNAL_PREFERENCES
SERIALIZABLE_PREFERENCES = list(USER_PREFERENCES)

PLOT_RC_PARAMS = {
    "axes.formatter.use_mathtext": True,
    "font.family": "serif",
    "font.serif": [
        "Palatino",
        "Palatino Linotype",
        "TeX Gyre Pagella",
        "URW Palladio L",
        "P052",
        "DejaVu Serif",
    ],
    "mathtext.fontset": "custom",
    "mathtext.rm": "serif",
    "mathtext.it": "serif:italic",
    "mathtext.bf": "serif:bold",
    "xtick.labelsize": 14,
    "ytick.labelsize": 14,
    "legend.fontsize": 16,
    "axes.labelsize": 16,
    "figure.constrained_layout.use": True,
    "xtick.direction": "in",
    "ytick.direction": "in",
}


def parse_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    value = str(value).strip().lower()
    if value in {"true", "1", "yes", "y", "on"}:
        return True
    if value in {"false", "0", "no", "n", "off"}:
        return False
    raise ValueError(f"Cannot parse boolean value: {value!r}")


def parse_optional_float(value, name="value"):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    value = str(value).strip()
    if value == "" or value.lower() == "none":
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be empty, None, or a number; got {value!r}.") from exc


def parse_positive_float(value, name):
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive number; got {value!r}.") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be positive; got {value!r}.")
    return parsed


def parse_nonnegative_float(value, name):
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a non-negative number; got {value!r}.") from exc
    if parsed < 0:
        raise ValueError(f"{name} must be non-negative; got {value!r}.")
    return parsed


def parse_positive_int(value, name):
    try:
        parsed = int(float(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive integer; got {value!r}.") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be positive; got {value!r}.")
    return parsed


def validate_preference(name, value):
    if name in {"fig_width_cm", "fig_height_cm", "legend_line_length"}:
        return parse_positive_float(value, name)
    elif name == "plot_dpi":
        return parse_positive_int(value, name)
    elif name in {"marks", "background_points"}:
        return parse_positive_int(value, name)
    elif name == "background_alpha":
        parsed = parse_nonnegative_float(value, name)
        if parsed > 1:
            raise ValueError(f"{name} must be between 0 and 1; got {value!r}.")
        return parsed
    elif name == "label_decimal":
        return int(float(value))
    elif name == "grid":
        return parse_bool(value)
    elif name in {"xmin", "xmax"}:
        return parse_optional_float(value, name)
    elif name == "color_palette" and not isinstance(value, (dict, str)):
        raise ValueError("color_palette must be a mapping or a palette string.")
    return value
