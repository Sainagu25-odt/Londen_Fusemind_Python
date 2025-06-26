from flask import abort, current_app
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from sql.campaigns_sql import counts_sql_template, states_sql_template, soft_delete_sql, undelete_sql, \
    GET_ACTIVE_CAMPAIGNS_SQL, GET_DELETED_CAMPAIGNS_SQL, GET_CRITERIA, GET_CAMPAIGN, ADD_CRITERION


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