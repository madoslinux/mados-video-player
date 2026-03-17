# AGENTS.md - madOS Video Player

This file provides guidelines for agentic coding agents operating in this repository.

## Project Overview

madOS Video Player is a minimalist GTK3 video player using GStreamer for playback. It features a floating controls interface, playlist management, and session persistence via SQLite.

## Technology Stack

- **Language**: Python 3
- **UI Framework**: GTK3 (PyGObject)
- **Media Engine**: GStreamer (via GObject introspection)
- **Database**: SQLite (built-in)
- **No external test framework** - the project has no tests

## Build/Lint/Test Commands

### Running the Application

```bash
# Run with Python module
python -m mados_video_player

# Or use the executable
./mados-video-player

# Or run directly
python __main__.py
```

### Testing

**No test framework is configured.** There are no test files in this repository. Do not attempt to run tests.

### Linting/Type Checking

**No linting or type checking tools are configured.** The project does not have:
- pyproject.toml
- setup.py
- pytest
- ruff
- mypy
- black
- isort

If adding linting is needed, recommend using `ruff` for linting and `mypy` for type checking.

## Code Style Guidelines

### Imports

```python
# Standard library first
import os
import sqlite3
from contextlib import contextmanager

# Third-party (GTK/GStreamer)
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango

# Local imports (absolute)
from __init__ import __version__, __app_id__, __app_name__
from theme import apply_theme
from player import PlayerEngine, format_time, GST_AVAILABLE
```

### Naming Conventions

- **Classes**: `PascalCase` (e.g., `VideoPlayerApp`, `PlaylistDB`, `PlayerEngine`)
- **Functions/Variables**: `snake_case` (e.g., `get_display_name`, `is_media_file`)
- **Private attributes**: `self._private_name` (prefix with underscore)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `ALL_MEDIA_EXTENSIONS`, `DEFAULT_DB_PATH`)
- **Modules**: `snake_case.py` (e.g., `player.py`, `database.py`)

### Type Hints

Use type hints for properties and function signatures where helpful:

```python
@property
def is_playing(self) -> bool:
    return self._playing

def load(self, filepath: str) -> bool:
    ...
```

### Docstrings

Use Google-style docstrings with `Args:` and `Returns:` sections:

```python
def load(self, filepath: str) -> bool:
    """Load a media file.

    Args:
        filepath: Absolute path to the media file.

    Returns:
        True if loading started, False if GStreamer unavailable.
    """
```

### Error Handling

- Use try/except with specific exception types when possible
- Use context managers for database transactions
- Silent failures with `pass` are acceptable for non-critical operations
- Print errors for playback issues: `print(f"Playback error: {message}")`

### Code Patterns

**Private attributes with underscore prefix:**
```python
self._engine = PlayerEngine()
self._playlist = Playlist()
self._hide_controls_id = None
```

**Callbacks as instance attributes:**
```python
self.on_eos = None
self.on_error = None
self.on_state = None
```

**GTK signal connections:**
```python
self.connect("destroy", self._on_destroy)
button.connect("clicked", self._on_play_clicked)
```

**Property decorators for read-only access:**
```python
@property
def duration(self) -> int:
    """Return duration in nanoseconds, or -1 if unknown."""
    return self._duration
```

### Formatting

- 4-space indentation (no tabs)
- Maximum line length: 100 characters (soft limit, some CSS lines exceed this)
- Use f-strings for string formatting
- No trailing whitespace
- Blank lines between class methods

### GTK-Specific Patterns

**Window initialization:**
```python
super().__init__(title=__app_name__)
self.set_default_size(854, 480)
self.connect("destroy", self._on_destroy)
```

**Building UI:**
```python
self._overlay = Gtk.Overlay()
self.add(self._overlay)
controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
controls_box.get_style_context().add_class("control-bar-floating")
```

**CSS styling via theme module:**
```python
from theme import apply_theme
apply_theme()  # Call in __init__ before building UI
```

### GStreamer Patterns

**Initialization with fallback:**
```python
GST_AVAILABLE = False
try:
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst, GstVideo
    Gst.init(None)
    GST_AVAILABLE = True
except (ValueError, ImportError):
    pass
```

**Pipeline setup with video sink detection:**
```python
self._pipeline = Gst.ElementFactory.make("playbin", "player")
bus = self._pipeline.get_bus()
bus.add_signal_watch()
bus.connect("message::eos", self._on_bus_eos)
```

## Common Tasks

### Adding a New Menu Item

In `app.py`, add to `_on_menu_clicked`:
```python
menu_item = Gtk.MenuItem(label=self._t("menu_key"))
menu_item.connect("activate", self._on_handler)
menu.append(menu_item)
```

### Adding a New Keyboard Shortcut

In `app.py`, add to `_on_key_press`:
```python
if key == Gdk.KEY_KeyName:
    self._some_action()
    return True
```

### Database Schema Changes

Edit `_create_tables()` in `database.py`. Increment `_SCHEMA_VERSION` when changing tables.

## File Structure

```
mados-video-player/
├── AGENTS.md           # This file
├── __init__.py         # Package metadata
├── __main__.py         # Entry point
├── app.py              # Main window (GTK)
├── player.py           # GStreamer engine
├── playlist.py         # Playlist logic (no GTK)
├── database.py         # SQLite persistence
├── theme.py            # Nord CSS theme
├── translations.py     # i18n strings
└── mados-video-player # Executable launcher
```

## Important Notes

1. **No tests exist** - Do not attempt to run or add tests
2. **No CI/CD** - There are no GitHub Actions or similar
3. **GStreamer optional** - Player works in degraded mode without GStreamer
4. **Wayland/X11 handling** - Different video sinks for different display servers
5. **SQLite WAL mode** - Uses Write-Ahead Logging for concurrency