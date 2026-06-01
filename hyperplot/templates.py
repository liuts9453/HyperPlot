import json
import os
from datetime import datetime

from .settings import USER_PREFERENCES


TEMPLATE_DIR_NAME = "templates"
TEMPLATE_EXTENSION = ".hpt.json"
DEFAULT_TEMPLATE_NAMES = (
    "default.hpt.json",
    "default.json",
    "default.hptemplate",
    "default",
)


def template_dir(base_file):
    return os.path.join(os.path.dirname(os.path.abspath(base_file)), TEMPLATE_DIR_NAME)


def default_template_path(base_file):
    folder = template_dir(base_file)
    for template_name in DEFAULT_TEMPLATE_NAMES:
        path = os.path.join(folder, template_name)
        if os.path.isfile(path):
            return path
    return None


def is_template_path(file_path):
    file_name = os.path.basename(file_path).lower()
    return (
        file_name.endswith(TEMPLATE_EXTENSION)
        or file_name.endswith(".hptemplate")
        or file_name in DEFAULT_TEMPLATE_NAMES
    )


def template_state(preferences):
    clean_preferences = {
        key: value for key, value in preferences.items() if key in USER_PREFERENCES
    }
    return {
        "app": "HyperPlot",
        "kind": "template",
        "version": 1,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "preferences": clean_preferences,
    }


def save_template(path, state):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2)
        file.write("\n")
    return path


def read_template_state(path):
    with open(path, "r", encoding="utf-8") as file:
        state = json.load(file)

    if state.get("app") != "HyperPlot" or state.get("kind") != "template":
        raise ValueError(f"{path} is not a HyperPlot template.")
    return state
