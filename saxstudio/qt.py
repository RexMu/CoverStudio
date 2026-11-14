"""Qt6 production, Qt5 fallback for offline Linux UI validation."""
try:
    from PySide6 import QtCore, QtGui, QtWidgets, QtMultimedia, QtMultimediaWidgets
    Signal = QtCore.Signal
    QT6 = True
except ImportError:
    from PyQt5 import QtCore, QtGui, QtWidgets, QtMultimedia, QtMultimediaWidgets
    Signal = QtCore.pyqtSignal
    QT6 = False


def source(player, path):
    url = QtCore.QUrl.fromLocalFile(str(path)) if path else QtCore.QUrl()
    if QT6:
        player.setSource(url)
    else:
        player.setMedia(QtMultimedia.QMediaContent(url))


def state_playing(player):
    state = player.playbackState() if QT6 else player.state()
    states = QtMultimedia.QMediaPlayer.PlaybackState if QT6 else QtMultimedia.QMediaPlayer
    return state == states.PlayingState


def state_stopped(player):
    state = player.playbackState() if QT6 else player.state()
    states = QtMultimedia.QMediaPlayer.PlaybackState if QT6 else QtMultimedia.QMediaPlayer
    return state == states.StoppedState


def player(parent, video_widget=None, muted=False):
    p = QtMultimedia.QMediaPlayer(parent)
    if QT6:
        out = QtMultimedia.QAudioOutput(parent)
        out.setMuted(muted)
        p.setAudioOutput(out)
        p._audio_output = out
    else:
        p.setMuted(muted)
    if video_widget:
        p.setVideoOutput(video_widget)
    return p
