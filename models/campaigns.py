from flask import abort, current_app
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from sql.campaigns_sql import counts_sql_template, states_sql_template, soft_delete_sql, undelete_sql, \
    GET_ACTIVE_CAMPAIGNS_SQL, GET_DELETED_CAMPAIGNS_SQL, GET_CRITERIA, GET_CAMPAIGN, ADD_CRITERION, ADD_CAMPAIGN, \
    GET_DROPDOWN_FOR_DATASOURCE, GET_USER_FROM_TOKEN, GET_CAMPAIGN_DETAILS_BY_ID, GET_PREBUILT_FIELDSETS_BY_CAMPAIGN, \
    GET_CAMPAIGN_COLUMNS_BY_ID, GET_PREVIOUS_PULLS_BY_CAMPAIGN, GET_ACTIVE_PULLS_BY_CAMPAIGN

from datetime import datetime, timedelta

def get_campaigns(include_deleted):
    try:
        sql = GET_DELETED_CAMPAIGNS_SQL if include_deleted else GET_ACTIVE_CAMPAIGNS_SQL
        result = db.session.execute(text(sql)).mappings().all()
        return [dict(row) for row in result]
    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error in get_campaigns: {str(e)}")
        raise




# from sql.campaigns_sql import get_counts, get_household_counts, get_counts_by_state, get_household_counts_by_state, \
#     get_universe, get_household_universe
#
#
# class Campaign:
#     def __init__(self, id):
#         self.id = id  # included for compatibility
#
#     def counts(self, exclude=None):
#         return get_counts(exclude)
#
#     def household_counts(self, exclude=None):
#         return get_household_counts(exclude)
#
#     def counts_by_state(self, exclude=None):
#         return get_counts_by_state(exclude)
#
#     def household_counts_by_state(self, exclude=None):
#         return get_household_counts_by_state(exclude)
#
#     def universe(self):
#         return get_universe()
#
#     def household_universe(self):
#         return get_household_universe()




def get_campaign_details(campaign_id: int, household: bool, exclude: str | None) -> dict:
    # Fetch base criteria SQL
    row = db.session.execute(
        text("SELECT criteria_sql FROM campaign_lists WHERE id = :id"),
        {"id": campaign_id}
    ).fetchone()
    if not row:
        return None

    criteria_sql = row.criteria_sql
    exclude_clause = f"WHERE {exclude}" if exclude else ""

    cnt_sql = counts_sql_template(household).format(
        criteria_sql=criteria_sql,
        exclude_clause=exclude_clause
    )
    st_sql = states_sql_template(household).format(
        criteria_sql=criteria_sql,
        exclude_clause=exclude_clause
    )

    counts_row = db.session.execute(text(cnt_sql)).fetchone()
    states_rows = db.session.execute(text(st_sql)).fetchall()

    return {
        "counts": counts_row.counts if counts_row else 0,
        "universe": counts_row.counts if counts_row else 0,
        "states": [
            {
                "state": r.state,
                "total": r.total,
                **({"total_dups": r.total_dups} if household else {})
            }
            for r in states_rows
        ]
    }

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
    result = db.session.execute(text(GET_CAMPAIGN), {"id": campaign_id}).mappings().first()

    if not result:
        return {"message": "Campaign not found"}, 404

    criteria_rows = db.session.execute(text(GET_CRITERIA), {"id": campaign_id}).mappings().all()
    criteria = [{
        "column_name": row["column_name"],
        "operator": row["operator"],
        "value": row["value"],
        "is_or": row["is_or"]
    } for row in criteria_rows]

    response = {
        "id": result["id"],
        "name": result["name"],
        "description": result["description"],
        "channel": result["channel"],
        "deleted": result["deleted"],
        "datasource_table": result["tablename"],
        "criteria": criteria
    }

    if show_counts == 1 and result["tablename"]:
        count_query = f"SELECT COUNT(*) FROM {result['tablename']} p"
        count = db.session.execute(text(count_query)).scalar()
        response["counts"] = count

    return response

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
        print(result)
        new_id = result.fetchone()[0]
        print(new_id)
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

def build_campaign_request_response(campaign_id, user):
    campaign = db.session.execute(text(GET_CAMPAIGN_DETAILS_BY_ID), {'campaign_id': campaign_id}).fetchone()
    if not campaign:
        return {'error': 'Campaign not found'}, 404

    campaign = dict(campaign._mapping)

    now = datetime.now()
    day = now.day  # This gives day without leading zero on all platforms
    list_title = f"{campaign['name']} {now.strftime('%b')} {day}, {now.strftime('%Y %I:%M:%S%p').lower()}"

    # Prebuilt fieldsets based on datasource of campaign
    fieldsets = db.session.execute(text(GET_PREBUILT_FIELDSETS_BY_CAMPAIGN), {'campaign_id': campaign_id}).fetchall()
    prebuilt_fieldsets = [dict(row._mapping) for row in fieldsets]

    # Campaign columns (custom fields)
    columns = db.session.execute(text(GET_CAMPAIGN_COLUMNS_BY_ID), {'campaign_id': campaign_id}).fetchall()

    campaign_columns = list({row[0] for row in columns if row[0] is not None})

    # Build all retrieval method “radio” options
    retrieval_options = get_retrieval_methods()

    # Previous pulls by campaign with username and date
    pre_pulls = db.session.execute(
        text(GET_PREVIOUS_PULLS_BY_CAMPAIGN ), {'campaign_id': campaign_id}
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

    # get active pulls
    act_pulls = db.session.execute(
        text(GET_ACTIVE_PULLS_BY_CAMPAIGN), {'campaign_id': campaign_id}
    ).mappings().fetchall()

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
    latest_pull = db.session.execute(
        text("""
                SELECT householding, every_n, num_records 
                FROM campaign_lists 
                WHERE campaign_id = :campaign_id 
                ORDER BY requested_at DESC LIMIT 1
                """), {'campaign_id': campaign_id}
    ).mappings().fetchone()
    if latest_pull:
        retrieval_selection = {
            "householding": latest_pull['householding'],
            "every_records": latest_pull['every_n'],
            "pull_records": latest_pull['num_records']
        }
    else:
        retrieval_selection = {
            "householding": None,
            "every_records": None,
            "pull_records": None
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





