from sqlalchemy import text
from extensions import db
import sql.dashboard_sql as q

def get_dashboard_stats():
    policy_holders = db.session.execute(text(q.GET_POLICY_HOLDERS)).scalar()
    non_insurance = db.session.execute(text(q.GET_NON_INSURANCE)).scalar()
    total_responders = db.session.execute(text(q.GET_TOTAL_RESPONDERS)).scalar()

    return {
        "policy_holders": policy_holders,
        "non_insurance": non_insurance,
        "total_responders": total_responders
    }