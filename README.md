# madOS Video Player

A minimalist GTK3 video player using GStreamer for playback, featuring a floating controls interface, playlist management, and session persistence via SQLite.

## Features

- **Floating Controls**: Ultra-minimalist interface with controls that appear on hover
- **Playlist Management**: Add files, directories, shuffle, and repeat modes
- **Session Persistence**: Automatically saves and restores last playlist
- **Keyboard Shortcuts**: Space (play/pause), F/F11 (fullscreen), arrows (seek/volume)
- **Drag & Drop**: Drop video files directly onto the window
- **Multi-format Support**: MP4, MKV, AVI, MOV, WEBM, and many more

## Requirements

- Python 3
- GTK3
- GStreamer 1.0 + GStreamer Python bindings
- SQLite3 (built-in)

## Installation

```bash
# Run with Python module
python -m mados_video_player

# Or use the executable
./mados-video-player

# Or run directly
python __main__.py
```

## Architecture

### Frontend (GTK3 UI)

```
┌─────────────────────────────────────────────────────────────┐
│                      VideoPlayerApp                         │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐   │
│  │  Overlay    │  │ Video       │  │ Floating         │   │
│  │  Container  │  │ Display     │  │ Controls         │   │
│  └─────────────┘  └─────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    PlaylistWindow                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  TreeView with playlist items                       │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Backend (Core Modules)

```
┌─────────────────────────────────────────────────────────────┐
│  player.py - GStreamer Engine                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  PlayerEngine: play, pause, stop, seek, volume     │   │
│  │  Video sink detection (Wayland/X11/GTK)             │   │
│  │  Callbacks: on_eos, on_error, on_state, on_position│   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  playlist.py - Playlist Management                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Playlist: add_file, add_directory, next, previous │   │
│  │  Repeat modes: NONE, ALL, ONE                       │   │
│  │  Shuffle support                                    │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  database.py - SQLite Persistence                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  PlaylistDB: save/load playlists, session state    │   │
│  │  Tables: playlists, playlist_items, session         │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Sequence Diagrams

### Frontend Flow: Play Video

```mermaid
sequenceDiagram
    participant User
    participant UI as VideoPlayerApp
    participant Engine as PlayerEngine
    participant Playlist as Playlist
    participant Display as Video Display

    User->>UI: Double-click / Play button
    UI->>Playlist: get current file
    Playlist-->>UI: filepath
    UI->>Engine: load(filepath)
    Engine->>Engine: Set GStreamer URI
    Engine-->>UI: True (loaded)
    UI->>Engine: play()
    Engine->>Display: Start video output
    Engine->>UI: on_state("playing")
    UI->>UI: Update play button to ⏸

    loop Playback
        Engine->>UI: on_position(ns)
        UI->>UI: Update seek slider
    end

    Engine->>UI: on_eos()
    UI->>Playlist: next()
    Playlist-->>UI: next filepath
    UI->>Engine: load(filepath)
    UI->>Engine: play()
```

### Frontend Flow: Playlist Management

```mermaid
sequenceDiagram
    participant User
    participant UI as VideoPlayerApp
    participant Window as PlaylistWindow
    participant Playlist as Playlist
    participant DB as PlaylistDB

    User->>UI: Menu > Playlist
    UI->>Window: Create PlaylistWindow
    Window->>Playlist: _refresh()
    Playlist-->>Window: items list
    Window->>Window: Populate TreeView

    User->>Window: Double-click item
    Window->>Playlist: select(index)
    Playlist-->>Window: filepath
    Window->>UI: _play_current()
    UI->>UI: Engine.load() + play()

    User->>Window: Click delete
    Window->>Playlist: remove(index)
    Playlist-->>Window: updated items
    Window->>Window: _refresh()
    Window->>DB: save_session_playlist()
```

### Backend Flow: Seek Operation

```mermaid
sequenceDiagram
    participant UI
    participant Engine as PlayerEngine
    participant Gst as GStreamer
    participant Pipeline as Pipeline

    UI->>UI: _on_seek_changed()
    UI->>UI: _do_debounced_seek(50ms debounce)
    UI->>Engine: seek(position_ns)

    alt Pipeline not ready
        Engine->>Pipeline: set_state(PAUSED)
    end

    Engine->>Pipeline: seek(speed, TIME, FLUSH, SET, position)
    Pipeline-->>Engine: seek result
    Engine-->>UI: Return

    Note over Engine,Pipeline: If was playing, stay playing<br/>If was paused, stay paused
```

### Backend Flow: Session Persistence

```mermaid
sequenceDiagram
    participant App
    participant Playlist as Playlist
    participant DB as PlaylistDB
    participant SQLite as SQLite DB

    Note over App,SQLite: On Startup (restore_session)
    App->>DB: load_session_playlist()
    DB->>SQLite: Query session + playlist
    SQLite-->>DB: Session data
    DB-->>App: {filepaths, current_index, repeat_mode, shuffle}
    App->>Playlist: items.extend(filepaths)
    App->>Playlist: current_index = ...
    App->>Playlist: repeat_mode = ...

    Note over App,SQLite: On Close (_on_destroy)
    App->>Playlist: get current state
    App->>DB: save_session_playlist(filepaths, index, repeat, shuffle)
    DB->>SQLite: INSERT/UPDATE playlists + session
    SQLite-->>DB: Success
    DB-->>App: Return
```

### Backend Flow: Video Sink Detection

```mermaid
sequenceDiagram
    participant Engine as PlayerEngine
    participant Gst as GStreamer
    participant Display as Gdk.Display

    Engine->>Engine: _setup_pipeline()
    Engine->>Gst: ElementFactory.make("playbin")

    alt gtksink available (preferred)
        Engine->>Gst: ElementFactory.make("gtksink")
        Engine->>Engine: Use gtksink widget
    else Wayland display
        Engine->>Display: get_default()
        Display-->>Engine: WaylandDisplay
        Engine->>Gst: Try gtkglsink, then waylandsink
    else X11 display
        Engine->>Display: get_default()
        Display-->>Engine: X11Display
        Engine->>Gst: Try xvimagesink, fallback to ximagesink
    else Other
        Engine->>Gst: Use autovideosink
    end

    Engine->>Gst: pipeline.set_property("video-sink", sink)
    Engine->>Gst: bus.add_signal_watch()
    Engine->>Engine: Connect bus callbacks
```

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Space | Play/Pause |
| F / F11 | Toggle Fullscreen |
| Escape | Exit Fullscreen |
| Left/Right | Seek -10s / +10s (Ctrl for 60s) |
| Up/Down | Volume ±5% |
| M | Toggle Mute |
| N | Next track |
| P | Previous track |
| Ctrl+O | Open file |
| Ctrl+Q | Quit |

## File Structure

```
mados-video-player/
├── __init__.py         # Package metadata
├── __main__.py         # Entry point
├── app.py              # Main window (GTK)
├── player.py           # GStreamer engine
├── playlist.py         # Playlist logic
├── database.py         # SQLite persistence
├── theme.py            # Nord CSS theme
├── translations.py     # i18n strings
├── .gitignore
├── AGENTS.md          # Developer guidelines
└── README.md
```

## License

MIT License