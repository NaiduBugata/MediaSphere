# sources/

Each collector applies the shared Narasaraopet Parliamentary Constituency
filter (`sources.base.constituency_validator`) before saving articles:

- **Sakshi** — tag URL + location-priority links + content validator
- **Lokal** — API tag feed + content validator
- **YouTube** — place-name search + news cleaner + content validator

```
sources/
├── base/                 # Collector framework
│   ├── base_collector.py     # BaseCollector ABC
│   ├── registry.py           # @register decorator + discovery
│   ├── collector_manager.py  # run_all_collectors()
│   └── interfaces.py         # CollectorProtocol / CollectorResult
│
├── lokal/                # Lokal app API collector
│   ├── collector.py          # run() orchestration + save
│   ├── api.py                # HTTP session + paginated API fetch
│   ├── parser.py             # timestamp parsing
│   ├── extractor.py          # lookback-window post extraction
│   ├── normalizer.py         # article shape + dedupe
│   ├── config.py             # env-driven settings
│   ├── constants.py          # static constants
│   ├── models.py             # typed shapes
│   └── tests/
│
├── youtube/              # YouTube collector
│   ├── collector.py          # run() orchestration
│   ├── channels.py           # Data API keyword/channel search
│   ├── transcript.py         # Telugu caption fetching
│   ├── parser.py             # TranscriptCleaner news filter
│   ├── normalizer.py         # transcript -> article shape
│   ├── config.py             # env-driven settings
│   └── tests/
│
└── sakshi/               # Sakshi.com web collector
    ├── collector.py          # SakshiCollector + run()
    ├── parser.py             # URL heuristics, link ranking, HTML helpers
    ├── extractor.py          # article field extraction from HTML
    ├── validator.py          # Narasaraopet constituency validation
    ├── normalizer.py         # article shape
    ├── config.py             # env-driven settings
    └── tests/
```

Legacy import paths (`lokal_collector`, `youtube.*`, `collectors.*`) remain
available as thin shims that re-export from this package.
