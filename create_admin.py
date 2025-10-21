from app import app, db
from models import User


def create_admin_user():
    with app.app_context():
        # Проверяем, есть ли уже администратор
        if not User.query.filter_by(is_admin=True).first():
            admin = User(
                username='admin',
                email='admin@example.com',
                is_admin=True
            )
            admin.set_password('2563214')  # Установите надежный пароль!
            db.session.add(admin)
            db.session.commit()
            print('Администратор создан!')

            # Проверим длину хеша
            user = User.query.filter_by(username='admin').first()
            print(f'Длина хеша пароля: {len(user.password_hash)}')
        else:
            print('Администратор уже существует')


if __name__ == '__main__':
    create_admin_user()