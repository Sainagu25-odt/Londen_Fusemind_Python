from datetime import datetime, timedelta

from sql.reports_sql import  RESPONDER_FILE_QUERY, get_feed_manager_query

from sqlalchemy import text
from extensions import db


def get_responder_data():
    result = db.session.execute(text(RESPONDER_FILE_QUERY))
    rows = [dict(row._mapping) for row in result]

    fields = {
        "state": "C",
        "total": "N",
        "policy_holders": "N",
        "household_duplicates": "N",
        "net": "N"
    }

    return {"data": rows, "fields": fields}


def normalize_date(date_str):
    """Converts various date formats to YYYY-MM-DD for SQL"""
    formats = ['%d/%m/%Y', '%Y-%m-%d', '%m/%d/%Y']
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    raise ValueError(f"Invalid date format: {date_str}")


def fetch_feed_manager_data(date_from=None, date_to=None, start_index=0, page_size=25, sort=None, dir_="asc"):
    # Default date logic (like PHP code)
    if date_from:
        date_from = normalize_date(date_from)
    else:
        date_from = (datetime.now() - timedelta(days=15)).strftime('%Y-%m-%d')

    if date_to:
        date_to = normalize_date(date_to)
    else:
        date_to = datetime.now().strftime('%Y-%m-%d')

    sql = get_feed_manager_query(True)

    result = db.session.execute(text(sql), {
        "date_from": date_from,
        "date_to": date_to
    })

    rows = result.mappings().fetchall()
    full_data = [dict(row) for row in rows]

    # Sorting
    if sort and full_data and sort in full_data[0]:
        reverse = dir_.lower() == "desc"
        full_data.sort(key=lambda x: x.get(sort), reverse=reverse)

    paginated = full_data[start_index:start_index + page_size]

    # Fields same as in PHP
    fields = {
        "filename": "C",
        "processed": "C",
        "records": "N",
        "downloaded_at": "C",
        "imported_at": "C",
        "completed_at": "C"
    }

    return {
        "recordsReturned": len(paginated),
        "totalRecords": len(full_data),
        "startIndex": start_index,
        "sort": sort,
        "dir": dir_,
        "pageSize": page_size,
        "records": paginated,
        "fields": fields
    }



