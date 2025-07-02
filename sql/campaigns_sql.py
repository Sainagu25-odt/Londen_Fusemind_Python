from sqlalchemy import text
from extensions import db




# def get_campaigns_data_list(args):
#     include_deleted = args['include_deleted']
#
#     if include_deleted:
#         sql = text("SELECT * FROM campaigns WHERE campaign_subquery_id IS NULL")
#     else:
#         sql = text("SELECT * FROM campaigns WHERE deleted_at IS NULL AND campaign_subquery_id IS NULL")
#
#     result = db.session.execute(sql)
#     campaigns = [dict(row._mapping) for row in result]
#     print(campaigns)
#     return campaigns

GET_ACTIVE_CAMPAIGNS_SQL = """
SELECT * FROM campaigns
WHERE deleted_at IS NULL
  AND campaign_subquery_id IS NULL
"""

GET_DELETED_CAMPAIGNS_SQL = """
SELECT * FROM campaigns
WHERE deleted_at IS NOT NULL
  AND campaign_subquery_id IS NULL
"""


# def execute_scalar(sql, params=None):
#     result = db.session.execute(text(sql), params or {})
#     row = result.first()
#     return row[0] if row else None
#
# def execute_all(sql, params=None):
#     result = db.session.execute(text(sql), params or {})
#     return [dict(row._mapping) for row in result]
#
# def build_exclude_clause(exclude):
#     if not exclude:
#         return "", {}
#     placeholders = ", ".join(f":ex{i}" for i in range(len(exclude)))
#     clause = f" AND p.policy NOT IN ({placeholders}) "
#     params = {f"ex{i}": v for i, v in enumerate(exclude)}
#     return clause, params
#
# def get_counts(exclude=None):
#     excl, params = build_exclude_clause(exclude)
#     sql = f"""
#         SELECT COUNT(*) FROM primary_policies AS p
#         WHERE TRUE {excl}
#     """
#     return execute_scalar(sql, params)
#
# def get_household_counts(exclude=None):
#     excl, params = build_exclude_clause(exclude)
#     sql = f"""
#         SELECT COUNT(*) AS total, SUM(cnt) AS total_dups FROM (
#             SELECT address2, zip_code, COALESCE(sl.state_name, p.state_code) AS state_code,
#                    COUNT(*) AS cnt
#             FROM primary_policies AS p
#             LEFT JOIN state_lookup AS sl ON p.state = sl.state_code
#             WHERE TRUE {excl}
#             GROUP BY address2, zip_code, COALESCE(sl.state_name, p.state)
#         ) AS s
#     """
#     return execute_scalar(sql, params)
#
# def get_counts_by_state(exclude=None):
#     excl, params = build_exclude_clause(exclude)
#     sql = f"""
#         SELECT COALESCE(sl.state_name, p.state) AS state, COUNT(*) AS total
#         FROM primary_policies AS p
#         LEFT JOIN state_lookup AS sl ON p.state = sl.state_code
#         WHERE TRUE {excl}
#         GROUP BY COALESCE(sl.state_name, p.state)
#         ORDER BY state
#     """
#     return execute_all(sql, params)
#
# def get_household_counts_by_state(exclude=None):
#     excl, params = build_exclude_clause(exclude)
#     sql = f"""
#         SELECT state_code AS state, COUNT(*) AS total, SUM(cnt) AS total_dups FROM (
#             SELECT address2, zip_code, COALESCE(sl.state_name, p.state) AS state_code, COUNT(*) AS cnt
#             FROM primary_policies AS p
#             LEFT JOIN state_lookup AS sl ON p.state = sl.state_code
#             WHERE TRUE {excl}
#             GROUP BY address2, zip_code, COALESCE(sl.state_name, p.state)
#         ) AS s
#         GROUP BY state_code
#         ORDER BY state
#     """
#     return execute_all(sql, params)
#
# def get_universe():
#     sql = """
#         SELECT COUNT(*) FROM primary_policies AS p
#     """
#     return execute_scalar(sql)
#
# def get_household_universe():
#     sql = """
#         SELECT COUNT(*) FROM (
#             SELECT address2, zip_code, COALESCE(sl.state_name, p.state) AS state_code, COUNT(*) AS cnt
#             FROM primary_policies AS p
#             LEFT JOIN state_lookup AS sl ON p.state = sl.state_code
#             GROUP BY address2, zip_code, COALESCE(sl.state_name, p.state)
#         ) AS s
#     """
#     return execute_scalar(sql)


def counts_sql_template(household: bool) -> str:
    if household:
        return """
        SELECT
            COUNT(*) AS counts,
            SUM(cnt) AS total_dups
        FROM (
            SELECT
                address2, zip_code, state_code,
                COUNT(*) AS cnt
            FROM ({criteria_sql}) AS campaign_data
            {exclude_clause}
            GROUP BY address2, zip_code, state_code
        ) s
        """
    else:
        return """
        SELECT COUNT(*) AS counts
        FROM ({criteria_sql}) AS campaign_data
        {exclude_clause}
        """

def states_sql_template(household: bool) -> str:
    if household:
        return """
        SELECT
            state_code AS state,
            COUNT(*) AS total,
            SUM(cnt) AS total_dups
        FROM (
            SELECT
                address2, zip_code, state_code,
                COUNT(*) AS cnt
            FROM ({criteria_sql}) AS campaign_data
            {exclude_clause}
            GROUP BY address2, zip_code, state_code
        ) s
        GROUP BY state_code
        ORDER BY state_code
        """
    else:
        return """
        SELECT
            state_code AS state,
            COUNT(*) AS total
        FROM ({criteria_sql}) AS campaign_data
        {exclude_clause}
        GROUP BY state_code
        ORDER BY state_code
        """

soft_delete_sql = """
    UPDATE campaigns
    SET deleted_at = NOW()
    WHERE id = :campaign_id
"""

undelete_sql = """
    UPDATE campaigns
    SET deleted_at = NULL
    WHERE id = :campaign_id
"""


GET_CAMPAIGN = """
SELECT 
    c.id,
    c.name,
    c.description,
    c.channel,
    c.deleted_at IS NOT NULL AS deleted,
    d.tablename
FROM campaigns c
LEFT JOIN campaign_datasources d ON c.datasource = d.datasource
WHERE c.id = :id
"""

GET_CRITERIA = """
SELECT column_name, sql_type AS operator, sql_value AS value, or_next AS is_or
FROM campaign_criteria
WHERE campaign_id = :id
ORDER BY id
"""

ADD_CRITERION = """
    INSERT INTO campaign_criteria 
        (campaign_id, column_name, sql_type, sql_value, or_next)
    VALUES 
        (:campaign_id, :column_name, :sql_type, :sql_value, :or_next)
"""

ADD_CAMPAIGN = """
    INSERT INTO campaigns (name, description, channel, datasource, begin_date)
    VALUES (:name, :description, :channel, :datasource, :begin_date)
    RETURNING id
"""

GET_DROPDOWN_FOR_DATASOURCE = """
    SELECT datasource FROM campaign_datasources
"""

GET_USER_FROM_TOKEN = """
SELECT username, email
FROM users
WHERE token = :token
"""

GET_CAMPAIGN_DETAILS_BY_ID = """
SELECT id, name FROM campaigns WHERE id = :campaign_id
"""


GET_PREBUILT_FIELDSETS_BY_CAMPAIGN = """
SELECT id, label FROM campaign_list_fieldsets
WHERE datasource = (
    SELECT datasource FROM campaigns WHERE id = :campaign_id
)
"""

GET_CAMPAIGN_COLUMNS_BY_ID = """
SELECT column_name FROM campaign_criteria WHERE campaign_id = :campaign_id
"""

# Previous pulls for this campaign
GET_PREVIOUS_PULLS_BY_CAMPAIGN = """
SELECT name, requested_at, requested_by, householding, every_n, num_records
FROM campaign_lists
WHERE campaign_id = :campaign_id
AND completed_at IS NOT NULL
ORDER BY requested_at DESC
"""

GET_ACTIVE_PULLS_BY_CAMPAIGN = """
SELECT name, requested_at, requested_by, householding, every_n, num_records
FROM campaign_lists
WHERE campaign_id = :campaign_id
AND completed_at IS NULL
ORDER BY requested_at DESC
"""
