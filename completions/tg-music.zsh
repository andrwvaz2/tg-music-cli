#compdef tg-music tgmusic-cli

_tg_music() {
    local -a commands
    commands=(
        'init:Configura api_id y api_hash de Telegram'
        'scan:Escanea audios de un canal'
        'add-channel:Agrega/escanea un canal de musica'
        'channels:Lista canales agregados'
        'list:Lista canciones indexadas'
        'search:Busca canciones indexadas'
        'play:Descarga si hace falta y reproduce por id'
        'play-latest:Reproduce el audio mas reciente'
        'random:Reproduce una cancion al azar'
        'cache:Descarga canciones al cache'
        'watch:Vigila canales indexados'
        'ignore:Ignora canciones'
        'unignore:Quita canciones de la lista ignorada'
        'ignored:Lista canciones ignoradas'
        'status:Muestra resumen de la biblioteca'
        'cleanup:Limpia archivos cacheados antiguos'
        'favorite:Marca/desmarca favorito'
        'recent:Canciones reproducidas recientemente'
        'top:Canciones mas reproducidas'
        'tag:Gestiona tags'
        'export:Exporta playlist a m3u'
        'import:Importa playlist m3u'
        'share:Muestra link de Telegram'
        'lyrics:Muestra letras'
        'volume:Ajusta volumen'
        'settings:Muestra/configura ajustes'
        'tui:Abre la interfaz de terminal'
    )

    _arguments -C \
        '1:command:->command' \
        '*::arg:->args'

    case "$state" in
        command)
            _describe 'command' commands
            ;;
        args)
            case "$words[1]" in
                scan|add-channel)
                    _arguments \
                        '1:channel:_urls' \
                        '--limit[Messages to check]:number' \
                        '--cache[Download found audio]'
                    ;;
                play)
                    _arguments '1:track id:_tg_music_tracks'
                    ;;
                list|search)
                    _arguments \
                        '1:query' \
                        '--limit[Max results]:number' \
                        '--json[JSON output]' \
                        '--favorites[Favorites only]' \
                        '--tag[Filter by tag]:tag name'
                    ;;
                cache)
                    _arguments \
                        '1:channel:_urls' \
                        '--limit[Max tracks]:number' \
                        '--workers[Parallel downloads]:number'
                    ;;
                ignore|unignore|favorite)
                    _arguments '*:track id:_tg_music_tracks'
                    ;;
                tag)
                    _arguments \
                        '1:subcommand:(add remove list show)' \
                        '2:track id:_tg_music_tracks' \
                        '3:tag name'
                    ;;
                volume)
                    _arguments '1:level:(0 25 50 75 100 125 150)'
                    ;;
                export)
                    _arguments \
                        '1:output file:_files' \
                        '--channel:channel' \
                        '--favorites[Favorites only]' \
                        '--tag:tag name' \
                        '--limit:number'
                    ;;
                import)
                    _arguments '1:input file:_files'
                    ;;
                share|lyrics)
                    _arguments '1:track id:_tg_music_tracks'
                    ;;
            esac
            ;;
    esac
}

_tg_music_tracks() {
    local -a tracks
    if [[ -f ~/.local/share/tg-music/library.sqlite3 ]]; then
        tracks=("${(@f)$(sqlite3 ~/.local/share/tg-music/library.sqlite3 'SELECT id || \" \" || title FROM tracks ORDER BY id' 2>/dev/null)}")
    fi
    _describe 'track' tracks
}

_tg_music "$@"
