from sqlalchemy import text
from extensions import db

def find_user_by_username(username):
    sql = text("SELECT * FROM logins WHERE name = :username")
    result = db.session.execute(sql, {'username': username}).fetchone()
    return dict(result._mapping) if result else None