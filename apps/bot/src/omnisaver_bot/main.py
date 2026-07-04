from omnisaver_config import load_settings


def main() -> None:
    settings = load_settings()
    print(f"omnisaver bot service placeholder ({settings.environment})")
