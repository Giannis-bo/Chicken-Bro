import os


def load_templates():
    if not os.environ.get("WOW_WARCRAFTLOGS_CLIENT_ID") or not os.environ.get("WOW_WARCRAFTLOGS_CLIENT_SECRET"):
        return {
            "status": "missing_credentials",
            "sourceName": "Warcraft Logs",
            "templates": [],
            "errors": ["WOW_WARCRAFTLOGS_CLIENT_ID/WOW_WARCRAFTLOGS_CLIENT_SECRET are not configured"],
        }
    return {
        "status": "blocked",
        "sourceName": "Warcraft Logs",
        "templates": [],
        "errors": ["Warcraft Logs adapter scaffolded; GraphQL implementation pending"],
    }
