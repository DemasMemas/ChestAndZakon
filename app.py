import os
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename

from config import Config

# Сначала создаем экземпляр Flask
app = Flask(__name__)
app.config.from_object(Config)

from models import db, News, Event, Comment, User
db.init_app(app)

# Настройка Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице.'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.context_processor
def inject_models():
    from models import Comment
    from datetime import datetime
    return dict(
        News=News,
        Event=Event,
        Comment=Comment,
        User=User,
        now=datetime.now()
    )


# Маршруты
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/news')
def news():
    news_list = News.query.order_by(News.created_at.desc()).all()
    return render_template('news.html', news_list=news_list)


@app.route('/news/<int:news_id>', methods=['GET', 'POST'])
def news_detail(news_id):
    news_item = News.query.get_or_404(news_id)

    # Обработка добавления комментария
    if request.method == 'POST':
        author = request.form['author']
        content = request.form['content']

        # Создаем комментарий
        comment = Comment(news_id=news_id, author=author, content=content)
        db.session.add(comment)
        db.session.commit()

        return redirect(url_for('news_detail', news_id=news_id))

    # Получаем комментарии для этой новости
    comments = Comment.query.filter_by(news_id=news_id).order_by(Comment.created_at.desc()).all()

    return render_template('news_detail.html', news_item=news_item, comments=comments)


@app.route('/comment/delete/<int:comment_id>')
@login_required
def delete_comment(comment_id):
    if not current_user.is_admin:
        return "Доступ запрещен", 403

    comment = Comment.query.get_or_404(comment_id)
    news_id = comment.news_id
    db.session.delete(comment)
    db.session.commit()
    return redirect(url_for('news_detail', news_id=news_id))


@app.route('/events')
def events():
    # Получаем все мероприятия, отсортированные по дате (ближайшие первыми)
    events_list = Event.query.filter(Event.event_date >= datetime.now()).order_by(Event.event_date.asc()).all()

    # Прошедшие мероприятия
    past_events = Event.query.filter(Event.event_date < datetime.now()).order_by(Event.event_date.desc()).all()

    return render_template('events.html', events_list=events_list, past_events=past_events)


@app.route('/events/<int:event_id>')
def event_detail(event_id):
    event = Event.query.get_or_404(event_id)
    return render_template('event_detail.html', event=event)


@app.route('/admin/event/delete/<int:event_id>')
@login_required
def delete_event(event_id):
    if not current_user.is_admin:
        return "Доступ запрещен", 403

    event = Event.query.get_or_404(event_id)
    db.session.delete(event)
    db.session.commit()
    return redirect(url_for('events'))


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']
        print(f"Новое сообщение от {name} ({email}): {message}")
        return redirect(url_for('contact_success'))

    return render_template('contact.html')


@app.route('/contact/success')
def contact_success():
    return render_template('contact_success.html')


@app.route('/admin/news/add', methods=['GET', 'POST'])
@login_required
def add_news():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']

        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_path = f'uploads/{filename}'

        news = News(title=title, content=content, image_path=image_path)
        db.session.add(news)
        db.session.commit()

        return redirect(url_for('news'))

    return render_template('add_news.html')


@app.route('/admin/news/delete/<int:news_id>')
@login_required
def delete_news(news_id):
    # Проверяем, что пользователь - администратор
    if not current_user.is_admin:
        return "Доступ запрещен", 403

    news = News.query.get_or_404(news_id)
    Comment.query.filter_by(news_id=news_id).delete()

    db.session.delete(news)
    db.session.commit()

    return redirect(url_for('news'))

@app.route('/admin/events/add', methods=['GET', 'POST'])
@login_required
def add_event():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        event_date = request.form['event_date']
        location = request.form['location']

        # Обработка даты (преобразуем из строки в datetime)
        from datetime import datetime
        event_date = datetime.strptime(event_date, '%Y-%m-%dT%H:%M')

        # Обработка загрузки изображения
        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_path = f'uploads/{filename}'

        # Создаем мероприятие
        event = Event(
            title=title,
            description=description,
            event_date=event_date,
            location=location,
            image_path=image_path
        )
        db.session.add(event)
        db.session.commit()

        return redirect(url_for('events'))

    return render_template('add_event.html')

@app.route('/admin')
@login_required
def admin_panel():
    return render_template('admin_panel.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_panel'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('admin_panel'))
        else:
            flash('Неверное имя пользователя или пароль')

    return render_template('login.html')


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    if not current_user.is_admin:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        is_admin = 'is_admin' in request.form

        # Проверка длины пароля
        if len(password) < 6:
            return render_template('register.html', error='Пароль должен содержать минимум 6 символов')

        if User.query.filter_by(username=username).first():
            return render_template('register.html', error='Пользователь с таким именем уже существует')

        user = User(username=username, email=email, is_admin=is_admin)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        return redirect(url_for('admin_panel'))

    return render_template('register.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)