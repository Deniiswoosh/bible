import hashlib
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.parse import quote
from urllib.request import Request, urlopen
import base64

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db
from models import User, PasswordResetRequest
from forms import LoginForm, PasswordResetForm, PasswordResetRequestForm
from forms.auth_forms import deliverable_email_value

auth_bp = Blueprint('auth', __name__)


def _utcnow():
    return datetime.now(timezone.utc)


def _normalize_phone(value):
    value = (value or '').strip()
    if value.startswith('0'):
        return '+254' + value[1:]
    return value


def _find_reset_user(identifier):
    identifier = identifier.strip()
    email = deliverable_email_value(identifier) if '@' in identifier else None
    if email:
        return User.query.filter_by(email=email).first(), 'email', email

    phone = _normalize_phone(identifier)
    phone_variants = {phone}
    if phone.startswith('+254'):
        phone_variants.add('0' + phone[4:])
    user = User.query.filter(User.phone.in_(phone_variants)).first()
    return user, 'phone', phone


def _send_email(user, reset_url):
    if not all((current_app.config['MAIL_SERVER'], current_app.config['MAIL_DEFAULT_SENDER'])):
        raise RuntimeError('Email reset delivery is not configured.')
    message = EmailMessage()
    message['Subject'] = 'Reset your Bible Accountability password'
    message['From'] = current_app.config['MAIL_DEFAULT_SENDER']
    message['To'] = user.email
    message.set_content(
        f'Hello {user.name},\n\nUse this link to reset your password:\n{reset_url}\n\n'
        f'The link expires in {current_app.config["PASSWORD_RESET_TTL_MINUTES"]} minutes and can only be used once.'
    )
    smtp_class = smtplib.SMTP_SSL if current_app.config['MAIL_USE_SSL'] else smtplib.SMTP
    with smtp_class(current_app.config['MAIL_SERVER'], current_app.config['MAIL_PORT'], timeout=10) as server:
        if current_app.config['MAIL_USE_TLS'] and not current_app.config['MAIL_USE_SSL']:
            server.starttls()
        if current_app.config['MAIL_USERNAME']:
            server.login(current_app.config['MAIL_USERNAME'], current_app.config['MAIL_PASSWORD'])
        server.send_message(message)


def _send_sms(user, reset_url):
    config = current_app.config
    if not all((config['TWILIO_ACCOUNT_SID'], config['TWILIO_AUTH_TOKEN'], config['TWILIO_FROM_NUMBER'])):
        raise RuntimeError('SMS reset delivery is not configured.')
    body = (
        f'Bible Accountability password reset: {reset_url} '
        f'(expires in {config["PASSWORD_RESET_TTL_MINUTES"]} minutes)'
    )
    payload = f'From={quote(config["TWILIO_FROM_NUMBER"])}&To={quote(_normalize_phone(user.phone))}&Body={quote(body)}'.encode()
    credentials = base64.b64encode(
        f'{config["TWILIO_ACCOUNT_SID"]}:{config["TWILIO_AUTH_TOKEN"]}'.encode()
    ).decode()
    twilio_url = (
        f'https://api.twilio.com/2010-04-01/Accounts/'
        f'{config["TWILIO_ACCOUNT_SID"]}/Messages.json'
    )
    sms_request = Request(twilio_url, data=payload, method='POST', headers={
        'Authorization': f'Basic {credentials}',
        'Content-Type': 'application/x-www-form-urlencoded',
    })
    with urlopen(sms_request, timeout=10):
        pass


def _reset_token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _is_expired(reset_request):
    expires_at = reset_request.expires_at
    if expires_at.tzinfo is None:
        return expires_at <= _utcnow().replace(tzinfo=None)
    return expires_at <= _utcnow()


def _purge_old_reset_requests(now):
    retention_seconds = max(
        current_app.config['PASSWORD_RESET_TTL_MINUTES'] * 60,
        current_app.config['PASSWORD_RESET_COOLDOWN_SECONDS'],
        current_app.config['PASSWORD_RESET_IP_WINDOW_SECONDS'],
    )
    cutoff = now - timedelta(seconds=retention_seconds)
    PasswordResetRequest.query.filter(
        PasswordResetRequest.requested_at < cutoff
    ).delete(synchronize_session=False)
    db.session.commit()

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_super_admin:
            return redirect(url_for('super_admin.dashboard'))
        if current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('member.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                if user.is_super_admin:
                    next_page = url_for('super_admin.dashboard')
                elif user.is_admin:
                    next_page = url_for('admin.dashboard')
                else:
                    next_page = url_for('member.dashboard')
            return redirect(next_page)
        else:
            flash('Invalid email or password. Please try again.', 'danger')

    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = PasswordResetRequestForm()
    if form.validate_on_submit():
        _purge_old_reset_requests(_utcnow())
        user, channel, destination = _find_reset_user(form.identifier.data)
        if not user or not user.is_active:
            flash('If an active account matches that contact, a reset link will be sent.', 'success')
            return redirect(url_for('auth.login'))
        else:
            now = _utcnow()
            cooldown_since = now - timedelta(seconds=current_app.config['PASSWORD_RESET_COOLDOWN_SECONDS'])
            ip_since = now - timedelta(seconds=current_app.config['PASSWORD_RESET_IP_WINDOW_SECONDS'])
            recent_contact = PasswordResetRequest.query.filter(
                PasswordResetRequest.destination == destination,
                PasswordResetRequest.requested_at >= cooldown_since,
            ).first()
            recent_ip_count = PasswordResetRequest.query.filter(
                PasswordResetRequest.requested_ip == request.remote_addr,
                PasswordResetRequest.requested_at >= ip_since,
            ).count()
            if recent_contact or recent_ip_count >= current_app.config['PASSWORD_RESET_IP_LIMIT']:
                flash('If an active account matches that contact, a reset link will be sent. Please wait before trying again.', 'success')
                return redirect(url_for('auth.login'))
            else:
                token = secrets.token_urlsafe(32)
                reset_request = PasswordResetRequest(
                    user_id=user.id,
                    channel=channel,
                    destination=destination,
                    token_hash=_reset_token_hash(token),
                    requested_ip=request.remote_addr or 'unknown',
                    requested_at=now,
                    expires_at=now + timedelta(minutes=current_app.config['PASSWORD_RESET_TTL_MINUTES']),
                )
                PasswordResetRequest.query.filter_by(user_id=user.id, used_at=None).update(
                    {'used_at': now}, synchronize_session=False
                )
                db.session.add(reset_request)
                db.session.commit()
                reset_url = url_for('auth.reset_password', token=token, _external=True)
                try:
                    if channel == 'email':
                        _send_email(user, reset_url)
                    else:
                        _send_sms(user, reset_url)
                except Exception:
                    current_app.logger.exception('Password reset delivery failed')
                flash('If an active account matches that contact, a reset link will be sent.', 'success')
                return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html', form=form)


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    reset_request = PasswordResetRequest.query.filter_by(
        token_hash=_reset_token_hash(token), used_at=None
    ).first()
    if not reset_request or _is_expired(reset_request):
        flash('That password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    form = PasswordResetForm()
    if form.validate_on_submit():
        user = User.query.get(reset_request.user_id)
        if not user or not user.is_active:
            flash('That password reset link is no longer valid.', 'danger')
            return redirect(url_for('auth.forgot_password'))

        claimed_at = _utcnow()
        claimed = PasswordResetRequest.query.filter(
            PasswordResetRequest.id == reset_request.id,
            PasswordResetRequest.used_at.is_(None),
        ).update({'used_at': claimed_at}, synchronize_session=False)
        if claimed != 1:
            db.session.rollback()
            flash('That password reset link has already been used.', 'danger')
            return redirect(url_for('auth.forgot_password'))

        user.set_password(form.password.data)
        PasswordResetRequest.query.filter(
            PasswordResetRequest.user_id == user.id,
            PasswordResetRequest.used_at.is_(None),
            PasswordResetRequest.id != reset_request.id,
        ).update({'used_at': claimed_at}, synchronize_session=False)
        db.session.commit()
        flash('Your password has been reset. You can now log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', form=form)
