import psycopg2
from config import DATABASE_DSN
from PIL import Image
import io

conn = psycopg2.connect(DATABASE_DSN)
cursor = conn.cursor()

# Берём первое изображение
cursor.execute("SELECT id, name, media FROM media WHERE id = 6")
img_id, name, media_data = cursor.fetchone()
conn.close()

if media_data:
    img = Image.open(io.BytesIO(media_data))
    img.show()  # Откроется стандартное приложение для просмотра
    print(f"Изображение {img_id}: {name}, размер {img.size}")