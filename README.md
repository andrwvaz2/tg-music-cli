# tg-music-cli

Reproductor de música para canales de Telegram desde la terminal.

```text
┌──────────────────────────────────────────────────────────┐
│                                                          │
│                    T G  -  M U S I C                     │
│       Terminal music player for Telegram channels        │
│                                                          │
├──────────────────────────────────────────────────────────┤
│                                                          │
│                          SETUP                           │
│                                                          │
│     1. Go to https://my.telegram.org/apps                │
│     2. Log in and get your api_id and api_hash           │
│     3. Run configuration command:                        │
│     $ tg-music init                                      │
│                                                          │
├──────────────────────────────────────────────────────────┤
│                                                          │
│                        QUICKSTART                        │
│                                                          │
│   Scan a channel:  tg-music scan @channel --limit 300    │
│   Open the player:  tg-music tui                         │
│   Cache tracks:  tg-music cache @channel --limit 50      │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

## Características

* **Navegación tipo carpetas:** Explora los canales de Telegram indexados como directorios locales.
* **Precarga inteligente:** Descarga en segundo plano los siguientes 3 tracks de la lista para evitar cortes.
* **Portadas embebidas:** Renderizado de carátulas en la terminal mediante `chafa` (con soporte para imágenes reales en Kitty/Ghostty y caracteres en otros terminales).
* **Base de datos local:** Almacenamiento rápido en SQLite para historial, favoritos y tags.
* **Múltiples vistas:** Vista clásica, Split View (3 paneles) y Mini View (reproductor compacto).
* **Bloqueo de canciones:** Permite ignorar pistas para que no se muestren ni se descarguen en masa.

---

## Requisitos

* Python 3.11+
* `uv` (opcional, recomendado para ejecución rápida)
* `mpv` (backend de audio)
* `chafa` (opcional, para visualización de portadas)
* Una app de Telegram creada en `https://my.telegram.org` para obtener `api_id` y `api_hash`.

---

## Inicio rápido

Si usas `uv`:

```bash
# Acceder al proyecto
cd ~/Proyectos/tg-music-cli

# Configurar credenciales de Telegram
uv run tg-music init

# Escanear un canal
uv run tg-music scan https://t.me/Christian_Electronic --limit 300

# Abrir el reproductor
uv run tg-music tui
```

*Nota: En el primer inicio, la API de Telegram solicitará tu número de teléfono y el código de verificación. La sesión se almacena de forma local en `~/.local/share/tg-music/session.session`.*

---

## Diseños de la TUI

### Split View (Teclar `P`)
Divide la interfaz en tres columnas:
1. **Channels:** Lista de canales agregados y carpetas locales.
2. **Tracks:** Canciones del canal seleccionado.
3. **Details:** Pista actual, carátula y cola de reproducción.

### Mini View (Teclar `M`)
Reduce la interfaz a una sola línea inferior que muestra el progreso, título actual, volumen y estado de reproducción.

---

## Atajos de teclado

### Navegación y reproducción

| Tecla | Acción |
|---|---|
| `Flechas` / `j`/`k` | Mover cursor |
| `Enter` | Abrir canal / reproducir canción |
| `Space` / `→` | Expandir canal |
| `Backspace` / `←` | Colapsar canal / volver a la lista de canales |
| `s` | Detener reproducción |
| `n` | Siguiente canción |
| `+` / `-` | Ajustar volumen |
| `/` | Buscar en la lista |
| `r` | Refrescar listado |
| `q` | Salir del reproductor |

### Gestión y cola

| Tecla | Acción |
|---|---|
| `e` | Encolar canción seleccionada |
| `[` / `]` | Reordenar cola (subir / bajar) |
| `f` | Marcar/desmarcar favorita |
| `1` | Mostrar solo favoritas |
| `t` | Editar tags del track seleccionado |
| `L` | Mostrar/ocultar letras |
| `m` | Descargar tracks faltantes de la vista actual |
| `u` | Escanear canciones más antiguas del canal seleccionado |
| `w` | Buscar novedades en el canal activo |
| `W` | Alternar vigilancia en segundo plano |
| `x` | Bloquear canción (borra caché y la salta en descargas) |

---

## Comandos CLI

El comando `tg-music` permite gestionar el reproductor directamente desde la shell:

### Canales
```bash
tg-music add-channel <URL_O_USER> --limit 300   # Guardar un canal
tg-music channels                               # Listar canales guardados
tg-music scan <URL_O_USER> --limit 300          # Indexar metadata
tg-music scan <URL_O_USER> --cache              # Indexar y descargar audio
```

### Reproducción y Descarga
```bash
tg-music play <ID>                              # Reproducir un track específico
tg-music play-latest <URL_O_USER>               # Reproducir último audio de un canal
tg-music cache <URL_O_USER> --workers 2          # Descargar pistas faltantes
```

### Gestión de Tags
```bash
tg-music tag add <ID> <tag>                     # Asignar tag a una canción
tg-music tag remove <ID> <tag>                  # Eliminar tag
tg-music tag list                               # Listar todos los tags del sistema
tg-music tag show <ID>                          # Mostrar tags de una canción
```

### Bloqueos y Favoritos
```bash
tg-music favorite <ID>                          # Alternar favorito
tg-music ignore <ID>                            # Bloquear track (elimina el archivo local)
tg-music unignore <ID>                          # Desbloquear track
tg-music ignored                                # Listar canciones bloqueadas
```

---

## Ubicaciones de archivos

* **Caché de audio:** `~/.cache/tg-music/audio`
* **Base de datos SQLite:** `~/.local/share/tg-music/library.sqlite3`
* **Sesión de Telegram:** `~/.local/share/tg-music/session.session`
