from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
DATA_DIR = BASE_DIR / "data"
NOTES_DIR = DATA_DIR / "notes"
LIBRARY_DIR = DATA_DIR / "library"
ZIM_DIR = DATA_DIR / "zim"
TASKS_FILE = DATA_DIR / "tasks.json"
TERMINAL_HISTORY_FILE = DATA_DIR / "terminal_history.txt"
WIKI_BOOKMARKS_FILE = DATA_DIR / "wiki_bookmarks.json"
WIKI_HISTORY_FILE = DATA_DIR / "wiki_history.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
SSH_SHORTCUTS_FILE = DATA_DIR / "ssh_shortcuts.json"
GAME_STATS_FILE = DATA_DIR / "game_stats.json"
TERMINAL_HISTORY_LIMIT = 20
TERMINAL_COMMAND_TIMEOUT = 10.0
WIKI_BOOKMARKS_LIMIT = 200
WIKI_HISTORY_LIMIT = 50
SSH_SHORTCUT_LIMIT = 100
SSH_COMMAND_TIMEOUT = 12.0
SSH_MAX_OUTPUT_CHARS = 256 * 1024
FILE_VIEWER_ROOTS = (Path("/home/pi"), Path("/var/log"))
FILE_VIEWER_MAX_BYTES = 256 * 1024

KIWIX_ENABLED = True
KIWIX_SERVER_PATH = Path("/usr/bin/kiwix-serve")
KIWIX_HOST = "127.0.0.1"
KIWIX_PORT = 8080
KIWIX_ZIM_PATH = ZIM_DIR / "wikipedia_de_all_nopic_2026-01.zim"
KIWIX_THREADS = 1
KIWIX_START_TIMEOUT = 15.0
KIWIX_HTTP_TIMEOUT = 10.0
KIWIX_POLL_INTERVAL = 0.25
KIWIX_STOP_TIMEOUT = 3.0
KIWIX_RESULT_LIMIT = 30
KIWIX_MAX_RESPONSE_BYTES = 4 * 1024 * 1024

INPUT_MODE = "auto"
CARDKB_I2C_BUS = 3
CARDKB_I2C_ADDRESS = 0x5F
CARDKB_POLL_INTERVAL = 0.03
# Unit CardKB v1.1 default firmware: Fn+R emits 0x90.
CARDKB_FULL_REFRESH_CODE = 0x90

WAVESHARE_LIB_PATH = Path(
    "/home/pi/e-Paper/RaspberryPi_JetsonNano/python/lib"
)

DISPLAY_WIDTH = 250
DISPLAY_HEIGHT = 122
DISPLAY_MODEL = "epd2in13_V3"
BOOT_LOGO_PATH = ASSETS_DIR / "boot_logo.png"
BOOT_SCREEN_SECONDS = 0.5
PARTIAL_REFRESH_LIMIT = 10
DEFAULT_START_SCREEN = "dashboard"

MENU_ITEMS = [
    ("Notes", "notes"),
    ("Tasks", "tasks"),
    ("Terminal", "terminal"),
    ("Library", "library"),
    ("Tools", "tools"),
    ("Games", "games"),
    ("Settings", "settings"),
]
