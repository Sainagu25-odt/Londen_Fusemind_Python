from sqlalchemy import text
from extensions import db

def get_reports_responder_file_data():
    """
        Data retrieval for /api/reports/responderFile endpoint
        """
    sql = text("""
            SELECT coalesce(state_name, state, '') as state, 
                coalesce(total_dups,0) + coalesce(policy,0) AS total, 
                coalesce(policy,0) as policy_holders, 
                coalesce(total_dups,0) - coalesce(total,0) AS household_duplicates,
                coalesce(total,0) AS net
            FROM (
                SELECT coalesce(state,'') AS state, count(*) as policy
                FROM responder_file
                WHERE cust_flag = 'Y'
                GROUP BY coalesce(state, '')
                ) AS p
            FULL OUTER JOIN (
                SELECT state, count(*) AS total, sum(cnt) AS total_dups
                FROM (
                    SELECT address_2, postal, coalesce(state, '') AS state, count(*) as cnt
                    FROM responder_file
                    WHERE coalesce(cust_flag, 'N') <> 'Y'
                    GROUP BY address_2, postal, coalesce(state, '')
                ) AS hh
                GROUP BY state
            ) AS h1 USING (state)
            JOIN state_lookup ON (state = state_code)
        """)
    result = db.session.execute(sql)
    data = [dict(row) for row in result]
    fields = {
        'state': 'C',
        'total': 'N',
        'policy_holders': 'N',
        'household_duplicates': 'N',
        'net': 'N'
    }
    return {'data': data, 'fields': fields}


def generate_feed_report(date_from=None, date_to=None):
    sql = """
        SELECT filename, processed, records,
               downloaded_at, imported_at, completed_at
        FROM import_logs
    """
    params = {}

    if date_from and date_to:
        sql += " WHERE downloaded_at BETWEEN :date_from AND :date_to"
        params["date_from"] = date_from
        params["date_to"] = date_to

    result = db.session.execute(text(sql), params)
    return [dict(row._mapping) for row in result.fetchall()]
