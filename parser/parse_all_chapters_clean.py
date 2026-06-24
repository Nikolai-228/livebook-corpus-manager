# parser/parse_all_chapters_clean.py
"""
Парсинг Google Drive с ПОЛНОЙ ОЧИСТКОЙ БД перед началом.
Удаляет все данные из таблиц chapters, folders, documents, media
и заполняет заново.
Добавлены поля: date (дата написания),
date_uploaded (дата загрузки на диск), date_imported (дата импорта в БД)
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
    clear_database,
    print_stats
)
from text_extractor import extract_text_and_images, is_image

SAVE_IMAGES = False  # True - сохранять изображения, False - не сохранять


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
# 3. ОСНОВНАЯ ФУНКЦИЯ ПАРСИНГА ОДНОГО РАЗДЕЛА
# ==========================================================

def parse_folder_recursive(drive_service, conn, chapter_id, folder_id, parent_db_id=None, current_path=""):
    """
    Рекурсивно обходит папки Google Drive и сохраняет данные в БД.
    Все папки и документы привязываются к chapter_id.
    """
    print(f"\n📁 Папка: {current_path or '/root'} (раздел ID: {chapter_id})")

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
        folder_db_id = get_or_create_folder(
            conn,
            item_name,
            chapter_id,
            parent_db_id,
            f"{current_path}/{item_name}" if current_path else item_name
        )

        # Рекурсивный обход подпапки
        new_path = f"{current_path}/{item_name}" if current_path else item_name
        parse_folder_recursive(drive_service, conn, chapter_id, item_id, folder_db_id, new_path)

    # ==========================================================
    # 2. ЗАТЕМ ОБРАБАТЫВАЕМ ВСЕ ФАЙЛЫ В ТЕКУЩЕЙ ПАПКЕ
    # ==========================================================
    for item in files:
        item_name = item['name']
        mime_type = item['mimeType']
        item_id = item['id']

        # Получаем дату создания/загрузки файла на Google Drive
        created_time = item.get('createdTime')
        modified_time = item.get('modifiedTime')
        # Используем createdTime как дату загрузки, если есть, иначе modifiedTime
        drive_upload_date = created_time if created_time else modified_time
        if drive_upload_date:
            # Парсим ISO формат даты
            try:
                drive_upload_date = datetime.fromisoformat(drive_upload_date.replace('Z', '+00:00')).date()
            except:
                drive_upload_date = None

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
            file_type_map = {
                'application/vnd.google-apps.document': 'google_doc',
                'application/pdf': 'pdf',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
                'application/msword': 'doc',
                'text/plain': 'txt',
            }
            file_type = file_type_map.get(mime_type, 'other')

            # Убираем расширение из названия
            clean_title = re.sub(r'\.(docx|pdf|txt|doc|pptx)$', '', item_name, flags=re.IGNORECASE)

            # Извлекаем текст, изображения и дату из документа
            file_metadata = {
                'id': item_id,
                'name': item_name,
                'mimeType': mime_type
            }

            print(f"    ⏳ Извлечение текста из документа...")
            extracted_text, images, doc_date = extract_text_and_images(drive_service, file_metadata)

            # Проверка что текст извлечен
            if extracted_text:
                print(f"    ✅ Текст извлечен (длина: {len(extracted_text)} символов)")
            else:
                print(f"    ⚠️ Текст не извлечен или пустой")

            # URL документа
            doc_url = f"https://drive.google.com/file/d/{item_id}/view"

            # Сохраняем документ в БД с новыми полями
            print(f"    💾 Сохранение документа в БД...")
            try:
                doc_id = save_document(
                    conn,
                    clean_title,
                    file_type,
                    chapter_id,
                    parent_db_id,
                    extracted_text,
                    doc_url,
                    doc_date,  # дата написания
                    drive_upload_date,  # дата загрузки на диск
                    datetime.now().date()  # дата импорта в БД
                )
                # Принудительно коммитим каждое сохранение документа
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

            # Сохраняем изображения, извлечённые из документа
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

        # ======================================================
        # 2.2 ОТДЕЛЬНЫЕ ИЗОБРАЖЕНИЯ
        # ======================================================
        elif is_image(mime_type):
            if SAVE_IMAGES:
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
                    save_media(
                        conn,
                        chapter_id,
                        item_name,
                        img_bytes,
                        parent_db_id,
                        None
                    )
                    conn.commit()
                    print(f"    ✅ Изображение сохранено: {item_name}")
                except Exception as e:
                    print(f"    ❌ Ошибка скачивания изображения: {e}")
            else:
                # Если SAVE_IMAGES = False, просто пропускаем изображения
                print(f"  ⏭️ Изображение пропущено (SAVE_IMAGES=False): {item_name}")

        # ======================================================
        # 2.3 ОСТАЛЬНЫЕ ТИПЫ ФАЙЛОВ (ПРОПУСКАЕМ)
        # ======================================================
        else:
            print(f"  ⏭️ Пропущен (неподдерживаемый тип): {item_name} ({mime_type})")


# ==========================================================
# 4. ПАРСИНГ ВСЕХ РАЗДЕЛОВ С ОЧИСТКОЙ
# ==========================================================

def parse_all_chapters_clean():
    """Парсит все разделы с полной очисткой БД"""
    print("=" * 70)
    print("🚀 ПАРСИНГ С ПОЛНОЙ ОЧИСТКОЙ БД")
    print("   - Все старые данные будут удалены")
    print("   - Все разделы будут перезаписаны")
    if SAVE_IMAGES:
        print("   - Изображения СОХРАНЯЮТСЯ")
    else:
        print("   - Изображения НЕ СОХРАНЯЮТСЯ (только документы)")
    print("   - Извлекается дата написания документов")
    print("=" * 70)

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

    # 3. ОЧИСТКА БД
    clear_database(conn)

    # 4. Парсинг каждого раздела
    total_docs = 0
    total_media = 0

    for idx, chapter in enumerate(CHAPTERS, 1):
        chapter_name = chapter["name"]
        folder_id = chapter["folder_id"]

        print("\n" + "=" * 60)
        print(f"📚 РАЗДЕЛ {idx}/{len(CHAPTERS)}: {chapter_name}")
        print(f"📁 ID папки: {folder_id}")
        print("=" * 60)

        # Получаем или создаём chapter_id
        chapter_id = get_or_create_chapter(conn, chapter_name)
        print(f"✅ ID раздела в БД: {chapter_id}")

        try:
            # Парсим корневую папку раздела
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

    # 5. Статистика
    print_stats(conn)

    conn.close()
    print("\n🔌 Соединение с БД закрыто")
    print("\n✅ ПАРСИНГ ВСЕХ РАЗДЕЛОВ ЗАВЕРШЁН!")


if __name__ == "__main__":
    parse_all_chapters_clean()