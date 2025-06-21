"""Common forms for the FlaskSaaS application."""

from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SelectMultipleField, BooleanField, IntegerField, PasswordField, SubmitField, RadioField
from wtforms.validators import DataRequired, NumberRange, Optional as OptionalValidator, Email, EqualTo, Length

class LoginForm(FlaskForm):
    """Form for user login."""
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegisterForm(FlaskForm):
    """Form for user registration."""
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    password2 = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Create Account')

class PlaylistForm(FlaskForm):
    """Form for creating a new playlist."""
    name = StringField('Playlist Name', validators=[DataRequired()])
    description = StringField('Description')
    genre = SelectField('Genre', choices=[
            ('all', 'All Genres'),
            ('house', 'House'),
            ('deep-house', 'Deep House'),
            ('nu-disco', 'Nu Disco')
        ])
    days = IntegerField('Days to Look Back', default=7, validators=[NumberRange(min=1, max=90)])
    public = BooleanField('Public Playlist', default=True)
    source_selection = RadioField('Music Sources', choices=[
            ('both', 'Use both predefined and my custom sources'),
            ('predefined', 'Use only predefined sources'),
            ('custom', 'Use only my custom sources')
        ], default='both')
