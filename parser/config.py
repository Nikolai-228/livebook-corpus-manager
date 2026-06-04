# parser/config.py

import os

# Google Drive Service Account
SERVICE_ACCOUNT_FILE = r'C:\Users\HUAWEI\Desktop\practica\API\livebook-parser-265c1e8112e9.json'

# Список всех разделов с их ID и названиями
CHAPTERS = [
    {"name": "Выпуск 1962", "folder_id": "0B8SHLgKhSzzVQkJlTmlZTTA3VlU"},
    {"name": "Спортлагерь", "folder_id": "0B2fTk0YpFkQobkppcF9JU1Z3RVU"},
    {"name": "Джаз оркестр", "folder_id": "0B4XKvmcd84NmNGUwN0pSNC1xV00"},
    {"name": "ЛИТО \"Прикосновение\"", "folder_id": "0B19WL5_6ZLiOaThvd1ZGSDVGa2s"},
    {"name": "Шибановы", "folder_id": "0B6a0UXSu1ww8MjlQZFYzOWpWQTQ"},
    {"name": "Стройотряды", "folder_id": "0B7oIjQ46Neu2b0poX0JQVE9iZ1E"},
    {"name": "Легкоатлетические пробеги", "folder_id": "0B0MPL6rx3K74Wnp5bHFJeDBLR0U"},
    {"name": "Наша рота", "folder_id": "0ByXznipCdl-6MlhSSVY3UVBvMk0"},
    {"name": "Водная станция", "folder_id": "0ByXznipCdl-6cXlySG5SQlZndVk"},
    {"name": "КВН - СТЭМ - театр \"Молодой человек\"", "folder_id": "0B2Px5XCTuiOATXFmUDZTalpYOGc"},
    {"name": "Программисты ИжГТУ", "folder_id": "1JwjK2CI87L1lRVuGQtaQd_kZCsdbZRUK"},
    {"name": "Выпускник ИМИ-ИжГТУ, чемпион мира А.Р. Чижов", "folder_id": "1lzumS1hpUKlWjAUDl161MLRyvD22kLZb"},
]

# PostgreSQL
DATABASE_DSN = "postgresql://postgres:228228@localhost:5432/livebook_corpus"

# Chandra OCR настройки
CHANDRA_METHOD = "hf"
CHANDRA_TEMP_DIR = os.path.join(os.path.dirname(__file__), "temp_chandra")