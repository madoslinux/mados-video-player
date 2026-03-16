"""
madOS Video Player - Minimalist Interface
============================================

Ultra-minimalist video player with floating controls.
Only video fills the window, controls appear on hover.
"""

import os

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango

from .__init__ import __version__, __app_id__, __app_name__
from .theme import apply_theme
from .translations import detect_system_language, get_text
from .playlist import Playlist, RepeatMode, is_media_file, ALL_MEDIA_EXTENSIONS
from .player import PlayerEngine, format_time, GST_AVAILABLE
from .database import PlaylistDB

if GST_AVAILABLE:
    from gi.repository import Gst


class VideoPlayerApp(Gtk.Window):
    """Minimalist video player application window."""

    def __init__(self, initial_files=None):
        """Initialize the video player application."""
        super().__init__(title=__app_name__)

        self._language = detect_system_language()
        self._fullscreen_active = False
        self._controls_visible = False
        self._hide_controls_id = None
        self._programmatic_seek_update = False
        self._seek_debounce_id = None
        self._menu_open = False
        self._has_video = False

        # Apply Nord theme
        apply_theme()

        # Player engine and playlist
        self._engine = PlayerEngine()
        self._engine.on_eos = self._on_eos
        self._engine.on_error = self._on_error
        self._engine.on_state = self._on_state_changed
        self._engine.on_duration = self._on_duration
        self._engine.on_position = self._on_position
        self._engine.on_tags = self._on_tags
        self._playlist = Playlist()
        self._db = PlaylistDB()

        # Window setup
        self.set_default_size(854, 480)
        self.set_wmclass(__app_id__, __app_name__)
        self.set_icon_name("multimedia-video-player")
        self.connect("destroy", self._on_destroy)
        self.connect("key-press-event", self._on_key_press)

        # Enable drag-and-drop
        self.drag_dest_set(
            Gtk.DestDefaults.ALL,
            [Gtk.TargetEntry.new("text/uri-list", 0, 0)],
            Gdk.DragAction.COPY,
        )
        self.connect("drag-data-received", self._on_drag_data)

        # Build UI
        self._build_ui()

        # Load initial files
        if initial_files:
            for f in initial_files:
                abspath = os.path.abspath(f)
                if os.path.isdir(abspath):
                    self._playlist.add_directory(abspath)
                elif os.path.isfile(abspath):
                    self._playlist.add_file(abspath)
            if not self._playlist.is_empty:
                self._play_current()
        else:
            self._restore_session()

        # Show window
        self.show_all()
        self._controls_container.set_visible(False)
        self._placeholder.set_visible(False)
        self._update_title()
        
        # Connect size allocation for responsive controls
        self.connect("size-allocate", self._on_size_allocate)

    def _t(self, key):
        """Get translated string."""
        return get_text(key, self._language)

    def _build_ui(self):
        """Build the minimal user interface."""
        # Main container with overlay
        self._overlay = Gtk.Overlay()
        self.add(self._overlay)

        # Video display - fills entire window - wrap in EventBox for click handling
        if self._engine.video_widget:
            self._video_display = self._engine.video_widget
        else:
            self._video_display = Gtk.DrawingArea()
            self._video_display.connect("draw", self._on_video_draw)

        self._video_display.get_style_context().add_class("video-area")
        
        # Event box for video clicks - below controls
        self._video_event_box = Gtk.EventBox()
        self._video_event_box.set_above_child(False)
        self._video_event_box.add(self._video_display)
        self._video_event_box.connect("button-press-event", self._on_video_click)
        self._overlay.add(self._video_event_box)

        # Placeholder for when no video is loaded
        self._placeholder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._placeholder.set_halign(Gtk.Align.CENTER)
        self._placeholder.set_valign(Gtk.Align.CENTER)
        
        placeholder_icon = Gtk.Label(label="▶")
        placeholder_icon.get_style_context().add_class("placeholder-icon-large")
        self._placeholder.pack_start(placeholder_icon, False, False, 0)
        
        placeholder_text = Gtk.Label(label=self._t("drop_files_here"))
        placeholder_text.get_style_context().add_class("placeholder-text-large")
        self._placeholder.pack_start(placeholder_text, False, False, 0)
        
        self._overlay.add_overlay(self._placeholder)

        # Floating controls container (bottom center) - wrap in EventBox to capture events
        self._controls_event_box = Gtk.EventBox()
        self._controls_event_box.set_above_child(True)
        
        self._controls_container = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0
        )
        self._controls_container.set_halign(Gtk.Align.FILL)
        self._controls_container.set_hexpand(True)
        self._controls_container.set_valign(Gtk.Align.END)
        self._controls_container.set_margin_bottom(4)
        self._controls_container.get_style_context().add_class("floating-controls")
        
        self._controls_event_box.add(self._controls_container)

        # Build the floating control bar
        self._build_floating_controls()
        
        # Add controls LAST so they are on top and receive events first
        self._overlay.add_overlay(self._controls_event_box)
        
        # Connect window-level events for showing/hiding controls
        self.connect("motion-notify-event", self._on_window_motion)
        self.connect("enter-notify-event", self._on_window_motion)

    def _build_floating_controls(self):
        """Build the ultra-minimalist floating control bar."""
        # Main control bar - ultra compact - half size
        controls_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=2
        )
        controls_box.get_style_context().add_class("control-bar-floating")
        controls_box.set_margin_start(2)
        controls_box.set_margin_end(2)
        controls_box.set_margin_top(1)
        controls_box.set_margin_bottom(1)

        # Menu button (hamburger icon) - back to classic
        menu_btn = Gtk.Button(label="☰")
        menu_btn.set_tooltip_text(self._t("menu"))
        menu_btn.set_size_request(20, 20)
        menu_btn.get_style_context().add_class("control-btn")
        menu_btn.connect("clicked", self._on_menu_clicked)
        controls_box.pack_start(menu_btn, False, False, 0)

        # Play/Pause button - back to classic
        self._play_btn = Gtk.Button(label="▶")
        self._play_btn.set_tooltip_text(self._t("play"))
        self._play_btn.set_size_request(20, 20)
        self._play_btn.get_style_context().add_class("control-btn")
        self._play_btn.get_style_context().add_class("play-btn")
        self._play_btn.connect("clicked", lambda w: self._on_play_clicked())
        controls_box.pack_start(self._play_btn, False, False, 0)

        # Current time label - smaller
        self._time_label = Gtk.Label(label="0:00")
        self._time_label.get_style_context().add_class("time-label-floating")
        self._time_label.set_size_request(30, -1)
        controls_box.pack_start(self._time_label, False, False, 0)

        # Seek slider - expands to fill width, shrinks with window
        self._seek_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1000, 1)
        self._seek_scale.set_draw_value(False)
        self._seek_scale.set_hexpand(True)
        self._seek_scale.set_size_request(50, -1)
        self._seek_scale.get_style_context().add_class("seek-slider-floating")
        self._seek_scale.connect("value-changed", self._on_seek_changed)
        controls_box.pack_start(self._seek_scale, True, True, 0)

        # Duration label - smaller
        self._duration_label = Gtk.Label(label="0:00")
        self._duration_label.get_style_context().add_class("time-label-floating")
        self._duration_label.set_size_request(30, -1)
        controls_box.pack_start(self._duration_label, False, False, 0)

        # Volume button - standard icon
        self._volume_btn = Gtk.Button(label="🔊")
        self._volume_btn.set_tooltip_text(self._t("volume"))
        self._volume_btn.set_size_request(24, 20)
        self._volume_btn.get_style_context().add_class("control-btn")
        self._volume_btn.connect("clicked", self._on_volume_button_clicked)
        controls_box.pack_start(self._volume_btn, False, False, 0)

        # Volume slider - compact
        self._volume_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self._volume_scale.set_draw_value(False)
        self._volume_scale.set_size_request(50, -1)
        self._volume_scale.set_value(80)
        self._volume_scale.get_style_context().add_class("volume-slider-floating")
        self._volume_scale.connect("value-changed", self._on_volume_changed)
        controls_box.pack_start(self._volume_scale, False, False, 0)

        # Fullscreen button - standard icon
        fs_btn = Gtk.Button(label="⛶")
        fs_btn.set_tooltip_text(self._t("fullscreen"))
        fs_btn.set_size_request(20, 20)
        fs_btn.get_style_context().add_class("control-btn")
        fs_btn.connect("clicked", lambda w: self._toggle_fullscreen())
        controls_box.pack_start(fs_btn, False, False, 0)

        self._controls_container.pack_start(controls_box, True, True, 0)

    def _on_window_motion(self, widget, event):
        """Show controls when mouse moves over window."""
        self._show_controls()
        return False

    def _show_controls(self):
        """Show the floating controls."""
        if not self._controls_visible:
            self._controls_visible = True
            self._controls_container.set_visible(True)
        
        # Cancel existing hide timer
        if self._hide_controls_id:
            GLib.source_remove(self._hide_controls_id)
        
        # Schedule hide after 3 seconds (only if menu is not open)
        if not self._menu_open:
            self._hide_controls_id = GLib.timeout_add(3000, self._hide_controls)
    
    def _on_size_allocate(self, widget, allocation):
        """Handle window resize to hide/show controls responsively."""
        width = allocation.width
        
        # Minimum width thresholds
        VOLUME_HIDE_WIDTH = 450
        TIME_HIDE_WIDTH = 350
        
        # Show/hide volume slider
        if hasattr(self, '_volume_scale'):
            if width < VOLUME_HIDE_WIDTH:
                self._volume_scale.set_visible(False)
            else:
                self._volume_scale.set_visible(True)
        
        # Show/hide time labels
        if hasattr(self, '_time_label') and hasattr(self, '_duration_label'):
            if width < TIME_HIDE_WIDTH:
                self._time_label.set_visible(False)
                self._duration_label.set_visible(False)
            else:
                self._time_label.set_visible(True)
                self._duration_label.set_visible(True)

    def _hide_controls(self):
        """Hide the floating controls."""
        if self._menu_open:
            # Don't hide if menu is open
            return True
        self._controls_visible = False
        self._controls_container.set_visible(False)
        self._hide_controls_id = None
        return False

    def _on_video_draw(self, widget, cr):
        """Draw dark background on fallback video area."""
        alloc = widget.get_allocation()
        cr.set_source_rgb(0.0, 0.0, 0.0)
        cr.rectangle(0, 0, alloc.width, alloc.height)
        cr.fill()
        return False

    def _update_placeholder(self):
        """Update placeholder visibility based on video state."""
        if self._has_video:
            self._placeholder.set_visible(False)
        else:
            self._placeholder.set_visible(True)

    def _on_video_click(self, widget, event):
        """Handle click on video area (double-click = fullscreen)."""
        if event.type == Gdk.EventType.DOUBLE_BUTTON_PRESS:
            self._toggle_fullscreen()
        elif event.type == Gdk.EventType.BUTTON_PRESS:
            self._on_play_clicked()

    def _on_menu_clicked(self, widget):
        """Show popup menu with file options."""
        self._menu_open = True
        
        menu = Gtk.Menu()
        menu.connect("hide", self._on_menu_hidden)
        
        # Open file
        open_item = Gtk.MenuItem(label=self._t("open_file"))
        open_item.connect("activate", self._on_open_file)
        menu.append(open_item)
        
        # Open directory
        open_dir_item = Gtk.MenuItem(label=self._t("open_directory"))
        open_dir_item.connect("activate", self._on_open_directory)
        menu.append(open_dir_item)
        
        menu.append(Gtk.SeparatorMenuItem())
        
        # Playlist
        playlist_item = Gtk.MenuItem(label=self._t("playlist"))
        playlist_item.connect("activate", self._on_show_playlist)
        menu.append(playlist_item)
        
        menu.append(Gtk.SeparatorMenuItem())
        
        # About
        about_item = Gtk.MenuItem(label=self._t("about"))
        about_item.connect("activate", self._on_about)
        menu.append(about_item)
        
        # Quit
        quit_item = Gtk.MenuItem(label=self._t("quit"))
        quit_item.connect("activate", lambda w: self._on_destroy(w))
        menu.append(quit_item)
        
        menu.show_all()
        
        # Position menu above the button
        # widget = button, anchor = top-left of button, menu_anchor = bottom-left of menu
        menu.popup_at_widget(widget, Gdk.Gravity.NORTH, Gdk.Gravity.SOUTH, None)

    def _on_menu_hidden(self, menu):
        """Called when menu is closed."""
        self._menu_open = False
        # Restart hide timer
        if self._hide_controls_id:
            GLib.source_remove(self._hide_controls_id)
        self._hide_controls_id = GLib.timeout_add(3000, self._hide_controls)

    def _on_volume_button_clicked(self, widget):
        """Toggle mute on volume button click."""
        self._on_toggle_mute()

    # ------------------------------------------------------------------
    # Playback control
    # ------------------------------------------------------------------

    def _play_current(self):
        """Load and play the current playlist item."""
        filepath = self._playlist.current
        if filepath is None:
            return

        if self._engine.load(filepath):
            self._has_video = True
            self._update_placeholder()
            self._engine.play()
            self._update_title()

    def _on_play_clicked(self):
        """Handle play button click."""
        if self._engine.is_playing:
            self._engine.pause()
        elif self._playlist.current:
            if self._engine.get_position() >= 0:
                self._engine.play()
            else:
                self._play_current()
        elif not self._playlist.is_empty:
            self._playlist.select(0)
            self._play_current()

    def _on_next(self):
        """Play the next track."""
        track = self._playlist.next()
        if track:
            self._play_current()

    def _on_previous(self):
        """Play the previous track or restart current."""
        pos = self._engine.get_position()
        if GST_AVAILABLE and pos > 3 * Gst.SECOND:
            self._engine.seek(0)
            return
        track = self._playlist.previous()
        if track:
            self._play_current()

    def _seek_relative(self, seconds):
        """Seek relative by given seconds."""
        if GST_AVAILABLE:
            self._engine.seek_relative(int(seconds * Gst.SECOND))

    # ------------------------------------------------------------------
    # Volume
    # ------------------------------------------------------------------

    def _on_volume_changed(self, scale):
        """Handle volume slider change."""
        vol = scale.get_value() / 100.0
        self._engine.set_volume(vol)
        self._update_volume_icon()

    def _on_toggle_mute(self):
        """Toggle mute."""
        muted = self._engine.toggle_mute()
        self._update_volume_icon()

    def _update_volume_icon(self):
        """Update the volume button icon."""
        if self._engine.muted or self._engine.volume == 0:
            self._volume_btn.set_label("🔈")
        else:
            self._volume_btn.set_label("🔊")

    # ------------------------------------------------------------------
    # Seek bar
    # ------------------------------------------------------------------

    def _on_seek_changed(self, scale):
        """Handle seek bar value change (user-initiated only)."""
        if self._programmatic_seek_update:
            return
        if GST_AVAILABLE and self._engine.duration > 0:
            value = scale.get_value()
            position = int(value / 1000.0 * self._engine.duration)
            self._time_label.set_text(format_time(position))
            if self._seek_debounce_id is not None:
                GLib.source_remove(self._seek_debounce_id)
            self._seek_debounce_id = GLib.timeout_add(50, self._do_debounced_seek, position)

    def _do_debounced_seek(self, position_ns):
        """Execute a debounced seek operation."""
        self._seek_debounce_id = None
        self._engine.seek(position_ns)
        return False

    # ------------------------------------------------------------------
    # Engine callbacks
    # ------------------------------------------------------------------

    def _on_eos(self):
        """Handle end of stream."""
        next_track = self._playlist.next()
        if next_track:
            GLib.idle_add(self._play_current)

    def _on_error(self, message):
        """Handle playback error."""
        print(f"Playback error: {message}")

    def _on_state_changed(self, state):
        """Handle player state change."""
        if state == "playing":
            self._play_btn.set_label("⏸")
            self._play_btn.set_tooltip_text(self._t("pause"))
        elif state in ("paused", "stopped"):
            self._play_btn.set_label("▶")
            self._play_btn.set_tooltip_text(self._t("play"))

    def _on_duration(self, duration_ns):
        """Handle duration discovery."""
        self._duration_label.set_text(format_time(duration_ns))

    def _on_position(self, position_ns):
        """Handle position update."""
        self._time_label.set_text(format_time(position_ns))
        if self._engine.duration > 0:
            self._programmatic_seek_update = True
            percent = (position_ns / self._engine.duration) * 1000.0
            self._seek_scale.set_value(percent)
            self._programmatic_seek_update = False

    def _on_tags(self, tags):
        """Handle stream tags."""
        pass

    # ------------------------------------------------------------------
    # File dialogs
    # ------------------------------------------------------------------

    def _on_open_file(self, widget=None):
        """Show file open dialog."""
        dialog = Gtk.FileChooserDialog(
            title=self._t("open_file"),
            parent=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK,
        )
        dialog.set_select_multiple(True)

        media_filter = Gtk.FileFilter()
        media_filter.set_name("Media Files")
        for ext in sorted(ALL_MEDIA_EXTENSIONS):
            media_filter.add_pattern(f"*{ext}")
            media_filter.add_pattern(f"*{ext.upper()}")
        dialog.add_filter(media_filter)

        all_filter = Gtk.FileFilter()
        all_filter.set_name("All Files")
        all_filter.add_pattern("*")
        dialog.add_filter(all_filter)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filenames = dialog.get_filenames()
            was_empty = self._playlist.is_empty
            for f in filenames:
                self._playlist.add_file(f)
            if was_empty and not self._playlist.is_empty:
                self._play_current()
        dialog.destroy()

    def _on_open_directory(self, widget=None):
        """Show directory open dialog."""
        dialog = Gtk.FileChooserDialog(
            title=self._t("open_directory"),
            parent=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK,
        )

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            directory = dialog.get_filename()
            was_empty = self._playlist.is_empty
            self._playlist.add_directory(directory)
            if was_empty and not self._playlist.is_empty:
                self._play_current()
        dialog.destroy()

    def _on_show_playlist(self, widget=None):
        """Show playlist window."""
        if not hasattr(self, '_playlist_window') or self._playlist_window is None:
            self._playlist_window = PlaylistWindow(self._playlist, self)
            self._playlist_window.connect("destroy", self._on_playlist_window_closed)
        self._playlist_window._refresh()
        self._playlist_window.show_all()
        self._playlist_window.present()

    def _on_playlist_window_closed(self, widget):
        """Handle playlist window close."""
        self._playlist_window = None

    # ------------------------------------------------------------------
    # Drag and drop
    # ------------------------------------------------------------------

    def _on_drag_data(self, widget, context, x, y, data, info, time):
        """Handle files dropped onto the window."""
        uris = data.get_uris()
        was_empty = self._playlist.is_empty
        for uri in uris:
            filepath = GLib.filename_from_uri(uri)[0]
            if os.path.isdir(filepath):
                self._playlist.add_directory(filepath)
            elif os.path.isfile(filepath) and is_media_file(filepath):
                self._playlist.add_file(filepath)
        if was_empty and not self._playlist.is_empty:
            self._play_current()

    # ------------------------------------------------------------------
    # Fullscreen
    # ------------------------------------------------------------------

    def _toggle_fullscreen(self):
        """Toggle fullscreen mode."""
        if self._fullscreen_active:
            self.unfullscreen()
            self._fullscreen_active = False
        else:
            self.fullscreen()
            self._fullscreen_active = True

    # ------------------------------------------------------------------
    # About dialog
    # ------------------------------------------------------------------

    def _on_about(self, widget):
        """Show about dialog."""
        dialog = Gtk.MessageDialog(
            parent=self,
            flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            message_format=self._t("about_text").format(version=__version__),
        )
        dialog.set_title(self._t("about"))
        dialog.run()
        dialog.destroy()

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def _on_key_press(self, widget, event):
        """Handle keyboard shortcuts."""
        key = event.keyval
        state = event.state & Gtk.accelerator_get_default_mod_mask()
        ctrl = state & Gdk.ModifierType.CONTROL_MASK

        if key == Gdk.KEY_space:
            self._on_play_clicked()
            return True

        if key in (Gdk.KEY_f, Gdk.KEY_F11):
            self._toggle_fullscreen()
            return True

        if key == Gdk.KEY_Escape:
            if self._fullscreen_active:
                self._toggle_fullscreen()
                return True

        if key == Gdk.KEY_Right:
            self._seek_relative(10 if not ctrl else 60)
            return True

        if key == Gdk.KEY_Left:
            self._seek_relative(-10 if not ctrl else -60)
            return True

        if key == Gdk.KEY_Up:
            self._adjust_volume(0.05)
            return True

        if key == Gdk.KEY_Down:
            self._adjust_volume(-0.05)
            return True

        if key in (Gdk.KEY_m, Gdk.KEY_M):
            self._on_toggle_mute()
            return True

        if key in (Gdk.KEY_n, Gdk.KEY_N):
            self._on_next()
            return True

        if key in (Gdk.KEY_p, Gdk.KEY_P):
            self._on_previous()
            return True

        if ctrl and key == Gdk.KEY_o:
            self._on_open_file()
            return True

        if ctrl and key == Gdk.KEY_q:
            self._on_destroy(widget)
            return True

        return False

    def _adjust_volume(self, delta):
        """Adjust volume by delta."""
        new_vol = self._engine.volume + delta
        new_vol = max(0.0, min(1.0, new_vol))
        self._engine.set_volume(new_vol)
        self._volume_scale.set_value(new_vol * 100)
        self._update_volume_icon()

    # ------------------------------------------------------------------
    # UI updates
    # ------------------------------------------------------------------

    def _update_title(self):
        """Update the window title."""
        name = self._playlist.get_display_name()
        if name:
            self.set_title(f"{name} - {self._t('title')}")
        else:
            self.set_title(self._t("title"))

    # ------------------------------------------------------------------
    # Session persistence
    # ------------------------------------------------------------------

    def _restore_session(self):
        """Restore last session playlist from database."""
        try:
            session = self._db.load_session_playlist()
            if session and session["filepaths"]:
                for fp in session["filepaths"]:
                    if os.path.isfile(fp):
                        self._playlist.items.append(fp)
                if self._playlist.items:
                    self._playlist.current_index = max(
                        0, min(session["current_index"], len(self._playlist.items) - 1)
                    )
                    rm = session.get("repeat_mode", "none")
                    if rm in (RepeatMode.NONE, RepeatMode.ALL, RepeatMode.ONE):
                        self._playlist.repeat_mode = rm
                    if session.get("shuffle", False):
                        self._playlist.toggle_shuffle()
        except Exception:
            pass

    def _on_destroy(self, widget):
        """Handle window destroy."""
        try:
            self._db.save_session_playlist(
                filepaths=list(self._playlist.items),
                current_index=self._playlist.current_index,
                repeat_mode=self._playlist.repeat_mode,
                shuffle=self._playlist.shuffle,
            )
        except Exception:
            pass
        self._engine.cleanup()
        Gtk.main_quit()


class PlaylistWindow(Gtk.Window):
    """Separate playlist window."""

    def __init__(self, playlist, parent):
        super().__init__(title="Playlist")
        self._playlist = playlist
        self._parent = parent
        
        self.set_default_size(300, 400)
        self.set_transient_for(parent)
        
        # Build UI - use expand to fill window
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        vbox.set_vexpand(True)
        self.add(vbox)
        
        # Header with buttons
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        header.set_margin_start(4)
        header.set_margin_end(4)
        header.set_margin_top(4)
        header.set_margin_bottom(4)
        
        title = Gtk.Label(label="Playlist")
        title.set_hexpand(True)
        title.set_xalign(0.0)
        header.pack_start(title, True, True, 0)
        
        add_btn = Gtk.Button(label="+")
        add_btn.set_tooltip_text(self._parent._t("add_files"))
        add_btn.connect("clicked", self._on_add_files)
        header.pack_start(add_btn, False, False, 0)
        
        clear_btn = Gtk.Button(label="🗑")
        clear_btn.set_tooltip_text(self._parent._t("clear_playlist"))
        clear_btn.connect("clicked", self._on_clear)
        header.pack_start(clear_btn, False, False, 0)
        
        vbox.pack_start(header, False, False, 0)
        
        # Scrolled list - expand to fill available space
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        
        # Store: index, name, playing icon, delete button
        self._store = Gtk.ListStore(int, str, str, str)
        self._view = Gtk.TreeView(model=self._store)
        self._view.set_headers_visible(False)
        self._view.set_vexpand(True)
        self._view.connect("row-activated", self._on_row_activated)
        self._view.connect("cursor-changed", self._on_cursor_changed)
        
        # Enable selection
        selection = self._view.get_selection()
        selection.set_mode(Gtk.SelectionMode.SINGLE)
        
        # Playing icon column
        renderer_icon = Gtk.CellRendererText()
        col_icon = Gtk.TreeViewColumn("", renderer_icon, text=2)
        col_icon.set_fixed_width(24)
        self._view.append_column(col_icon)
        
        # Name column
        renderer_name = Gtk.CellRendererText()
        renderer_name.set_property("ellipsize", Pango.EllipsizeMode.END)
        col_name = Gtk.TreeViewColumn("", renderer_name, text=1)
        col_name.set_expand(True)
        self._view.append_column(col_name)
        
        # Delete button column (shows 🗑 on hover/selection)
        renderer_delete = Gtk.CellRendererText()
        renderer_delete.set_property("text", "🗑")
        renderer_delete.set_property("foreground", "#BF616A")
        col_delete = Gtk.TreeViewColumn("", renderer_delete, text=3)
        col_delete.set_fixed_width(32)
        self._view.append_column(col_delete)
        
        # Connect button click
        self._view.connect("button-press-event", self._on_view_button_press)
        
        scroll.add(self._view)
        vbox.pack_start(scroll, True, True, 0)
        
        # Refresh to show current playlist items
        self._refresh()
    
    def _on_cursor_changed(self, treeview):
        """Handle cursor change to show delete button."""
        pass  # Delete is always visible now
    
    def _on_view_button_press(self, treeview, event):
        """Handle click on delete button."""
        if event.type == Gdk.EventType.BUTTON_PRESS:
            # Get the row and column at click position
            result = treeview.get_path_at_pos(int(event.x), int(event.y))
            if result:
                path, column, cell_x, cell_y = result
                # Get column position and width
                width = column.get_width()
                # Check if click is in the last column (delete column)
                # Delete column is at index 2, check if click is in the right side
                model = treeview.get_model()
                tree_col = treeview.get_columns()
                if len(tree_col) >= 3:
                    delete_col = tree_col[2]
                    if column == delete_col:
                        itr = model.get_iter(path)
                        if itr:
                            idx = model.get_value(itr, 0)
                            self._remove_item(idx)
                            return True
        return False
    
    def _remove_item(self, idx):
        """Remove item at index."""
        # Stop if removing currently playing item
        if idx == self._playlist.current_index:
            self._parent._engine.stop()
        # Remove from playlist
        if idx < len(self._playlist.items):
            self._playlist.items.pop(idx)
            # Adjust current index if needed
            if self._playlist.current_index > idx:
                self._playlist.current_index -= 1
            elif self._playlist.current_index >= len(self._playlist.items):
                self._playlist.current_index = max(0, len(self._playlist.items) - 1)
        
        # Update database
        try:
            self._parent._db.save_session_playlist(
                filepaths=list(self._playlist.items),
                current_index=self._playlist.current_index,
                repeat_mode=self._playlist.repeat_mode,
                shuffle=self._playlist.shuffle,
            )
        except Exception:
            pass
        
        self._refresh()
    
    def _refresh(self):
        """Refresh the playlist view."""
        self._store.clear()
        for i, filepath in enumerate(self._playlist.items):
            icon = "▶" if i == self._playlist.current_index else ""
            name = os.path.basename(filepath)
            delete_icon = "🗑"
            self._store.append([i, name, icon, delete_icon])
    
    def _on_row_activated(self, treeview, path, column):
        """Handle double-click on playlist item."""
        model = treeview.get_model()
        itr = model.get_iter(path)
        if itr:
            idx = model.get_value(itr, 0)
            self._playlist.select(idx)
            self._parent._play_current()
            self._refresh()
    
    def _on_add_files(self, widget):
        """Add files to playlist."""
        self._parent._on_open_file()
        self._refresh()
    
    def _on_remove_selected(self, widget):
        """Remove selected item from playlist."""
        selection = self._view.get_selection()
        model, itr = selection.get_selected()
        if itr:
            idx = model.get_value(itr, 0)
            # Stop if removing currently playing item
            if idx == self._playlist.current_index:
                self._parent._engine.stop()
            # Remove from playlist
            if idx < len(self._playlist.items):
                self._playlist.items.pop(idx)
                # Adjust current index if needed
                if self._playlist.current_index > idx:
                    self._playlist.current_index -= 1
                elif self._playlist.current_index >= len(self._playlist.items):
                    self._playlist.current_index = max(0, len(self._playlist.items) - 1)
            self._refresh()
    
    def _on_clear(self, widget):
        """Clear playlist."""
        self._parent._engine.stop()
        self._playlist.clear()
        
        # Update database
        try:
            self._parent._db.save_session_playlist(
                filepaths=list(self._playlist.items),
                current_index=self._playlist.current_index,
                repeat_mode=self._playlist.repeat_mode,
                shuffle=self._playlist.shuffle,
            )
        except Exception:
            pass
        
        self._refresh()
