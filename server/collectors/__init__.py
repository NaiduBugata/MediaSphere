"""MediaSphere news source collectors package.

Provides access to all collector implementations and the registry framework.
"""

from collectors.base.base_collector import BaseCollector  # noqa: F401
from collectors.base.registry import register, all_collectors, enabled_collectors  # noqa: F401
from collectors.sakshi.collector import collect_sakshi_articles  # noqa: F401

__all__ = ["BaseCollector", "collect_sakshi_articles", "register", "all_collectors", "enabled_collectors"]
