from functools import wraps
import secrets

from flask import abort, Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from models import Comment, Group, GroupMember, Notification, Reading, Role, Streak, User
from forms.auth_forms import (
    deliverable_email_value,
    kenyan_phone_error,
    strong_password_error,
)


super_admin_bp = Blueprint('super_admin', __name__, url_prefix='/platform')


def super_admin_required(view):
    @wraps(view)
    @login_required
    def wrapped_view(*args, **kwargs):
        if not current_user.is_super_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped_view


def generate_invite_code():
    return secrets.token_urlsafe(6).upper()[:8]


@super_admin_bp.route('/dashboard')
@super_admin_required
def dashboard():
    groups = []
    for group in Group.query.order_by(Group.name.asc()).all():
        users = User.query.filter_by(group_id=group.id).order_by(User.name.asc()).all()
        groups.append({
            'group': group,
            'users': users,
            'member_count': sum(not user.is_admin and not user.is_super_admin for user in users),
            'admin_count': sum(user.is_admin and not user.is_super_admin for user in users),
        })
    platform_users = [user for user in User.query.all() if not user.is_super_admin]
    return render_template(
        'super_admin/dashboard.html',
        groups=groups,
        group_count=len(groups),
        user_count=len(platform_users),
        active_user_count=sum(user.is_active for user in platform_users),
    )


@super_admin_bp.route('/groups/new', methods=['POST'])
@super_admin_required
def create_group():
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip() or None
    if len(name) < 2:
        flash('Group name must be at least 2 characters.', 'danger')
        return redirect(url_for('super_admin.dashboard'))

    group = Group(
        name=name,
        description=description,
    )
    db.session.add(group)
    db.session.commit()
    flash(f'{group.name} was created. Add its first admin below.', 'success')
    return redirect(url_for('super_admin.dashboard'))


@super_admin_bp.route('/users/new', methods=['GET', 'POST'])
@super_admin_required
def create_user():
    groups = Group.query.order_by(Group.name.asc()).all()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = deliverable_email_value(request.form.get('email', '').strip())
        password = request.form.get('password', '')
        group_id = request.form.get('group_id', type=int)
        role_name = request.form.get('role', 'Member')

        error = (
            'Name, email, password, and group are required.'
            if not name or not email or not group_id or not password else None
        )
        if not error:
            error = strong_password_error(password)
        if not error and User.query.filter_by(email=email).first():
            error = 'That email is already in use.'
        if not error and not Group.query.get(group_id):
            error = 'The selected group does not exist.'
        if not error and role_name not in ('Admin', 'Member'):
            error = 'Choose either Admin or Member. Super Admin is a platform-only account.'

        if error:
            flash(error, 'danger')
        else:
            role = Role.query.filter_by(name=role_name).one()
            user = User(name=name, email=email, group_id=group_id, role_id=role.id)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash(f'{user.name} was created as a {role_name}.', 'success')
            return redirect(url_for('super_admin.dashboard'))

    return render_template('super_admin/create_user.html', groups=groups)


@super_admin_bp.route('/users/<int:user_id>/role', methods=['POST'])
@super_admin_required
def change_user_role(user_id):
    user = User.query.get_or_404(user_id)
    if user.is_super_admin or user.id == current_user.id:
        flash('This account cannot be changed here.', 'danger')
        return redirect(url_for('super_admin.dashboard'))

    role_name = request.form.get('role')
    role = Role.query.filter_by(name=role_name).first()
    if not role or role_name not in ('Admin', 'Member'):
        abort(400)

    user.role_id = role.id
    db.session.commit()
    flash(f'{user.name} is now a {role_name}.', 'success')
    return redirect(url_for('super_admin.dashboard'))


@super_admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@super_admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.is_super_admin or user.id == current_user.id:
        flash('Super Admin accounts cannot be deleted here.', 'danger')
        return redirect(url_for('super_admin.dashboard'))

    comment_ids = [comment.id for comment in Comment.query.filter_by(user_id=user.id).all()]
    if comment_ids:
        Notification.query.filter(Notification.comment_id.in_(comment_ids)).delete(
            synchronize_session=False
        )
        Comment.query.filter(Comment.id.in_(comment_ids)).delete(synchronize_session=False)
    Notification.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    Reading.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    Streak.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    GroupMember.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    name = user.name
    db.session.delete(user)
    db.session.commit()
    flash(f'{name} was deleted.', 'success')
    return redirect(url_for('super_admin.dashboard'))


@super_admin_bp.route('/groups/<int:group_id>/delete', methods=['POST'])
@super_admin_required
def delete_group(group_id):
    group = Group.query.get_or_404(group_id)
    users = User.query.filter_by(group_id=group.id).all()
    if any(user.is_super_admin for user in users):
        flash('A group containing a Super Admin cannot be deleted.', 'danger')
        return redirect(url_for('super_admin.dashboard'))

    user_ids = [user.id for user in users]
    comment_ids = [
        comment.id for comment in Comment.query.filter(Comment.group_id == group.id).all()
    ]
    if comment_ids:
        Notification.query.filter(Notification.comment_id.in_(comment_ids)).delete(
            synchronize_session=False
        )
        Comment.query.filter(Comment.id.in_(comment_ids)).delete(synchronize_session=False)
    if user_ids:
        Notification.query.filter(Notification.user_id.in_(user_ids)).delete(
            synchronize_session=False
        )
        Reading.query.filter(Reading.group_id == group.id).delete(synchronize_session=False)
        Streak.query.filter(Streak.user_id.in_(user_ids)).delete(synchronize_session=False)
        GroupMember.query.filter(GroupMember.user_id.in_(user_ids)).delete(
            synchronize_session=False
        )
        User.query.filter(User.id.in_(user_ids)).delete(synchronize_session=False)
    GroupMember.query.filter_by(group_id=group.id).delete(synchronize_session=False)
    name = group.name
    db.session.delete(group)
    db.session.commit()
    flash(f'{name} and its users were deleted.', 'success')
    return redirect(url_for('super_admin.dashboard'))
