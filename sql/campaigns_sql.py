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
    c.begin_date,
    c.deleted_at IS NOT NULL AS deleted,
    d.tablename
FROM campaigns c
LEFT JOIN campaign_datasources d ON c.datasource = d.datasource
WHERE c.id = :id
"""

GET_CRITERIA = """
SELECT 
    cc.id AS row_id,
    cc.column_name,
    cc.sql_type AS operator,
    cc.sql_value AS value,
    cc.or_next AS is_or
FROM campaign_criteria cc
WHERE cc.campaign_id = :id
ORDER BY cc.position
"""

GET_SUBQUERY_CHILDREN = """
SELECT 
    c.id, 
    c.name, 
    c.begin_date,
    c.deleted_at IS NOT NULL AS deleted
FROM campaigns c
WHERE c.subquery = TRUE AND c.campaign_subquery_id = :parent_id
ORDER BY c.id
"""

GET_SUBQUERY_CRITERIA = """
SELECT 
    cc.id AS row_id,
    cc.column_name,
    cc.sql_type AS operator,
    cc.sql_value AS value,
    cc.or_next AS is_or
FROM campaign_criteria cc
WHERE cc.campaign_id = :sub_id
ORDER BY cc.position
"""

GET_SUBQUERY_JOIN = """
SELECT 
    cs.label,
    cs.parent_table,
    cs.child_table,
    cs.parent_field,
    cs.child_field
FROM campaign_subqueries cs
WHERE cs.campaign_id = :parent_id AND cs.subquery_campaign_id = :sub_id
"""

ADD_CRITERION = """
    INSERT INTO campaign_criteria 
        (campaign_id, column_name, sql_type, sql_value, or_next)
    VALUES 
        (:campaign_id, :column_name, :sql_type, :sql_value, :or_next)
"""


SAVE_CRITERIA_INSERT = """
INSERT INTO campaign_criteria (campaign_id, column_name, sql_type, sql_value, or_next)
VALUES (:campaign_id, :column_name, :operator, :value, :is_or)
"""

SAVE_CRITERIA_UPDATE = """
UPDATE campaign_criteria
SET column_name = :column_name,
    sql_type = :operator,
    sql_value = :value,
    or_next = :is_or
WHERE id = :id AND campaign_id = :campaign_id
"""

DELETE_CRITERIA_ROW = """
DELETE FROM campaign_criteria
WHERE id = :id AND campaign_id = :campaign_id
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
SELECT id, name, channel FROM campaigns WHERE id = :campaign_id
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
SELECT cl.id AS list_id, c.name AS campaign, cl.name,
    cl.requested_by,
    cl.requested_at,
    cl.completed_at, cl.householding, cl.every_n, cl.num_records
FROM campaign_lists cl
JOIN campaigns c ON c.id = cl.campaign_id
AND cl.completed_at IS NULL
ORDER BY cl.requested_at DESC
"""

GET_LATEST_PULL_SETTINGS = """
SELECT every_n, num_records, fields, fieldset_id,
       excluded_pulls, householding, request_email
FROM campaign_lists
WHERE campaign_id = :campaign_id
ORDER BY requested_at DESC LIMIT 1
"""

INSERT_PULL_LIST = """
INSERT INTO campaign_lists (
    campaign_id, requested_at, completed_at,
    fieldset_id, every_n, num_records,
    fields, requested_by, excluded_pulls,
    householding, request_email, criteria_sql, name
) VALUES (
    :campaign_id, :requested_at, :completed_at,
    :fieldset_id, :every_n, :num_records,
    :fields, :requested_by, :excluded_pulls,
    :householding, :request_email, :criteria_sql, :name
)
"""

# sql/campaign_queries.py

GET_ALL_CAMPAIGNS_SQL = """
SELECT id AS campaign_id, name AS campaign, datasource
FROM campaigns
WHERE deleted_at IS NULL AND campaign_subquery_id IS NULL;
"""

GET_CAMPAIGN_DETAILS_SQL = """
SELECT id, name, datasource
FROM campaigns
WHERE id = :campaign_id
  AND deleted_at IS NULL
  AND campaign_subquery_id IS NULL;
"""



def get_show_records_sql(table_name: str) -> str:
    return f"""
    SELECT
      p.*,
      ARRAY_TO_STRING(
        ARRAY(
          SELECT DISTINCT d.campaign_list_id
          FROM campaign_list_data d
          WHERE d.keyvalue = p.company_number::text || ',' || p.policy::text
        ), ','
      ) AS lists
    FROM "{table_name}" AS p
    LEFT JOIN state_lookup ON p.state = state_lookup.state_code
    ORDER BY p.company_number, p.policy;
    """

get_records = f"""
    SELECT
        p.company AS "Company Number",
        p.policy_number AS "Policy",
        p.insuredl AS "Insured",
        p.ownerl AS "Owner Last Name",
        p.address1 AS "Address1",
        p.address2 AS "Address2",
        p.city AS "City",
        p.state AS "State",
        p.zip5 AS "Zip Code",
        p.bad_address AS "Bad Address",
        p.do_not_call AS "Do Not Call",
        p.donotmail AS "Do Not Mail",
        p.fcgs AS "Fcgs Membership",
        p.language_flag AS "Language Flag",
        p.child_rider_units AS "Child Rider Units",
        p.pay_type AS "Pay Type",
        p.mode AS "Mode",
        p.annual_premium AS "Annual Premium",
        p.semiannual_premium AS "Semiannual Premium",
        p.quarterly_premium AS "Quarterly Premium",
        p.monthly_premium AS "Monthly Premium",
        p.draft_premium AS "Draft Premium",
        p.insured_prefix AS "Insured Prefix",
        p.insured_first_name AS "Insured First Name",
        p.insured_middle_name AS "Insured Middle Name",
        p.insured_last_name AS "Insured Last Name",
        p.insured_suffix AS "Insured Suffix",
        p.gender AS "Gender",
        p.issue_age AS "Issue Age",
        p.status AS "Status",
        p.plan AS "Plan",
        p.class AS "Class",
        p.face_amount AS "Face Amount",
        p.premiums_payable_period AS "Premiums Payable Period",
        p.line_of_business AS "Line Of Business",
        p.accidental_death AS "Accidental Death",
        p.add_units AS "Add Units",
        p.add_camp AS "Add Camp",
        p.mga AS "Mga",
        p.mmga AS "Mmga",
        p.dob AS "Date Of Birth",
        p.issue_date AS "Issue Date",
        p.paid_to AS "Paid To",
        p.phone_number AS "Phone Number",
        p.phone_type AS "Phone Type",
        p.assigned_flag AS "Assigned Flag",
        p.fh_is_beneficiary AS "Fh Is Beneficiary",
        p.payor_prefix AS "Payor Prefix",
        p.payor_first_name AS "Payor First Name",
        p.payor_middle_name AS "Payor Middle Name",
        p.payor_last_name AS "Payor Last Name",
        p.payor_suffix AS "Payor Suffix",
        p.company_division AS "Company Division",
        p.roger_policy_number AS "Roger Policy Number",
        p.last_four AS "Last Four",
        p.inforce_flag AS "Inforce Flag",
        p.name_bank AS "Name Bank",
        p.savings_flag AS "Savings Flag",
        p.first_beneficiary AS "First Beneficiary",
        p.second_beneficiary AS "Second Beneficiary",
        COALESCE(state_lookup.state_name, p.state) AS "State Code",
        p.county_code AS "County Code"
    FROM policies p
    LEFT JOIN state_lookup ON p.state = state_lookup.state_code
    ORDER BY 1 DESC
    LIMIT 100
"""

# queries/campaign_queries.py
GET_CAMPAIGN_TABLE = """
SELECT ds.tablename
FROM campaigns c
JOIN campaign_datasources ds ON c.datasource = ds.datasource
WHERE c.id = :campaign_id
"""

GET_HOUSEHOLD_FIELDS = """
SELECT string_agg(column_name, ',') AS hf
FROM campaign_datasource_household
WHERE datasource = (
    SELECT datasource FROM campaigns WHERE id = :campaign_id
)
"""

SQL_COUNTS_BY_STATE = """
SELECT coalesce(sl.state_name, p.state) AS state, count(*) AS total
FROM {table_name} p
LEFT JOIN state_lookup sl ON p.state = sl.state_code
WHERE TRUE {exclude}
GROUP BY coalesce(sl.state_name, p.state)
ORDER BY state
"""

SQL_TOTAL_COUNTS = """
SELECT count(*) AS total
FROM {table_name} p
WHERE TRUE {exclude}
"""

SQL_HOUSEHOLD_COUNTS = """
SELECT count(*) AS total_households, sum(cnt) AS total_dups
FROM (
  SELECT {fields}, coalesce(sl.state_name, p.state) AS state_code, count(*) AS cnt
  FROM {table_name} p
  LEFT JOIN state_lookup sl ON p.state = sl.state_code
  WHERE TRUE {exclude}
  GROUP BY {fields}, coalesce(sl.state_name, p.state)
) AS s
"""

SQL_GLOBAL_CAMPAIGNS = """
SELECT c.id, ds.tablename
FROM campaigns c
JOIN campaign_datasources ds ON c.datasource = ds.datasource
WHERE c.deleted_at IS NULL AND c.campaign_subquery_id IS NULL
"""

GET_CAMPAIGN_LIST_FILENAME = """
SELECT name
FROM campaign_lists
WHERE id = :id
"""

get_campaign_records_sql = '''
SELECT {primary_key}, 
       coalesce(state_name, state_code) AS state_code,
       array_to_string (
           ARRAY(
               SELECT DISTINCT campaign_list_id 
               FROM campaign_list_data AS d 
               WHERE d.keyvalue = {pk_concat_sql}
           ), ','
       ) as lists
FROM {table_name} AS p
    {joins}
WHERE TRUE
    {where_conditions}
ORDER BY {order_by}
LIMIT {limit} OFFSET {offset}
'''
