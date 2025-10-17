

import interactive_config


def test_fetch_log_list_parses_default_fixture():

    logs = interactive_config.extract_logs_from_log_list(interactive_config.DEFAULT_LOG_LIST_URL)

    # assert log_list["operators"][0]["name"] == "Google"

    # assert parsed["logs"][0]["name"] == "google_argon2022_log"
    # assert parsed["logs"][0]["log_url"] == "https://ct.googleapis.com/logs/argon2022/"
