"""Interactive configuration utilities for heliotorrent."""

from __future__ import annotations

import json
import logging
import urllib.request
from copy import deepcopy
from typing import Any, Dict, Optional

import yaml


DEFAULT_LOG_LIST_URL = "https://www.gstatic.com/ct/log_list/v3/all_logs_list.json"

EXAMPLE_CONFIG_HEADER = """# Global settings for Heliotorrent
# Configure directories, ports, and the base feed URL. Each log's feed defaults to {feed_url_base}/<log_name>/feed.xml.
"""

EXAMPLE_CONFIG_FOOTER = """# You can add more logs here. Optional keys override the global defaults above.
#  - name: "another-log"
#    log_url: "https://another.log.server/log/"
    # Optional Keys:
    # feed_url: "http://127.0.0.1/alternative-location/feed.xml"
    # frequency: 300
    # entry_limit: null
    # delete_tiles: false
    # webseeds:
    #  - "http://webseed.example.com/"
"""

DEFAULT_CONFIG_TEMPLATE: Dict[str, Any] = {
    "data_dir": "data",
    "torrent_dir": "torrents",
    "https_port": 8443,
    "http_port": 8080,
    "tls_cert": None,
    "tls_key": None,
    "feed_url_base": "http://127.0.0.1:8080/torrents",
    "scraper_contact_email": None,
    "frequency": 0,
    "entry_limit": 1048576,
    "delete_tiles": True,
    "webseeds": ["http://127.0.0.1:8080/webseed/"],
    "logs": [
        {
            "name": "tuscolo2026h1",
            "log_url": "https://tuscolo2026h1.skylight.geomys.org/",
        }
    ],
}


def get_default_config() -> Dict[str, Any]:
    """Return a deep copy of the default configuration template."""

    return deepcopy(DEFAULT_CONFIG_TEMPLATE)


def render_config(config: Dict[str, Any], include_comments: bool = True) -> str:
    """Render a configuration dictionary to YAML, optionally adding helpful comments."""

    yaml_body = yaml.dump(config, default_flow_style=False, sort_keys=False)
    if not include_comments:
        return yaml_body

    header = EXAMPLE_CONFIG_HEADER.format(
        feed_url_base=config.get("feed_url_base", "http://127.0.0.1/torrents")
    ).rstrip()
    footer = EXAMPLE_CONFIG_FOOTER.rstrip()
    pieces = [header, yaml_body.rstrip(), footer]
    return "\n".join(piece for piece in pieces if piece) + "\n"


def fetch_log_list(url: str) -> Dict[str, Any]:
    """Fetch and parse the CT log list from the given URL."""

    with urllib.request.urlopen(url) as response:
        data = response.read()
    return json.loads(data)


def extract_logs_from_log_list(
    log_url: str
) -> str:

    log_list = fetch_log_list(log_url)
    config = {"logs": []}

    for operator in log_list.get("operators", []):
        for tiled_log in operator.get("tiled_logs", []):

            if tiled_log.get('log_type') == "test":
                logging.info(
                    "Skipping log %s test log",
                    tiled_log.get("description", "<unknown>")
                )
                continue

            status = tiled_log.get("state")
            if not status or ("qualified" not in status and "active" not in status and "usable" not in status):
                logging.info(
                    "Skipping log %s with state %s",
                    tiled_log.get("description", "<unknown>"),
                    status,
                )
                continue

            monitoring_url = tiled_log.get("monitoring_url")
            if not monitoring_url:
                logging.error("No url for tiled log %s, skipping", tiled_log.get("description", "<unknown>"))
                continue

            description = tiled_log.get("description", "")
            log_name = (
                description.replace(" ", "_")
                .replace("'", "")
                .replace("/", "_")
                .lower()
            )

            config["logs"].append(
                {
                    "name": log_name,
                    "log_url": monitoring_url,
                }
            )

    return yaml.dump(config, default_flow_style=False, sort_keys=False)


def _prompt_with_default(prompt_text: str, default: str) -> str:
    response = input(f"{prompt_text} [{default}]: ").strip()
    return response or default


def _prompt_yes_no(prompt_text: str, default: bool) -> bool:
    default_hint = "Y/n" if default else "y/N"
    while True:
        response = input(f"{prompt_text} [{default_hint}]: ").strip().lower()
        if not response:
            return default
        if response in {"y", "yes"}:
            return True
        if response in {"n", "no"}:
            return False
        print("Please respond with 'y' or 'n'.")


def _prompt_int(prompt_text: str, default: int) -> int:
    while True:
        response = input(f"{prompt_text} [{default}]: ").strip()
        if not response:
            return default
        try:
            return int(response)
        except ValueError:
            print("Please enter an integer value.")


def _prompt_optional_int(prompt_text: str, default: Optional[int]) -> Optional[int]:
    default_label = "null" if default is None else str(default)
    while True:
        response = input(f"{prompt_text} [{default_label}]: ").strip()
        if not response:
            return default
        lowered = response.lower()
        if lowered in {"null", "none"}:
            return None
        try:
            return int(response)
        except ValueError:
            print("Please enter an integer value or 'null'.")


def _prompt_non_empty(prompt_text: str, default: Optional[str] = None) -> str:
    while True:
        if default is not None:
            response = input(f"{prompt_text} [{default}]: ").strip()
            if not response:
                response = default
        else:
            response = input(f"{prompt_text}: ").strip()
        if response:
            return response
        print("This field is required.")


def _sanitize_domain(domain: str) -> str:
    domain = domain.strip()
    if domain.startswith("http://"):
        domain = domain[len("http://") :]
    if domain.startswith("https://"):
        domain = domain[len("https://") :]
    return domain.strip("/")


def run_interactive_config() -> tuple[Dict[str, Any], str]:
    """Interactively prompt the user for configuration values.

    Returns:
        A tuple of (config_dict, save_path)
    """

    print("Interactive config generation. Press Enter to accept defaults.")
    config = get_default_config()

    config["data_dir"] = _prompt_with_default(
        "Directory to save downloaded tiles", config["data_dir"]
    )
    config["torrent_dir"] = _prompt_with_default(
        "Directory to store torrent files", config["torrent_dir"]
    )

    use_https = _prompt_yes_no("Enable HTTPS?", True)
    if use_https:
        config["https_port"] = _prompt_int("HTTPS port", config["https_port"])

    config["http_port"] = _prompt_int("HTTP port", config["http_port"])

    domain = _prompt_with_default(
        "Domain name where Heliotorrent will be hosted", "127.0.0.1"
    )
    config["tls_cert"] = _prompt_with_default(
        "Path to TLS certificate file", f"/etc/letsencrypt/live/{domain}/fullchain.pem")

    config["tls_key"] = _prompt_with_default(
        "Path to TLS private key file", f"/etc/letsencrypt/live/{domain}/privkey.pem")

    protocol = "https" if use_https else "http"
    port = config['https_port'] if use_https else config['http_port']
    domain = _sanitize_domain(domain)
    config["feed_url_base"] = f"{protocol}://{domain}:{port}/torrents"

    while True:
        contact = _prompt_non_empty(
            "Scraper contact email (required)", None
        )
        if contact:
            config["scraper_contact_email"] = contact
            break
        print("Contact email is required.")

    config["frequency"] = 3600
    config["entry_limit"] = None
    config["delete_tiles"] = True

    config['webseeds'] = [f"{protocol}://{domain}:{port}/webseed/"]

    if _prompt_yes_no("Populate logs from the all_logs public CT log list?", True):
        try:
            log_config_yaml = extract_logs_from_log_list(
                DEFAULT_LOG_LIST_URL
            )
            fetched = yaml.safe_load(log_config_yaml)
            config["logs"] = fetched.get("logs", [])
            if not config["logs"]:
                print("No logs found in fetched list; keeping example entry.")
                config["logs"] = get_default_config()["logs"]
        except Exception as exc:  # pragma: no cover - interactive usage
            print(f"Failed to fetch log list, keeping example entry: {exc}")
            config["logs"] = get_default_config()["logs"]

    # Ask for save location
    save_path = _prompt_with_default(
        "Where to save the config file", "config.yml"
    )

    return config, save_path


__all__ = [
    "DEFAULT_LOG_LIST_URL",
    "DEFAULT_CONFIG_TEMPLATE",
    "fetch_log_list",
    "extract_logs_from_log_list",
    "get_default_config",
    "render_config",
    "run_interactive_config",
]
