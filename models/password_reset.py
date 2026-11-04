from datetime import datetime, timezone

from extensions import db


class PasswordResetRequest(db.Model):
    __tablename__ = 'password_reset_requests'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    channel = db.Column(db.String(10), nullable=False)
    destination = db.Column(db.String(254), nullable=False, index=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    requested_ip = db.Column(db.String(45), nullable=False, index=True)
    requested_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', backref=db.backref('password_reset_requests', lazy=True))
