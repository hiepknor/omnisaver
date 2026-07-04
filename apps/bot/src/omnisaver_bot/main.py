import sys

from omnisaver_bot.runtime import build_application
from omnisaver_config import load_settings


def main() -> None:
    settings = load_settings()
    if len(sys.argv) > 1 and sys.argv[1] == "health":
        print("ok")
        return
    build_application(settings).run_polling()
