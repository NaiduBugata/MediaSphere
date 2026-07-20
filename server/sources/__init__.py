"""MediaSphere news source packages.

Each source lives in its own subpackage with a consistent internal layout:

- ``base/``    — collector framework (ABC, registry, manager, protocols)
- ``lokal/``   — Lokal app API collector (api / parser / extractor / normalizer)
- ``youtube/`` — YouTube collector (channels / transcript / parser / normalizer)
- ``sakshi/``  — Sakshi web collector (parser / extractor / validator / normalizer)
"""
