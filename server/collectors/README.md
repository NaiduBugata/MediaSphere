# collectors/

News source collectors for MediaSphere. Each source has its own sub-package.

## Structure

```
collectors/
├── base/          # Abstract base class, registry, manager
├── lokal/         # Lokal Telugu app API collector
├── youtube/       # YouTube constituency news collector
└── sakshi/        # Sakshi newspaper web scraper
```

## Adding a New Collector

1. Create `collectors/<name>/` with `__init__.py`, `collector.py`, `config.py`
2. Extend `BaseCollector` from `collectors.base`
3. Register with `@register("<name>")` decorator
4. The pipeline runner will automatically discover enabled collectors
