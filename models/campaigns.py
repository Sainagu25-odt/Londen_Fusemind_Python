import os
from decimal import Decimal

from flask import abort, current_app
from sqlalchemy import text, inspect
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from sql.campaigns_sql import counts_sql_template, states_sql_template, soft_delete_sql, undelete_sql, \
    GET_ACTIVE_CAMPAIGNS_SQL, GET_DELETED_CAMPAIGNS_SQL, GET_CRITERIA, GET_CAMPAIGN, ADD_CRITERION, ADD_CAMPAIGN, \
    GET_DROPDOWN_FOR_DATASOURCE, GET_USER_FROM_TOKEN, GET_CAMPAIGN_DETAILS_BY_ID, GET_PREBUILT_FIELDSETS_BY_CAMPAIGN, \
    GET_CAMPAIGN_COLUMNS_BY_ID, GET_PREVIOUS_PULLS_BY_CAMPAIGN, GET_ACTIVE_PULLS_BY_CAMPAIGN, GET_LATEST_PULL_SETTINGS, \
    INSERT_PULL_LIST, GET_ALL_CAMPAIGNS_SQL, \
    get_show_records_sql, get_records

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


# def get_campaign_edit_data(campaign_id, show_counts):
#     result = db.session.execute(text(GET_CAMPAIGN), {"id": campaign_id}).mappings().first()
#
#     if not result:
#         return {"message": "Campaign not found"}, 404
#
#     criteria_rows = db.session.execute(text(GET_CRITERIA), {"id": campaign_id}).mappings().all()
#     print(criteria_rows)
#     criteria = [{
#         "row_id": row["id"],
#         "column_name": row["column_name"],
#         "operator": row["operator"],
#         "value": row["value"],
#         "is_or": row["is_or"]
#     } for row in criteria_rows]
#
#     response = {
#         "id": result["id"],
#         "name": result["name"],
#         "description": result["description"],
#         "channel": result["channel"],
#         "begin_date": str(result["begin_date"]),
#         "deleted": result["deleted"],
#         "datasource_table": result["tablename"],
#         "criteria": criteria
#     }
#
#     if show_counts == 1 and result["tablename"]:
#         count_query = f"SELECT COUNT(*) FROM {result['tablename']} p"
#         count = db.session.execute(text(count_query)).scalar()
#         response["counts"] = count
#
#     return response


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
        "datasource_table": result["tablename"],
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
        print(params)


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
    list_title = f"{campaign['channel']} {campaign['name']} {now.strftime('%b')} {day}, {now.strftime('%Y %I:%M:%S%p').lower()}"

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
        print(current_user)

        now = datetime.now().replace(microsecond=0)
        day = now.day  # This gives day without leading zero on all platforms
        list_title = f"{campaign['channel']} {campaign['name']} {now.strftime('%b')} {day}, {now.strftime('%Y %I:%M:%S%p').lower()}"

        latest_pull = db.session.execute(text(GET_LATEST_PULL_SETTINGS), {'campaign_id': campaign_id}).mappings().fetchone()
        latest_pull = latest_pull or {}
        print(latest_pull)
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
        print(payload)

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




# def get_show_records(campaign_id: int, limit: int = 100):
#     row = db.session.execute(
#         text("SELECT datasource FROM campaigns WHERE id = :cid AND deleted_at IS NULL"),
#         {"cid": campaign_id}
#     ).first()
#
#     if not row:
#         return [], f"Campaign {campaign_id} not found or deleted"
#
#     table_name = row[0]
#     print(table_name)
#
#     # Define key columns based on table
#     if table_name in ["primary_policies", "noninsurance_policies"]:
#         key_company = "p.company_number"
#         key_policy = "p.policy"
#         key_insured = "p.insured"
#     elif table_name == "policies":
#         key_company = "p.company"
#         key_policy = "p.policy_number"
#         key_insured = "p.insuredl"
#     else:
#         return [], f"Unsupported datasource table: {table_name}"
#
#     # key_expr = f"{key_company}::text || ',' || {key_policy}::text"
#     # print(key_expr)
#
#     sql = f"""
#         SELECT
#             {key_company} AS "Company Number",
#             {key_policy} AS "Policy",
#             {key_insured} AS "Insured",
#             p.ownerl AS "Owner Last Name",
#             p.address1 AS "Address1",
#             p.address2 AS "Address2",
#             COALESCE(state_lookup.state_name, p.state) AS "State Code",
#             (
#                 SELECT STRING_AGG(DISTINCT d.campaign_list_id::text, ',')
#                 FROM campaign_list_data d
#                 WHERE d.keyvalue LIKE '%' || p.policy_number::text
#             ) AS "lists"
#         FROM {table_name} p
#         LEFT JOIN state_lookup ON p.state = state_lookup.state_code
#         ORDER BY 1 DESC,
#                  (SELECT {key_policy} ~ '^[0-9]+$') DESC,
#                  2 DESC, 3
#         LIMIT {limit};
#     """
#
#     rows = db.session.execute(text(sql)).mappings().all()
#     records_data = [dict(r) for r in rows]
#     print(records_data)
#     return records_data

# Mapping of frontend fields to DB columns

FIELD_MAP = {
    "Company Number": "p.company",
    "Policy": "p.policy_number",
    "Insured": "p.insuredl",
    "Owner Last Name": "p.ownerl",
    "Address1": "p.address1",
    "Address2": "p.address2",
    "City": "p.city",
    "State": "p.state",
    "Zip Code": "p.zip5",
    "Bad Address": "p.bad_address",
    "Do Not Call": "p.do_not_call",
    "Do Not Mail": "p.donotmail",
    "Fcgs Membership": "p.fcgs",
    "Language Flag": "p.language_flag",
    "Child Rider Units": "p.child_rider_units",
    "Pay Type": "p.pay_type",
    "Mode": "p.mode",
    "Annual Premium": "p.annual_premium",
    "Semiannual Premium": "p.semiannual_premium",
    "Quarterly Premium": "p.quarterly_premium",
    "Monthly Premium": "p.monthly_premium",
    "Draft Premium": "p.draft_premium",
    "Insured Prefix": "p.insured_prefix",
    "Insured First Name": "p.insured_first_name",
    "Insured Middle Name": "p.insured_middle_name",
    "Insured Last Name": "p.insured_last_name",
    "Insured Suffix": "p.insured_suffix",
    "Gender": "p.gender",
    "Issue Age": "p.issue_age",
    "Status": "p.status",
    "Plan": "p.plan",
    "Class": "p.class",
    "Face Amount": "p.face_amount",
    "Premiums Payable Period": "p.premiums_payable_period",
    "Line Of Business": "p.line_of_business",
    "Accidental Death": "p.accidental_death",
    "Add Units": "p.add_units",
    "Add Camp": "p.add_camp",
    "Mga": "p.mga",
    "Mmga": "p.mmga",
    "Date Of Birth": "p.dob",
    "Issue Date": "p.issue_date",
    "Paid To": "p.paid_to",
    "Phone Number": "p.phone_number",
    "Phone Type": "p.phone_type",
    "Assigned Flag": "p.assigned_flag",
    "Fh Is Beneficiary": "p.fh_is_beneficiary",
    "Payor Prefix": "p.payor_prefix",
    "Payor First Name": "p.payor_first_name",
    "Payor Middle Name": "p.payor_middle_name",
    "Payor Last Name": "p.payor_last_name",
    "Payor Suffix": "p.payor_suffix",
    "Company Division": "p.company_division",
    "Roger Policy Number": "p.roger_policy_number",
    "Last Four": "p.last_four",
    "Inforce Flag": "p.inforce_flag",
    "Name Bank": "p.name_bank",
    "Savings Flag": "p.savings_flag",
    "First Beneficiary": "p.first_beneficiary",
    "Second Beneficiary": "p.second_beneficiary",
    "State Code": "COALESCE(state_lookup.state_name, p.state)",
    "County Code": "p.county_code",
}


# List of expected fields (based on UI + PHP code)
EXPECTED_COLUMNS = [
    "company_number", "policy", "insured", "owner_last_name", "address1", "address2", "city", "state", "zip_code",
    "bad_address", "do_not_call", "do_not_mail", "fcgs_membership", "language_flag", "child_rider_units", "pay_type",
    "mode", "annual_premium", "semiannual_premium", "quarterly_premium", "monthly_premium", "draft_premium",
    "insured_prefix", "insured_first_name", "insured_middle_name", "insured_last_name", "insured_suffix", "gender",
    "issue_age", "status", "plan", "class", "face_amount", "premiums_payable_period", "line_of_business",
    "accidental_death", "add_units", "add_camp", "mga", "mmga", "dob", "issue_date", "paid_to", "phone_number",
    "phone_type", "assigned_flag", "fh_is_beneficiary", "payor_prefix", "payor_first_name", "payor_middle_name",
    "payor_last_name", "payor_suffix", "company_division", "roger_policy_number", "last_four", "inforce_flag",
    "name_bank", "savings_flag", "first_beneficiary", "second_beneficiary", "county_code"
]

def to_label(col):
    return ' '.join(word.capitalize() for word in col.split('_'))

def get_table_columns(table_name):
    sql = """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = :tname
    """
    result = db.session.execute(text(sql), {'tname': table_name}).fetchall()
    return {row[0] for row in result}

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
    #
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
    #
    primary_key_fields = [f"p.{row[0]}" for row in primary_keys]
    primary_key = ', '.join(primary_key_fields)
    pk_concat_sql = "||','||".join([f"p.{row[0]}::text" for row in primary_keys])
    #

    # # Step 3: Get household fields
    household_columns = db.session.execute(text("""
        SELECT column_name FROM campaign_datasource_household h
        JOIN campaign_datasources d ON h.datasource = d.datasource
        WHERE d.datasource = :datasource_id
    """), {'datasource_id': campaign_info.datasource}).fetchall()


    household_fields = ', '.join([f"p.{row[0]}" for row in household_columns]) or 'NULL'

    #
    # Step 4: Get order_by column (if not in schema use fallback)
    order_by_row = db.session.execute(text("""
        SELECT order_by FROM campaign_datasources WHERE datasource = :datasource
    """), {'datasource': campaign_info.datasource}).fetchone()
    order_by = order_by_row[0] if order_by_row and order_by_row[0] else "p.id"
    print(order_by)
    #
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
    #
    # Step 6: Where conditions (from campaign_criteria if needed)
    # Currently kept empty, can be built dynamically later
    where_conditions = ''
    #
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








# counts
def build_exclude(excludes):
    if not excludes:
        return ''
    clauses = [f"AND {e.strip()}" for e in excludes.split(',') if e.strip()]
    return ' '.join(clauses)

def get_campaign_counts(campaign_id, household=False, excludes=None):
    row = db.session.execute(text(q.GET_CAMPAIGN_TABLE), {"campaign_id": campaign_id}).first()
    if not row:
        raise ValueError("Campaign not found")

    table = row.tablename
    exclude = build_exclude(excludes)

    if household:
        hf_row = db.session.execute(text(q.GET_HOUSEHOLD_FIELDS), {"campaign_id": campaign_id}).first()
        if not hf_row or not hf_row.hf:
            raise ValueError("No household fields defined")
        fields = hf_row.hf

        sql = q.SQL_HOUSEHOLD_COUNTS.format(table_name=table, fields=fields, exclude=exclude)
        h = db.session.execute(text(sql)).first()

        return {
            "state_counts": None,
            "total_count": None,
            "total_households": int(h.total_households or 0),
            "total_duplicates": int(h.total_dups or 0)
        }

    state_sql = q.SQL_COUNTS_BY_STATE.format(table_name=table, exclude=exclude)
    rows = db.session.execute(text(state_sql)).fetchall()

    total_sql = q.SQL_TOTAL_COUNTS.format(table_name=table, exclude=exclude)
    total = db.session.execute(text(total_sql)).scalar()

    return {
        "state_counts": [{"state": r.state, "total": int(r.total)} for r in rows],
        "total_count": int(total or 0),
        "total_households": 0,
        "total_duplicates": 0
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
