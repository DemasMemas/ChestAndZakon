# Создайте файл update_database.py
from app import app, db
from models import User


def update_database():
    with app.app_context():
        # Удаляем существующую таблицу пользователей
        db.drop_all()

        # Создаем все таблицы заново с новой структурой
        db.create_all()

        print("База данных обновлена!")


if __name__ == '__main__':
    update_database()