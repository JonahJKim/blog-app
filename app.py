from flask import Flask, render_template, flash, redirect, url_for, request
from flask_migrate import Migrate
from extensions import db, login
from werkzeug.urls import url_parse
from datetime import datetime
import models
from config import Config
from forms import LoginForm, RegistrationForm, PostForm, UserSearchForm, AvatarPredictionForm
from models import User, Post
from flask_login import login_user, logout_user, current_user, login_required
import timeago
from flask_bootstrap import Bootstrap
from PIL import Image
import urllib.request
from torchvision import transforms
import torch
import io

'''
TODO: 
1. Finish up core features: profile page
2. Decorate using CSS Bootstrap
3. Add ML model
'''

app = Flask(__name__)
app.config.from_object(Config)


db.init_app(app)
login.init_app(app)
login.login_view = 'login'
migrate = Migrate(app, db)
bootstrap = Bootstrap(app)
# model = torch.load('model.pkl', map_location=torch.device('cpu'))

# model = CPU_Unpickler(open('model.pkl', 'rb')).load()
model = torch.load(open('classifier.pt', 'rb'), torch.device('cpu'))
model.eval()
# print(model)

@app.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()

@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    usersearchform = UserSearchForm()
    form = PostForm()

    if usersearchform.validate_on_submit():
        user = User.query.filter_by(username=usersearchform.username.data).first()
        if user is None:
            flash('User does not exist!')
            return redirect(url_for('index'))
        return redirect(url_for('profile', username=usersearchform.username.data))

    
    if form.validate_on_submit():
        post = Post(body=form.post.data, user=current_user)
        db.session.add(post)
        db.session.commit()
        return redirect(url_for('index'))

    page = request.args.get('page', 1, type=int)
    posts = current_user.followed_posts().paginate(
        page, 3, False)
    next_url = url_for('index', page=posts.next_num) if posts.has_next else None
    prev_url = url_for('index', page=posts.prev_num) if posts.has_prev else None


    now = datetime.now()
    then = datetime.now()
    print(timeago.format(now, then))
    return render_template('index.html', timeago=timeago, datetime=datetime, posts=posts.items, form=form, usersearchform=usersearchform, next_url=next_url, prev_url=prev_url)


@app.route('/explore', methods=['GET'])
@login_required
def explore():
    page = request.args.get('page', 1, type=int)
    posts = Post.query.order_by(Post.timestamp.desc()).paginate(
        page, 3, False)
    next_url = url_for('explore', page=posts.next_num) if posts.has_next else None
    prev_url = url_for('explore', page=posts.prev_num) if posts.has_prev else None

    return render_template('explore.html', timeago=timeago, datetime=datetime, posts=posts.items, next_url=next_url, prev_url=prev_url)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()

        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password!')
            return redirect(url_for('login'))

        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            return redirect(url_for('index'))
        return redirect(next_page)


    return render_template('login.html', title='Sign in', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.hash_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        login_user(user, remember=True)
        flash('Successfully registered and logged in!')
        return redirect(url_for('index'))

    return render_template('registration.html', title='Register', form=form)

@app.route('/logout', methods=['GET'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/profile/<username>', methods=['GET', 'POST'])
@login_required
def profile(username):

    avatar_form = AvatarPredictionForm()
    if avatar_form.validate_on_submit():
        urllib.request.urlretrieve(
  current_user.avatar(224),
   "image.png")

        transform = transforms.ToTensor()
        image = torch.unsqueeze(transform(Image.open('image.png')), dim=0)
        
        prediction = torch.squeeze(model(image))
        prediction = torch.argmax(prediction)
        prediction = 'dog' if prediction == 0 else 'cat'

        flash(f'Prediction: {prediction}')

        # print(model)

    user = User.query.filter_by(username=username).first_or_404()
    return render_template('profile.html', user=user, avatar_form=avatar_form)


@app.route('/follow/<username>')
@login_required
def follow(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        flash('User does not exist!')
        return redirect(url_for('index'))

    current_user.follow(user)
    db.session.commit()

    return redirect(url_for('profile', username=username))
    


@app.route('/unfollow/<username>')
@login_required
def unfollow(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        flash('User does not exist!')
        return redirect(url_for('index'))

    current_user.unfollow(user)
    db.session.commit()

    return redirect(url_for('profile', username=username))

if __name__ == '__main__':
    app.run(debug=True)

import errors