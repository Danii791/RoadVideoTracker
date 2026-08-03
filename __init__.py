# -*- coding: utf-8 -*-
import os
import sys

_plugin_dir = os.path.dirname(os.path.abspath(__file__))
if _plugin_dir not in sys.path:
    sys.path.insert(0, _plugin_dir)


def classFactory(iface):
    from .video_tracker import VideoTracker
    return VideoTracker(iface)
