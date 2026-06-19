try:
    from ..simulator_payload import warcraftlogs_credentials_state
except ImportError:
    from simulator_payload import warcraftlogs_credentials_state


def load_templates():
    credentials = warcraftlogs_credentials_state()
    if not credentials["configured"]:
        return {
            "status": "missing_credentials",
            "sourceName": "Warcraft Logs",
            "templates": [],
            "errors": [
                "WOW_WARCRAFTLOGS_CLIENT_ID/WOW_WARCRAFTLOGS_CLIENT_SECRET or WOW_WARCRAFTLOGS_API_KEY are not configured"
            ],
        }
    return {
        "status": "blocked",
        "sourceName": "Warcraft Logs",
        "credentialMode": credentials["mode"],
        "api": credentials["api"],
        "templates": [],
        "errors": [f"Warcraft Logs adapter scaffolded for {credentials['api']}; extraction implementation pending"],
    }
