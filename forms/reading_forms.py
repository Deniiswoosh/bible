from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

class CommentForm(FlaskForm):
    body = TextAreaField('Comment', validators=[
        DataRequired(message="Please write a comment."),
        Length(max=1000, message="Comments must be under 1000 characters.")
    ])
    submit = SubmitField('Post comment')

class ReadingForm(FlaskForm):
    passage = StringField('Bible Passage', validators=[
        DataRequired(message="Please specify the passage read."),
        Length(max=250, message="Passage text is too long.")
    ])
    reflection = TextAreaField("What did you learn from today's passage?", validators=[
        DataRequired(message="Please share your reflection."),
        Length(max=500, message="Reflection must be under 500 characters.")
    ])
    application = TextAreaField('What will you apply from this?', validators=[
        DataRequired(message="Please share your practical application."),
        Length(max=500, message="Application must be under 500 characters.")
    ])
    prayer = TextAreaField('Prayer (Optional)', validators=[
        Optional(),
        Length(max=300, message="Prayer must be under 300 characters.")
    ])
    submit = SubmitField('Submit')
