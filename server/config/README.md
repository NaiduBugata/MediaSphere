# config/

Centralized configuration for MediaSphere.

| File | Purpose |
|------|---------|
| `settings.py` | Runtime settings from environment variables |
| `constants.py` | Static constants: paths, filenames, encodings |
| `environment.py` | Helpers: `_truthy()`, `_int_env()`, `_float_env()` |

## Usage

```python
from config import OUTPUT_PATH, ARTICLE_SEPARATOR
from config.environment import _truthy
```
