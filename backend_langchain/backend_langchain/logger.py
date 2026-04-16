LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        }
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "common.agent": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "common.embedding": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "common.skill_router": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "Langchain_Agent.tools": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "chromadb.telemetry": {
            "handlers": ["console"],
            "level": "CRITICAL",
            "propagate": False,
        },
        "chromadb.telemetry.product.posthog": {
            "handlers": ["console"],
            "level": "CRITICAL",
            "propagate": False,
        },
        "huggingface_hub": {
            "handlers": ["console"],
            "level": "CRITICAL",
            "propagate": False,
        },
        "huggingface_hub.utils._http": {
            "handlers": ["console"],
            "level": "CRITICAL",
            "propagate": False,
        },
    },
}
