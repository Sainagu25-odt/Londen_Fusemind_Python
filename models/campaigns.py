from flask import abort, current_app
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from sql.campaigns_sql import counts_sql_template, states_sql_template, soft_delete_sql, undelete_sql, \
    GET_ACTIVE_CAMPAIGNS_SQL, GET_DELETED_CAMPAIGNS_SQL, GET_CAMPAIGN_BY_ID, GET_CHANNELS, GET_CRITERIA


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



def get_campaign_edit_data(campaign_id, show_counts=False):
    # Check if campaign exists
    result = db.session.execute(text(GET_CAMPAIGN_BY_ID), {"id": campaign_id}).fetchone()
    if not result:
        abort(404, f"Campaign with ID {campaign_id} not found")

    # Get distinct channels
    channels_result = db.session.execute(text(GET_CHANNELS)).fetchall()
    channels = [row[0] for row in channels_result]

    # Get criteria
    criteria_result = db.session.execute(text(GET_CRITERIA), {"id": campaign_id}).fetchall()
    criteria = [
        {
            "column_name": row[0],
            "operator": row[1],
            "value": row[2],
            "is_or": row[3]
        }
        for row in criteria_result
    ]

    steps = []
    if show_counts:
        for i in range(1, len(criteria) + 1):
            where_clauses = []
            params = {}
            for idx, crit in enumerate(criteria[:i]):
                key = f"param_{idx}"
                where_clauses.append(f"p.{crit['column_name']} {crit['operator']} :{key}")
                params[key] = crit['value']
            where_sql = " AND ".join(where_clauses)
            sql = f"SELECT COUNT(*) FROM campaigns AS p WHERE {where_sql}" if where_sql else "SELECT COUNT(*) FROM campaigns"
            count = db.session.execute(text(sql), params).scalar()
            steps.append(count)

    return {
        "campaign_id": campaign_id,
        "channels": channels,
        "criteria": criteria,
        "steps": steps,
        "currentStep": 0 if show_counts else None
    }