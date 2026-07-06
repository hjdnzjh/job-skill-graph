# Shared settings access — avoids circular imports between server.py and api_*.py

_settings = None


def get_settings():
    global _settings
    if _settings is None:
        from config.settings import Settings
        _settings = Settings()
    return _settings
