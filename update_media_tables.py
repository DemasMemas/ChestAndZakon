from app import app, db
from models import NewsImage, NewsVideo

def update_database():
    with app.app_context():
        db.create_all()
        print("Таблицы для медиа созданы!")

if __name__ == '__main__':
    update_database()