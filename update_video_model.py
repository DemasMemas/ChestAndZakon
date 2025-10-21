from app import app, db
from models import NewsVideo

def update_database():
    with app.app_context():
        # Создаем новые таблицы или обновляем существующие
        db.create_all()
        print("База данных обновлена для поддержки загружаемых видео!")

if __name__ == '__main__':
    update_database()