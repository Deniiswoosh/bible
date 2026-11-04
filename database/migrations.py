from sqlalchemy import inspect, text


def ensure_multitenant_columns(db):
    """Add tenant columns to databases created before group isolation existed."""
    inspector = inspect(db.engine)

    for table in ('readings', 'comments'):
        columns = {column['name'] for column in inspector.get_columns(table)}
        if 'group_id' not in columns:
            db.session.execute(text(
                f'ALTER TABLE {table} ADD COLUMN group_id INTEGER REFERENCES groups(id)'
            ))

    # Older installs had one default group but allowed users without an assignment.
    db.session.execute(text(
        'UPDATE users SET group_id = (SELECT id FROM groups ORDER BY id LIMIT 1) '
        'WHERE group_id IS NULL AND EXISTS (SELECT 1 FROM groups)'
    ))
    db.session.execute(text(
        'UPDATE readings SET group_id = ('
        'SELECT group_id FROM users WHERE users.id = readings.user_id'
        ') WHERE group_id IS NULL'
    ))
    db.session.execute(text(
        'UPDATE comments SET group_id = ('
        'SELECT group_id FROM users WHERE users.id = comments.user_id'
        ') WHERE group_id IS NULL'
    ))
    db.session.execute(text(
        'CREATE INDEX IF NOT EXISTS ix_readings_group_id ON readings(group_id)'
    ))
    db.session.execute(text(
        'CREATE INDEX IF NOT EXISTS ix_comments_group_id ON comments(group_id)'
    ))
    db.session.commit()
