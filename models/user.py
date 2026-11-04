from datetime import datetime, timezone, date
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db, login_manager

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=True)
    phone = db.Column(db.String(30), nullable=True)
    residence = db.Column(db.String(150), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    role = db.relationship('Role', backref='users')
    group = db.relationship('Group', back_populates='users', foreign_keys=[group_id])
    readings = db.relationship('Reading', backref='user', lazy=True, cascade='all, delete-orphan')
    streak = db.relationship('Streak', backref='user', uselist=False, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role and self.role.name.lower() == 'admin'

    @property
    def is_super_admin(self):
        return self.role and self.role.name.lower() == 'super admin'

    def has_submitted_today(self, target_date=None):
        if target_date is None:
            target_date = date.today()
        from models.reading import Reading
        return Reading.query.filter_by(user_id=self.id, reading_date=target_date).first() is not None

    def get_today_reading(self, target_date=None):
        if target_date is None:
            target_date = date.today()
        from models.reading import Reading
        return Reading.query.filter_by(user_id=self.id, reading_date=target_date).first()

    def __repr__(self):
        return f'<User {self.email}>'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
