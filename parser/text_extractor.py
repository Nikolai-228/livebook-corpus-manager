import base64
import os
import io
import re

import kreuzberg
import requests

from bs4 import BeautifulSoup
from googleapiclient.http import MediaIoBaseDownload


def extract_text_from_pdf(content_bytes):
    """
    Извлекает текст из PDF через PyMuPDF с простой, но эффективной пост-обработкой.
    """
    import fitz
    import re

    doc = fitz.open(stream=content_bytes, filetype="pdf")
    all_text = []

    for page_num in range(doc.page_count):
        page = doc[page_num]
        page_text = page.get_text("text")

        if not page_text:
            continue

        # Разбиваем на строки
        lines = page_text.split('\n')
        cleaned_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 1. Убираем номера страниц (строка из одного числа)
            if re.match(r'^\s*\d+\s*$', line):
                continue

            # 2. Убираем числа в начале строки (например, "98  Текст")
            line = re.sub(r'^\s*\d+\s+', '', line)

            # 3. Убираем сноски и примечания после звёздочки (*) в конце строки
            line = re.sub(r'\*[^\*]*$', '', line)

            # 4. Убираем строки, которые начинаются со звёздочки (*) или (•)
            if re.match(r'^\s*[*•]', line):
                continue

            # 5. Убираем строки с диапазонами страниц (С. 98–101)
            if re.match(r'^\s*[Сс]\.\s*\d+\s*[-–]\s*\d+\s*$', line):
                continue

            if line:
                cleaned_lines.append(line)

        # Объединяем строки в текст
        page_text = ' '.join(cleaned_lines)

        # Дополнительная очистка от лишних пробелов
        page_text = re.sub(r'\s+', ' ', page_text)

        all_text.append(page_text)

    doc.close()

    result = '\n\n'.join(all_text)

    # Финальная очистка от ссылок
    result = clean_text_from_urls(result)

    return result


def clean_text_from_urls(text):
    """Удаляет ссылки из текста"""
    if not text:
        return text

    # Удаляем URL
    text = re.sub(r'https?://\S+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'www\.\S+', '', text, flags=re.IGNORECASE)

    # Удаляем конструкции [Image:, [image:, [IMG:
    text = re.sub(r'\[\s*[Ii]mage\s*:?\s*\]?', '', text)
    text = re.sub(r'\[\s*[Ii][Mm][Gg]\s*:?\s*\]?', '', text)
    text = re.sub(r'\[[^\]]*[Ii]mage[^\]]*\]', '', text)

    # Удаляем пустые квадратные скобки
    text = re.sub(r'\[\s*\]', '', text)

    # Удаляем предложения со словом "ссылка"
    text = re.sub(r'[А-Я][^.]*ссылка[^.]*\.', '', text, flags=re.IGNORECASE)

    # Удаляем строки после звёздочек
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        if not re.match(r'^\s*\*{1,2}\s*$', line) and not re.match(r'^\s*\*{1,2}\s*[А-Я]', line):
            cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)

    # Очистка от лишних пробелов
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n\s*\n+', '\n\n', text)

    return text.strip()


def extract_date_from_text(text):
    """
    Извлекает дату из текста (ищет в конце текста).
    Возвращает дату в формате YYYY-MM-DD или None.
    """
    if not text:
        return None

    # Разбиваем текст на строки и ищем дату в последних строках
    lines = text.split('\n')
    # Проверяем последние 20 строк (или меньше)
    check_lines = lines[-20:] if len(lines) > 20 else lines

    # Собираем текст из последних строк для поиска
    end_text = '\n'.join(check_lines)

    # Паттерны для поиска даты (от более специфичных к менее)
    patterns = [
        # Дата в формате ДД.ММ.ГГГГ или ДД/ММ/ГГГГ или ДД-ММ-ГГГГ
        r'(\d{2})[\.\-/](\d{2})[\.\-/](\d{4})',
        # Дата с месяцем прописью: 17 апреля 2014
        r'(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+(\d{4})',
        # Дата: 17.04.2014
        r'(\d{2})\.(\d{2})\.(\d{4})',
        # Год: 2014
        r'(\d{4})',
    ]

    months = {
        'января': '01', 'февраля': '02', 'марта': '03', 'апреля': '04',
        'мая': '05', 'июня': '06', 'июля': '07', 'августа': '08',
        'сентября': '09', 'октября': '10', 'ноября': '11', 'декабря': '12'
    }

    # Ищем дату в последних строках
    for pattern in patterns:
        matches = re.findall(pattern, end_text)
        if matches:
            # Берем последнее совпадение
            match = matches[-1]
            if len(match) == 3:
                # Проверяем, если первая часть - год (4 цифры)
                if len(match[0]) == 4:
                    year, month, day = match
                    return f"{year}-{int(month):02d}-{int(day):02d}"
                elif match[1] in months:  # Месяц прописью
                    day, month_name, year = match
                    month = months[month_name]
                    return f"{year}-{month}-{int(day):02d}"
                else:
                    day, month, year = match
                    return f"{year}-{int(month):02d}-{int(day):02d}"
            elif len(match) == 1 and len(match[0]) == 4:
                return f"{match[0]}-01-01"

    # Если не нашли в конце, ищем во всем тексте
    for pattern in patterns:
        matches = re.findall(pattern, text)
        if matches:
            match = matches[-1]
            if len(match) == 3:
                if len(match[0]) == 4:
                    year, month, day = match
                    return f"{year}-{int(month):02d}-{int(day):02d}"
                elif match[1] in months:
                    day, month_name, year = match
                    month = months[month_name]
                    return f"{year}-{month}-{int(day):02d}"
                else:
                    day, month, year = match
                    return f"{year}-{int(month):02d}-{int(day):02d}"
            elif len(match) == 1 and len(match[0]) == 4:
                return f"{match[0]}-01-01"

    return None


def download_file_content_with_service(drive_service, file_id):
    """Скачивает файл через Service Account"""
    try:
        request = drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        fh.seek(0)
        return fh.read()
    except Exception as e:
        print(f"    ❌ Download error: {e}")
        return None


def extract_text_from_html(html_content):
    """Извлекает текст из HTML"""
    soup = BeautifulSoup(html_content, 'html.parser')
    for script in soup(["script", "style"]):
        script.decompose()
    text = soup.get_text(separator='\n', strip=True)
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n'.join(lines)


def extract_images_from_html(html_content):
    """Извлекает изображения из HTML"""
    soup = BeautifulSoup(html_content, 'html.parser')
    images = []

    for idx, img_tag in enumerate(soup.find_all('img')):
        img_src = img_tag.get('src', '')
        img_alt = img_tag.get('alt', f'image_{idx}')

        if img_src.startswith('data:image'):
            try:
                header, encoded = img_src.split(',', 1)
                img_bytes = base64.b64decode(encoded)
                images.append((f"{img_alt}_{idx}.png", img_bytes))
            except Exception:
                pass
        elif img_src.startswith('http'):
            try:
                response = requests.get(img_src, timeout=10)
                if response.status_code == 200:
                    content_type = response.headers.get('Content-Type', 'image/jpeg')
                    ext = content_type.split('/')[-1] if '/' in content_type else 'jpg'
                    filename = f"{img_alt.replace(' ', '_')}_{idx}.{ext}"
                    images.append((filename, response.content))
            except Exception:
                pass

    return images


def extract_text_and_images_from_google_doc(drive_service, file_id):
    """Экспортирует Google Документ"""
    try:
        request = drive_service.files().export_media(fileId=file_id, mimeType='text/html')
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        fh.seek(0)
        html_content = fh.read().decode('utf-8')

        text = extract_text_from_html(html_content)
        text = clean_text_from_urls(text)
        images = extract_images_from_html(html_content)
        return text, images
    except Exception as e:
        print(f"    ❌ Google Docs export error: {e}")
        return '', []


def extract_images_from_docx(content_bytes):
    """Извлекает изображения из DOCX"""
    import zipfile
    images = []
    try:
        with zipfile.ZipFile(io.BytesIO(content_bytes), 'r') as docx_zip:
            for file_name in docx_zip.namelist():
                if file_name.startswith('word/media/') and file_name not in ['word/media/', 'word/media//']:
                    if any(file_name.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']):
                        img_bytes = docx_zip.read(file_name)
                        img_name = file_name.split('/')[-1]
                        images.append((img_name, img_bytes))
    except Exception as e:
        print(f"    ⚠️ DOCX image extraction error: {e}")
    return images


def extract_text_from_other(content_bytes, mime_type):
    """Извлекает текст из других форматов через kreuzberg"""
    result = kreuzberg.extract_bytes_sync(content_bytes, mime_type=mime_type)
    return result.content


def extract_text_and_images(drive_service, file_metadata, content_bytes=None):
    """
    Главная функция: извлекает текст и изображения из файла.
    Возвращает (text, images, date)
    """
    mime_type = file_metadata.get('mimeType', '')
    file_id = file_metadata['id']
    file_name = file_metadata.get('name', 'unknown')

    text = ""
    images = []
    date = None

    # PDF - используем PyMuPDF
    if mime_type == 'application/pdf':
        print(f"    📑 PDF: {file_name}")

        if content_bytes is None:
            content_bytes = download_file_content_with_service(drive_service, file_id)

        if content_bytes:
            text = extract_text_from_pdf(content_bytes)
            date = extract_date_from_text(text)
        else:
            text = ""

        return text, [], date

    # Google Docs
    if mime_type == 'application/vnd.google-apps.document':
        print(f"    📄 Google Doc: {file_name}")
        text, images = extract_text_and_images_from_google_doc(drive_service, file_id)
        date = extract_date_from_text(text)
        return text, images, date

    # Скачиваем файл для остальных типов
    if content_bytes is None:
        content_bytes = download_file_content_with_service(drive_service, file_id)
        if content_bytes is None:
            return '', [], None

    # DOCX
    if mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        print(f"    📝 DOCX: {file_name}")
        text = extract_text_from_other(content_bytes, mime_type)
        text = clean_text_from_urls(text)
        images = extract_images_from_docx(content_bytes)
        date = extract_date_from_text(text)
        return text, images, date

    # Другие форматы
    if mime_type in ['text/plain', 'application/msword']:
        print(f"    📝 File: {file_name}")
        text = extract_text_from_other(content_bytes, mime_type)
        text = clean_text_from_urls(text)
        date = extract_date_from_text(text)
        return text, [], date

    print(f"    ⏭️ Skipped: {file_name} ({mime_type})")
    return '', [], None


def is_image(mime_type):
    """Проверяет, является ли файл изображением"""
    image_types = [
        'image/jpeg', 'image/png', 'image/gif',
        'image/webp', 'image/bmp', 'image/tiff'
    ]
    return mime_type in image_types