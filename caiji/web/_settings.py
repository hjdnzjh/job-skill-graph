# Shared settings access — avoids circular imports between server.py and api_*.py

_settings = None


def get_settings():
    global _settings
    if _settings is None:
        from config.settings import Settings
        _settings = Settings()
        # Start the log-buffer flush thread on first access
        from web.middleware.logging import init_log_buffer
        init_log_buffer(_settings)
    return _settings
