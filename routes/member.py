from datetime import date, datetime, timedelta, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from extensions import db
from models import Reading, Comment, Notification, Streak
from forms import ChangePasswordForm, ReadingForm, CommentForm
from heatmap import build_heatmap

member_bp = Blueprint('member', __name__, url_prefix='/member')


@member_bp.before_request
@login_required
def prevent_platform_account_access():
    if current_user.is_super_admin:
        return redirect(url_for('super_admin.dashboard'))

@member_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if current_user.is_admin:
        return redirect(url_for('admin.dashboard'))

    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            form.current_password.errors.append('Current password is incorrect.')
        else:
            current_user.set_password(form.password.data)
            db.session.commit()
            flash('Your password has been changed successfully.', 'success')
            return redirect(url_for('member.dashboard'))

    return render_template('member/change_password.html', form=form)

@member_bp.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    if current_user.is_admin:
        return redirect(url_for('admin.dashboard'))

    today = date.today()
    formatted_date = today.strftime("%A, %B %d, %Y")

    # Check if reading exists for today
    today_reading = Reading.query.filter_by(
        user_id=current_user.id, group_id=current_user.group_id, reading_date=today
    ).first()

    form = ReadingForm()

    if form.validate_on_submit():
        if today_reading:
            # Update existing reading
            today_reading.passage = form.passage.data.strip()
            today_reading.reflection = form.reflection.data.strip()
            today_reading.application = form.application.data.strip()
            today_reading.prayer = form.prayer.data.strip() if form.prayer.data else None
            today_reading.updated_at = datetime.now(timezone.utc)
            flash('Your reading reflection has been updated successfully!', 'success')
        else:
            # Create new reading
            new_reading = Reading(
                user_id=current_user.id,
                group_id=current_user.group_id,
                reading_date=today,
                passage=form.passage.data.strip(),
                reflection=form.reflection.data.strip(),
                application=form.application.data.strip(),
                prayer=form.prayer.data.strip() if form.prayer.data else None
            )
            db.session.add(new_reading)

            # Update streak logic
            streak = Streak.query.filter_by(user_id=current_user.id).first()
            if not streak:
                streak = Streak(user_id=current_user.id, current_streak=1, longest_streak=1, last_reading_date=today)
                db.session.add(streak)
            else:
                if streak.last_reading_date == today - timedelta(days=1):
                    streak.current_streak += 1
                elif streak.last_reading_date == today:
                    pass # Already counted for today
                else:
                    streak.current_streak = 1

                if streak.current_streak > streak.longest_streak:
                    streak.longest_streak = streak.current_streak
                streak.last_reading_date = today

            flash('Praise God! Your daily reading has been recorded.', 'success')

        db.session.commit()
        return redirect(url_for('member.dashboard'))

    elif request.method == 'GET' and today_reading:
        # Pre-fill form if already submitted today
        form.passage.data = today_reading.passage
        form.reflection.data = today_reading.reflection
        form.application.data = today_reading.application
        form.prayer.data = today_reading.prayer or ''

    streak_info = Streak.query.filter_by(user_id=current_user.id).first()
    heatmap_year = request.args.get('year', date.today().year, type=int)
    heatmap_readings = Reading.query.filter_by(
        user_id=current_user.id, group_id=current_user.group_id
    ).all()

    return render_template(
        'member/dashboard.html',
        form=form,
        today_date=formatted_date,
        today_reading=today_reading,
        streak_info=streak_info,
        heatmap=build_heatmap(heatmap_readings, heatmap_year, current_app.config['DAILY_DEADLINE'])
    )


@member_bp.route('/heatmap')
@login_required
def heatmap():
    if current_user.is_admin:
        return redirect(url_for('admin.dashboard'))

    year = request.args.get('year', date.today().year, type=int)
    year = max(2000, min(year, date.today().year))
    readings = Reading.query.filter_by(
        user_id=current_user.id, group_id=current_user.group_id
    ).all()
    return render_template(
        'member/heatmap.html',
        heatmap=build_heatmap(readings, year, current_app.config['DAILY_DEADLINE']),
        viewing_user=current_user,
        is_admin_view=False,
        current_year=date.today().year
    )

@member_bp.route('/history')
@login_required
def history():
    if current_user.is_admin:
        return redirect(url_for('admin.dashboard'))

    Notification.query.filter_by(user_id=current_user.id, read_at=None).update(
        {'read_at': datetime.now(timezone.utc)}, synchronize_session=False
    )
    db.session.commit()

    query = Reading.query.filter_by(user_id=current_user.id, group_id=current_user.group_id)
    start_date = parse_date(request.args.get('from'))
    end_date = parse_date(request.args.get('to'))
    if start_date:
        query = query.filter(Reading.reading_date >= start_date)
    if end_date:
        query = query.filter(Reading.reading_date <= end_date)
    readings = query.order_by(Reading.reading_date.desc()).all()
    streak_info = Streak.query.filter_by(user_id=current_user.id).first()
    comment_forms = {reading.id: CommentForm(prefix=f'comment-{reading.id}') for reading in readings}
    return render_template('member/history.html', readings=readings, streak_info=streak_info,
                           viewing_user=current_user, comment_forms=comment_forms,
                           from_date=request.args.get('from', ''), to_date=request.args.get('to', ''),
                           is_admin_view=False)


@member_bp.route('/reading/<int:reading_id>/comments', methods=['POST'])
@login_required
def add_comment(reading_id):
    reading = Reading.query.filter_by(
        id=reading_id, group_id=current_user.group_id
    ).first_or_404()
    if not current_user.is_admin and reading.user_id != current_user.id:
        return redirect(url_for('member.history'))

    form = CommentForm(prefix=f'comment-{reading.id}')
    if form.validate_on_submit():
        parent_id = request.form.get('parent_id', type=int)
        if parent_id and not Comment.query.filter_by(
            id=parent_id, reading_id=reading.id, group_id=current_user.group_id
        ).first():
            parent_id = None
        comment = Comment(reading_id=reading.id, user_id=current_user.id,
                  group_id=current_user.group_id,
                          parent_id=parent_id, body=form.body.data.strip())
        db.session.add(comment)
        db.session.flush()

        recipient_id = None
        if parent_id:
            parent = Comment.query.filter_by(
                id=parent_id, group_id=current_user.group_id
            ).first()
            recipient_id = parent.user_id if parent and parent.user_id != current_user.id else None
        elif reading.user_id != current_user.id:
            recipient_id = reading.user_id
        if recipient_id:
            db.session.add(Notification(user_id=recipient_id, comment_id=comment.id))
        db.session.commit()
        flash('Comment posted.', 'success')
    else:
        flash('Please enter a comment under 1000 characters.', 'danger')

    destination = request.form.get('next') or url_for('member.history')
    if not destination.startswith('/') or destination.startswith('//'):
        destination = url_for('member.history')
    return redirect(destination)


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None
