LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "agent.graph_factory": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "agent.rag.embedding": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "agent.rag.skill_router": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "agent.tools": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "app.routers.api": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "agent.mcp.mcp_multiserver": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "huggingface_hub": {"handlers": ["console"], "level": "CRITICAL", "propagate": False},
        "huggingface_hub.utils._http": {
            "handlers": ["console"],
            "level": "CRITICAL",
            "propagate": False,
        },
    },
}
