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
        "common.config.config": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "common.config.failover": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "products.interview.agent.execution.graph_factory": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "products.interview.rag.embedding": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "products.interview.rag.skill_router": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "products.interview.pdf.schema_tools": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "common.integrations.mcp.mcp_multiserver": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "huggingface_hub": {"handlers": ["console"], "level": "CRITICAL", "propagate": False},
        "huggingface_hub.utils._http": {
            "handlers": ["console"],
            "level": "CRITICAL",
            "propagate": False,
        },
    },
}
