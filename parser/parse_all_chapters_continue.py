# parser/parse_all_chapters_continue.py
"""
Парсинг Google Drive с ПРОДОЛЖЕНИЕМ с того же места.
Пропускает уже существующие разделы, папки и документы.
Добавляет только новые файлы.
Проверяет изображения внутри существующих документов и добавляет недостающие.
"""

import os
import re
import io
from datetime import datetime
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

SAVE_IMAGES = True  # True - сохранять изображения, False - не сохранять


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
            fields="nextPageToken, files(id, name, mimeType, modifiedTime, parents, createdTime)",
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

def document_exists(conn, doc_url: str) -> tuple:
    """
    Проверяет, существует ли документ с таким URL
    Возвращает (существует, doc_id)
    """
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM documents WHERE url = %s", (doc_url,))
        result = cur.fetchone()
        if result:
            return True, result[0]
        return False, None


def get_document_media_names(conn, doc_id: int) -> set:
    """Возвращает множество имён изображений, связанных с документом"""
    with conn.cursor() as cur:
        cur.execute("SELECT name FROM media WHERE document_id = %s", (doc_id,))
        results = cur.fetchall()
        return {row[0] for row in results}


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


def save_missing_images(conn, chapter_id, doc_id, images, parent_db_id):
    """
    Сохраняет только те изображения, которых ещё нет в БД для этого документа
    Возвращает количество добавленных изображений
    """
    # Получаем существующие имена изображений для этого документа
    existing_names = get_document_media_names(conn, doc_id)

    added_count = 0
    for img_name, img_bytes in images:
        if img_name in existing_names:
            print(f"      ⏭️ Пропущено (уже есть): {img_name}")
            continue

        try:
            save_media(
                conn,
                chapter_id,
                img_name,
                img_bytes,
                parent_db_id,
                doc_id
            )
            conn.commit()
            print(f"      ✅ Добавлено новое изображение: {img_name}")
            added_count += 1
        except Exception as e:
            print(f"      ❌ Ошибка сохранения изображения {img_name}: {e}")

    return added_count


# ==========================================================
# 4. РЕКУРСИВНЫЙ ПАРСИНГ ПАПКИ (с проверкой изображений)
# ==========================================================

def parse_folder_recursive(drive_service, conn, chapter_id, folder_id, parent_db_id=None, current_path=""):
    """
    Рекурсивно обходит папки Google Drive.
    - Пропускает уже существующие документы (но проверяет их изображения)
    - Добавляет новые документы
    - Проверяет изображения внутри существующих документов
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
    # 2. ОБРАБОТКА ФАЙЛОВ
    # ==========================================================
    for item in files:
        item_name = item['name']
        mime_type = item['mimeType']
        item_id = item['id']

        # Получаем дату создания/загрузки файла на Google Drive
        created_time = item.get('createdTime')
        modified_time = item.get('modifiedTime')
        drive_upload_date = created_time if created_time else modified_time
        if drive_upload_date:
            try:
                drive_upload_date = datetime.fromisoformat(drive_upload_date.replace('Z', '+00:00')).date()
            except:
                drive_upload_date = None

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
            # Проверяем, есть ли документ в БД
            exists, doc_id = document_exists(conn, doc_url)

            if exists:
                # Документ уже есть - проверяем изображения внутри
                print(f"  📄 Документ уже есть: {item_name} (ID: {doc_id})")

                if SAVE_IMAGES:
                    # Получаем изображения из документа
                    file_metadata = {
                        'id': item_id,
                        'name': item_name,
                        'mimeType': mime_type
                    }
                    print(f"    ⏳ Извлечение изображений из документа...")
                    extracted_text, images, doc_date = extract_text_and_images(drive_service, file_metadata)

                    if images:
                        print(f"    🖼️ Проверка изображений в документе (найдено: {len(images)})")
                        added = save_missing_images(conn, chapter_id, doc_id, images, parent_db_id)
                        if added > 0:
                            print(f"    ✅ Добавлено {added} новых изображений")
                        else:
                            print(f"    ✅ Все изображения уже есть в БД")
                    else:
                        print(f"    ℹ️ Изображений в документе не найдено")
                else:
                    print(f"    ⏭️ Проверка изображений пропущена (SAVE_IMAGES=False)")
                continue

            # Документа нет - создаём новый
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

            print(f"    ⏳ Извлечение текста из документа...")
            extracted_text, images, doc_date = extract_text_and_images(drive_service, file_metadata)

            if extracted_text:
                print(f"    ✅ Текст извлечен (длина: {len(extracted_text)} символов)")
            else:
                print(f"    ⚠️ Текст не извлечен или пустой")

            try:
                doc_id = save_document(
                    conn,
                    clean_title,
                    file_type,
                    chapter_id,
                    parent_db_id,
                    extracted_text,
                    doc_url,
                    doc_date,
                    drive_upload_date,
                    datetime.now().date()
                )
                conn.commit()
                print(f"    ✅ Документ сохранён (ID: {doc_id})")
                if doc_date:
                    print(f"    📅 Дата написания: {doc_date}")
                if drive_upload_date:
                    print(f"    ☁️ Загружен на диск: {drive_upload_date}")
            except Exception as e:
                print(f"    ❌ Ошибка при сохранении документа: {e}")
                import traceback
                traceback.print_exc()
                continue

            # Сохраняем изображения из документа
            if SAVE_IMAGES:
                if images:
                    print(f"    🖼️ Извлечено изображений из документа: {len(images)}")
                    for img_name, img_bytes in images:
                        try:
                            save_media(
                                conn,
                                chapter_id,
                                img_name,
                                img_bytes,
                                parent_db_id,
                                doc_id
                            )
                            conn.commit()
                            print(f"      ✅ Изображение сохранено: {img_name}")
                        except Exception as e:
                            print(f"      ❌ Ошибка сохранения изображения {img_name}: {e}")

        # ИЗОБРАЖЕНИЯ (отдельные файлы)
        elif is_image(mime_type):
            if SAVE_IMAGES:
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
                    conn.commit()
                    print(f"    ✅ Изображение сохранено")
                except Exception as e:
                    print(f"    ❌ Ошибка скачивания: {e}")
            else:
                # Если SAVE_IMAGES = False, просто пропускаем изображения
                print(f"  ⏭️ Изображение пропущено (SAVE_IMAGES=False): {item_name}")

        else:
            print(f"  ⏭️ Пропущен (неподдерживаемый тип): {item_name}")


# ==========================================================
# 5. ОСНОВНАЯ ФУНКЦИЯ
# ==========================================================

def parse_all_chapters_continue():
    """Парсит разделы, проверяя изображения в существующих документах"""
    print("=" * 70)
    print("🚀 ПАРСИНГ С ПРОДОЛЖЕНИЕМ (с проверкой изображений)")
    print("   - Существующие документы проверяются на наличие новых изображений")
    print("   - Добавляются только новые файлы и изображения")
    print("   - Извлекается дата написания документов")
    if SAVE_IMAGES:
        print("   - Изображения СОХРАНЯЮТСЯ")
    else:
        print("   - Изображения НЕ СОХРАНЯЮТСЯ (только документы)")
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
    try:
        conn = get_db_connection()
        print("✅ Подключение установлено")
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        return

    # 3. Сохраняем начальное количество
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM documents")
        old_docs_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM media")
        old_media_count = cur.fetchone()[0]
        print(f"\n📊 Документов в БД до начала: {old_docs_count}")
        print(f"📊 Изображений в БД до начала: {old_media_count}")

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
            import traceback
            traceback.print_exc()

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
        media_count = cur.fetchone()[0]
        print(f"   🖼️ Изображений: {media_count}")

    # 6. Сколько нового добавлено
    new_docs = docs_count - old_docs_count
    new_media = media_count - old_media_count
    print(f"\n📊 ДОБАВЛЕНО НОВЫХ ДОКУМЕНТОВ: {new_docs}")
    print(f"📊 ДОБАВЛЕНО НОВЫХ ИЗОБРАЖЕНИЙ: {new_media}")

    if new_docs == 0 and new_media == 0:
        print("   ✅ Всё актуально, новых файлов нет")

    conn.close()
    print("\n✅ ПАРСИНГ ЗАВЕРШЁН!")


if __name__ == "__main__":
    parse_all_chapters_continue()