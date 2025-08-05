import os
from decimal import Decimal
from flask import abort, current_app
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from extensions import db
from sql.campaigns_sql import  soft_delete_sql, undelete_sql, \
    GET_ACTIVE_CAMPAIGNS_SQL, GET_DELETED_CAMPAIGNS_SQL, ADD_CRITERION, ADD_CAMPAIGN, \
    GET_DROPDOWN_FOR_DATASOURCE, GET_CAMPAIGN_DETAILS_BY_ID, GET_PREBUILT_FIELDSETS_BY_CAMPAIGN, \
    GET_CAMPAIGN_COLUMNS_BY_ID, GET_PREVIOUS_PULLS_BY_CAMPAIGN, GET_ACTIVE_PULLS_BY_CAMPAIGN, GET_LATEST_PULL_SETTINGS, \
    INSERT_PULL_LIST
from datetime import datetime, timedelta, date
import sql.campaigns_sql as q


def get_campaigns(include_deleted):
    try:
        sql = GET_DELETED_CAMPAIGNS_SQL if include_deleted else GET_ACTIVE_CAMPAIGNS_SQL
        result = db.session.execute(text(sql)).mappings().all()
        return [dict(row) for row in result]
    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error in get_campaigns: {str(e)}")
        raise


def soft_delete_campaign(campaign_id):
    try:
        sql = text(soft_delete_sql)
        result = db.session.execute(sql, {'campaign_id': campaign_id})
        db.session.commit()
        if result.rowcount == 0:
            abort(404, description="Campaign not found")
    except SQLAlchemyError as e:
        db.session.rollback()
        abort(500, description=f"Database error: {str(e)}")


def undelete_campaign(campaign_id):
    try:
        sql = text(undelete_sql)
        result = db.session.execute(sql, {'campaign_id': campaign_id})
        db.session.commit()
        if result.rowcount == 0:
            abort(404, description="Campaign not found")
    except SQLAlchemyError as e:
        db.session.rollback()
        abort(500, description=f"Database error: {str(e)}")


def get_campaign_edit_data(campaign_id, show_counts):
    result = db.session.execute(text(q.GET_CAMPAIGN), {"id": campaign_id}).mappings().first()

    if not result:
        return {"message": "Campaign not found"}, 404

    # Fetch root criteria
    criteria_rows = db.session.execute(text(q.GET_CRITERIA), {"id": campaign_id}).mappings().all()
    criteria = [dict(row) for row in criteria_rows]

    # Fetch subquery children
    subquery_rows = db.session.execute(text(q.GET_SUBQUERY_CHILDREN), {"parent_id": campaign_id}).mappings().all()
    subqueries = []

    for sub in subquery_rows:
        # Join info from campaign_subqueries table
        join_info = db.session.execute(
            text(q.GET_SUBQUERY_JOIN),
            {"parent_id": campaign_id, "sub_id": sub["id"]}
        ).mappings().first()

        # Subquery criteria
        sub_criteria_rows = db.session.execute(
            text(q.GET_SUBQUERY_CRITERIA),
            {"sub_id": sub["id"]}
        ).mappings().all()

        subqueries.append({
            "id": sub["id"],
            "name": sub["name"],
            "begin_date": str(sub["begin_date"]) if sub["begin_date"] else None,
            "deleted": sub["deleted"],
            "criteria": [dict(sc) for sc in sub_criteria_rows],
            "join": dict(join_info) if join_info else {}
        })

    response = {
        "id": result["id"],
        "name": result["name"],
        "description": result["description"],
        "channel": result["channel"],
        "begin_date": str(result["begin_date"]) if result["begin_date"] else None,
        "deleted": result["deleted"],
        "datasource_table": result["datasource"],
        "criteria": criteria,
        "subqueries": subqueries
    }

    if show_counts and result["tablename"]:
        count_query = f"SELECT COUNT(*) FROM {result['tablename']} p"
        try:
            count = db.session.execute(text(count_query)).scalar()
            response["counts"] = int(count)
        except Exception as e:
            response["counts"] = None

    return response


def save_campaign_criteria(campaign_id, criteria_list):
    for row in criteria_list:
        params = {
            "campaign_id": campaign_id,
            "column_name": row.get("column_name"),
            "operator": row.get("operator"),
            "value": row.get("value"),
            "is_or": row.get("is_or", False)
        }

        if "row_id" in row and row["row_id"]:
            params["id"] = row["row_id"]
            db.session.execute(text(q.SAVE_CRITERIA_UPDATE), params)
        else:
            db.session.execute(text(q.SAVE_CRITERIA_INSERT), params)


def delete_criteria_row(campaign_id, row_id):
    db.session.execute(text(q.DELETE_CRITERIA_ROW), {
        "id": row_id,
        "campaign_id": campaign_id
    })


def add_criterion(campaign_id, data):
    try:
        db.session.execute(text(ADD_CRITERION), {
            "campaign_id": campaign_id,
            "column_name": data["column_name"],
            "sql_type": data["sql_type"],
            "sql_value": data["sql_value"],
            "or_next": data.get("or_next", False)
        })
        db.session.commit()
        return {"message": "Criterion added successfully"}
    except SQLAlchemyError as e:
        db.session.rollback()
        raise e


def add_campaign(data):
    try:
        result = db.session.execute(text(ADD_CAMPAIGN), {
            "name": data["name"],
            "description": data["description"],
            "channel": data["channel"],
            "datasource": data["datasource"],
            "begin_date": data["begin_date"]
        })
        new_id = result.fetchone()[0]
        db.session.commit()
        return {"message": "Campaign added successfully", "id": new_id}
    except SQLAlchemyError as e:
        db.session.rollback()
        raise e


def get_dropdowns_for_datasources():
    result = db.session.execute(text(GET_DROPDOWN_FOR_DATASOURCE))
    rows = result.fetchall()
    dropdown_set = {row[0] for row in rows if row[0] not in (None, '')}
    dropdown_list = sorted(dropdown_set)
    return {
        "count": len(dropdown_list),
        "datasources": dropdown_list
    }

def get_retrieval_methods():
    return [
        {"method": "one_per_household", "label": "One per household"},
        {"method": "every_n", "label": "Select every Nth record", "default_value": 1},
        {"method": "num_records", "label": "Pull exactly N records", "default_value": 1}
    ]

def format_pull_values(row):
    return {
        'householding': "One per household" if row['householding'] == '1' else "All in household",
        'every_n': f"every {row['every_n']} record(s)" if row['every_n'] else None,
        'num_records': f"Pull only {row['num_records']} records" if row['num_records'] else None,
    }

def get_previous_pulls(campaign_id):
    # Previous pulls by campaign with username and date
    pre_pulls = db.session.execute(
        text(GET_PREVIOUS_PULLS_BY_CAMPAIGN), {'campaign_id': campaign_id}
    ).mappings().fetchall()

    previous_pulls = []
    for r in pre_pulls:
        pull_values = format_pull_values(r)
        previous_pulls.append({
            "name": r['name'],
            "requested_at": r['requested_at'].strftime("%m/%d/%Y %I:%M %p") if r['requested_at'] else None,
            "requested_by": r['requested_by'],
            "householding": pull_values['householding'],
            "every_n": pull_values['every_n'],
            "pull_records": pull_values['num_records']
        })
    return previous_pulls

def build_campaign_request_response(campaign_id, user):
    campaign = db.session.execute(text(GET_CAMPAIGN_DETAILS_BY_ID), {'campaign_id': campaign_id}).fetchone()
    if not campaign:
        return {'error': 'Campaign not found'}, 404

    campaign = dict(campaign._mapping)

    now = datetime.now()
    day = now.day  # This gives day without leading zero on all platforms
    list_title = f"{campaign['channel']} {campaign['name']} {now.strftime('%b')} {day}, {now.strftime('%Y %I:%M:%S%p').lower()}"

    # Prebuilt fieldsets based on datasource of campaign
    fieldsets = db.session.execute(text(GET_PREBUILT_FIELDSETS_BY_CAMPAIGN), {'campaign_id': campaign_id}).fetchall()
    prebuilt_fieldsets = [dict(row._mapping) for row in fieldsets]

    # Campaign columns (custom fields)
    columns = db.session.execute(text(GET_CAMPAIGN_COLUMNS_BY_ID), {'campaign_id': campaign_id}).fetchall()

    campaign_columns = list({row[0] for row in columns if row[0] is not None})

    # Build all retrieval method “radio” options
    retrieval_options = get_retrieval_methods()

    #get_previous_pulls
    previous_pulls = get_previous_pulls(campaign_id)

    # get active pulls
    act_pulls = db.session.execute(
        text(GET_ACTIVE_PULLS_BY_CAMPAIGN)).mappings().fetchall()

    active_pulls = []
    for r in act_pulls:
        pull_values = format_pull_values(r)
        active_pulls.append({
            "name": r['name'],
            "requested_at": r['requested_at'].strftime("%m/%d/%Y %I:%M %p") if r['requested_at'] else None,
            "requested_by": r['requested_by'],
            "householding": pull_values['householding'],
            "every_n": pull_values['every_n'],
            "pull_records": pull_values['num_records']
        })

    # Get the latest pull record to get current retrieval selections
    latest_pull = db.session.execute(text(GET_LATEST_PULL_SETTINGS), {'campaign_id': campaign_id}).mappings().fetchone()
    retrieval_selection = {
        "householding": latest_pull['householding'] if latest_pull else None,
        "every_records": latest_pull['every_n'] if latest_pull else None,
        "pull_records": latest_pull['num_records'] if latest_pull else None
    }
    return {
        "campaign": campaign,
        "list_title": list_title,
        "prebuilt_fieldsets": prebuilt_fieldsets,
        "custom_fieldsets": campaign_columns,
        "retrieval_options": retrieval_options,
        "retrieval_selection": retrieval_selection,
        "previous_pulls": previous_pulls,
        "active_pulls": active_pulls
    }

def _build_pull_response(rows):
    pull_list = []
    for row in rows:
        row = dict(row)  # convert RowMapping to dict
        pull_list.append({
            "campaign_list_id" : row.get("list_id"),
            "campaign": row.get("campaign"),
            "list_title": row.get("name"),  # FIXED: was null because key was incorrect
            "requested_by": row.get("requested_by"),
            "time_requested": row.get("requested_at").strftime("%m/%d/%y %H:%M:%S") if row.get("requested_at") else None,
            "time_completed": row.get("completed_at").strftime("%m/%d/%y %H:%M:%S") if row.get("completed_at") else "Pending"
        })
    return pull_list

def insert_pull_list(args, current_user):
    try:
        campaign_id = args["campaign_id"]

        campaign = db.session.execute(text(GET_CAMPAIGN_DETAILS_BY_ID), {'campaign_id': campaign_id}).fetchone()
        if not campaign:
            return {'error': 'Campaign not found'}, 404

        campaign = dict(campaign._mapping)

        now = datetime.now().replace(microsecond=0)
        day = now.day  # This gives day without leading zero on all platforms
        list_title = f"{campaign['channel']} {campaign['name']} {now.strftime('%b')} {day}, {now.strftime('%Y %I:%M:%S%p').lower()}"

        latest_pull = db.session.execute(text(GET_LATEST_PULL_SETTINGS), {'campaign_id': campaign_id}).mappings().fetchone()
        latest_pull = latest_pull or {}
        payload = {
            "campaign_id": campaign_id,
            "requested_at": now,
            "completed_at": None,
            "fieldset_id": args.get("fieldset_id") or latest_pull.get("fieldset_id") or 1,
            "every_n": args.get("every_n") or latest_pull.get("every_n") or 1,
            "num_records": args.get("num_records") or latest_pull.get("num_records"),
            "fields": args.get("fields") or latest_pull.get("fields") or "",
            "requested_by": current_user['name'],
            "excluded_pulls": args.get("excluded_pulls") or latest_pull.get("excluded_pulls") or "",
            "householding": args.get("householding") or latest_pull.get("householding") or "",
            "request_email": args.get("request_email") or latest_pull.get("request_email") or current_user["email"],
            "criteria_sql": "",
            "name": list_title
        }
        db.session.execute(text(INSERT_PULL_LIST), payload)
        db.session.commit()

        # return just inserted pull as active
        rows = db.session.execute(text(GET_ACTIVE_PULLS_BY_CAMPAIGN)).mappings().fetchall()
        return {"active_pulls": _build_pull_response(rows)}
    except Exception as e:
        db.session.rollback()
        raise e

def get_global_active_pulls():
    try:
        rows = db.session.execute(text(GET_ACTIVE_PULLS_BY_CAMPAIGN)).mappings().fetchall()
        return {"active_pulls": _build_pull_response(rows)}
    except Exception as e:
        raise e

# show records
def serialize_record(record):
    def convert_value(value):
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        elif isinstance(value, Decimal):
            return float(value)
        return value
    return {k: convert_value(v) for k, v in record.items()}

def get_campaign_record_data(campaign_id, page=1, limit=25):

    offset = (page - 1) * limit
    # Step 1: Get campaign and datasource info
    campaign_info = db.session.execute(text("""
        SELECT c.id, c.datasource, d.tablename
        FROM campaigns c
        JOIN campaign_datasources d ON c.datasource = d.datasource
        WHERE c.id = :campaign_id
    """), {'campaign_id': campaign_id}).fetchone()

    if not campaign_info:
        return None

    table_name = campaign_info.tablename

    # Step 2: Get primary key fields
    primary_keys = db.session.execute(text("""
        SELECT column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'PRIMARY KEY'
          AND tc.table_name = :table
        ORDER BY column_name
    """), {'table': table_name}).fetchall()

    primary_key_fields = [f"p.{row[0]}" for row in primary_keys]
    primary_key = ', '.join(primary_key_fields)
    pk_concat_sql = "||','||".join([f"p.{row[0]}::text" for row in primary_keys])

    # # Step 3: Get household fields
    household_columns = db.session.execute(text("""
        SELECT column_name FROM campaign_datasource_household h
        JOIN campaign_datasources d ON h.datasource = d.datasource
        WHERE d.datasource = :datasource_id
    """), {'datasource_id': campaign_info.datasource}).fetchall()

    household_fields = ', '.join([f"p.{row[0]}" for row in household_columns]) or 'NULL'

    # Step 4: Get order_by column (if not in schema use fallback)
    order_by_row = db.session.execute(text("""
        SELECT order_by FROM campaign_datasources WHERE datasource = :datasource
    """), {'datasource': campaign_info.datasource}).fetchone()
    order_by = order_by_row[0] if order_by_row and order_by_row[0] else "p.id"

    # Step 5: Joins — always join state_lookup if 'state' exists
    columns = db.session.execute(text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = :table
    """), {'table': table_name}).fetchall()

    column_names = [row[0] for row in columns]

    all_column_names = ', '.join([f"p.{row[0]}" for row in columns])

    # If 'state' column exists, add join and computed column
    joins = ''
    if 'state' in column_names:
        joins += ' LEFT JOIN state_lookup ON (p.state = state_lookup.state_code) '

    # Step 6: Where conditions (from campaign_criteria if needed)
    # Currently kept empty, can be built dynamically later
    where_conditions = ''

    # Step 7: Final SQL
    final_sql = q.get_campaign_records_sql.format(
        primary_key=all_column_names,
        pk_concat_sql=pk_concat_sql,
        table_name=table_name,
        joins=joins,
        where_conditions=where_conditions,
        order_by=order_by,
        limit = limit,
        offset = offset
    )

    #
    result = db.session.execute(text(final_sql))
    columns = result.keys()  # Get all column names

    # Convert each row to a dictionary using column names
    records = [dict(zip(columns, row)) for row in result.fetchall()]
    serialized_data = [serialize_record(row) for row in records]
    return serialized_data



def get_campaign_datasource_info(campaign_id):
    sql = text(q.GET_CAMPAIGN_DATASOURCE_INFO_SQL)
    result = db.session.execute(sql, {"campaign_id": campaign_id}).mappings().first()
    if not result:
        raise ValueError(f"No datasource found for campaign_id {campaign_id}")
    return result


def get_household_columns(datasource):
    sql = text(q.GET_HOUSEHOLD_COLUMNS_SQL)
    rows = db.session.execute(sql, {"datasource": datasource}).fetchall()
    return ",".join([row.column_name for row in rows]) if rows else ""

def get_primary_key_concat_sql(table_alias, table_name):
    sql = text(q.GET_PRIMARY_KEYS_SQL)
    rows = db.session.execute(sql, {"table_name": table_name}).fetchall()
    if not rows:
        raise ValueError(f"No primary key for table {table_name}")
    return "||','||".join([f"{table_alias}.{row.column_name}::text" for row in rows])


def get_base_sql(table_name, alias="p"):
    return f"""
        FROM {table_name} AS {alias}
        LEFT JOIN state_lookup ON ({alias}.state = state_lookup.state_code)
        WHERE TRUE
    """

def get_campaign_counts(campaign_id, exclude=None, household=False):
    datasource_info = get_campaign_datasource_info(campaign_id)
    datasource = datasource_info["datasource"]
    tablename = datasource_info["tablename"]
    table_alias = "p"
    household_fields = get_household_columns(datasource)
    pk_concat_sql = get_primary_key_concat_sql(table_alias, tablename)
    exclude_sql = ""
    if exclude:
        exclude_sql = f"""
                AND {pk_concat_sql} NOT IN (
                    SELECT DISTINCT keyvalue
                    FROM campaign_list_data
                    WHERE campaign_list_id IN ({exclude})
                )
            """
    if household:
        counts_sql = q.GET_COUNTS_HOUSEHOLD_SQL.format(
            household_fields=household_fields,
            table_name=tablename,
            exclude_sql=exclude_sql
        )
        universe_sql = q.GET_UNIVERSE_HOUSEHOLD_SQL.format(
            household_fields=household_fields,
            table_name=tablename,
            exclude_sql=exclude_sql
        )
        states_sql = q.GET_COUNTS_BY_STATE_HOUSEHOLD_SQL.format(
            household_fields=household_fields,
            table_name=tablename,
            exclude_sql=exclude_sql
        )
    else:
        base_sql = get_base_sql(tablename, table_alias)
        counts_sql = q.GET_COUNTS_NON_HOUSEHOLD_SQL.format(
            base_sql=base_sql,
            exclude_sql=exclude_sql
        )
        universe_sql = q.GET_UNIVERSE_NON_HOUSEHOLD_SQL.format(
            table_name=tablename,
            exclude_sql=exclude_sql
        )
        states_sql = q.GET_COUNTS_BY_STATE_NON_HOUSEHOLD_SQL.format(
            base_sql=base_sql,
            exclude_sql=exclude_sql
        )

    counts = db.session.execute(text(counts_sql)).scalar()
    universe = db.session.execute(text(universe_sql)).scalar()
    states_rows = db.session.execute(text(states_sql)).fetchall()
    def clean_row(row):
        return {
            k: int(v) if isinstance(v, Decimal) else v
            for k, v in row._mapping.items()
        }

    states = [clean_row(row) for row in states_rows]
    previous_pulls = get_previous_pulls(campaign_id)
    return {
        "campaign_name" : datasource_info['name'],
        "channel" : datasource_info['channel'],
        "counts": counts,
        "universe": universe,
        "states": states,
        "previous_pulls" : previous_pulls
    }


def get_global_campaign_counts():
    rows = db.session.execute(text(q.SQL_GLOBAL_CAMPAIGNS)).fetchall()
    result = []

    for r in rows:
        campaign_id = r.id
        table = r.tablename

        sql = q.SQL_TOTAL_COUNTS.format(table_name=table, exclude="")
        total = db.session.execute(text(sql)).scalar()

        result.append({
            "campaign_id": campaign_id,
            "total": int(total or 0)
        })

    return result

#pull lists
def get_pull_file_path(pull_id):
    try:
        row = db.session.execute(text(q.GET_CAMPAIGN_LIST_FILENAME), {"id": pull_id}).mappings().first()
        if not row:
            return None, "Campaign list not found"

        # Clean filename by removing invalid characters
        raw_name = row["file_name"]
        clean_name = "".join(c for c in raw_name if c.isalnum() or c in " _-").replace(":", "").replace(",", "").replace("  ", " ")
        clean_name = clean_name.replace(" ", "")  # optional: tighten name
        file_name = f"{clean_name}.zip"

        base_dir = current_app.config.get("BASE_DIR", os.getcwd())
        file_path = os.path.join(base_dir, "lists", file_name)

        return file_path, None
    except Exception as e:
        current_app.logger.error(f"[get_pull_file_path] Error: {e}")
        return None, "Internal error"


# copy campaign
def copy_campaign(original_id):
    # Step 1: Fetch original campaign
    original_campaign = db.session.execute(text(q.GET_ALL_CAMPAIGN), {'id': original_id}).fetchone()

    if not original_campaign:
        return None

    # Step 2: Create new campaign with modified name
    new_name = f"Copy of {original_campaign.name}"
    result = db.session.execute(text(q.INSERT_INTO_CAMPAIGN), {
        'name': new_name,
        'channel': original_campaign.channel,
        'datasource': original_campaign.datasource,
        'subquery': original_campaign.subquery,
        'campaign_subquery_id': original_campaign.campaign_subquery_id
    })
    #
    new_campaign_id = result.scalar()
    #
    # Step 3: Copy campaign_criteria
    criteria = db.session.execute(text(q.GET_ALL_CAMPAIGN_CRITERIA), {'id': original_id}).fetchall()


    for crit in criteria:
        sql_value = crit.sql_value
        if crit.sql_type == 'campaign':  # Indicates subquery
            subquery_id = copy_campaign(int(crit.sql_value))  # Recursive copy
            sql_value = subquery_id

        db.session.execute(text(q.INSERT_CAMPAIGN_CRITERIA), {
            'campaign_id': new_campaign_id,
            'column_name': crit.column_name,
            'sql_type': crit.sql_type,
            'sql_value': sql_value,
            'position': crit.position,
            'or_next': crit.or_next
        })

    db.session.commit()
    return new_campaign_id


def add_new_criteria_simple(campaign_id : int):
    campaign = db.session.execute(
        text(q.GET_CAMPAIGN_BY_ID), {"cid": campaign_id}
    ).fetchone()
    if not campaign:
        return None, "Invalid Campaign ID"

    # 2. Insert new criterion
    result = db.session.execute(text(q.INSERT_CRITERION),
                           {"campaign_id": campaign_id})
    row = result.fetchone()
    db.session.commit()

    return row.id

OPERATORS = [
    {"key": "equals", "label": "Equals"},
    {"key": "not_equal", "label": "Not Equal"},
    {"key": "contains", "label": "Contains"},
    {"key": "does_not_contain", "label": "Does Not Contain"},
    {"key": "greater_than", "label": "Greater Than"},
    {"key": "less_than", "label": "Less Than"},
    {"key": "equals_field", "label": "Equals Field"},
    {"key": "not_equal_field", "label": "Not Equal Field"},
    {"key": "greater_than_field", "label": "Greater Than Field"},
    {"key": "less_than_field", "label": "Less Than Field"},
    {"key": "in_comma_separated_field", "label": "IN Comma Separated Field"},
    {"key": "not_in_comma_separated_field", "label": "Not In Comma Separated Field"},
    {"key": "is_empty", "label": "Is Empty"},
    {"key": "not_empty", "label": "Not Empty"},
]

def get_add_criteria_dropdowns(campaign_id : int):
    campaign = db.session.execute(
        text(q.GET_CAMPAIGN_BY_ID), {"cid": campaign_id}
    ).fetchone()
    if not campaign:
        return None, "Invalid Campaign ID"

    result = db.session.execute(text(q.GET_DATASOURCE_CAMPAIGN_ID), {"cid": campaign_id}).fetchone()

    if not result:
        return []
    table_name = result[0]

    rows = db.session.execute(text(q.GET_COLUMNS_SQL), {"table": table_name}).fetchall()
    columns = [row[0] for row in rows]
    return {
        "columns": columns,
        "operators": OPERATORS,
        "values": []
    }


def get_legend_values(campaign_id, column):

    result= db.session.execute(text(q.GET_DATASOURCE_CAMPAIGN_ID), {"cid": campaign_id}).fetchone()
    if not result:
        return []
    table_name = result[0]

    legend_sql = q.GET_LEGEND_VALUES_SQL.format(
        column=column,
        table_name=table_name
    )

    rows = db.session.execute(text(legend_sql)).fetchall()
    result = [
        {
            "value": str(row[0]) if row[0] is not None else "",
            "total": int(row[1])
        }
        for row in rows
    ]
    return result

def get_subquery_dialog_options(campaign_id : int):
    result = db.session.execute(text(q.GET_DATASOURCE), {"cid": campaign_id}).fetchone()
    if not result:
        return {"tables": [], "labels": []}
    datasource = result[0]

    rows = db.session.execute(text(q.GET_SUBQUERY_DIALOG_SQL), {"parent_table": datasource}).fetchall()
    table_names = []
    label_names = []

    for r in rows:
        table_value = r[0]
        label_value = r[1]

        if table_value not in table_names:
            table_names.append(table_value)
        if label_value not in label_names:
            label_names.append(label_value)
    return {
        "table": table_names,
        "operator" : ["In", "Not In"],
        "label": label_names
    }


def create_subquery_campaign(cid, table, label, method):

    parent = db.session.execute(text(q.GET_CAMPAIGN_BY_CAMPAIGN_ID), {"cid": cid}).mappings().first()
    if not parent:
        raise Exception("campaign not found")

    # Step 2: Get campaign_subquery ID
    subquery_row = db.session.execute(text(q.GET_CAMPAIGN_SUBQUERY), {
        "parent_ds": parent["datasource"],
        "table": table,
        "label": label
    }).mappings().first()


    if not subquery_row:
        raise Exception("Campaign subquery mapping not found")


    # Step 3: Insert new campaign (as subquery)
    subquery_name = f"subquery for {parent['name']}"
    result = db.session.execute(text(q.INSERT_SUBQUERY_CAMPAIGN), {
        "name": subquery_name,
        "subquery_id": subquery_row["id"],
        "table": table
    })
    new_subquery_id = result.scalar()

    # Step 4: Add criterion to parent campaign
    sql_type = "in_sub" if method == "in" else "not_in_sub"
    db.session.execute(text(q.INSERT_CRITERION_IN_PARENT), {
        "campaign_id": cid,
        "sql_type": sql_type,
        "sql_value": new_subquery_id
    })

    # Step 5: Add empty criterion to subquery
    db.session.execute(text(q.INSERT_EMPTY_CRITERION_IN_SUBQUERY), {
        "campaign_id": new_subquery_id
    })


    db.session.commit()
    return new_subquery_id









