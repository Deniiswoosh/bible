import os
from flask import Flask, redirect, url_for
from sqlalchemy import text
from flask_wtf.csrf import generate_csrf
from werkzeug.middleware.proxy_fix import ProxyFix
from config import Config
from extensions import csrf, db, login_manager
from models import User, Notification, Role
from flask_login import current_user
from routes import auth_bp, member_bp, admin_bp, super_admin_bp
from database.seed import seed_database
from database.migrations import ensure_multitenant_columns

def create_app(config_class=Config):
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    @app.context_processor
    def inject_csrf_token():
        return {'csrf_token': generate_csrf}

    @app.context_processor
    def inject_notifications():
        unread_notifications = 0
        if current_user.is_authenticated:
            unread_notifications = Notification.query.filter_by(
                user_id=current_user.id, read_at=None
            ).count()
        return {'unread_notifications': unread_notifications}

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(member_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(super_admin_bp)

    @app.route('/')
    def index():
        from flask_login import current_user
        if current_user.is_authenticated:
            if current_user.is_super_admin:
                return redirect(url_for('super_admin.dashboard'))
            if current_user.is_admin:
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('member.dashboard'))
        return redirect(url_for('auth.login'))

    # Custom CLI Command to seed database
    @app.cli.command('seed-db')
    def seed_db_command():
        """Seed the database with default roles, admin, and members."""
        seed_database()

    # Create database tables and ensure the Super Admin role exists.
    with app.app_context():
        db.create_all()
        ensure_multitenant_columns(db)
        if not Role.query.filter_by(name='Super Admin').first():
            db.session.add(Role(
                name='Super Admin',
                description='Platform administrator with access to all groups'
            ))
            db.session.commit()
        super_admin_role = Role.query.filter_by(name='Super Admin').first()
        db.session.execute(text(
            'CREATE UNIQUE INDEX IF NOT EXISTS uq_one_super_admin '
            f'ON users(role_id) WHERE role_id = {super_admin_role.id}'
        ))
        User.query.filter_by(role_id=super_admin_role.id).update(
            {'group_id': None}, synchronize_session=False
        )
        db.session.commit()

    return app

app = create_app()

if __name__ == '__main__':
    app.run(
        debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true',
        port=int(os.environ.get('PORT', '5000'))
    )
