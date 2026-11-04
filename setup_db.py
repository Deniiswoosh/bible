from getpass import getpass

from app import app
from extensions import db
from models import Role, User


ROLES = {
    'Super Admin': 'Platform administrator with access to all groups',
    'Admin': 'Group administrator with full management access',
    'Member': 'Regular member submitting daily readings',
}


def main():
    with app.app_context():
        db.create_all()

        for name, description in ROLES.items():
            if not Role.query.filter_by(name=name).first():
                db.session.add(Role(name=name, description=description))
        db.session.commit()

        role = Role.query.filter_by(name='Super Admin').first()
        if role is None:
            raise RuntimeError('Could not create or find the Super Admin role.')

        email = input('Super Admin email: ').strip().lower()
        if not email:
            raise ValueError('Super Admin email cannot be blank.')
        if User.query.filter_by(email=email).first():
            print('That user already exists. Nothing created.')
            return
        if User.query.filter_by(role_id=role.id).first():
            print('A Super Admin already exists. Nothing created.')
            return

        name = input('Super Admin name: ').strip()
        if not name:
            raise ValueError('Super Admin name cannot be blank.')

        password = getpass('Password (min 12 characters): ')
        if len(password) < 12:
            raise ValueError('Password must be at least 12 characters.')

        user = User(name=name, email=email, role_id=role.id, group_id=None)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print('Super Admin created:', email)


if __name__ == '__main__':
    main()
