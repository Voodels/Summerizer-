"""
Configuration handling for VideoInsight.
"""
import os
import shutil
from typing import Dict, Any
import yaml

# Default configuration paths
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "default.yaml")
USER_CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".videoinsight")
USER_CONFIG_PATH = os.path.join(USER_CONFIG_DIR, "config.yaml")


def ensure_config_exists() -> None:
    """
    Ensure that the user configuration file exists.
    If it doesn't, create it from the default configuration.
    """
    if not os.path.exists(USER_CONFIG_PATH):
        os.makedirs(os.path.dirname(USER_CONFIG_PATH), exist_ok=True)
        shutil.copyfile(DEFAULT_CONFIG_PATH, USER_CONFIG_PATH)


def load_config() -> Dict[str, Any]:
    """
    Load configuration from the user config file.
    If it doesn't exist, create it from the default configuration.
    
    Returns:
        Dict[str, Any]: Configuration dictionary
    """
    ensure_config_exists()
    with open(USER_CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
    return config


def save_config(config: Dict[str, Any]) -> None:
    """
    Save configuration to the user config file.

    Args:
        config (Dict[str, Any]): Configuration dictionary
    """
    os.makedirs(os.path.dirname(USER_CONFIG_PATH), exist_ok=True)
    with open(USER_CONFIG_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


def get_config_path() -> str:
    """
    Get the path to the user configuration file.

    Returns:
        str: Path to the user configuration file
    """
    ensure_config_exists()
    return USER_CONFIG_PATH


def update_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update configuration with new values.

    Args:
        updates (Dict[str, Any]): Dictionary of configuration updates
    
    Returns:
        Dict[str, Any]: Updated configuration dictionary
    """
    config = load_config()

    def deep_update(source: Dict[str, Any], updates: Dict[str, Any]) -> None:
        for key, value in updates.items():
            if key in source and isinstance(source[key], dict) and isinstance(value, dict):
                deep_update(source[key], value)
            else:
                source[key] = value

    deep_update(config, updates)
    save_config(config)
    return config
