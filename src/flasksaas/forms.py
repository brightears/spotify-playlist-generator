"""Common forms for the FlaskSaaS application."""

from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SelectMultipleField, BooleanField, IntegerField, PasswordField, SubmitField, RadioField, TextAreaField
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
    genre = SelectField('YouTube Channel', choices=[
            ('all', 'All Channels'),
            ('selected-base', 'Selected Base'),
            ('defected-music', 'Defected Music'),
            ('mrrevillz', 'MrRevillz'),
            ('glitterbox-ibiza', 'Glitterbox Ibiza')
        ])
    days = IntegerField('Days to Look Back', default=7, validators=[NumberRange(min=1, max=90)])
    public = BooleanField('Public Playlist', default=True)
    source_selection = RadioField('Music Sources', choices=[
            ('both', 'Use both selected channel and my custom sources'),
            ('predefined', 'Use only selected channel'),
            ('custom', 'Use only my custom sources')
        ], default='both')


class ContactForm(FlaskForm):
    """Form for contacting support."""
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    subject = StringField('Subject', validators=[DataRequired(), Length(min=5, max=200)])
    message = TextAreaField('Message', validators=[DataRequired(), Length(min=10, max=2000)])
    submit = SubmitField('Send Message')
