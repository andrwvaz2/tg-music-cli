# tg-music-cli

Reproductor de musica de canales de Telegram desde terminal.

## Requisitos

- Python 3.11+
- `uv`
- `mpv`
- `chafa` opcional para ver portadas dentro de la TUI
- Una app de Telegram creada en `https://my.telegram.org` para obtener `api_id` y `api_hash`

## Uso rapido

```bash
cd ~/Proyectos/tg-music-cli
uv run tg-music init
uv run tg-music scan https://t.me/Christian_Electronic --limit 300
uv run tg-music tui
```

Si instalas el paquete, también puedes usar `tgmusic-cli` directamente en lugar de
`uv run tg-music`.

En el primer uso Telegram pedira tu numero, codigo y quizas password 2FA.
La sesion queda guardada localmente en `~/.local/share/tg-music/session.session`.

## Comandos

```bash
tg-music init
tg-music scan CHANNEL_OR_URL --limit 300
tg-music scan CHANNEL_OR_URL --limit 300 --cache
tg-music add-channel CHANNEL_OR_URL --limit 300
tg-music channels
tg-music list --limit 50
tg-music search "texto"
tg-music play 123
tg-music play-latest CHANNEL_OR_URL
tg-music cache CHANNEL_OR_URL --limit 50 --workers 2
tg-music watch --interval 300
tg-music ignore 123
tg-music unignore 123
tg-music ignored
tg-music tui
tg-music status
tg-music cleanup
tg-music favorite 123
tg-music recent
tg-music top
tg-music random
tg-music tag add 123 rock
tg-music tag remove 123 rock
tg-music tag list
tg-music tag show 123
tg-music export playlist.m3u --channel
tg-music import playlist.m3u
tg-music share 123
tg-music lyrics 123
tg-music volume 80
tg-music settings
tgmusic-cli
```

Los audios descargados se guardan en `~/.cache/tg-music/audio`.
La metadata se guarda en `~/.local/share/tg-music/library.sqlite3`.

Para descargar automaticamente al cache canciones ya indexadas:

```bash
tg-music cache https://t.me/Christian_Electronic --limit 50 --workers 2
```

Tambien puedes escanear y cachear en un solo paso:

```bash
tg-music scan https://t.me/Christian_Electronic --limit 300 --cache
```

## TUI

La TUI muestra la biblioteca indexada en SQLite. Esa lista queda guardada entre sesiones:
puedes cerrar el programa, volver a abrirlo con `tg-music tui` y seguir navegando.

El layout ahora va mas cerca de `musikcube`: barra superior de estado, navegador de carpetas
`channels` a la izquierda y panel de reproduccion a la derecha. Los canales funcionan como
carpetas: `Enter` abre, `Space` o flecha derecha expanden, `Backspace` o flecha izquierda
colapsan, y `c` regresa al navegador de carpetas. Si el audio trae portada embebida o thumbnail
de Telegram y tienes `chafa`
instalado, la portada se renderiza en ese panel. En Ghostty/Kitty se usa imagen real; en otros
terminales se usa arte de caracteres como fallback.

Al reproducir una cancion, la TUI empieza a cachear automaticamente hasta 3 canciones
siguientes en segundo plano.

- Flechas o `j`/`k`: moverse
- `Enter`: abrir carpeta o reproducir track
- `Space` o flecha derecha: expandir carpeta
- `Backspace`, `h` o flecha izquierda: colapsar o volver al navegador de carpetas
- `e`: poner el track seleccionado en la cola
- `m`: descargar las canciones faltantes del canal o biblioteca actual
- `w`: revisar si hay musica nueva en el canal activo
- `W`: activar o desactivar la vigilancia en segundo plano
- `[` y `]`: mover el track en la cola hacia arriba o abajo
- `?` o `F1`: mostrar esta ayuda de teclas
- `a`: agregar otro canal de musica por URL/@username
- `c`: volver a la lista de carpetas
- `u`: escanear mas canciones del canal activo o seleccionado
- `n`: reproducir siguiente
- `x`: ignorar seleccion, borrar cache local y saltarla en futuras descargas
- `s`: detener reproduccion
- `/`: buscar
- `r`: refrescar lista
- `q`: salir

Cuando una cancion termina, la TUI reproduce automaticamente la siguiente de la lista visible.

### Split View (3 paneles)

Presiona `P` para activar el modo split view, que muestra 3 paneles lado a lado:

1. **Channels** (izquierda): Lista de canales disponibles
2. **Tracks** (centro): Canciones del canal seleccionado
3. **Details** (derecha): Informacion de la cancion actual, cola de reproduccion y portada

Teclas en split view:
- `Tab`: Cambiar entre paneles (Channels -> Tracks -> Details)
- `Enter` en panel Channels: Seleccionar canal y ver sus tracks
- `Enter` en panel Tracks: Reproducir cancion seleccionada
- `Backspace`: Volver al panel Channels

### Mini View

Presiona `M` para activar el mini view, que muestra una barra compacta con:
- Titulo de la cancion actual
- Barra de progreso con tiempo
- Indicadores de repeat (R) y shuffle (S)
- Volumen actual

### Favoritos y Tags

- `f`: Marcar/desmarcar cancion como favorita
- `1`: Filtrar solo favoritos
- `t`: Agregar/eliminar tags a la cancion seleccionada
- `tag add/remove/list/show`: Gestionar tags desde CLI

### Otros atajos

- `R`: Activar/desactivar repeat (repetir lista)
- `S`: Activar/desactivar shuffle (aleatorio)
- `+`/`-`: Ajustar volumen
- `L`: Mostrar/ocultar letras de la cancion
- `M`: Activar/desactivar mini view
- `P`: Activar/desactivar split view

## Canales

Puedes agregar mas canales desde terminal:

```bash
tg-music add-channel https://t.me/Christian_Electronic --limit 300
tg-music channels
```

O desde la TUI:

- `a`: agregar un canal nuevo
- `c`: ver canales agregados
- `Enter`: abrir el canal seleccionado
- `Space` o flecha derecha: expandir o colapsar el canal seleccionado
- `Backspace` o flecha izquierda: volver al navegador de carpetas
- `e`: encolar el track seleccionado
- `m`: bajar canciones faltantes del canal actual
- `w`: revisar nuevas subidas del canal actual
- `W`: activar o desactivar la vigilancia en segundo plano
- `[` y `]`: reordenar la cola
- `u`: buscar mas canciones del canal

## Ignorar canciones

Si una cancion no te gusta, puedes bloquearla para que no vuelva a descargarse:

```bash
tg-music ignore 123
```

Eso borra su archivo local, borra portadas cacheadas, la oculta de la lista normal y la salta
en `cache`, `scan --cache` y el precache automatico de la TUI.

Para verla o restaurarla:

```bash
tg-music ignored
tg-music unignore 123
```

## Notas

Funciona con canales publicos y con canales privados donde tu cuenta ya sea miembro.
El programa usa tu cuenta de Telegram via MTProto, no un bot.
