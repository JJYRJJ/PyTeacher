import json
import os
import io
import contextlib
import traceback


def log_info(message):
    print(f"[INFO] {message}")


def log_error(message):
    print(f"[ERROR] {message}")


def load_config(path="config.json"):
    if not os.path.exists(path):
        log_error(f"Config file not found: {path}")
    with open(path, 'r') as f:
        config = json.load(f)
    return config


def execute_code(code):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        try:
            exec(code)
        except Exception as e:
            return traceback.format_exc()
    return output.getvalue()
