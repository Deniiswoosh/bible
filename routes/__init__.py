from routes.auth import auth_bp
from routes.member import member_bp
from routes.admin import admin_bp
from routes.super_admin import super_admin_bp

__all__ = ['auth_bp', 'member_bp', 'admin_bp', 'super_admin_bp']
