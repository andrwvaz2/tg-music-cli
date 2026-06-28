_tg_music_completions() {
    local cur prev commands
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    commands="init scan add-channel channels list search play play-latest random cache watch ignore unignore ignored status cleanup favorite recent top tag export import share lyrics volume settings tui"

    if [ "$COMP_CWORD" -eq 1 ]; then
        COMPREPLY=( $(compgen -W "$commands" -- "$cur") )
        return 0
    fi

    case "${prev}" in
        scan|add-channel|cache|play-latest)
            COMPREPLY=( $(compgen -f -- "$cur") )
            return 0
            ;;
        play|ignore|unignore|favorite|tag|share|lyrics)
            local ids=$(sqlite3 ~/.local/share/tg-music/library.sqlite3 "SELECT id FROM tracks ORDER BY id" 2>/dev/null)
            COMPREPLY=( $(compgen -W "$ids" -- "$cur") )
            return 0
            ;;
        tag)
            COMPREPLY=( $(compgen -W "add remove list show" -- "$cur") )
            return 0
            ;;
        export)
            COMPREPLY=( $(compgen -f -- "$cur") )
            return 0
            ;;
        import)
            COMPREPLY=( $(compgen -f -- "$cur") )
            return 0
            ;;
        volume)
            COMPREPLY=( $(compgen -W "0 25 50 75 100 125 150" -- "$cur") )
            return 0
            ;;
    esac

    if [[ "$cur" == --* ]]; then
        COMPREPLY=( $(compgen -W "--limit --json --cache --workers --channel --once --interval --favorites --tag --max-age --volume" -- "$cur") )
        return 0
    fi
}

complete -F _tg_music_completions tg-music
complete -F _tg_music_completions tgmusic-cli
