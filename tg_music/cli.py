from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import re
import sys
from pathlib import Path

from .config import CONFIG_FILE, ensure_dirs, load_settings, save_config, save_settings
from .cache import CacheResult, cache_tracks_async
from .welcome import show_welcome
from .db import (
    add_to_playlist,
    connect,
    create_playlist,
    delete_playlist,
    get_all_favorite_ids,
    get_playlist_by_name,
    get_playlist_tracks,
    get_track,
    get_track_tags,
    is_favorite,
    latest_for_channel,
    latest_message_id_for_channel,
    list_all_tags,
    list_ignored_tracks,
    list_channels,
    list_playlists,
    list_random_tracks,
    list_recently_played,
    list_top_played,
    list_tracks,
    list_uncached_tracks,
    record_play,
    remove_channel,
    remove_from_playlist,
    remove_tag,
    rename_playlist,
    set_ignored,
    tag_track,
    toggle_favorite,
    untag_track,
)
from .lyrics import fetch_lyrics
from .themes import THEME_ORDER
from .models import format_duration
from .player import play_file
from .shared import cleanup_stale_cache, delete_cached_files, format_bytes, notify_user
from .telegram_client import download_track, normalize_channel, scan_channel, scan_channel_since
from .tui import run_tui


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv or ["tui"])

    try:
        ensure_dirs()
        return args.func(args)
    except KeyboardInterrupt:
        print("\nCancelado.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tg-music")
    sub = parser.add_subparsers()

    init = sub.add_parser("init", help="Configura api_id y api_hash de Telegram")
    init.set_defaults(func=cmd_init)

    scan = sub.add_parser("scan", help="Escanea audios de un canal")
    scan.add_argument("channel", help="URL, @usuario o username del canal")
    scan.add_argument("--limit", type=int, default=300, help="Mensajes a revisar")
    scan.add_argument(
        "--cache",
        action="store_true",
        help="Descarga al cache los audios encontrados que aun falten",
    )
    scan.set_defaults(func=cmd_scan)

    add_channel = sub.add_parser("add-channel", help="Agrega/escanea un canal de musica")
    add_channel.add_argument("channel", help="URL, @usuario o username del canal")
    add_channel.add_argument("--limit", type=int, default=300, help="Mensajes a revisar")
    add_channel.add_argument("--cache", action="store_true", help="Descarga al cache lo encontrado")
    add_channel.set_defaults(func=cmd_scan)

    channels = sub.add_parser("channels", help="Lista canales agregados")
    channels.set_defaults(func=cmd_channels)

    remove_channel_cmd = sub.add_parser("remove-channel", help="Elimina un canal de la base de datos")
    remove_channel_cmd.add_argument("channel", help="Username del canal a eliminar")
    remove_channel_cmd.set_defaults(func=cmd_remove_channel)

    list_cmd = sub.add_parser("list", help="Lista canciones indexadas")
    list_cmd.add_argument("--limit", type=int, default=50)
    list_cmd.add_argument("--json", action="store_true", help="Salida en formato JSON")
    list_cmd.add_argument("--favorites", action="store_true", help="Solo favoritos")
    list_cmd.add_argument("--tag", type=str, help="Filtrar por tag")
    list_cmd.set_defaults(func=cmd_list)

    search = sub.add_parser("search", help="Busca canciones indexadas")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=50)
    search.add_argument("--json", action="store_true", help="Salida en formato JSON")
    search.set_defaults(func=cmd_search)

    play = sub.add_parser("play", help="Descarga si hace falta y reproduce por id")
    play.add_argument("id", type=int)
    play.set_defaults(func=cmd_play)

    latest = sub.add_parser("play-latest", help="Reproduce el audio mas reciente de un canal indexado")
    latest.add_argument("channel")
    latest.set_defaults(func=cmd_play_latest)

    random_play = sub.add_parser("random", help="Reproduce una cancion al azar")
    random_play.add_argument("--limit", type=int, default=1, help="Numero de canciones")
    random_play.set_defaults(func=cmd_random)

    cache = sub.add_parser("cache", help="Descarga canciones indexadas al cache")
    cache.add_argument("channel", nargs="?", help="Canal opcional para limitar la descarga")
    cache.add_argument("--limit", type=int, default=50, help="Maximo de canciones a descargar")
    cache.add_argument("--workers", type=int, default=1, help="Descargas paralelas, maximo recomendado 3")
    cache.set_defaults(func=cmd_cache)

    watch = sub.add_parser(
        "watch",
        help="Vigila canales indexados y avisa cuando aparezca musica nueva",
    )
    watch.add_argument("channel", nargs="*", help="Canales opcionales; si no, vigila todos")
    watch.add_argument("--interval", type=int, default=300, help="Segundos entre revisiones")
    watch.add_argument("--once", action="store_true", help="Revisa una vez y sale")
    watch.set_defaults(func=cmd_watch)

    ignore = sub.add_parser("ignore", help="Ignora canciones y borra su cache local")
    ignore.add_argument("ids", nargs="+", type=int, help="IDs de canciones a ignorar")
    ignore.set_defaults(func=cmd_ignore)

    unignore = sub.add_parser("unignore", help="Quita canciones de la lista ignorada")
    unignore.add_argument("ids", nargs="+", type=int, help="IDs de canciones a restaurar")
    unignore.set_defaults(func=cmd_unignore)

    ignored = sub.add_parser("ignored", help="Lista canciones ignoradas")
    ignored.add_argument("--limit", type=int, default=50)
    ignored.set_defaults(func=cmd_ignored)

    status = sub.add_parser("status", help="Muestra resumen de la biblioteca")
    status.set_defaults(func=cmd_status)

    cleanup = sub.add_parser("cleanup", help="Limpia archivos cacheados antiguos")
    cleanup.add_argument("--max-age", type=int, default=30, help="Dias maximos de antiguedad")
    cleanup.set_defaults(func=cmd_cleanup)

    fav = sub.add_parser("favorite", help="Marca/desmarca un track como favorito")
    fav.add_argument("ids", nargs="+", type=int, help="IDs de canciones")
    fav.set_defaults(func=cmd_favorite)

    recent = sub.add_parser("recent", help="Muestra canciones reproducidas recientemente")
    recent.add_argument("--limit", type=int, default=20)
    recent.add_argument("--json", action="store_true")
    recent.set_defaults(func=cmd_recent)

    top = sub.add_parser("top", help="Muestra las canciones mas reproducidas")
    top.add_argument("--limit", type=int, default=20)
    top.add_argument("--json", action="store_true")
    top.set_defaults(func=cmd_top)

    t = sub.add_parser("tag", help="Gestiona tags en canciones")
    t_sub = t.add_subparsers()
    t_add = t_sub.add_parser("add", help="Agrega un tag a un track")
    t_add.add_argument("track_id", type=int)
    t_add.add_argument("tag_name")
    t_add.set_defaults(func=cmd_tag_add)
    t_rm = t_sub.add_parser("remove", help="Quita un tag de un track")
    t_rm.add_argument("track_id", type=int)
    t_rm.add_argument("tag_name")
    t_rm.set_defaults(func=cmd_tag_remove)
    t_ls = t_sub.add_parser("list", help="Lista tags disponibles")
    t_ls.set_defaults(func=cmd_tag_list)
    t_show = t_sub.add_parser("show", help="Muestra tags de un track")
    t_show.add_argument("track_id", type=int)
    t_show.set_defaults(func=cmd_tag_show)
    t_delete = t_sub.add_parser("delete", help="Elimina un tag completamente")
    t_delete.add_argument("tag_name", help="Nombre del tag a eliminar")
    t_delete.set_defaults(func=cmd_tag_delete)
    t.set_defaults(func=cmd_tag_list)

    pl = sub.add_parser("playlist", help="Gestiona playlists personales")
    pl_sub = pl.add_subparsers()
    pl_create = pl_sub.add_parser("create", help="Crea una playlist nueva")
    pl_create.add_argument("name", help="Nombre de la playlist")
    pl_create.set_defaults(func=cmd_playlist_create)
    pl_delete = pl_sub.add_parser("delete", help="Elimina una playlist")
    pl_delete.add_argument("name", help="Nombre de la playlist")
    pl_delete.set_defaults(func=cmd_playlist_delete)
    pl_rename = pl_sub.add_parser("rename", help="Renombra una playlist")
    pl_rename.add_argument("old_name", help="Nombre actual")
    pl_rename.add_argument("new_name", help="Nuevo nombre")
    pl_rename.set_defaults(func=cmd_playlist_rename)
    pl_list = pl_sub.add_parser("list", help="Lista todas las playlists")
    pl_list.set_defaults(func=cmd_playlist_list)
    pl_add = pl_sub.add_parser("add", help="Agrega tracks a una playlist")
    pl_add.add_argument("name", help="Nombre de la playlist")
    pl_add.add_argument("ids", nargs="+", type=int, help="IDs de canciones")
    pl_add.set_defaults(func=cmd_playlist_add)
    pl_rm = pl_sub.add_parser("remove", help="Quita tracks de una playlist")
    pl_rm.add_argument("name", help="Nombre de la playlist")
    pl_rm.add_argument("ids", nargs="+", type=int, help="IDs de canciones")
    pl_rm.set_defaults(func=cmd_playlist_remove)
    pl_show = pl_sub.add_parser("show", help="Muestra tracks de una playlist")
    pl_show.add_argument("name", help="Nombre de la playlist")
    pl_show.set_defaults(func=cmd_playlist_show)
    pl.set_defaults(func=cmd_playlist_list)

    export = sub.add_parser("export", help="Exporta una playlist a archivo m3u")
    export.add_argument("output", help="Archivo de salida")
    export.add_argument("--channel", help="Canal opcional")
    export.add_argument("--favorites", action="store_true")
    export.add_argument("--tag", help="Tag opcional")
    export.add_argument("--limit", type=int, default=500)
    export.set_defaults(func=cmd_export)

    import_cmd = sub.add_parser("import", help="Importa una playlist m3u")
    import_cmd.add_argument("input_file", help="Archivo m3u de entrada")
    import_cmd.set_defaults(func=cmd_import)

    share = sub.add_parser("share", help="Muestra link de Telegram para un track")
    share.add_argument("id", type=int)
    share.set_defaults(func=cmd_share)

    lyrics_cmd = sub.add_parser("lyrics", help="Muestra letras de una cancion")
    lyrics_cmd.add_argument("id", type=int)
    lyrics_cmd.set_defaults(func=cmd_lyrics)

    vol = sub.add_parser("volume", help="Muestra o ajusta el volumen")
    vol.add_argument("level", nargs="?", type=int, help="Volumen 0-150")
    vol.set_defaults(func=cmd_volume)

    settings_cmd = sub.add_parser("settings", help="Muestra o ajusta configuracion")
    settings_sub = settings_cmd.add_subparsers()
    settings_show = settings_sub.add_parser("show", help="Muestra la configuracion actual")
    settings_show.set_defaults(func=cmd_settings)
    settings_set = settings_sub.add_parser("set", help="Ajusta un valor de configuracion")
    settings_set.add_argument("key", choices=["volume", "crossfade", "theme"], help="Clave a ajustar")
    settings_set.add_argument("value", help="Nuevo valor (para theme: dark, light, dracula, nord, etc.)")
    settings_set.set_defaults(func=cmd_settings_set)
    settings_cmd.set_defaults(func=cmd_settings)

    play_folder = sub.add_parser("play-folder", help="Reproduce musica de una carpeta local")
    play_folder.add_argument("folder", help="Ruta a la carpeta de musica")
    play_folder.add_argument("--shuffle", action="store_true", help="Modo aleatorio")
    play_folder.add_argument("--recursive", action="store_true", help="Escaneo recursivo")
    play_folder.add_argument("--volume", type=int, help="Volumen (0-150)")
    play_folder.set_defaults(func=cmd_play_folder)

    tui = sub.add_parser("tui", help="Abre la interfaz de terminal")
    tui.set_defaults(func=cmd_tui)

    return parser


def cmd_init(_args: argparse.Namespace) -> int:
    show_welcome()
    api_id = input("api_id: ").strip()
    api_hash = getpass.getpass("api_hash: ").strip()
    if not api_id.isdigit():
        raise RuntimeError("api_id debe ser numerico.")
    if not re.fullmatch(r"[0-9a-fA-F]{32}", api_hash):
        raise RuntimeError(
            "api_hash invalido. Debe ser una cadena hexadecimal de 32 caracteres, "
            "no el token del bot ni el app short name."
        )
    save_config(api_id, api_hash)
    print(f"\nConfig guardada en {CONFIG_FILE}")
    print("Siguiente paso: tg-music scan https://t.me/Christian_Electronic --limit 300")
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    channel = normalize_channel(args.channel)
    count = asyncio.run(scan_channel(channel, args.limit))
    print(f"Indexados {count} audios desde {channel}")
    if args.cache:
        return cache_tracks(channel=channel, limit=args.limit, workers=1)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    with connect() as conn:
        tracks = list_tracks(
            conn,
            limit=args.limit,
            favorites_only=getattr(args, "favorites", False),
            tag=getattr(args, "tag", None),
        )
    if getattr(args, "json", False):
        print(json.dumps([_track_to_dict(t) for t in tracks], ensure_ascii=False, indent=2))
    else:
        print_tracks(tracks)
    return 0


def cmd_channels(_args: argparse.Namespace) -> int:
    with connect() as conn:
        channels = list_channels(conn)
    if not channels:
        print("No hay canales agregados. Usa: tg-music add-channel <url>")
        return 0
    for channel in channels:
        title = channel.title or channel.channel
        scanned = channel.last_scan_at or "sin escaneo"
        print(f"{channel.channel:32s} | {title} | {scanned}")
    return 0


def cmd_remove_channel(args: argparse.Namespace) -> int:
    with connect() as conn:
        removed = remove_channel(conn, args.channel)
    if removed:
        print(f"Canal '{args.channel}' eliminado.")
    else:
        print(f"No se encontro el canal '{args.channel}'.", file=sys.stderr)
        return 1
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    with connect() as conn:
        tracks = list_tracks(conn, limit=args.limit, query=args.query)
    if getattr(args, "json", False):
        print(json.dumps([_track_to_dict(t) for t in tracks], ensure_ascii=False, indent=2))
    else:
        print_tracks(tracks)
    return 0


def cmd_play(args: argparse.Namespace) -> int:
    settings = load_settings()
    with connect() as conn:
        track = get_track(conn, args.id)
    if track is None:
        raise RuntimeError(f"No existe track con id {args.id}")
    if track.ignored:
        raise RuntimeError("Esta cancion esta ignorada. Usa tg-music unignore ID para restaurarla.")
    path = asyncio.run(download_track(track, progress=print_download_progress))
    print()
    with connect() as conn:
        record_play(conn, track.id)
    play_file(path, volume=settings.volume)
    return 0


def cmd_play_latest(args: argparse.Namespace) -> int:
    settings = load_settings()
    channel = normalize_channel(args.channel)
    with connect() as conn:
        track = latest_for_channel(conn, channel)
    if track is None:
        print("No hay audios indexados para ese canal. Escaneando primero...")
        asyncio.run(scan_channel(channel, 100))
        with connect() as conn:
            track = latest_for_channel(conn, channel)
    if track is None:
        raise RuntimeError("No encontre audios en ese canal.")
    path = asyncio.run(download_track(track, progress=print_download_progress))
    print()
    with connect() as conn:
        record_play(conn, track.id)
    play_file(path, volume=settings.volume)
    return 0


def cmd_play_folder(args: argparse.Namespace) -> int:
    from .local import scan_folder

    settings = load_settings()
    volume = args.volume if args.volume is not None else settings.volume
    try:
        tracks = scan_folder(args.folder, recursive=args.recursive)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 1
    if not tracks:
        print("No se encontraron archivos de audio en esa carpeta.")
        return 0
    print(f"Encontrados {len(tracks)} archivos de audio")
    import random as rng

    if args.shuffle:
        rng.shuffle(tracks)
    for track in tracks:
        print(f"  Reproduciendo: {track.display_title}")
        play_file(track.local_path, volume=volume)
    return 0


def cmd_random(args: argparse.Namespace) -> int:
    settings = load_settings()
    with connect() as conn:
        tracks = list_random_tracks(conn, limit=args.limit)
    if not tracks:
        print("No hay canciones en la biblioteca.")
        return 0
    for track in tracks:
        print(f"Reproduciendo: {track.display_title}")
        path = asyncio.run(download_track(track, progress=print_download_progress))
        print()
        with connect() as conn:
            record_play(conn, track.id)
        play_file(path, volume=settings.volume)
    return 0


def cmd_cache(args: argparse.Namespace) -> int:
    channel = normalize_channel(args.channel) if args.channel else None
    return cache_tracks(channel=channel, limit=args.limit, workers=args.workers)


def cmd_watch(args: argparse.Namespace) -> int:
    channels = [normalize_channel(channel) for channel in args.channel] if args.channel else None
    interval = max(30, args.interval)
    seen: dict[str, int | None] = {}

    while True:
        with connect() as conn:
            if channels is None:
                watched_channels = [channel.channel for channel in list_channels(conn)]
            else:
                watched_channels = channels

            if not watched_channels:
                print("No hay canales para vigilar.")
                return 0

            for channel in watched_channels:
                latest_known = seen.get(channel)
                if latest_known is None:
                    latest_known = latest_message_id_for_channel(conn, channel)
                    seen[channel] = latest_known
                if latest_known is None:
                    continue

                new_count, newest_title = asyncio.run(
                    scan_new_uploads(channel, latest_known)
                )
                if new_count:
                    seen[channel] = latest_message_id_for_channel(conn, channel)
                    message = f"{channel}: {new_count} cancion(es) nueva(s)"
                    if newest_title:
                        message += f" | {newest_title}"
                    notify_user("TG Music", message)
                    print(message)
                    if newest_title:
                        print(f"  Ultima: {newest_title}")

        if args.once:
            return 0
        time.sleep(interval)


async def scan_new_uploads(channel: str, since_message_id: int | None) -> tuple[int, str | None]:
    new_count = await scan_channel_since(channel, since_message_id, limit=50)
    newest_title = None
    if new_count:
        with connect() as conn:
            latest = latest_message_id_for_channel(conn, normalize_channel(channel))
            if latest is not None:
                track = get_track(conn, latest)
                newest_title = track.display_title if track else None
    return new_count, newest_title


def cmd_ignore(args: argparse.Namespace) -> int:
    changed = 0
    with connect() as conn:
        for track_id in args.ids:
            track = get_track(conn, track_id)
            if track is None:
                print(f"No existe track con id {track_id}", file=sys.stderr)
                continue
            delete_cached_files(track)
            set_ignored(conn, track_id, True)
            print(f"Ignorada: {track.display_title}")
            changed += 1
    print(f"Total ignoradas: {changed}")
    return 0


def cmd_unignore(args: argparse.Namespace) -> int:
    changed = 0
    with connect() as conn:
        for track_id in args.ids:
            track = get_track(conn, track_id)
            if track is None:
                print(f"No existe track con id {track_id}", file=sys.stderr)
                continue
            set_ignored(conn, track_id, False)
            print(f"Restaurada: {track.display_title}")
            changed += 1
    print(f"Total restauradas: {changed}")
    return 0


def cmd_ignored(args: argparse.Namespace) -> int:
    with connect() as conn:
        tracks = list_ignored_tracks(conn, limit=args.limit)
    print_tracks(tracks, show_ignored=True, empty_message="No hay canciones ignoradas.")
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    from .config import AUDIO_CACHE_DIR, CONFIG_FILE, DB_FILE

    with connect() as conn:
        channels = list_channels(conn)
        all_tracks = list_tracks(conn, limit=999999, include_ignored=True)
        uncached = list_uncached_tracks(conn, limit=999999)
        favs = list_tracks(conn, limit=999999, favorites_only=True)
        tags = list_all_tags(conn)

    cached_count = len(all_tracks) - len(uncached)
    ignored_count = sum(1 for t in all_tracks if t.ignored)

    db_size = format_bytes(DB_FILE.stat().st_size) if DB_FILE.exists() else "0 B"
    cache_size_bytes = sum(f.stat().st_size for f in AUDIO_CACHE_DIR.rglob("*") if f.is_file())
    cache_size = format_bytes(cache_size_bytes)

    print(f"Canales:        {len(channels)}")
    print(f"Tracks total:   {len(all_tracks)}")
    print(f"Cached:         {cached_count}")
    print(f"Sin cache:      {len(uncached)}")
    print(f"Ignorados:      {ignored_count}")
    print(f"Favoritos:      {len(favs)}")
    print(f"Tags:           {len(tags)}")
    print(f"DB size:        {db_size}")
    print(f"Cache size:     {cache_size}")
    print(f"Config:         {CONFIG_FILE}")
    print(f"DB file:        {DB_FILE}")
    return 0


def cmd_cleanup(args: argparse.Namespace) -> int:
    removed = cleanup_stale_cache(max_age_days=args.max_age)
    print(f"Eliminados {removed} archivos antiguos (>{args.max_age} dias)")
    return 0


def cmd_favorite(args: argparse.Namespace) -> int:
    with connect() as conn:
        for track_id in args.ids:
            track = get_track(conn, track_id)
            if track is None:
                print(f"No existe track con id {track_id}", file=sys.stderr)
                continue
            is_now_fav = toggle_favorite(conn, track_id)
            state = "favorito" if is_now_fav else "removido de favoritos"
            print(f"{track.display_title}: {state}")
    return 0


def cmd_recent(args: argparse.Namespace) -> int:
    with connect() as conn:
        tracks = list_recently_played(conn, limit=args.limit)
    if getattr(args, "json", False):
        print(json.dumps([_track_to_dict(t) for t in tracks], ensure_ascii=False, indent=2))
    else:
        if not tracks:
            print("No hay canciones reproducidas recientemente.")
            return 0
        for track in tracks:
            print(
                f"{track.id:4d} {format_duration(track.duration):>6} "
                f"plays:{track.play_count:3d} {track.display_title}"
            )
    return 0


def cmd_top(args: argparse.Namespace) -> int:
    with connect() as conn:
        tracks = list_top_played(conn, limit=args.limit)
    if getattr(args, "json", False):
        print(json.dumps([_track_to_dict(t) for t in tracks], ensure_ascii=False, indent=2))
    else:
        if not tracks:
            print("No hay canciones reproducidas aun.")
            return 0
        for rank, track in enumerate(tracks, 1):
            print(
                f"{rank:3d}. {track.id:4d} {format_duration(track.duration):>6} "
                f"plays:{track.play_count:3d} {track.display_title}"
            )
    return 0


def cmd_tag_add(args: argparse.Namespace) -> int:
    with connect() as conn:
        track = get_track(conn, args.track_id)
        if track is None:
            print(f"No existe track con id {args.track_id}", file=sys.stderr)
            return 1
        tag_track(conn, args.track_id, args.tag_name)
        print(f"Tag '{args.tag_name}' agregado a: {track.display_title}")
    return 0


def cmd_tag_remove(args: argparse.Namespace) -> int:
    with connect() as conn:
        track = get_track(conn, args.track_id)
        if track is None:
            print(f"No existe track con id {args.track_id}", file=sys.stderr)
            return 1
        untag_track(conn, args.track_id, args.tag_name)
        print(f"Tag '{args.tag_name}' removido de: {track.display_title}")
    return 0


def cmd_tag_list(_args: argparse.Namespace) -> int:
    with connect() as conn:
        tags = list_all_tags(conn)
    if not tags:
        print("No hay tags creados.")
        return 0
    print("Tags:", ", ".join(tags))
    return 0


def cmd_tag_show(args: argparse.Namespace) -> int:
    with connect() as conn:
        track = get_track(conn, args.track_id)
        if track is None:
            print(f"No existe track con id {args.track_id}", file=sys.stderr)
            return 1
        tags = get_track_tags(conn, args.track_id)
    print(f"{track.display_title}: {', '.join(tags) if tags else '(sin tags)'}")
    return 0


def cmd_tag_delete(args: argparse.Namespace) -> int:
    with connect() as conn:
        remove_tag(conn, args.tag_name)
    print(f"Tag '{args.tag_name}' eliminado.")
    return 0


def cmd_playlist_create(args: argparse.Namespace) -> int:
    with connect() as conn:
        pl_id = create_playlist(conn, args.name)
    print(f"Playlist '{args.name}' creada (id: {pl_id})")
    return 0


def cmd_playlist_delete(args: argparse.Namespace) -> int:
    with connect() as conn:
        pl = get_playlist_by_name(conn, args.name)
        if pl is None:
            print(f"No existe playlist '{args.name}'", file=sys.stderr)
            return 1
        delete_playlist(conn, pl["id"])
    print(f"Playlist '{args.name}' eliminada")
    return 0


def cmd_playlist_rename(args: argparse.Namespace) -> int:
    with connect() as conn:
        pl = get_playlist_by_name(conn, args.old_name)
        if pl is None:
            print(f"No existe playlist '{args.old_name}'", file=sys.stderr)
            return 1
        rename_playlist(conn, pl["id"], args.new_name)
    print(f"Playlist '{args.old_name}' -> '{args.new_name}'")
    return 0


def cmd_playlist_list(_args: argparse.Namespace) -> int:
    with connect() as conn:
        playlists = list_playlists(conn)
    if not playlists:
        print("No hay playlists creadas.")
        return 0
    print(f"{'ID':>4}  {'Tracks':>5}  Nombre")
    for pl in playlists:
        print(f"{pl['id']:4d}  {pl['count']:5d}  {pl['name']}")
    return 0


def cmd_playlist_add(args: argparse.Namespace) -> int:
    with connect() as conn:
        pl = get_playlist_by_name(conn, args.name)
        if pl is None:
            print(f"No existe playlist '{args.name}'", file=sys.stderr)
            return 1
        added = 0
        for track_id in args.ids:
            track = get_track(conn, track_id)
            if track is None:
                print(f"Track {track_id} no existe, saltando", file=sys.stderr)
                continue
            add_to_playlist(conn, pl["id"], track_id)
            added += 1
            print(f"  + {track.display_title}")
    print(f"Agregados: {added}")
    return 0


def cmd_playlist_remove(args: argparse.Namespace) -> int:
    with connect() as conn:
        pl = get_playlist_by_name(conn, args.name)
        if pl is None:
            print(f"No existe playlist '{args.name}'", file=sys.stderr)
            return 1
        removed = 0
        for track_id in args.ids:
            track = get_track(conn, track_id)
            if track is None:
                print(f"Track {track_id} no existe, saltando", file=sys.stderr)
                continue
            remove_from_playlist(conn, pl["id"], track_id)
            removed += 1
            print(f"  - {track.display_title}")
    print(f"Removidos: {removed}")
    return 0


def cmd_playlist_show(args: argparse.Namespace) -> int:
    with connect() as conn:
        pl = get_playlist_by_name(conn, args.name)
        if pl is None:
            print(f"No existe playlist '{args.name}'", file=sys.stderr)
            return 1
        tracks = get_playlist_tracks(conn, pl["id"])
    if not tracks:
        print(f"Playlist '{args.name}' vacia.")
        return 0
    print(f"Playlist: {args.name} ({len(tracks)} tracks)")
    for i, track in enumerate(tracks, 1):
        print(f"  {i:3d}. {track.id:4d}  {format_duration(track.duration):>5}  {track.display_title}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    with connect() as conn:
        tracks = list_tracks(
            conn,
            limit=args.limit,
            channel=normalize_channel(args.channel) if args.channel else None,
            favorites_only=getattr(args, "favorites", False),
            tag=getattr(args, "tag", None),
        )
    if not tracks:
        print("No hay canciones para exportar.")
        return 0

    output = Path(args.output)
    with output.open("w", encoding="utf-8") as fh:
        fh.write("#EXTM3U\n")
        for track in tracks:
            duration = track.duration or -1
            fh.write(f"#EXTINF:{duration},{track.display_title}\n")
            if track.local_path:
                fh.write(f"{track.local_path}\n")
            else:
                fh.write(f"{track.telegram_url}\n")
    print(f"Playlist exportada: {len(tracks)} canciones -> {output}")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    input_file = Path(args.input_file)
    if not input_file.exists():
        print(f"Archivo no encontrado: {input_file}", file=sys.stderr)
        return 1

    lines = input_file.read_text(encoding="utf-8").splitlines()
    imported = 0
    with connect() as conn:
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            path = Path(line)
            if path.exists():
                item = {
                    "channel": "imported",
                    "channel_title": "Imported",
                    "message_id": imported + 1,
                    "title": path.stem,
                    "performer": "",
                    "duration": None,
                    "mime_type": "",
                    "filename": path.name,
                    "size": path.stat().st_size if path.exists() else None,
                    "date": "",
                    "local_path": str(path),
                }
                from .db import upsert_tracks_batch
                upsert_tracks_batch(conn, [item])
                imported += 1
    print(f"Importadas {imported} canciones desde {input_file}")
    return 0


def cmd_share(args: argparse.Namespace) -> int:
    with connect() as conn:
        track = get_track(conn, args.id)
    if track is None:
        print(f"No existe track con id {args.id}", file=sys.stderr)
        return 1
    print(track.telegram_url)
    return 0


def cmd_lyrics(args: argparse.Namespace) -> int:
    with connect() as conn:
        track = get_track(conn, args.id)
    if track is None:
        print(f"No existe track con id {args.id}", file=sys.stderr)
        return 1
    print(f"Buscando letras: {track.display_title}...")
    result = fetch_lyrics(
        track.performer or track.channel_title,
        track.title or track.filename,
        track.duration,
    )
    if result is None:
        print("No se encontraron letras para esta cancion.")
        return 1
    if result.synced:
        print(result.synced)
    elif result.plain:
        print(result.plain)
    else:
        print("Letras no disponibles (solo metadata encontrada).")
        print(f"  Album: {result.album or '?'}")
    return 0


def cmd_volume(args: argparse.Namespace) -> int:
    settings = load_settings()
    if args.level is not None:
        settings.volume = max(0, min(150, args.level))
        save_settings(settings)
        print(f"Volumen ajustado a {settings.volume}")
    else:
        print(f"Volumen actual: {settings.volume}")
    return 0


def cmd_settings(_args: argparse.Namespace) -> int:
    settings = load_settings()
    print(f"Volume:     {settings.volume}")
    print(f"Crossfade:  {settings.crossfade}s")
    print(f"Theme:      {settings.theme}")
    print(f"Config:     {CONFIG_FILE}")
    return 0


def cmd_settings_set(args: argparse.Namespace) -> int:
    settings = load_settings()
    key = args.key
    value = args.value
    if key == "volume":
        try:
            settings.volume = max(0, min(150, int(value)))
        except ValueError:
            print("Volumen debe ser un numero entero.", file=sys.stderr)
            return 1
    elif key == "crossfade":
        try:
            settings.crossfade = max(0, float(value))
        except ValueError:
            print("Crossfade debe ser un numero.", file=sys.stderr)
            return 1
    elif key == "theme":
        if value not in THEME_ORDER:
            print(f"Theme invalido. Opciones: {', '.join(THEME_ORDER)}", file=sys.stderr)
            return 1
        settings.theme = value
    save_settings(settings)
    print(f"{key} ajustado a {getattr(settings, key)}")
    return 0


def cmd_tui(_args: argparse.Namespace) -> int:
    run_tui()
    return 0


def _track_to_dict(track) -> dict:
    return {
        "id": track.id,
        "channel": track.channel,
        "channel_title": track.channel_title,
        "message_id": track.message_id,
        "title": track.title,
        "performer": track.performer,
        "duration": track.duration,
        "mime_type": track.mime_type,
        "filename": track.filename,
        "size": track.size,
        "date": track.date,
        "local_path": track.local_path,
        "ignored": track.ignored,
        "display_title": track.display_title,
        "play_count": track.play_count,
        "last_played_at": track.last_played_at,
        "telegram_url": track.telegram_url,
    }


def cache_tracks(channel: str | None, limit: int, workers: int = 1) -> int:
    with connect() as conn:
        tracks = list_uncached_tracks(conn, limit=limit, channel=channel)
    if not tracks:
        print("No hay canciones pendientes de cache.")
        return 0

    workers = max(1, min(workers, 3))
    print(f"Descargando {len(tracks)} canciones al cache con {workers} worker(s)...")

    current_title = ""

    def progress_factory(track):
        nonlocal current_title
        if workers != 1:
            return None
        current_title = track.display_title
        print(f"\n{current_title}")
        return print_download_progress

    def result_callback(result: CacheResult, completed: int, total: int) -> None:
        if workers == 1:
            print()
        prefix = "OK" if result.error is None else "Error"
        detail = str(result.path) if result.path else str(result.error)
        stream = sys.stdout if result.error is None else sys.stderr
        print(f"[{completed}/{total}] {prefix}: {result.track.display_title} | {detail}", file=stream)

    results = asyncio.run(
        cache_tracks_async(
            tracks,
            workers=workers,
            progress_factory=progress_factory,
            result_callback=result_callback,
        )
    )
    downloaded = sum(1 for result in results if result.error is None)
    failed = len(results) - downloaded

    print(f"\nCache terminado: {downloaded} OK, {failed} errores.")
    return 1 if failed else 0


def print_tracks(
    tracks: list,
    show_ignored: bool = False,
    empty_message: str = "No hay canciones indexadas. Ejecuta tg-music scan <canal>.",
) -> None:
    if not tracks:
        print(empty_message)
        return
    with connect() as conn:
        fav_ids = get_all_favorite_ids(conn)
    for track in tracks:
        cached = "*" if track.local_path else " "
        ignored = "x" if show_ignored and track.ignored else " "
        fav = "♥" if track.id in fav_ids else " "
        print(
            f"{track.id:4d}{cached}{ignored} {format_duration(track.duration):>6} "
            f"{track.channel_title} | {track.display_title}"
        )


def print_download_progress(downloaded: int, total: int) -> None:
    if total:
        percent = downloaded / total * 100
        text = f"\rCache: {percent:6.2f}%  {format_bytes(downloaded)} / {format_bytes(total)}"
    else:
        text = f"\rCache: {format_bytes(downloaded)}"
    print(text, end="", flush=True)
