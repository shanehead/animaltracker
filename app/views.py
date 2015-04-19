from app import app, db, lm
from auth import OAuthSignIn
from flask import render_template, url_for, flash, redirect, session, request, g, send_from_directory
from flask.ext.login import login_user, logout_user, current_user, login_required
from forms import UserEditForm, AddAnimalForm
from models import User, Animal
from datetime import date
from uuid import uuid4
from werkzeug import secure_filename
from dateutil.relativedelta import relativedelta
import json

@app.route('/')
@app.route('/index')
@login_required
def index():
	# Send them to their home page if they are logged in
	# login_required decorator will send them to the login page if they aren't
	if g.user is not None and g.user.is_authenticated():
		return redirect(url_for('user', id=g.user.id))

@lm.user_loader
def load_user(id):
	return User.query.filter_by(id=id).first()

@app.route('/login', methods=['GET', 'POST'])
def login():
	# Send them to their home page if they are logged in
	if g.user is not None and g.user.is_authenticated():
		return redirect(url_for('user', id=g.user.id))
	return render_template('login.html', title='Sign In')

@app.route('/authorize/<provider>')
def oauth_authorize(provider):
	if not current_user.is_anonymous():
		return redirect(url_for('index'))
	oauth = OAuthSignIn.get_provider(provider)
	return oauth.authorize()

@app.route('/callback/<provider>')
def oauth_callback(provider):
	if not current_user.is_anonymous():
		return redirect(url_for('user', id=g.user.id))
	oauth = OAuthSignIn.get_provider(provider)
	username, email, picture = oauth.callback()
	if email is None:
		flash('Authentication failed')
		return redirect(url_for('index'))
	user = User.query.filter_by(email=email).first()
	if user is None:
		name = username
		if name is None or name == "":
			name = email.split('@')[0]
		user = User(email=email, name=name, avatar=picture)
		# @todo: avatar from picture
		db.session.add(user)
		db.session.commit()
	login_user(user, remember=True)
	g.user = user
	return redirect(url_for('user', id=g.user.id))

@app.route('/logout')
def logout():
	logout_user()
	g.user = None
	return redirect(url_for('index'))

@app.route('/user/<id>')
@login_required
def user(id):
	if id == g.user.id:
		user = g.user
	else:
		user = User.query.filter_by(id=id).first()
	if user == None:
		flash('User %s not found.' % id)
		return redirect(url_for('index'))
	animals = user.animals.all()
	return render_template('user.html', user=user, animals=animals)

@app.route('/edit_user', methods=['GET', 'POST'])
@login_required
def edit_user():
	form = UserEditForm()
	if request.method == 'POST' and form.validate_on_submit():
		g.user.about_me = form.about_me.data
		db.session.add(g.user)
		db.session.commit()
		flash('Your changes have been saved')
		return redirect(url_for('user', id=g.user.id))
	else:
		form.about_me.data = g.user.about_me
	return render_template('edit_user.html', form=form, user=g.user)

@app.route('/edit_animal/<id>', methods=['GET', 'POST'])
@login_required
def edit_animal(id):
	animal = Animal.query.filter_by(id=id).first()
	form = AddAnimalForm()
	if request.method == 'POST' and form.validate_on_submit():
		animal.name = form.name.data
		animal.species = form.species.data
		animal.species_common = form.species_common.data
		animal.dob = form.dob.data
		if form.avatar.data:
			animal.avatar = "%s_%s" % (uuid4(), secure_filename(form.avatar.data.filename))
			photo_path = app.config['MEDIA_FOLDER'] + '/' + animal.avatar
			form.avatar.data.save(photo_path)
		db.session.add(animal)
		db.session.commit()
		flash('Your changes have been saved')
		return redirect(url_for('animal', id=animal.id))
	else:
		form.name.data = animal.name
		form.species.data = animal.species
		form.species_common.data = animal.species_common
		form.dob.data = animal.dob
	return render_template('edit_animal.html', form=form, animal=animal)

@app.route('/add_animal', methods=['GET', 'POST'])
@login_required
def add_animal():
	form = AddAnimalForm()
	if request.method == 'POST' and form.validate_on_submit():
		photo_filename = "%s_%s" % (uuid4(), secure_filename(form.avatar.data.filename))
		photo_path = app.config['MEDIA_FOLDER'] + '/' + photo_filename
		animal = Animal(name=form.name.data, species=form.species.data,
						species_common=form.species_common.data, dob=form.dob.data, owner=g.user.id)
		animal.avatar = photo_filename
		form.avatar.data.save(photo_path)
		db.session.add(animal)
		db.session.commit()
		flash('%s has been added' % form.name.data)
		return redirect(url_for('user', id=g.user.id))
	return render_template('add_animal.html', title='Add an animal', form=form)

@app.route('/animal/<id>')
def animal(id):
	animal = Animal.query.filter_by(id=id).first()
	if animal == None:
		flash('Animal with ID %d not found.' % id)
		return redirect(url_for('index'))
	# Calculate the age here
	delta = relativedelta(date.today(), animal.dob)
	if delta.years != 0:
		if delta.months != 0:
			animal.age = '%d years, %d months' % (delta.years, delta.months)
		else:
			animal.age = '%d years' % (delta.years, delta.months)
	else:
		if delta.months != 0:
			if delta.days != 0:
				animal.age = '%d months, %d days' % (delta.months, delta.years)
			else:
				animal.age = '%d months' % (delta.months, delta.years)
		else:
			animal.age = '%d days' % delta.days
	return render_template('animal.html', animal=animal)

@app.route('/uploads/<img_name>')
def uploads(img_name):
	return send_from_directory(app.config['MEDIA_FOLDER'], img_name)

@app.route('/qrcode/<id>')
def qrcode(id):
	return render_template('qrcode.html', id=id)

@app.before_request
def before_request():
	g.user = current_user

@app.errorhandler(404)
def not_found_error(error):
	return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
	db.session.rollback()
	return render_template('500.html'), 500

