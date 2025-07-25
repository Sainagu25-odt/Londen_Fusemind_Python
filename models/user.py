from sqlalchemy import text
from extensions import db

def find_user_by_username(username):
    sql = text("SELECT * FROM logins WHERE name = :username")
    result = db.session.execute(sql, {'username': username}).fetchone()
    return dict(result._mapping) if result else None

def get_permissions_by_username(username):
    sql = text("""
        SELECT p.name
        FROM permissions p
        JOIN login_permissions lp ON lp.permission_name = p.name
        WHERE lp.login_name = :username
    """)
    result = db.session.execute(sql, {"username": username}).fetchall()
    return [row[0] for row in result]