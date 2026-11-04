import re
from email_validator import EmailNotValidError, validate_email
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Optional, Regexp, ValidationError


def deliverable_email_value(value):
    try:
        result = validate_email(value, check_deliverability=True)
    except EmailNotValidError:
        return None
    return result.normalized


def validate_deliverable_email(form, field):
    normalized = deliverable_email_value(field.data)
    if not normalized:
        raise ValidationError('Please enter a real, deliverable email address.')
    field.data = normalized


def kenyan_phone_error(value):
    if value and not re.fullmatch(r'(?:0[17]\d{8}|\+254[17]\d{8})', value.strip()):
        return 'Use a valid Kenyan number, such as 0712345678 or +254712345678.'
    return None


def validate_kenyan_phone(form, field):
    error = kenyan_phone_error(field.data)
    if error:
        raise ValidationError(error)


def strong_password_error(password):
    password = password or ''
    checks = (
        (len(password) >= 8, 'at least 8 characters'),
        (re.search(r'[A-Z]', password), 'an uppercase letter'),
        (re.search(r'[a-z]', password), 'a lowercase letter'),
        (re.search(r'\d', password), 'a number'),
        (re.search(r'[^A-Za-z0-9]', password), 'a symbol'),
    )
    missing = [requirement for passed, requirement in checks if not passed]
    if missing:
        return 'Password must contain ' + ', '.join(missing) + '.'
    return None


def validate_strong_password(form, field):
    error = strong_password_error(field.data)
    if error:
        raise ValidationError(error)

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[
        DataRequired(),
        Regexp(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', message="Please enter a valid email address.")
    ])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')


class MemberCreateForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), validate_deliverable_email])
    phone = StringField('Phone Number', validators=[Optional(), validate_kenyan_phone])
    residence = StringField('Area of Residence')
    password = PasswordField('Temporary Password', validators=[DataRequired(), validate_strong_password])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(), EqualTo('password', message='Passwords must match.')
    ])
    submit = SubmitField('Create Member')


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    password = PasswordField('New Password', validators=[DataRequired(), validate_strong_password])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(), EqualTo('password', message='Passwords must match.')
    ])
    submit = SubmitField('Change Password')


class PasswordResetRequestForm(FlaskForm):
    identifier = StringField('Email or phone number', validators=[DataRequired()])
    submit = SubmitField('Send reset link')


class PasswordResetForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired(), validate_strong_password])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(), EqualTo('password', message='Passwords must match.')
    ])
    submit = SubmitField('Reset password')
