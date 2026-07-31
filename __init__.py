# -*- coding: utf-8 -*-
def classFactory(iface):
    from .video_tracker import VideoTracker
    return VideoTracker(iface)
