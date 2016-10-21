import sys
from datetime import date
from dateutil.parser import parse

from modularodm import Q

from website.app import init_app
from website.models import User
from website.settings import KEEN as keen_settings
from keen.client import KeenClient

def count(today):
    counts = {
        'active_users': User.find(
            Q('is_registered', 'eq', True) &
            Q('password', 'ne', None) &
            Q('merged_by', 'eq', None) &
            Q('date_disabled', 'eq', None) &
            Q('date_confirmed', 'ne', None) &
            Q('date_confirmed', 'lt', today)
        ).count(),
        'unconfirmed_users': User.find(
            Q('date_created', 'lt', today) &
            Q('date_confirmed', 'eq', None)
        ).count(),
        'deactivated_users': User.find(
            Q('date_disabled', 'ne', None) &
            Q('date_disabled', 'lt', today)
        ).count()
    }
    return {'user_count_analytics': [counts]}

def main(today):
    keen_payload = count(today)
    keen_project = keen_settings['private']['project_id']
    write_key = keen_settings['private']['write_key']
    if keen_project and write_key:
        client = KeenClient(
            project_id=keen_project,
            write_key=write_key,
        )
        client.add_events(keen_payload)
    else:
        print(keen_payload)


if __name__ == '__main__':
    init_app()
    try:
        date = parse(sys.argv[1])
    except IndexError:
        date = date.today()
    main(date)
