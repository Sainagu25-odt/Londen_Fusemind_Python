

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
    d.tablename,
    c.datasource
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

UPDATE_CAMPAIGN = """
    UPDATE campaigns
    SET name = :name,
        description = :description,
        channel = :channel,
        begin_date = :begin_date,
        datasource = :datasource
    WHERE id = :id
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
WHERE id = :id 
"""

DELETE_CRITERIA_ROW = """
DELETE FROM campaign_criteria
WHERE id = :id
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
SELECT id, name, requested_at, requested_by, householding, every_n, num_records
FROM campaign_lists
WHERE campaign_id = :campaign_id
ORDER BY requested_at DESC
"""



GET_ACTIVE_PULLS_BY_CAMPAIGN = """
SELECT cl.id AS list_id, c.name AS campaign, cl.name,
    cl.requested_by,
    cl.requested_at,
    cl.completed_at, cl.householding, cl.every_n, cl.num_records
FROM campaign_lists cl
JOIN campaigns c ON cl.campaign_id = c.id
WHERE cl.requested_at > :since_date
AND c.deleted_at IS NULL
ORDER BY cl.id ASC
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

## global counts
SQL_TOTAL_COUNTS = """
SELECT count(*) AS total
FROM {table_name} p
WHERE TRUE {exclude}
"""

SQL_GLOBAL_CAMPAIGNS = """
SELECT c.id, ds.tablename
FROM campaigns c
JOIN campaign_datasources ds ON c.datasource = ds.datasource
WHERE c.deleted_at IS NULL AND c.campaign_subquery_id IS NULL
"""

## counts by each campaign sql queries
GET_CAMPAIGN_DATASOURCE_INFO_SQL = """
SELECT 
    c.name,
	c.channel,
    cd.datasource, 
    cd.tablename 
FROM campaigns c
JOIN campaign_datasources cd ON c.datasource = cd.datasource
WHERE c.id = :campaign_id
"""
GET_COUNTS_SQL = """
SELECT count(*) FROM {table_name} AS p
WHERE TRUE
{exclude_sql}
"""

GET_HOUSEHOLD_COLUMNS_SQL = """
SELECT column_name
FROM campaign_datasource_household
WHERE datasource = :datasource
ORDER BY column_name
"""

GET_PRIMARY_KEYS_SQL = """
SELECT column_name
FROM information_schema.table_constraints tc
JOIN information_schema.constraint_column_usage ccu 
  ON tc.constraint_name = ccu.constraint_name
WHERE tc.table_name = :table_name
  AND tc.constraint_type = 'PRIMARY KEY'
ORDER BY column_name
"""

GET_COUNTS_NON_HOUSEHOLD_SQL = """
SELECT count(*) {base_sql} {exclude_sql}
"""

GET_UNIVERSE_NON_HOUSEHOLD_SQL = """
SELECT count(*) FROM {table_name} AS p WHERE TRUE {exclude_sql}
"""

GET_COUNTS_BY_STATE_NON_HOUSEHOLD_SQL = """
SELECT coalesce(state_name, state_code) AS state, count(*) AS total
{base_sql} {exclude_sql}
GROUP BY coalesce(state_name, state_code)
ORDER BY 1
"""

GET_COUNTS_HOUSEHOLD_SQL = """
SELECT count(*) AS total, sum(cnt) AS total_dups FROM (
    SELECT {household_fields}, coalesce(state_name, state_code) AS state_code,
        count(*) AS cnt
    FROM {table_name} AS p
    LEFT JOIN state_lookup ON (p.state = state_lookup.state_code)
    WHERE TRUE {exclude_sql}
    GROUP BY {household_fields}, coalesce(state_name, state_code)
) AS s
"""

GET_UNIVERSE_HOUSEHOLD_SQL = """
SELECT count(*) FROM (
    SELECT {household_fields}, coalesce(state_name, state_code) AS state_code,
        count(*) AS cnt
    FROM {table_name} AS p
    LEFT JOIN state_lookup ON (p.state = state_lookup.state_code)
    WHERE TRUE {exclude_sql}
    GROUP BY {household_fields}, coalesce(state_name, state_code)
) AS s
"""

GET_COUNTS_BY_STATE_HOUSEHOLD_SQL = """
SELECT state_code AS state, count(*) AS total, sum(cnt) AS total_dups FROM (
    SELECT {household_fields}, coalesce(state_name, state_code) AS state_code,
        count(*) AS cnt
    FROM {table_name} AS p
    LEFT JOIN state_lookup ON (p.state = state_lookup.state_code)
    WHERE TRUE {exclude_sql}
    GROUP BY {household_fields}, coalesce(state_name, state_code)
) AS s
GROUP BY state_code
ORDER BY 1
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


GET_ALL_CAMPAIGN = """
SELECT * FROM campaigns WHERE id = :id
"""

INSERT_INTO_CAMPAIGN = """
INSERT INTO campaigns (name, channel, datasource, subquery, campaign_subquery_id)
VALUES (:name, :channel, :datasource, :subquery, :campaign_subquery_id)
RETURNING id
"""

GET_ALL_CAMPAIGN_CRITERIA = """
SELECT * FROM campaign_criteria WHERE campaign_id = :id
"""

INSERT_CAMPAIGN_CRITERIA = """
INSERT INTO campaign_criteria (
campaign_id, column_name, sql_type, sql_value, position, or_next
) VALUES (
:campaign_id, :column_name, :sql_type, :sql_value, :position, :or_next
)
"""

GET_CAMPAIGN_BY_ID = """
    SELECT id FROM campaigns WHERE id = :cid
"""

INSERT_CRITERION = """
    INSERT INTO campaign_criteria (campaign_id, position)
    VALUES (:campaign_id, (
        SELECT COALESCE(MAX(position), 0) + 1 FROM campaign_criteria WHERE campaign_id = :campaign_id
    ))
    RETURNING id, campaign_id, position
"""

GET_DATASOURCE_CAMPAIGN_ID = """
        SELECT cd.tablename
        FROM campaigns c
        JOIN campaign_datasources cd ON cd.datasource = c.datasource
        WHERE c.id = :cid
    """

GET_COLUMNS_SQL = """
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = :table
ORDER BY column_name
"""

GET_LEGEND_VALUES = """
SELECT name, position FROM frequent_value
WHERE tablename = :tablename AND columnname = :columnname
ORDER BY position ASC
"""

GET_DATASOURCE = """
SELECT datasource FROM campaigns WHERE id =:cid
"""

GET_SUBQUERY_DIALOG_SQL = """
SELECT child_table AS table, label
FROM campaign_subqueries
WHERE parent_table = :parent_table
GROUP BY child_table, label
ORDER BY child_table;
"""

GET_CAMPAIGN_SUBQUERY = """
SELECT id FROM campaign_subqueries
WHERE parent_table = :parent_ds AND child_table = :table AND label = :label
"""

INSERT_SUBQUERY_CAMPAIGN = """
INSERT INTO campaigns (name, begin_date, subquery, campaign_subquery_id, datasource)
VALUES (:name, CURRENT_DATE, true, :subquery_id, :table)
RETURNING id
"""


INSERT_CRITERION_IN_PARENT = """
INSERT INTO campaign_criteria (campaign_id, position, sql_type, sql_value)
VALUES (:campaign_id, (SELECT COALESCE(MAX(position), 0) + 1 FROM campaign_criteria WHERE campaign_id = :campaign_id),
        :sql_type, :sql_value)
"""

INSERT_EMPTY_CRITERION_IN_SUBQUERY = """
INSERT INTO campaign_criteria (campaign_id, position)
VALUES (:campaign_id,
        (SELECT COALESCE(MAX(position), 0) + 1 FROM campaign_criteria WHERE campaign_id = :campaign_id))
"""

GET_CAMPAIGN_BY_CAMPAIGN_ID = """
SELECT id, name, datasource FROM campaigns WHERE id = :cid
"""

GET_CAMPAIGN_BY_ID_SQL = """
SELECT * FROM campaigns WHERE id = :id
"""

GET_CAMPAIGN_CRITERIA = """
SELECT 
    cc.id, cc.column_name, cc.sql_type, cc.sql_value, cc.position, cc.or_next
FROM campaign_criteria cc
WHERE cc.campaign_id = :campaign_id
ORDER BY cc.position;
"""

GET_SUBQUERY_DETAILS = """
SELECT c.id, c.name, cs.id AS subquery_id, cs.label, cs.child_table
FROM campaigns c
JOIN campaign_subqueries cs ON cs.id = c.campaign_subquery_id
WHERE c.id = :subquery_campaign_id;
"""

