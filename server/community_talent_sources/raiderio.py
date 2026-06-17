import os


def load_templates():
    if not os.environ.get("WOW_RAIDERIO_API_KEY"):
        return {
            "status": "missing_credentials",
            "sourceName": "Raider.IO",
            "templates": [],
            "errors": ["WOW_RAIDERIO_API_KEY is not configured"],
        }
    return {
        "status": "blocked",
        "sourceName": "Raider.IO",
        "templates": [],
        "errors": ["Raider.IO adapter scaffolded; API implementation pending"],
    }

