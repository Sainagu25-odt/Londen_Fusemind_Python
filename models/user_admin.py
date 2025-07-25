from sqlalchemy import text

from extensions import db
import sql.user_admin_sql  as q


def get_all_users():
    result = db.session.execute(text(q.GET_USERS_SQL))
    rows = result.mappings().all()
    users = []
    for row in rows:
        user = {
            "username": row["name"],
            "display_name": row["display_name"],
            "email": row["email"],
            "created_at": row["created_at"].strftime("%m/%d/%Y %I:%M %p") if row["created_at"] else None,
            "permissions": row["permissions"].split(",") if row["permissions"] else [],
        }
        users.append(user)

    return users