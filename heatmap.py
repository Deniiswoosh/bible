import calendar
from datetime import date, datetime, time


def build_heatmap(readings, year, deadline='23:59', today=None, now=None):
    """Build Monday-first monthly contribution grids for one year."""
    today = today or date.today()
    now = now or datetime.now()
    deadline_hour, deadline_minute = map(int, deadline.split(':'))
    deadline_time = time(deadline_hour, deadline_minute)
    submitted_dates = {reading.reading_date for reading in readings}
    months = []
    calendar_builder = calendar.Calendar(firstweekday=calendar.MONDAY)

    for month in range(1, 13):
        weeks = []
        for week in calendar_builder.monthdatescalendar(year, month):
            cells = []
            for current_date in week:
                if current_date.month != month:
                    cells.append(None)
                    continue

                if current_date in submitted_dates:
                    status = 'submitted'
                elif current_date < today or (current_date == today and now.time() >= deadline_time):
                    status = 'missing'
                else:
                    status = 'pending'

                cells.append({
                    'date': current_date,
                    'day': current_date.day,
                    'status': status,
                })
            weeks.append(cells)

        months.append({
            'number': month,
            'name': calendar.month_name[month],
            'weeks': weeks,
        })

    return {'year': year, 'months': months}
