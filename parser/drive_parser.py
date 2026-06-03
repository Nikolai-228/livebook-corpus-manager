# parser/drive_parser.py

import os
import re
import io
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from config import SERVICE_ACCOUNT_FILE, FOLDER_ID
from db_utils import get_db_connection, get_or_create_folder, save_document, save_media
from text_extractor import extract_text_and_images, is_image, extract_date_from_text
from config import SERVICE_ACCOUNT_FILE, FOLDER_ID


# ==========================================================
# 1. АВТОРИЗАЦИЯ
# ==========================================================

def get_drive_service():
    """Создаёт и возвращает авторизованный сервис Google Drive."""
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        print(f"❌ Файл ключей не найден: {SERVICE_ACCOUNT_FILE}")
        return None

    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=['https://www.googleapis.com/auth/drive.readonly']
    )
    return build('drive', 'v3', credentials=credentials)


# ==========================================================
# 2. ПОЛУЧЕНИЕ ВСЕХ ФАЙЛОВ В ПАПКЕ
# ==========================================================

def get_all_folder_contents(drive_service, folder_id):
    """Возвращает список всех файлов и папок внутри folder_id."""
    all_items = []
    page_token = None

    while True:
        results = drive_service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="nextPageToken, files(id, name, mimeType, modifiedTime, parents)",
            pageSize=1000,
            pageToken=page_token,
            orderBy='folder,name'
        ).execute()

        items = results.get('files', [])
        all_items.extend(items)

        page_token = results.get('nextPageToken')
        if not page_token:
            break

    return all_items


# ==========================================================
# 3. ОСНОВНАЯ ФУНКЦИЯ ПАРСИНГА
# ==========================================================

def parse_folder_recursive(drive_service, conn, folder_id, parent_db_id=None, current_path=""):
    """
    Рекурсивно обходит папки Google Drive и сохраняет данные в БД.

    Порядок обработки:
    1. Сначала обрабатываются все подпапки (рекурсивно)
    2. Затем обрабатываются все файлы в текущей папке
    """
    print(f"\n📁 Папка: {current_path or '/root'}")

    # Получаем ВСЕ элементы в текущей папке
    all_items = get_all_folder_contents(drive_service, folder_id)

    # Разделяем на папки и файлы
    folders = [item for item in all_items if item['mimeType'] == 'application/vnd.google-apps.folder']
    files = [item for item in all_items if item['mimeType'] != 'application/vnd.google-apps.folder']

    # Сортируем для предсказуемого порядка
    folders.sort(key=lambda x: x.get('name', ''))
    files.sort(key=lambda x: x.get('name', ''))

    # ==========================================================
    # 1. СНАЧАЛА ОБРАБАТЫВАЕМ ВСЕ ПОДПАПКИ (РЕКУРСИВНО)
    # ==========================================================
    for item in folders:
        item_name = item['name']
        item_id = item['id']

        print(f"  📂 Вход в папку: {item_name}")

        # Создаём запись о папке в БД
        folder_db_id = get_or_create_folder(conn, item_name, current_path, parent_db_id)

        # Рекурсивный обход подпапки
        new_path = f"{current_path}/{item_name}" if current_path else item_name
        parse_folder_recursive(drive_service, conn, item_id, folder_db_id, new_path)

    # ==========================================================
    # 2. ЗАТЕМ ОБРАБАТЫВАЕМ ВСЕ ФАЙЛЫ В ТЕКУЩЕЙ ПАПКЕ
    # ==========================================================
    for item in files:
        item_name = item['name']
        mime_type = item['mimeType']
        item_id = item['id']

        # ======================================================
        # 2.1 ТЕКСТОВЫЕ ДОКУМЕНТЫ
        # ======================================================
        if mime_type in [
            'text/plain',
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/msword',
            'application/vnd.google-apps.document',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'application/vnd.google-apps.presentation',
        ]:
            print(f"  📄 Документ: {item_name}")

            # Определяем тип файла
            if mime_type == 'application/vnd.google-apps.document':
                file_type = 'google_doc'
            elif mime_type == 'application/pdf':
                file_type = 'pdf'
            elif mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                file_type = 'docx'
            elif mime_type == 'application/msword':
                file_type = 'doc'
            elif mime_type == 'text/plain':
                file_type = 'txt'
            else:
                file_type = 'other'

            # Убираем расширение из названия
            clean_title = re.sub(r'\.(docx|pdf|txt|doc|pptx)$', '', item_name, flags=re.IGNORECASE)

            # Извлекаем текст и изображения из документа
            file_metadata = {
                'id': item_id,
                'name': item_name,
                'mimeType': mime_type
            }
            extracted_text, images = extract_text_and_images(drive_service, file_metadata)

            # Извлекаем дату из текста
            creation_date = extract_date_from_text(extracted_text)
            if creation_date:
                print(f"    📅 Найдена дата: {creation_date}")
            else:
                print(f"    📅 Дата не найдена")

            # URL документа
            doc_url = f"https://drive.google.com/file/d/{item_id}/view"

            # Сохраняем документ в БД
            doc_id = save_document(
                conn,
                clean_title,
                file_type,
                parent_db_id,
                extracted_text,
                doc_url,
                creation_date
            )
            print(f"    ✅ Документ сохранён (ID: {doc_id})")

            # Сохраняем изображения, извлечённые из документа
            if images:
                print(f"    🖼️ Извлечено изображений из документа: {len(images)}")
                for img_name, img_bytes in images:
                    save_media(conn, parent_db_id, doc_id, img_name, img_bytes)
                    print(f"      ✅ Изображение сохранено: {img_name}")

        # ======================================================
        # 2.2 ОТДЕЛЬНЫЕ ИЗОБРАЖЕНИЯ
        # ======================================================
        elif is_image(mime_type):
            print(f"  🖼️ Изображение (файл): {item_name}")

            try:
                # Скачиваем изображение через Service Account
                request = drive_service.files().get_media(fileId=item_id)
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                fh.seek(0)
                img_bytes = fh.read()

                # Сохраняем в БД (без привязки к документу)
                save_media(conn, parent_db_id, None, item_name, img_bytes)
                print(f"    ✅ Изображение сохранено: {item_name}")
            except Exception as e:
                print(f"    ❌ Ошибка скачивания изображения: {e}")

        # ======================================================
        # 2.3 ОСТАЛЬНЫЕ ТИПЫ ФАЙЛОВ (ПРОПУСКАЕМ)
        # ======================================================
        else:
            print(f"  ⏭️ Пропущен (неподдерживаемый тип): {item_name} ({mime_type})")


# ==========================================================
# 4. ТОЧКА ВХОДА
# ==========================================================

def main():
    print("=" * 60)
    print("🚀 ЗАПУСК ПАРСЕРА GOOGLE DRIVE")
    print("=" * 60)

    # 1. Авторизация
    print("\n🔐 Авторизация через Service Account...")
    drive_service = get_drive_service()
    if not drive_service:
        print("❌ Не удалось создать сервис. Проверьте файл с ключами.")
        return

    print("✅ Авторизация успешна")

    # 2. Подключение к БД
    print("\n💾 Подключение к PostgreSQL...")
    try:
        conn = get_db_connection()
        print("✅ Подключение установлено")
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        return

    # Проверка наличия Chandra OCR
    print("\n🔍 Проверка Chandra OCR...")
    try:
        from chandra.model import InferenceManager
        print("✅ Chandra OCR доступен")
    except ImportError:
        print("⚠️ Chandra OCR не установлен. PDF будут парситься стандартным методом.")
        print("   Установите: pip install chandra-ocr")

    # 3. Запуск парсинга
    print(f"\n📁 Целевая папка ID: {FOLDER_ID}")
    print("\n" + "=" * 60)
    print("НАЧАЛО ПАРСИНГА")
    print("=" * 60)

    try:
        parse_folder_recursive(drive_service, conn, FOLDER_ID)
        print("\n" + "=" * 60)
        print("✅ ПАРСИНГ ЗАВЕРШЁН УСПЕШНО")
        print("=" * 60)

        # Статистика
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM folders")
        folders_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM documents")
        docs_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM media")
        media_count = cursor.fetchone()[0]

        print(f"\n📊 ИТОГОВАЯ СТАТИСТИКА:")
        print(f"   📁 Папок: {folders_count}")
        print(f"   📄 Документов: {docs_count}")
        print(f"   🖼️ Изображений: {media_count}")

    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()
        print("\n🔌 Соединение с БД закрыто")


if __name__ == "__main__":
    main()