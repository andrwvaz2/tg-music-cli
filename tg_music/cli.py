from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import re
import sys
import time
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
    raw_args = sys.argv[1:] if argv is None else argv
    if not raw_args:
        raw_args = ["tui"]
    elif raw_args[0] == "help":
        raw_args = ["--help"] if len(raw_args) == 1 else [*raw_args[1:], "--help"]
    args = parser.parse_args(raw_args)

    try:
        ensure_dirs()
        return args.func(args)
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tg-music")
    sub = parser.add_subparsers()

    init = sub.add_parser("init", help="Configure Telegram api_id and api_hash")
    init.set_defaults(func=cmd_init)

    scan = sub.add_parser("scan", help="Scan audio from a channel")
    scan.add_argument("channel", help="Channel URL, @username, or username")
    scan.add_argument("--limit", type=int, default=300, help="Messages to scan")
    scan.add_argument(
        "--cache",
        action="store_true",
        help="Download newly found missing audio to cache",
    )
    scan.set_defaults(func=cmd_scan)

    add_channel = sub.add_parser("add-channel", help="Add/scan a music channel")
    add_channel.add_argument("channel", help="Channel URL, @username, or username")
    add_channel.add_argument("--limit", type=int, default=300, help="Messages to scan")
    add_channel.add_argument("--cache", action="store_true", help="Download found tracks to cache")
    add_channel.set_defaults(func=cmd_scan)

    channels = sub.add_parser("channels", help="List added channels")
    channels.set_defaults(func=cmd_channels)

    remove_channel_cmd = sub.add_parser("remove-channel", help="Remove a channel from the database")
    remove_channel_cmd.add_argument("channel", help="Username of the channel to remove")
    remove_channel_cmd.set_defaults(func=cmd_remove_channel)

    list_cmd = sub.add_parser("list", help="List indexed tracks")
    list_cmd.add_argument("--limit", type=int, default=50)
    list_cmd.add_argument("--json", action="store_true", help="Output JSON")
    list_cmd.add_argument("--favorites", action="store_true", help="Favorites only")
    list_cmd.add_argument("--tag", type=str, help="Filter by tag")
    list_cmd.set_defaults(func=cmd_list)

    search = sub.add_parser("search", help="Search indexed tracks")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=50)
    search.add_argument("--json", action="store_true", help="Output JSON")
    search.set_defaults(func=cmd_search)

    play = sub.add_parser("play", help="Download if needed and play by id")
    play.add_argument("id", type=int)
    play.set_defaults(func=cmd_play)

    latest = sub.add_parser("play-latest", help="Play the latest audio from an indexed channel")
    latest.add_argument("channel")
    latest.set_defaults(func=cmd_play_latest)

    random_play = sub.add_parser("random", help="Play a random track")
    random_play.add_argument("--limit", type=int, default=1, help="Number of tracks")
    random_play.set_defaults(func=cmd_random)

    cache = sub.add_parser("cache", help="Download indexed tracks to cache")
    cache.add_argument("channel", nargs="?", help="Optional channel to limit downloads")
    cache.add_argument("--limit", type=int, default=50, help="Maximum tracks to download")
    cache.add_argument("--workers", type=int, default=1, help="Parallel downloads, recommended max 3")
    cache.set_defaults(func=cmd_cache)

    watch = sub.add_parser(
        "watch",
        help="Watch indexed channels and notify when new music appears",
    )
    watch.add_argument("channel", nargs="*", help="Optional channels; watches all if omitted")
    watch.add_argument("--interval", type=int, default=300, help="Seconds between checks")
    watch.add_argument("--once", action="store_true", help="Check once and exit")
    watch.set_defaults(func=cmd_watch)

    ignore = sub.add_parser("ignore", help="Ignore tracks and delete their local cache")
    ignore.add_argument("ids", nargs="+", type=int, help="Track IDs to ignore")
    ignore.set_defaults(func=cmd_ignore)

    unignore = sub.add_parser("unignore", help="Remove tracks from the ignored list")
    unignore.add_argument("ids", nargs="+", type=int, help="Track IDs to restore")
    unignore.set_defaults(func=cmd_unignore)

    ignored = sub.add_parser("ignored", help="List ignored tracks")
    ignored.add_argument("--limit", type=int, default=50)
    ignored.set_defaults(func=cmd_ignored)

    status = sub.add_parser("status", help="Show library summary")
    status.set_defaults(func=cmd_status)

    cleanup = sub.add_parser("cleanup", help="Clean old cached files")
    cleanup.add_argument("--max-age", type=int, default=30, help="Maximum age in days")
    cleanup.set_defaults(func=cmd_cleanup)

    fav = sub.add_parser("favorite", help="Toggle tracks as favorites")
    fav.add_argument("ids", nargs="+", type=int, help="Track IDs")
    fav.set_defaults(func=cmd_favorite)

    recent = sub.add_parser("recent", help="Show recently played tracks")
    recent.add_argument("--limit", type=int, default=20)
    recent.add_argument("--json", action="store_true")
    recent.set_defaults(func=cmd_recent)

    top = sub.add_parser("top", help="Show most played tracks")
    top.add_argument("--limit", type=int, default=20)
    top.add_argument("--json", action="store_true")
    top.set_defaults(func=cmd_top)

    t = sub.add_parser("tag", help="Manage track tags")
    t_sub = t.add_subparsers()
    t_add = t_sub.add_parser("add", help="Add a tag to a track")
    t_add.add_argument("track_id", type=int)
    t_add.add_argument("tag_name")
    t_add.set_defaults(func=cmd_tag_add)
    t_rm = t_sub.add_parser("remove", help="Remove a tag from a track")
    t_rm.add_argument("track_id", type=int)
    t_rm.add_argument("tag_name")
    t_rm.set_defaults(func=cmd_tag_remove)
    t_ls = t_sub.add_parser("list", help="List available tags")
    t_ls.set_defaults(func=cmd_tag_list)
    t_show = t_sub.add_parser("show", help="Show tags for a track")
    t_show.add_argument("track_id", type=int)
    t_show.set_defaults(func=cmd_tag_show)
    t_delete = t_sub.add_parser("delete", help="Delete a tag completely")
    t_delete.add_argument("tag_name", help="Tag name to delete")
    t_delete.set_defaults(func=cmd_tag_delete)
    t.set_defaults(func=cmd_tag_list)

    pl = sub.add_parser("playlist", help="Manage personal playlists")
    pl_sub = pl.add_subparsers()
    pl_create = pl_sub.add_parser("create", help="Create a new playlist")
    pl_create.add_argument("name", help="Playlist name")
    pl_create.set_defaults(func=cmd_playlist_create)
    pl_delete = pl_sub.add_parser("delete", help="Delete a playlist")
    pl_delete.add_argument("name", help="Playlist name")
    pl_delete.set_defaults(func=cmd_playlist_delete)
    pl_rename = pl_sub.add_parser("rename", help="Rename a playlist")
    pl_rename.add_argument("old_name", help="Current name")
    pl_rename.add_argument("new_name", help="New name")
    pl_rename.set_defaults(func=cmd_playlist_rename)
    pl_list = pl_sub.add_parser("list", help="List all playlists")
    pl_list.set_defaults(func=cmd_playlist_list)
    pl_add = pl_sub.add_parser("add", help="Add tracks to a playlist")
    pl_add.add_argument("name", help="Playlist name")
    pl_add.add_argument("ids", nargs="+", type=int, help="Track IDs")
    pl_add.set_defaults(func=cmd_playlist_add)
    pl_rm = pl_sub.add_parser("remove", help="Remove tracks from a playlist")
    pl_rm.add_argument("name", help="Playlist name")
    pl_rm.add_argument("ids", nargs="+", type=int, help="Track IDs")
    pl_rm.set_defaults(func=cmd_playlist_remove)
    pl_show = pl_sub.add_parser("show", help="Show playlist tracks")
    pl_show.add_argument("name", help="Playlist name")
    pl_show.set_defaults(func=cmd_playlist_show)
    pl.set_defaults(func=cmd_playlist_list)

    export = sub.add_parser("export", help="Export a playlist to an m3u file")
    export.add_argument("output", help="Output file")
    export.add_argument("--channel", help="Optional channel")
    export.add_argument("--favorites", action="store_true")
    export.add_argument("--tag", help="Optional tag")
    export.add_argument("--limit", type=int, default=500)
    export.set_defaults(func=cmd_export)

    import_cmd = sub.add_parser("import", help="Import an m3u playlist")
    import_cmd.add_argument("input_file", help="Input m3u file")
    import_cmd.set_defaults(func=cmd_import)

    share = sub.add_parser("share", help="Show Telegram link for a track")
    share.add_argument("id", type=int)
    share.set_defaults(func=cmd_share)

    lyrics_cmd = sub.add_parser("lyrics", help="Show lyrics for a track")
    lyrics_cmd.add_argument("id", type=int)
    lyrics_cmd.set_defaults(func=cmd_lyrics)

    vol = sub.add_parser("volume", help="Show or set volume")
    vol.add_argument("level", nargs="?", type=int, help="Volume 0-150")
    vol.set_defaults(func=cmd_volume)

    settings_cmd = sub.add_parser("settings", help="Show or change settings")
    settings_sub = settings_cmd.add_subparsers()
    settings_show = settings_sub.add_parser("show", help="Show current settings")
    settings_show.set_defaults(func=cmd_settings)
    settings_set = settings_sub.add_parser("set", help="Set a configuration value")
    settings_set.add_argument("key", choices=["volume", "crossfade", "theme"], help="Key to set")
    settings_set.add_argument("value", help="New value (for theme: dark, light, dracula, nord, etc.)")
    settings_set.set_defaults(func=cmd_settings_set)
    settings_cmd.set_defaults(func=cmd_settings)

    play_folder = sub.add_parser("play-folder", help="Play music from a local folder")
    play_folder.add_argument("folder", help="Path to music folder")
    play_folder.add_argument("--shuffle", action="store_true", help="Shuffle mode")
    play_folder.add_argument("--recursive", action="store_true", help="Recursive scan")
    play_folder.add_argument("--volume", type=int, help="Volume (0-150)")
    play_folder.set_defaults(func=cmd_play_folder)

    tui = sub.add_parser("tui", help="Open the terminal interface")
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
            "Invalid api_hash. It must be a 32-character hexadecimal string, no el token del bot ni el app short name."
        )
    save_config(api_id, api_hash)
    print(f"\nConfig saved to {CONFIG_FILE}")
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
        print("No channels added. Use: tg-music add-channel <url>")
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
        print(f"Channel '{args.channel}' removed.")
    else:
        print(f"Channel '{args.channel}' was not found.", file=sys.stderr)
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
        raise RuntimeError(f"Track with id {args.id} does not exist")
    if track.ignored:
        raise RuntimeError("This track is ignored. Use tg-music unignore ID to restore it.")
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
        print("No indexed audio for that channel. Scanning first...")
        asyncio.run(scan_channel(channel, 100))
        with connect() as conn:
            track = latest_for_channel(conn, channel)
    if track is None:
        raise RuntimeError("No audio found in that channel.")
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
    print(f"Found {len(tracks)} audio files")
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
        print("No tracks in the library.")
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
                print("No channels to watch.")
                return 0

            for channel in watched_channels:
                latest_known = seen.get(channel)
                if latest_known is None:
                    latest_known = latest_message_id_for_channel(conn, channel)
                    seen[channel] = latest_known
                if latest_known is None:
                    continue

                new_count, newest_title = asyncio.run(scan_new_uploads(channel, latest_known))
                if new_count:
                    seen[channel] = latest_message_id_for_channel(conn, channel)
                    message = f"{channel}: {new_count} new track(s)"
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
                print(f"Track with id {track_id} does not exist", file=sys.stderr)
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
                print(f"Track with id {track_id} does not exist", file=sys.stderr)
                continue
            set_ignored(conn, track_id, False)
            print(f"Restaurada: {track.display_title}")
            changed += 1
    print(f"Total restauradas: {changed}")
    return 0


def cmd_ignored(args: argparse.Namespace) -> int:
    with connect() as conn:
        tracks = list_ignored_tracks(conn, limit=args.limit)
    print_tracks(tracks, show_ignored=True, empty_message="No ignored tracks.")
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

    print(f"Channels:       {len(channels)}")
    print(f"Tracks total:   {len(all_tracks)}")
    print(f"Cached:         {cached_count}")
    print(f"Uncached:       {len(uncached)}")
    print(f"Ignored:        {ignored_count}")
    print(f"Favorites:      {len(favs)}")
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
                print(f"Track with id {track_id} does not exist", file=sys.stderr)
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
            print("No recently played tracks.")
            return 0
        for track in tracks:
            print(
                f"{track.id:4d} {format_duration(track.duration):>6} plays:{track.play_count:3d} {track.display_title}"
            )
    return 0


def cmd_top(args: argparse.Namespace) -> int:
    with connect() as conn:
        tracks = list_top_played(conn, limit=args.limit)
    if getattr(args, "json", False):
        print(json.dumps([_track_to_dict(t) for t in tracks], ensure_ascii=False, indent=2))
    else:
        if not tracks:
            print("No played tracks yet.")
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
            print(f"Track with id {args.track_id} does not exist", file=sys.stderr)
            return 1
        tag_track(conn, args.track_id, args.tag_name)
        print(f"Tag '{args.tag_name}' agregado a: {track.display_title}")
    return 0


def cmd_tag_remove(args: argparse.Namespace) -> int:
    with connect() as conn:
        track = get_track(conn, args.track_id)
        if track is None:
            print(f"Track with id {args.track_id} does not exist", file=sys.stderr)
            return 1
        untag_track(conn, args.track_id, args.tag_name)
        print(f"Tag '{args.tag_name}' removido de: {track.display_title}")
    return 0


def cmd_tag_list(_args: argparse.Namespace) -> int:
    with connect() as conn:
        tags = list_all_tags(conn)
    if not tags:
        print("No tags created.")
        return 0
    print("Tags:", ", ".join(tags))
    return 0


def cmd_tag_show(args: argparse.Namespace) -> int:
    with connect() as conn:
        track = get_track(conn, args.track_id)
        if track is None:
            print(f"Track with id {args.track_id} does not exist", file=sys.stderr)
            return 1
        tags = get_track_tags(conn, args.track_id)
    print(f"{track.display_title}: {', '.join(tags) if tags else '(sin tags)'}")
    return 0


def cmd_tag_delete(args: argparse.Namespace) -> int:
    with connect() as conn:
        remove_tag(conn, args.tag_name)
    print(f"Tag '{args.tag_name}' deleted.")
    return 0


def cmd_playlist_create(args: argparse.Namespace) -> int:
    with connect() as conn:
        pl_id = create_playlist(conn, args.name)
    print(f"Playlist '{args.name}' created (id: {pl_id})")
    return 0


def cmd_playlist_delete(args: argparse.Namespace) -> int:
    with connect() as conn:
        pl = get_playlist_by_name(conn, args.name)
        if pl is None:
            print(f"Playlist '{args.name}' does not exist", file=sys.stderr)
            return 1
        delete_playlist(conn, pl["id"])
    print(f"Playlist '{args.name}' deleted")
    return 0


def cmd_playlist_rename(args: argparse.Namespace) -> int:
    with connect() as conn:
        pl = get_playlist_by_name(conn, args.old_name)
        if pl is None:
            print(f"Playlist '{args.old_name}' does not exist", file=sys.stderr)
            return 1
        rename_playlist(conn, pl["id"], args.new_name)
    print(f"Playlist '{args.old_name}' -> '{args.new_name}'")
    return 0


def cmd_playlist_list(_args: argparse.Namespace) -> int:
    with connect() as conn:
        playlists = list_playlists(conn)
    if not playlists:
        print("No playlists created.")
        return 0
    print(f"{'ID':>4}  {'Tracks':>5}  Name")
    for pl in playlists:
        print(f"{pl['id']:4d}  {pl['count']:5d}  {pl['name']}")
    return 0


def cmd_playlist_add(args: argparse.Namespace) -> int:
    with connect() as conn:
        pl = get_playlist_by_name(conn, args.name)
        if pl is None:
            print(f"Playlist '{args.name}' does not exist", file=sys.stderr)
            return 1
        added = 0
        for track_id in args.ids:
            track = get_track(conn, track_id)
            if track is None:
                print(f"Track {track_id} does not exist, skipping", file=sys.stderr)
                continue
            add_to_playlist(conn, pl["id"], track_id)
            added += 1
            print(f"  + {track.display_title}")
    print(f"Added: {added}")
    return 0


def cmd_playlist_remove(args: argparse.Namespace) -> int:
    with connect() as conn:
        pl = get_playlist_by_name(conn, args.name)
        if pl is None:
            print(f"Playlist '{args.name}' does not exist", file=sys.stderr)
            return 1
        removed = 0
        for track_id in args.ids:
            track = get_track(conn, track_id)
            if track is None:
                print(f"Track {track_id} does not exist, skipping", file=sys.stderr)
                continue
            remove_from_playlist(conn, pl["id"], track_id)
            removed += 1
            print(f"  - {track.display_title}")
    print(f"Removed: {removed}")
    return 0


def cmd_playlist_show(args: argparse.Namespace) -> int:
    with connect() as conn:
        pl = get_playlist_by_name(conn, args.name)
        if pl is None:
            print(f"Playlist '{args.name}' does not exist", file=sys.stderr)
            return 1
        tracks = get_playlist_tracks(conn, pl["id"])
    if not tracks:
        print(f"Playlist '{args.name}' is empty.")
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
        print("No tracks to export.")
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
    print(f"Playlist exported: {len(tracks)} tracks -> {output}")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    input_file = Path(args.input_file)
    if not input_file.exists():
        print(f"File not found: {input_file}", file=sys.stderr)
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
    print(f"Imported {imported} tracks from {input_file}")
    return 0


def cmd_share(args: argparse.Namespace) -> int:
    with connect() as conn:
        track = get_track(conn, args.id)
    if track is None:
        print(f"Track with id {args.id} does not exist", file=sys.stderr)
        return 1
    print(track.telegram_url)
    return 0


def cmd_lyrics(args: argparse.Namespace) -> int:
    with connect() as conn:
        track = get_track(conn, args.id)
    if track is None:
        print(f"Track with id {args.id} does not exist", file=sys.stderr)
        return 1
    print(f"Searching lyrics: {track.display_title}...")
    result = fetch_lyrics(
        track.performer or track.channel_title,
        track.title or track.filename,
        track.duration,
    )
    if result is None:
        print("No lyrics found for this track.")
        return 1
    if result.synced:
        print(result.synced)
    elif result.plain:
        print(result.plain)
    else:
        print("Lyrics unavailable (metadata only).")
        print(f"  Album: {result.album or '?'}")
    return 0


def cmd_volume(args: argparse.Namespace) -> int:
    settings = load_settings()
    if args.level is not None:
        settings.volume = max(0, min(150, args.level))
        save_settings(settings)
        print(f"Volume set to {settings.volume}")
    else:
        print(f"Current volume: {settings.volume}")
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
            print("Volume must be an integer.", file=sys.stderr)
            return 1
    elif key == "crossfade":
        try:
            settings.crossfade = max(0, float(value))
        except ValueError:
            print("Crossfade must be a number.", file=sys.stderr)
            return 1
    elif key == "theme":
        if value not in THEME_ORDER:
            print(f"Invalid theme. Options: {', '.join(THEME_ORDER)}", file=sys.stderr)
            return 1
        settings.theme = value
    save_settings(settings)
    print(f"{key} set to {getattr(settings, key)}")
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
        print("No tracks pending cache.")
        return 0

    workers = max(1, min(workers, 3))
    print(f"Downloading {len(tracks)} tracks to cache with {workers} worker(s)...")

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

    print(f"\nCache complete: {downloaded} OK, {failed} errors.")
    return 1 if failed else 0


def print_tracks(
    tracks: list,
    show_ignored: bool = False,
    empty_message: str = "No indexed tracks. Run tg-music scan <channel>.",
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
            f"{track.id:4d}{cached}{ignored}{fav} {format_duration(track.duration):>6} "
            f"{track.channel_title} | {track.display_title}"
        )


def print_download_progress(downloaded: int, total: int) -> None:
    if total:
        percent = downloaded / total * 100
        text = f"\rCache: {percent:6.2f}%  {format_bytes(downloaded)} / {format_bytes(total)}"
    else:
        text = f"\rCache: {format_bytes(downloaded)}"
    print(text, end="", flush=True)
