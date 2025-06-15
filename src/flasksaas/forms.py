"""Common forms for the FlaskSaaS application."""

from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SelectMultipleField, BooleanField, IntegerField
from wtforms.validators import DataRequired, NumberRange, Optional as OptionalValidator

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
