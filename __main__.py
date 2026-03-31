#!/usr/bin/env python3

import sys
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from app import VideoPlayerApp
from __init__ import __app_name__


def main():
    files = sys.argv[1:] if len(sys.argv) > 1 else []
    
    window = VideoPlayerApp(files)
    window.show_all()
    
    Gtk.main()


if __name__ == "__main__":
    main()
