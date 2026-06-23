# postprocessing/config.py
import os
from pathlib import Path

# Корень проекта
PROJECT_ROOT = Path(__file__).parent.parent

# PostgreSQL
DATABASE_DSN = os.getenv(
    "DATABASE_DSN",
    "postgresql://postgres:password@localhost:5432/test_book"
)


# Параметры обработки
BATCH_SIZE = 50
MIN_TEXT_LENGTH = 20
MAX_TEXT_LENGTH = 100000

# Логирование
LOG_FILE = PROJECT_ROOT / "logs" / "postprocessing.log"
LOG_LEVEL = "INFO"
LOG_FILE.parent.mkdir(exist_ok=True)