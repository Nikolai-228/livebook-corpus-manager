# postprocessing/__init__.py
"""
Модуль постобработки текстов для Живой книги ИМИ

Содержит инструменты для:
- Обработки PDF через локальную нейросеть (Llama 3.2)
- Очистки текста от мусора и склейки разорванных слов
"""

from .local_cleaner import postprocess_text, clean_text_basic
from .fix_pdfs_only import fix_pdfs

__all__ = [
    # Основные функции обработки
    'postprocess_text',
    'clean_text_basic',

    # Скрипты для запуска
    'fix_pdfs',  # Только для PDF через нейросеть

    # Версия модуля
    '__version__',
]

__version__ = '1.0.0'