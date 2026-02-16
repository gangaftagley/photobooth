#!/usr/bin/env python3
"""config.py -- Load and save booth.yml configuration."""

import os
import yaml

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(PROJECT_DIR, 'booth.yml')

DEFAULTS = {
    'display': {
        'banner_text': 'Captains Photobooth',
        'text_color': [46, 65, 95],
        'screen_image': 'screen.jpg',
    },
    'printing': {
        'template_image': 'template.jpg',
        'paper_tray_count': 18,
        'max_retries': 3,
        'retry_delay': 5,
    },
    'state': {
        'images_printed': 0,
        'paper_bundles_loaded': 1,
    },
}


def load_config():
    """Load config from booth.yml, filling in defaults for missing keys."""
    config = {}
    for section, values in DEFAULTS.items():
        config[section] = dict(values)

    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            saved = yaml.safe_load(f)
        if saved and isinstance(saved, dict):
            for section in DEFAULTS:
                if section in saved and isinstance(saved[section], dict):
                    config[section] = {**DEFAULTS[section], **saved[section]}

    return config


def save_config(config):
    """Write config back to booth.yml."""
    with open(CONFIG_FILE, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)


def resolve_path(filename):
    """Resolve a filename relative to the project directory."""
    return os.path.join(PROJECT_DIR, filename)


def get_available_images(pattern=''):
    """Return sorted list of .jpg files in the project root, optionally filtered by pattern."""
    files = []
    for f in os.listdir(PROJECT_DIR):
        if f.lower().endswith(('.jpg', '.jpeg', '.png')) and os.path.isfile(os.path.join(PROJECT_DIR, f)):
            if pattern == '' or pattern in f.lower():
                files.append(f)
    return sorted(files)
