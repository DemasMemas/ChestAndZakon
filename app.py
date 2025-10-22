import os
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename

from config import Config

# Сначала создаем экземпляр Flask
app = Flask(__name__)
app.config.from_object(Config)

from models import db, News, Event, Comment, User, NewsVideo, NewsImage

db.init_app(app)
mail = Mail(app)

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
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv', 'webm'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_video_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_VIDEO_EXTENSIONS

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

        # Перенаправляем на ту же страницу чтобы избежать повторной отправки формы
        return redirect(url_for('news_detail', news_id=news_id))

    # Если метод GET, отображаем страницу с комментариями
    page = request.args.get('page', 1, type=int)
    comments_per_page = 10

    comments_pagination = Comment.query.filter_by(news_id=news_id) \
        .order_by(Comment.created_at.desc()) \
        .paginate(page=page, per_page=comments_per_page, error_out=False)

    return render_template('news_detail.html',
                           news_item=news_item,
                           comments=comments_pagination.items,
                           comments_pagination=comments_pagination)


@app.route('/news')
def news():
    page = request.args.get('page', 1, type=int)
    per_page = 6  # Количество новостей на странице

    news_pagination = News.query.order_by(News.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return render_template('news.html',
                           news_list=news_pagination.items,
                           pagination=news_pagination)


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
    page = request.args.get('page', 1, type=int)
    per_page = 6  # Количество мероприятий на странице

    # Предстоящие мероприятия с пагинацией
    upcoming_events_query = Event.query.filter(Event.event_date >= datetime.now()).order_by(Event.event_date.asc())
    upcoming_pagination = upcoming_events_query.paginate(page=page, per_page=per_page, error_out=False)

    # Прошедшие мероприятия (без пагинации или с ограничением)
    past_events = Event.query.filter(Event.event_date < datetime.now()).order_by(Event.event_date.desc()).limit(
        10).all()

    return render_template('events.html',
                           events_list=upcoming_pagination.items,
                           past_events=past_events,
                           pagination=upcoming_pagination)


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


@app.route('/admin/events/edit/<int:event_id>', methods=['GET', 'POST'])
@login_required
def edit_event(event_id):
    if not current_user.is_admin:
        return "Доступ запрещен", 403

    event = Event.query.get_or_404(event_id)

    if request.method == 'POST':
        event.title = request.form['title']
        event.description = request.form['description']
        event.location = request.form['location']

        # Обработка даты
        from datetime import datetime
        event.event_date = datetime.strptime(request.form['event_date'], '%Y-%m-%dT%H:%M')

        # Обработка загрузки изображения
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                event.image_path = f'uploads/{filename}'

        db.session.commit()
        return redirect(url_for('event_detail', event_id=event.id))

    # Преобразуем дату для HTML input[type="datetime-local"]
    event_date_formatted = event.event_date.strftime('%Y-%m-%dT%H:%M')

    return render_template('edit_event.html', event=event, event_date_formatted=event_date_formatted)


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']

        try:
            # Создаем и отправляем email
            msg = Message(
                subject=f"Новое сообщение от {name}",
                sender=app.config['MAIL_DEFAULT_SENDER'],
                recipients=[app.config['MAIL_USERNAME']],  # Отправляем себе
                reply_to=email  # Чтобы можно было ответить отправителю
            )

            msg.body = f"""
            Имя: {name}
            Email: {email}

            Сообщение:
            {message}

            ---
            Это сообщение отправлено через форму обратной связи на сайте.
            """

            mail.send(msg)

            # Логируем успешную отправку
            print(f"Email отправлен: от {name} ({email})")

            return redirect(url_for('contact_success'))

        except Exception as e:
            # В случае ошибки показываем сообщение и логируем
            print(f"Ошибка отправки email: {str(e)}")
            flash('Произошла ошибка при отправке сообщения. Пожалуйста, попробуйте позже.', 'error')
            return render_template('contact.html')

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

        # Создаем новость
        news = News(title=title, content=content)
        db.session.add(news)
        db.session.flush()  # Получаем ID новости

        # Обработка множественных изображений
        if 'images' in request.files:
            images = request.files.getlist('images')
            for i, image in enumerate(images):
                if image and image.filename and allowed_file(image.filename):
                    filename = secure_filename(image.filename)
                    image_path = f'uploads/{filename}'
                    image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

                    news_image = NewsImage(
                        news_id=news.id,
                        image_path=image_path,
                        order=i
                    )
                    db.session.add(news_image)

        # Обработка множественных видео (необязательных)
        video_upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'videos')
        os.makedirs(video_upload_folder, exist_ok=True)

        video_urls = request.form.getlist('video_urls')
        video_types = request.form.getlist('video_types')
        video_titles = request.form.getlist('video_titles')
        video_files = request.files.getlist('video_files')

        for i, (vtype, url, title) in enumerate(zip(video_types, video_urls, video_titles)):
            # Пропускаем пустые поля
            if not url.strip() and (i >= len(video_files) or not video_files[i].filename):
                continue

            if vtype == 'uploaded':
                # Обработка загруженного видеофайла
                if i < len(video_files) and video_files[i] and video_files[i].filename and allowed_video_file(
                        video_files[i].filename):
                    file = video_files[i]
                    filename = secure_filename(file.filename)
                    video_path = f'uploads/videos/{filename}'
                    file.save(os.path.join(video_upload_folder, filename))

                    news_video = NewsVideo(
                        news_id=news.id,
                        video_path=video_path,
                        video_type='uploaded',
                        title=title or f"Видео {i + 1}",
                        order=i
                    )
                    db.session.add(news_video)
            else:
                # Обработка видео по ссылке
                if url.strip():
                    news_video = NewsVideo(
                        news_id=news.id,
                        video_url=url.strip(),
                        video_type=vtype,
                        title=title or f"Видео {i + 1}",
                        order=i
                    )
                    db.session.add(news_video)

        db.session.commit()
        return redirect(url_for('news'))

    return render_template('add_news.html')


@app.route('/admin/news/delete/<int:news_id>')
@login_required
def delete_news(news_id):
    if not current_user.is_admin:
        return "Доступ запрещен", 403

    news = News.query.get_or_404(news_id)

    # Удаляем все комментарии
    Comment.query.filter_by(news_id=news_id).delete()

    # Удаляем все изображения (файлы останутся на сервере - можно добавить их удаление)
    NewsImage.query.filter_by(news_id=news_id).delete()

    # Удаляем все видео
    NewsVideo.query.filter_by(news_id=news_id).delete()

    # Удаляем саму новость
    db.session.delete(news)
    db.session.commit()

    return redirect(url_for('news'))


@app.route('/admin/news/edit/<int:news_id>', methods=['GET', 'POST'])
@login_required
def edit_news(news_id):
    if not current_user.is_admin:
        return "Доступ запрещен", 403

    news = News.query.get_or_404(news_id)

    if request.method == 'POST':
        # Обновляем основные данные новости
        news.title = request.form['title']
        news.content = request.form['content']

        # Обработка новых изображений (необязательных)
        if 'images' in request.files:
            images = request.files.getlist('images')
            for i, image in enumerate(images):
                if image and image.filename and allowed_file(
                        image.filename):  # Проверяем, что файл действительно загружен
                    filename = secure_filename(image.filename)
                    image_path = f'uploads/{filename}'
                    image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

                    news_image = NewsImage(
                        news_id=news.id,
                        image_path=image_path,
                        order=len(news.images) + i
                    )
                    db.session.add(news_image)

        # Обработка новых видео (необязательных)
        video_upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'videos')
        os.makedirs(video_upload_folder, exist_ok=True)

        video_urls = request.form.getlist('video_urls')
        video_types = request.form.getlist('video_types')
        video_titles = request.form.getlist('video_titles')
        video_files = request.files.getlist('video_files')

        for i, (vtype, url, title) in enumerate(zip(video_types, video_urls, video_titles)):
            # Пропускаем пустые поля
            if vtype == 'uploaded':
                # Обработка загруженного видеофайла (если файл действительно загружен)
                if i < len(video_files) and video_files[i] and video_files[i].filename and allowed_video_file(
                        video_files[i].filename):
                    file = video_files[i]
                    filename = secure_filename(file.filename)
                    video_path = f'uploads/videos/{filename}'
                    file.save(os.path.join(video_upload_folder, filename))

                    news_video = NewsVideo(
                        news_id=news.id,
                        video_path=video_path,
                        video_type='uploaded',
                        title=title or f"Видео {len(news.videos) + i + 1}",
                        order=len(news.videos) + i
                    )
                    db.session.add(news_video)
            else:
                # Обработка видео по ссылке (если URL не пустой)
                if url and url.strip():
                    news_video = NewsVideo(
                        news_id=news.id,
                        video_url=url.strip(),
                        video_type=vtype,
                        title=title or f"Видео {len(news.videos) + i + 1}",
                        order=len(news.videos) + i
                    )
                    db.session.add(news_video)

        db.session.commit()
        return redirect(url_for('news_detail', news_id=news.id))

    return render_template('edit_news.html', news=news)


@app.route('/admin/news/image/delete/<int:image_id>')
@login_required
def delete_news_image(image_id):
    if not current_user.is_admin:
        return "Доступ запрещен", 403

    image = NewsImage.query.get_or_404(image_id)
    news_id = image.news_id
    db.session.delete(image)
    db.session.commit()

    return redirect(url_for('edit_news', news_id=news_id))


@app.route('/admin/news/video/delete/<int:video_id>')
@login_required
def delete_news_video(video_id):
    if not current_user.is_admin:
        return "Доступ запрещен", 403

    video = NewsVideo.query.get_or_404(video_id)
    news_id = video.news_id
    db.session.delete(video)
    db.session.commit()

    return redirect(url_for('edit_news', news_id=news_id))

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


@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 10

    if not query:
        return render_template('search.html', query=query)

    # Разбиваем запрос на слова для улучшения поиска
    search_terms = query.split()

    # Поиск по новостям
    news_filters = []
    for term in search_terms:
        news_filters.append(News.title.ilike(f'%{term}%'))
        news_filters.append(News.content.ilike(f'%{term}%'))

    news_results = News.query.filter(db.or_(*news_filters)).order_by(News.created_at.desc())

    # Поиск по мероприятиям
    event_filters = []
    for term in search_terms:
        event_filters.append(Event.title.ilike(f'%{term}%'))
        event_filters.append(Event.description.ilike(f'%{term}%'))
        event_filters.append(Event.location.ilike(f'%{term}%'))

    events_results = Event.query.filter(db.or_(*event_filters)).order_by(Event.event_date.desc())

    # Пагинация
    news_pagination = news_results.paginate(page=page, per_page=per_page, error_out=False)
    events_list = events_results.limit(10).all()

    return render_template('search.html',
                           query=query,
                           news_results=news_pagination.items,
                           events_results=events_list,
                           news_pagination=news_pagination,
                           total_news=news_results.count(),
                           total_events=events_results.count())

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)