import os
from dotenv import load_dotenv


load_dotenv()


class Config:
    SECRET_KEY = os.environ['SECRET_KEY']
    SQLALCHEMY_DATABASE_URI = os.environ['DATABASE_URL']
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True, 'pool_recycle': 300}
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'true').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    DAILY_DEADLINE = os.environ.get('DAILY_DEADLINE', '23:59')
    PASSWORD_RESET_TTL_MINUTES = int(os.environ.get('PASSWORD_RESET_TTL_MINUTES', '30'))
    PASSWORD_RESET_COOLDOWN_SECONDS = int(os.environ.get('PASSWORD_RESET_COOLDOWN_SECONDS', '900'))
    PASSWORD_RESET_IP_LIMIT = int(os.environ.get('PASSWORD_RESET_IP_LIMIT', '5'))
    PASSWORD_RESET_IP_WINDOW_SECONDS = int(os.environ.get('PASSWORD_RESET_IP_WINDOW_SECONDS', '3600'))
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true'
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
    TWILIO_FROM_NUMBER = os.environ.get('TWILIO_FROM_NUMBER')
