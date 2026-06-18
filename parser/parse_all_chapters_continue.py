# parser/parse_all_chapters_continue.py
"""
Парсинг Google Drive с ПРОДОЛЖЕНИЕМ с того же места.
Пропускает уже существующие разделы, папки и документы.
Добавляет только новые файлы.
"""

import os
import re
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from config import SERVICE_ACCOUNT_FILE, CHAPTERS
from db_utils import (
    get_db_connection,
    get_or_create_folder,
    save_document,
    save_media,
    get_or_create_chapter,
    print_stats
)
from text_extractor import extract_text_and_images, is_image


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
# 2. ПОЛУЧЕНИЕ ФАЙЛОВ ИЗ ПАПКИ
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
# 3. ПРОВЕРКА СУЩЕСТВОВАНИЯ
# ==========================================================

def document_exists(conn, doc_url: str) -> bool:
    """Проверяет, существует ли уже документ с таким URL"""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM documents WHERE url = %s", (doc_url,))
        return cur.fetchone() is not None


def media_exists(conn, name: str, folder_id: int = None, document_id: int = None) -> bool:
    """Проверяет, существует ли уже медиафайл с таким именем в папке или документе"""
    with conn.cursor() as cur:
        if document_id:
            cur.execute(
                "SELECT id FROM media WHERE name = %s AND document_id = %s",
                (name, document_id)
            )
        elif folder_id:
            cur.execute(
                "SELECT id FROM media WHERE name = %s AND folder_id = %s AND document_id IS NULL",
                (name, folder_id)
            )
        else:
            return False
        return cur.fetchone() is not None


# ==========================================================
# 4. РЕКУРСИВНЫЙ ПАРСИНГ ПАПКИ (с пропуском существующих)
# ==========================================================

def parse_folder_recursive(drive_service, conn, chapter_id, folder_id, parent_db_id=None, current_path=""):
    """
    Рекурсивно обходит папки Google Drive.
    Пропускает уже существующие документы и изображения.
    """
    print(f"\n📁 Папка: {current_path or '/root'} (раздел ID: {chapter_id})")

    all_items = get_all_folder_contents(drive_service, folder_id)

    folders = [item for item in all_items if item['mimeType'] == 'application/vnd.google-apps.folder']
    files = [item for item in all_items if item['mimeType'] != 'application/vnd.google-apps.folder']

    folders.sort(key=lambda x: x.get('name', ''))
    files.sort(key=lambda x: x.get('name', ''))

    # ==========================================================
    # 1. ОБРАБОТКА ПОДПАПОК (РЕКУРСИВНО)
    # ==========================================================
    for item in folders:
        item_name = item['name']
        item_id = item['id']

        print(f"  📂 Вход в папку: {item_name}")

        folder_db_id = get_or_create_folder(
            conn,
            item_name,
            chapter_id,
            parent_db_id,
            f"{current_path}/{item_name}" if current_path else item_name
        )

        new_path = f"{current_path}/{item_name}" if current_path else item_name
        parse_folder_recursive(drive_service, conn, chapter_id, item_id, folder_db_id, new_path)

    # ==========================================================
    # 2. ОБРАБОТКА ФАЙЛОВ (только новых)
    # ==========================================================
    for item in files:
        item_name = item['name']
        mime_type = item['mimeType']
        item_id = item['id']

        doc_url = f"https://drive.google.com/file/d/{item_id}/view"

        # ТЕКСТОВЫЕ ДОКУМЕНТЫ
        if mime_type in [
            'text/plain',
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/msword',
            'application/vnd.google-apps.document',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'application/vnd.google-apps.presentation',
        ]:
            # ПРОВЕРКА: есть ли уже такой документ
            if document_exists(conn, doc_url):
                print(f"  ⏭️ Пропущен (уже есть): {item_name}")
                continue

            print(f"  📄 Новый документ: {item_name}")

            file_type_map = {
                'application/vnd.google-apps.document': 'google_doc',
                'application/pdf': 'pdf',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
                'application/msword': 'doc',
                'text/plain': 'txt',
            }
            file_type = file_type_map.get(mime_type, 'other')

            clean_title = re.sub(r'\.(docx|pdf|txt|doc|pptx)$', '', item_name, flags=re.IGNORECASE)

            file_metadata = {
                'id': item_id,
                'name': item_name,
                'mimeType': mime_type
            }
            extracted_text, images = extract_text_and_images(drive_service, file_metadata)

            doc_id = save_document(
                conn,
                clean_title,
                file_type,
                chapter_id,
                parent_db_id,
                extracted_text,
                doc_url
            )
            print(f"    ✅ Документ сохранён (ID: {doc_id})")

            # ✅ Сохраняем изображения, извлечённые из документа
            if images:
                print(f"    🖼️ Извлечено изображений из документа: {len(images)}")
                for img_name, img_bytes in images:
                    # Проверяем, есть ли уже такое изображение у этого документа
                    if media_exists(conn, img_name, document_id=doc_id):
                        print(f"      ⏭️ Пропущено (уже есть): {img_name}")
                        continue
                    save_media(
                        conn,
                        chapter_id,
                        img_name,
                        img_bytes,
                        parent_db_id,
                        doc_id
                    )
                    print(f"      ✅ Изображение сохранено: {img_name}")

        # ИЗОБРАЖЕНИЯ (отдельные файлы)
        elif is_image(mime_type):
            # Проверяем, есть ли уже такое изображение в этой папке
            if media_exists(conn, item_name, folder_id=parent_db_id):
                print(f"  ⏭️ Пропущено (уже есть): {item_name}")
                continue

            print(f"  🖼️ Новое изображение: {item_name}")

            try:
                request = drive_service.files().get_media(fileId=item_id)
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                fh.seek(0)
                img_bytes = fh.read()

                save_media(
                    conn,
                    chapter_id,
                    item_name,
                    img_bytes,
                    parent_db_id,
                    None
                )
                print(f"    ✅ Изображение сохранено")
            except Exception as e:
                print(f"    ❌ Ошибка скачивания: {e}")

        else:
            print(f"  ⏭️ Пропущен (неподдерживаемый тип): {item_name}")


# ==========================================================
# 5. ОСНОВНАЯ ФУНКЦИЯ
# ==========================================================

def parse_all_chapters_continue():
    """Парсит разделы, пропуская уже существующие документы"""
    print("=" * 70)
    print("🚀 ПАРСИНГ С ПРОДОЛЖЕНИЕМ")
    print("   - Существующие документы пропускаются")
    print("   - Добавляются только новые файлы")
    print("   - Изображения сохраняются")
    print("=" * 70)

    # 1. Авторизация
    print("\n🔐 Авторизация...")
    drive_service = get_drive_service()
    if not drive_service:
        print("❌ Не удалось создать сервис")
        return
    print("✅ Авторизация успешна")

    # 2. Подключение к БД
    print("\n💾 Подключение к PostgreSQL...")
    conn = get_db_connection()
    print("✅ Подключение установлено")

    # 3. Сохраняем начальное количество документов
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM documents")
        old_docs_count = cur.fetchone()[0]
        print(f"\n📊 Документов в БД до начала: {old_docs_count}")

    # 4. Парсинг каждого раздела
    print("\n" + "=" * 70)
    print("📚 НАЧАЛО ПАРСИНГА РАЗДЕЛОВ")
    print("=" * 70)

    for idx, chapter in enumerate(CHAPTERS, 1):
        chapter_name = chapter["name"]
        folder_id = chapter["folder_id"]

        print("\n" + "=" * 60)
        print(f"📚 РАЗДЕЛ {idx}/{len(CHAPTERS)}: {chapter_name}")
        print(f"📁 ID папки: {folder_id}")
        print("=" * 60)

        chapter_id = get_or_create_chapter(conn, chapter_name)
        print(f"✅ ID раздела в БД: {chapter_id}")

        try:
            parse_folder_recursive(
                drive_service,
                conn,
                chapter_id,
                folder_id,
                parent_db_id=None,
                current_path=chapter_name
            )
        except Exception as e:
            print(f"❌ Ошибка при парсинге раздела {chapter_name}: {e}")

    # 5. Финальная статистика
    print("\n" + "=" * 70)
    print("📊 ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 70)

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM chapters")
        print(f"   📚 Разделов: {cur.fetchone()[0]}")

        cur.execute("SELECT COUNT(*) FROM folders")
        print(f"   📁 Папок: {cur.fetchone()[0]}")

        cur.execute("SELECT COUNT(*) FROM documents")
        docs_count = cur.fetchone()[0]
        print(f"   📄 Документов: {docs_count}")

        cur.execute("SELECT COUNT(*) FROM media")
        print(f"   🖼️ Изображений: {cur.fetchone()[0]}")

    # 6. Сколько новых документов добавлено
    new_docs = docs_count - old_docs_count
    print(f"\n📊 ДОБАВЛЕНО НОВЫХ ДОКУМЕНТОВ: {new_docs}")

    if new_docs == 0:
        print("   ✅ Всё актуально, новых документов нет")

    conn.close()
    print("\n✅ ПАРСИНГ ЗАВЕРШЁН!")


if __name__ == "__main__":
    parse_all_chapters_continue()