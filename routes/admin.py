from datetime import date, datetime, time
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from extensions import db
from models import User, Role, Reading, Streak
from forms import MemberCreateForm
from forms.auth_forms import deliverable_email_value, kenyan_phone_error, strong_password_error
from heatmap import build_heatmap

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.before_request
@login_required
def check_admin():
    if not current_user.is_admin:
        flash('Access restricted to administrators only.', 'danger')
        return redirect(url_for('member.dashboard'))
    if current_user.group_id is None:
        flash('Your account is not assigned to a group.', 'danger')
        return redirect(url_for('auth.logout'))

@admin_bp.route('/dashboard')
def dashboard():
    # Date filter
    target_date_str = request.args.get('date')
    if target_date_str:
        try:
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = date.today()
    else:
        target_date = date.today()

    formatted_date = target_date.strftime("%A, %B %d, %Y")
    display_date = target_date.strftime("%b %d, %Y")

    # Fetch member role
    member_role = Role.query.filter_by(name='Member').first()
    member_role_id = member_role.id if member_role else 2

    # Query all members
    search_query = request.args.get('search', '').strip()
    query = User.query.filter(User.role_id == member_role_id, User.group_id == current_user.group_id)

    if search_query:
        query = query.filter(User.name.ilike(f'%{search_query}%'))

    all_members = query.order_by(User.name.asc()).all()

    # Total stats
    total_members_count = User.query.filter(
        User.role_id == member_role_id, User.group_id == current_user.group_id
    ).count()

    # Readings for target_date
    readings_today = {
        r.user_id: r for r in Reading.query.filter_by(
            reading_date=target_date, group_id=current_user.group_id
        ).all()
    }

    now = datetime.now()
    deadline_hour, deadline_minute = map(int, current_app.config['DAILY_DEADLINE'].split(':'))
    deadline_passed = target_date < date.today() or (target_date == date.today() and now.time() >= time(deadline_hour, deadline_minute))
    submitted_count = sum(1 for m in all_members if m.id in readings_today)
    missing_count = sum(1 for m in all_members if m.id not in readings_today and deadline_passed)

    # Pagination setup (8 members per page matching design spec)
    page = request.args.get('page', 1, type=int)
    per_page = 8
    total_pages = (len(all_members) + per_page - 1) // per_page if all_members else 1
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_members = all_members[start_idx:end_idx]

    # Member row details mapping
    member_rows = []
    for member in paginated_members:
        reading = readings_today.get(member.id)
        status = 'submitted' if reading else ('missing' if deadline_passed else 'pending')
        # Assign color theme for avatar based on name initial
        colors = ['bg-blue-100 text-blue-700', 'bg-purple-100 text-purple-700', 'bg-emerald-100 text-emerald-700', 'bg-amber-100 text-amber-700', 'bg-rose-100 text-rose-700']
        color_class = colors[member.id % len(colors)]

        member_rows.append({
            'id': member.id,
            'name': member.name,
            'initial': member.name[0].upper() if member.name else 'M',
            'color_class': color_class,
            'date': display_date,
            'passage': reading.passage if reading else '—',
            'status': status,
            'has_submitted': reading is not None,
            'reading': reading
        })

    # Drawer / detail view selection
    selected_member_id = request.args.get('selected_id', type=int)
    selected_reading_detail = None

    if selected_member_id:
        sel_member = User.query.filter_by(
            id=selected_member_id, group_id=current_user.group_id
        ).first()
        if sel_member:
            sel_reading = Reading.query.filter_by(
                user_id=sel_member.id, reading_date=target_date,
                group_id=current_user.group_id
            ).first()
            selected_reading_detail = {
                'member': sel_member,
                'date_str': formatted_date,
                'reading': sel_reading
            }
    elif member_rows and member_rows[0]['has_submitted']:
        # Default open first submitted reading if available
        first_sub = next((m for m in member_rows if m['has_submitted']), None)
        if first_sub:
            selected_member_id = first_sub['id']
            sel_member = User.query.filter_by(
                id=selected_member_id, group_id=current_user.group_id
            ).first()
            selected_reading_detail = {
                'member': sel_member,
                'date_str': formatted_date,
                'reading': first_sub['reading']
            }

    return render_template(
        'admin/dashboard.html',
        formatted_date=formatted_date,
        target_date_str=target_date.strftime('%Y-%m-%d'),
        total_members=total_members_count,
        submitted_today=submitted_count,
        missing_today=missing_count,
        member_rows=member_rows,
        search_query=search_query,
        page=page,
        total_pages=total_pages,
        total_items=len(all_members),
        start_item=start_idx + 1 if all_members else 0,
        end_item=min(end_idx, len(all_members)),
        selected_member_id=selected_member_id,
        selected_reading_detail=selected_reading_detail,
        deadline_passed=deadline_passed
    )

@admin_bp.route('/members')
def members():
    member_role = Role.query.filter_by(name='Member').first()
    member_role_id = member_role.id if member_role else 2

    search_query = request.args.get('search', '').strip()
    query = User.query.filter(User.role_id == member_role_id, User.group_id == current_user.group_id)
    if search_query:
        query = query.filter(User.name.ilike(f'%{search_query}%'))

    members_list = query.order_by(User.name.asc()).all()

    # Calculate streak and total submissions for each member
    members_data = []
    for m in members_list:
        streak = Streak.query.filter_by(user_id=m.id).first()
        total_submissions = Reading.query.filter_by(user_id=m.id, group_id=current_user.group_id).count()
        latest_reading = Reading.query.filter_by(
            user_id=m.id, group_id=current_user.group_id
        ).order_by(Reading.reading_date.desc()).first()

        members_data.append({
            'user': m,
            'streak': streak.current_streak if streak else 0,
            'longest_streak': streak.longest_streak if streak else 0,
            'total_submissions': total_submissions,
            'last_active': latest_reading.reading_date.strftime('%b %d, %Y') if latest_reading else 'Never'
        })

    return render_template('admin/members.html', members_data=members_data, search_query=search_query)


@admin_bp.route('/members/<int:user_id>/history')
def member_history(user_id):
    member_role = Role.query.filter_by(name='Member').first()
    member = User.query.filter_by(
        id=user_id, group_id=current_user.group_id,
        role_id=member_role.id if member_role else -1
    ).first_or_404()
    query = Reading.query.filter_by(user_id=member.id, group_id=current_user.group_id)
    start_date = parse_date(request.args.get('from'))
    end_date = parse_date(request.args.get('to'))
    if start_date:
        query = query.filter(Reading.reading_date >= start_date)
    if end_date:
        query = query.filter(Reading.reading_date <= end_date)
    readings = query.order_by(Reading.reading_date.desc()).all()
    from forms import CommentForm
    comment_forms = {reading.id: CommentForm(prefix=f'comment-{reading.id}') for reading in readings}
    streak_info = Streak.query.filter_by(user_id=member.id).first()
    return render_template('member/history.html', readings=readings, streak_info=streak_info,
                           viewing_user=member, comment_forms=comment_forms,
                           from_date=request.args.get('from', ''), to_date=request.args.get('to', ''),
                           is_admin_view=True)


@admin_bp.route('/member/<int:user_id>/heatmap')
def member_heatmap(user_id):
    member_role = Role.query.filter_by(name='Member').first()
    member = User.query.filter_by(
        id=user_id, group_id=current_user.group_id,
        role_id=member_role.id if member_role else -1
    ).first_or_404()
    year = request.args.get('year', date.today().year, type=int)
    year = max(2000, min(year, date.today().year))
    readings = Reading.query.filter_by(user_id=member.id, group_id=current_user.group_id).all()
    return render_template(
        'member/heatmap.html',
        heatmap=build_heatmap(readings, year, current_app.config['DAILY_DEADLINE']),
        viewing_user=member,
        is_admin_view=True,
        current_year=date.today().year
    )

@admin_bp.route('/members/new', methods=['GET', 'POST'])
def create_member():
    form = MemberCreateForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if User.query.filter_by(email=email).first():
            form.email.errors.append('That email is already in use.')
        else:
            member_role = Role.query.filter_by(name='Member').first()
            if not member_role:
                flash('The Member role is not configured.', 'danger')
                return render_template('admin/create_member.html', form=form)

            member = User(
                name=form.name.data.strip(),
                email=email,
                role_id=member_role.id,
                group_id=current_user.group_id,
                phone=form.phone.data.strip() or None,
                residence=form.residence.data.strip() or None
            )
            member.set_password(form.password.data)
            db.session.add(member)
            db.session.commit()
            flash(f'{member.name} was added successfully.', 'success')
            return redirect(url_for('admin.members'))

    return render_template('admin/create_member.html', form=form)

@admin_bp.route('/members/<int:user_id>/edit', methods=['GET', 'POST'])
def edit_member(user_id):
    member_role = Role.query.filter_by(name='Member').first()
    member = User.query.filter_by(
        id=user_id, group_id=current_user.group_id,
        role_id=member_role.id if member_role else -1
    ).first_or_404()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        new_password = request.form.get('password', '').strip()
        phone = request.form.get('phone', '').strip()
        residence = request.form.get('residence', '').strip()

        if not name or not email:
            flash('Name and email are required.', 'danger')
            return render_template('admin/edit_member.html', member=member)

        normalized_email = deliverable_email_value(email)
        phone_error = kenyan_phone_error(phone)
        password_error = strong_password_error(new_password) if new_password else None
        if not normalized_email:
            flash('Please enter a real, deliverable email address.', 'danger')
            return render_template('admin/edit_member.html', member=member)
        if phone_error or password_error:
            flash(phone_error or password_error, 'danger')
            return render_template('admin/edit_member.html', member=member)

        # Check email uniqueness (excluding current user)
        existing = User.query.filter(
            User.email == normalized_email,
            User.id != user_id,
            User.group_id == current_user.group_id
        ).first()
        if existing:
            flash('That email is already in use by another member.', 'danger')
            return render_template('admin/edit_member.html', member=member)

        member.name = name
        member.email = normalized_email
        member.phone = phone or None
        member.residence = residence or None
        if new_password:
            member.set_password(new_password)

        db.session.commit()
        flash(f'{member.name}\'s profile has been updated successfully.', 'success')
        return redirect(url_for('admin.members'))

    return render_template('admin/edit_member.html', member=member)

@admin_bp.route('/members/<int:user_id>/delete', methods=['POST'])
def delete_member(user_id):
    member_role = Role.query.filter_by(name='Member').first()
    member = User.query.filter_by(
        id=user_id, group_id=current_user.group_id,
        role_id=member_role.id if member_role else -1
    ).first_or_404()
    name = member.name
    db.session.delete(member)
    db.session.commit()
    flash(f'{name} has been removed from the system.', 'success')
    return redirect(url_for('admin.members'))

@admin_bp.route('/api/reading/<int:user_id>/<string:date_str>')
def get_reading_api(user_id, date_str):
    try:
        req_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400

    member = User.query.filter_by(id=user_id, group_id=current_user.group_id).first_or_404()
    reading = Reading.query.filter_by(
        user_id=member.id, reading_date=req_date, group_id=current_user.group_id
    ).first()

    if not reading:
        return jsonify({
            'member_name': member.name,
            'has_reading': False,
            'date': req_date.strftime("%A, %B %d, %Y")
        })

    return jsonify({
        'member_name': member.name,
        'has_reading': True,
        'date': req_date.strftime("%A, %B %d, %Y"),
        'passage': reading.passage,
        'reflection': reading.reflection,
        'application': reading.application,
        'prayer': reading.prayer or '',
        'submitted_at': reading.submitted_at.strftime('%I:%M %p') if reading.submitted_at else ''
    })


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None
