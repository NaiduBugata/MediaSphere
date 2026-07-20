"""Legacy shim package — canonical collectors live in ``sources``.

Provides access to all collector implementations and the registry framework.
"""

from sources.base.base_collector import BaseCollector  # noqa: F401
from sources.base.registry import register, all_collectors, enabled_collectors  # noqa: F401
from sources.sakshi.collector import collect_sakshi_articles  # noqa: F401

__all__ = ["BaseCollector", "collect_sakshi_articles", "register", "all_collectors", "enabled_collectors"]
