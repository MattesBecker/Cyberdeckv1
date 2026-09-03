from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
NOTES_DIR = DATA_DIR / "notes"
LIBRARY_DIR = DATA_DIR / "library"
TASKS_FILE = DATA_DIR / "tasks.json"

INPUT_MODE = "auto"
CARDKB_I2C_BUS = 3
CARDKB_I2C_ADDRESS = 0x5F
CARDKB_POLL_INTERVAL = 0.03

WAVESHARE_LIB_PATH = Path(
    "/home/pi/e-Paper/RaspberryPi_JetsonNano/python/lib"
)

DISPLAY_WIDTH = 250
DISPLAY_HEIGHT = 122
DISPLAY_MODEL = "epd2in13_V3"

MENU_ITEMS = [
    ("Notes", "notes"),
    ("Tasks", "tasks"),
    ("Terminal", "terminal"),
    ("Library", "library"),
    ("Tools", "tools"),
    ("Sync", "sync"),
]
