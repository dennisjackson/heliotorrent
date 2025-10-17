

import interactive_config


def test_fetch_log_list_parses_default_fixture():

    logs = interactive_config.extract_logs_from_log_list(interactive_config.DEFAULT_LOG_LIST_URL)
    assert(len(logs) > 0)
