import logging
import sys
import time
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

_FMT = (
    "%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)-30s | "
    "%(filename)s:%(lineno)d | %(message)s"
)
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: str = "DEBUG") -> None:
    root = logging.getLogger()
    if root.handlers:
        return  # already configured

    root.setLevel(level)

    # ── Console handler (INFO+) ──────────────────────────────────────────
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(_ColorFormatter(_FMT, datefmt=_DATE_FMT))

    # ── File handler – full DEBUG, rotated daily ─────────────────────────
    file_handler = logging.FileHandler(
        LOG_DIR / f"app_{time.strftime('%Y%m%d')}.log",
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(_FMT, datefmt=_DATE_FMT))

    # ── Separate file for LLM calls ──────────────────────────────────────
    llm_handler = logging.FileHandler(
        LOG_DIR / f"llm_{time.strftime('%Y%m%d')}.log",
        encoding="utf-8",
    )
    llm_handler.setLevel(logging.DEBUG)
    llm_handler.setFormatter(logging.Formatter(_FMT, datefmt=_DATE_FMT))
    logging.getLogger("llm").addHandler(llm_handler)
    logging.getLogger("llm").propagate = True

    # ── Separate file for search calls ───────────────────────────────────
    search_handler = logging.FileHandler(
        LOG_DIR / f"search_{time.strftime('%Y%m%d')}.log",
        encoding="utf-8",
    )
    search_handler.setLevel(logging.DEBUG)
    search_handler.setFormatter(logging.Formatter(_FMT, datefmt=_DATE_FMT))
    logging.getLogger("search").addHandler(search_handler)
    logging.getLogger("search").propagate = True

    root.addHandler(console)
    root.addHandler(file_handler)

    # Quiet noisy third-party libs
    for noisy in ("httpx", "httpcore", "urllib3", "arxiv"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)  # handled by middleware


class _ColorFormatter(logging.Formatter):
    _COLORS = {
        logging.DEBUG:    "\033[37m",    # grey
        logging.INFO:     "\033[32m",    # green
        logging.WARNING:  "\033[33m",    # yellow
        logging.ERROR:    "\033[31m",    # red
        logging.CRITICAL: "\033[1;31m",  # bold red
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self._COLORS.get(record.levelno, "")
        record.levelname = f"{color}{record.levelname}{self._RESET}"
        return super().format(record)
