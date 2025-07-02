
RESPONDER_FILE_QUERY = """
SELECT 
    COALESCE(state_name, state, '') AS state,
    COALESCE(total_dups, 0) + COALESCE(policy, 0) AS total,
    COALESCE(policy, 0) AS policy_holders,
    COALESCE(total_dups, 0) - COALESCE(total, 0) AS household_duplicates,
    COALESCE(total, 0) AS net
FROM (
    SELECT COALESCE(state, '') AS state, COUNT(*) AS policy
    FROM responder_file
    WHERE cust_flag = 'Y'
    GROUP BY COALESCE(state, '')
) AS p
FULL OUTER JOIN (
    SELECT state, COUNT(*) AS total, SUM(cnt) AS total_dups
    FROM (
        SELECT address_2, postal, COALESCE(state, '') AS state, COUNT(*) AS cnt
        FROM responder_file
        WHERE COALESCE(cust_flag, 'N') <> 'Y'
        GROUP BY address_2, postal, COALESCE(state, '')
    ) AS hh
    GROUP BY state
) AS h1 USING (state)
JOIN state_lookup ON (state = state_code)
"""

def get_feed_manager_query(with_date_filter=False):
    base_sql = """
        SELECT filename,
               processed,
               records,
               downloaded_at,
               imported_at,
               completed_at
        FROM import_logs
    """
    if with_date_filter:
        base_sql += " WHERE downloaded_at BETWEEN :date_from AND :date_to"

    return base_sql




