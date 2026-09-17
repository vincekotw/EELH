"""
Memoización de métricas con Django cache.

Cada métrica tiene un TTL distinto:
  - Corto (5 min):  métricas que dependen del estado actual
  - Medio (1h):     métricas de últimos días
  - Largo (24h):    métricas de comparaciones semanales

Usa LocMemCache por defecto. Si en producción se añade Redis,
funcionará igual pero compartido entre workers.
"""

import functools
import logging

from django.core.cache import cache


logger = logging.getLogger(__name__)

# TTLs predefinidos (segundos)
TTL_CORTO = 300      # 5 min
TTL_MEDIO = 3600     # 1 h
TTL_LARGO = 86400    # 24 h


def memoize(ttl=TTL_MEDIO, key_prefix='metrica'):
    """
    Decorador que cachea el resultado de una función sin argumentos
    o con argumentos simples (hashables).
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Clave de cache: prefix + nombre + args
            arg_str = ':'.join(str(a) for a in args)
            kw_str = ':'.join(f'{k}={v}' for k, v in sorted(kwargs.items()))
            parts = [p for p in [arg_str, kw_str] if p]
            key = f'{key_prefix}:{func.__name__}:{".".join(parts)}' if parts \
                  else f'{key_prefix}:{func.__name__}'

            value = cache.get(key)
            if value is not None:
                return value

            value = func(*args, **kwargs)
            cache.set(key, value, ttl)
            return value
        return wrapper
    return decorator


def invalidar_metricas():
    """Borra todas las métricas cacheadas. Útil al final del scraper."""
    try:
        cache.delete_pattern('metrica:*')
    except AttributeError:
        # LocMemCache no soporta delete_pattern
        logger.info('Cache backend no soporta delete_pattern, ignorando')