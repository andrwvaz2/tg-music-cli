import asyncio
import queue
import threading
from typing import Any

try:
    from dbus_next import BusType, RequestNameReply, Variant
    from dbus_next.aio import MessageBus
    from dbus_next.constants import PropertyAccess
    from dbus_next.service import ServiceInterface, dbus_property, method, signal

    HAS_DBUS = True
except ImportError:
    HAS_DBUS = False

    class ServiceInterface:  # type: ignore
        def __init__(self, name: str = "") -> None:
            pass

    def dbus_property(**kwargs):  # type: ignore
        def dec(fn):
            return fn

        return dec

    def method(**kwargs):  # type: ignore
        def dec(fn):
            return fn

        return dec

    def signal(**kwargs):  # type: ignore
        def dec(fn):
            return fn

        return dec

    class PropertyAccess:  # type: ignore
        READ = 1
        WRITE = 2
        READWRITE = 3

    class BusType:  # type: ignore
        SESSION = 1

    class RequestNameReply:  # type: ignore
        PRIMARY_OWNER = 1

    class Variant:  # type: ignore
        def __init__(self, sig: str, val: Any) -> None:
            self.value = val

from .cover import get_cover_uri
from .models import Track

# DBus type signatures used as method/property annotations (dbus-next reads
# them as strings). Kept as module constants so the linter sees defined names
# instead of bare signature tokens like "s"/"x".
_S = "s"
_B = "b"
_D = "d"
_X = "x"
_AS = "as"
_ASV = "a{sv}"
_O = "o"


def trackid_for(track: Track) -> str:
    return f"/org/mpris/MediaPlayer2/track/{track.id}"


def build_metadata(track: Track) -> dict[str, Variant]:
    # Snapshot the immutable Track reference once: all fields are then read from
    # this local, so a swap of self.tui.current_track mid-build cannot produce a
    # half-updated dict. The other scalars (volume, shuffle, repeat) are read
    # live by the individual property getters; a momentary inconsistency there is
    # harmless because MPRIS clients re-read on the next PropertiesChanged and
    # each value is an independent scalar (no partially-rendered structure).
    meta: dict[str, Variant] = {}
    meta["mpris:trackid"] = Variant(_O, trackid_for(track))
    meta["xesam:title"] = Variant(_S, track.display_title)
    artists = [track.performer] if track.performer else ([track.channel_title] if track.channel_title else [])
    meta["xesam:artist"] = Variant(_AS, artists)
    # xesam:album intentionally omitted: the Track model has no album field, and
    # emitting an empty string only makes clients show "Unknown Album". Omitting
    # is the correct representation when the album is genuinely unknown.
    if track.duration:
        meta["mpris:length"] = Variant(_X, int(track.duration * 1_000_000))
    meta["xesam:url"] = Variant(_S, track.telegram_url)
    art = get_cover_uri(track)
    if art:
        meta["mpris:artUrl"] = Variant(_S, art)
    return meta


class RootInterface(ServiceInterface):
    def __init__(self, service: "MprisService") -> None:
        super().__init__("org.mpris.MediaPlayer2")
        self._svc = service

    @method()
    def Raise(self) -> None:
        return

    @method()
    def Quit(self) -> None:
        self._svc.enqueue("quit")

    @dbus_property(access=PropertyAccess.READ)
    def CanQuit(self) -> _B:
        return False

    @dbus_property(access=PropertyAccess.READ)
    def CanRaise(self) -> _B:
        return False

    @dbus_property(access=PropertyAccess.READ)
    def HasTrackList(self) -> _B:
        return False

    @dbus_property(access=PropertyAccess.READ)
    def Identity(self) -> _S:
        return "tg-music"

    @dbus_property(access=PropertyAccess.READ)
    def DesktopEntry(self) -> _S:
        return "tg-music"

    @dbus_property(access=PropertyAccess.READ)
    def SupportedUriSchemes(self) -> _AS:
        return []

    @dbus_property(access=PropertyAccess.READ)
    def SupportedMimeTypes(self) -> _AS:
        return []


class PlayerInterface(ServiceInterface):
    def __init__(self, service: "MprisService") -> None:
        super().__init__("org.mpris.MediaPlayer2.Player")
        self._svc = service

    @method()
    def Play(self) -> None:
        self._svc.enqueue("play")

    @method()
    def Pause(self) -> None:
        self._svc.enqueue("pause")

    @method()
    def PlayPause(self) -> None:
        self._svc.enqueue("playpause")

    @method()
    def Stop(self) -> None:
        self._svc.enqueue("stop")

    @method()
    def Next(self) -> None:
        self._svc.enqueue("next")

    @method()
    def Previous(self) -> None:
        self._svc.enqueue("prev")

    @method()
    def Seek(self, offset: _X) -> None:
        self._svc.enqueue("seek", offset / 1_000_000)

    @method()
    def SetPosition(self, track_id: _S, position: _X) -> None:
        # La validación de track_id vive en el servicio (necesita el current_track).
        self._svc.handle_set_position(track_id, position / 1_000_000)

    @method()
    def OpenUri(self, uri: _S) -> None:
        return  # No soportado

    @dbus_property(access=PropertyAccess.READ)
    def PlaybackStatus(self) -> _S:
        return self._svc.playback_status()

    @dbus_property(access=PropertyAccess.READ)
    def LoopStatus(self) -> _S:
        return "Playlist" if self._svc.tui.repeat_mode else "None"

    @dbus_property(access=PropertyAccess.READ)
    def Rate(self) -> _D:
        return 1.0

    @dbus_property(access=PropertyAccess.READ)
    def Shuffle(self) -> _B:
        return self._svc.tui.shuffle_mode

    @dbus_property(access=PropertyAccess.READ)
    def Metadata(self) -> _ASV:
        track = self._svc.tui.current_track
        return build_metadata(track) if track is not None else {}

    @dbus_property(access=PropertyAccess.READ)
    def Volume(self) -> _D:
        return self._svc.tui.volume / 100.0

    @dbus_property(access=PropertyAccess.READ)
    def Position(self) -> _X:
        return int(self._svc.tui.player.get_position() * 1_000_000)

    @dbus_property(access=PropertyAccess.READ)
    def CanGoNext(self) -> _B:
        return self._svc.tui.current_track is not None

    @dbus_property(access=PropertyAccess.READ)
    def CanGoPrevious(self) -> _B:
        return self._svc.tui.current_track is not None

    @dbus_property(access=PropertyAccess.READ)
    def CanPlay(self) -> _B:
        return self._svc.tui.current_track is not None

    @dbus_property(access=PropertyAccess.READ)
    def CanPause(self) -> _B:
        return self._svc.tui.player.is_playing()

    @dbus_property(access=PropertyAccess.READ)
    def CanSeek(self) -> _B:
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanControl(self) -> _B:
        return True

    @signal()
    def Seeked(self, position: _X) -> None:
        pass


class MprisService:
    def __init__(self, tui: Any, bus_name: str = "org.mpris.MediaPlayer2.tg_music") -> None:
        self.tui = tui
        self.bus_name = bus_name
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._queue: "queue.Queue[tuple]" = queue.Queue()
        self.available = False
        self.status_message: str | None = None
        self._bus = None
        self._loop = None
        self._root = RootInterface(self)
        self._iface = PlayerInterface(self)

    def start(self) -> None:
        if not HAS_DBUS:
            self.available = False
            self.status_message = "MPRIS: no disponible (dbus no disponible)"
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)
        self.available = False

    def enqueue(self, *args: Any) -> None:
        self._queue.put(args)

    def drain(self) -> list[tuple]:
        items: list[tuple] = []
        while not self._queue.empty():
            items.append(self._queue.get())
        return items

    def handle_set_position(self, track_id: str, position: float) -> None:
        track = self.tui.current_track
        if track is None:
            return
        # Si el track_id no coincide con el current_track, la metadata del
        # cliente está desactualizada: la spec MPRIS manda ignorar en silencio.
        if trackid_for(track) != track_id:
            return
        self._queue.put(("seek_to", max(0.0, position)))

    def playback_status(self) -> str:
        if self.tui.current_track is None:
            return "Stopped"
        if self.tui.player.is_paused():
            return "Paused"
        if self.tui.player.is_playing():
            return "Playing"
        return "Stopped"

    def notify_state(self) -> None:
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self._emit_properties_changed)

    def _emit_properties_changed(self) -> None:
        try:
            track = self.tui.current_track
            self._iface.emit_properties_changed(
                {
                    "PlaybackStatus": Variant(_S, self.playback_status()),
                    "Metadata": Variant(_ASV, build_metadata(track) if track is not None else {}),
                    "Volume": Variant(_D, self.tui.volume / 100.0),
                },
                [],
            )
        except Exception:
            pass

    def _run(self) -> None:
        asyncio.run(self._serve())

    async def _serve(self) -> None:
        try:
            bus = await MessageBus(bus_type=BusType.SESSION).connect()
        except Exception as exc:
            self.available = False
            self.status_message = f"MPRIS: no disponible ({exc})"
            return
        reply = await bus.request_name(self.bus_name, flags=0)
        if reply != RequestNameReply.PRIMARY_OWNER:
            self.available = False
            self.status_message = "MPRIS: no disponible (otra instancia activa)"
            return
        self._bus = bus
        self._loop = asyncio.get_running_loop()
        bus.export("/org/mpris/MediaPlayer2", self._root)
        bus.export("/org/mpris/MediaPlayer2", self._iface)
        self.available = True
        try:
            while not self._stop_event.is_set():
                await asyncio.sleep(0.2)
        finally:
            try:
                bus.release_name(self.bus_name)
            except Exception:
                pass
            try:
                bus.disconnect()
            except Exception:
                pass
            self.available = False
            self._loop = None
