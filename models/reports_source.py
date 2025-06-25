from datetime import datetime, timedelta

from sql.reports_sql import generate_feed_report

# Helper to convert datetime objects to strings
def serialize_datetimes(obj):
    if isinstance(obj, dict):
        return {k: serialize_datetimes(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_datetimes(item) for item in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    else:
        return obj


def yui_date_to_iso(date_str):
    try:
        return datetime.strptime(date_str, "%m/%d/%Y").strftime('%Y-%m-%d')
    except:
        return None


def process_feedmanager_report(args):
    # Parse dates
    date_from = yui_date_to_iso(args.get('date_from'))
    date_to = yui_date_to_iso(args.get('date_to'))

    # Apply 15-day default if either date is missing
    if not date_from or not date_to:
        today = datetime.today().date()
        date_to = today.strftime('%Y-%m-%d')
        date_from = (today - timedelta(days=15)).strftime('%Y-%m-%d')

    print(date_from, date_to)

    # Required fields
    sort_field = args.get('sort')
    sort_dir = args.get('dir')
    start_index = args.get('startIndex')
    page_size = args.get('results')

    # Fetch data from DB
    full_set = generate_feed_report(date_from, date_to)

    # Sort data

    full_set.sort(key=lambda x: x.get(sort_field), reverse=(sort_dir != 'asc'))

    # Paginate
    paginated = full_set[start_index:start_index + page_size]

    paginated_serialized = serialize_datetimes(paginated)

    return {
        'recordsReturned': len(paginated_serialized),
        'totalRecords': len(full_set),
        'startIndex': start_index,
        'sort': sort_field,
        'dir': sort_dir,
        'pageSize': page_size,
        'records': paginated_serialized
    }


# def process_response_rates(args):
#     rid = args.get(id)






