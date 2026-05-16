from __future__ import annotations

import logging
from pythonjsonlogger import json

def get_logger(name: str) -> logging.Logger:
    """Configura e retorna um logger com formato JSON."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Evita adicionar handlers duplicados
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = json.JsonFormatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger

# Logger genérico para uso em toda a aplicação
log = get_logger(__name__)
