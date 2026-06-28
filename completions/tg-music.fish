complete -c tg-music -f
complete -c tgmusic-cli -f

set -l commands init scan add-channel channels list search play play-latest random cache watch ignore unignore ignored status cleanup favorite recent top tag export import share lyrics volume settings tui

complete -c tg-music -n "__fish_use_subcommand" -a "$commands"
complete -c tgmusic-cli -n "__fish_use_subcommand" -a "$commands"

complete -c tg-music -n "__fish_seen_subcommand_from scan add-channel" -l limit -d "Messages to check"
complete -c tg-music -n "__fish_seen_subcommand_from scan add-channel" -l cache -d "Download found audio"

complete -c tg-music -n "__fish_seen_subcommand_from play" -a "(sqlite3 ~/.local/share/tg-music/library.sqlite3 'SELECT id FROM tracks ORDER BY id' 2>/dev/null)"

complete -c tg-music -n "__fish_seen_subcommand_from list search" -l limit
complete -c tg-music -n "__fish_seen_subcommand_from list search" -l json
complete -c tg-music -n "__fish_seen_subcommand_from list" -l favorites
complete -c tg-music -n "__fish_seen_subcommand_from list" -l tag

complete -c tg-music -n "__fish_seen_subcommand_from cache" -l limit
complete -c tg-music -n "__fish_seen_subcommand_from cache" -l workers

complete -c tg-music -n "__fish_seen_subcommand_from ignore unignore favorite" -a "(sqlite3 ~/.local/share/tg-music/library.sqlite3 'SELECT id FROM tracks ORDER BY id' 2>/dev/null)"

complete -c tg-music -n "__fish_seen_subcommand_from tag" -a "add remove list show"

complete -c tg-music -n "__fish_seen_subcommand_from volume" -a "0 25 50 75 100 125 150"

complete -c tg-music -n "__fish_seen_subcommand_from share lyrics" -a "(sqlite3 ~/.local/share/tg-music/library.sqlite3 'SELECT id FROM tracks ORDER BY id' 2>/dev/null)"

complete -c tg-music -n "__fish_seen_subcommand_from export" -l channel -l favorites -l tag -l limit
