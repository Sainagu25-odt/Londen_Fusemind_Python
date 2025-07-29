from datetime import datetime

from sqlalchemy import text
import hashlib
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
            "homepage" : row["homepage"],
            "created_at": row["created_at"].strftime("%m/%d/%Y %I:%M %p") if row["created_at"] else None,
            "permissions": row["permissions"].split(",") if row["permissions"] else [],
        }
        users.append(user)

    return users

def add_user(data):
    username = data['username']
    display_name = data['display_name']
    raw_password = data['password']
    email = data['email']
    homepage = data.get('homepage')
    perms = data['permissions']

    # Check if user exists
    existing = db.session.execute(text(q.CHECK_USER_SQL), {'username': username}).fetchone()
    if existing:
        raise ValueError(f"User '{username}' already exists")
    hashed = hashlib.md5(raw_password.encode()).hexdigest()
    now = datetime.utcnow()
    db.session.execute(text(q.INSERT_USER_SQL), {
        'username': username,
        'password': hashed,
        'display_name': display_name,
        'email': email,
        'homepage': homepage,
        'created_at': now,
    })
    db.session.execute(text(q.DELETE_USER_PERMS_SQL), {'username': username})
    for perm in perms:
        db.session.execute(text(q.INSERT_USER_PERM_SQL), {
            'username': username,
            'perm_name': perm
        })
    db.session.commit()
    return {
        'username': username,
        'display_name': display_name,
        'email': email,
        'homepage': homepage,
        'created_at': now.strftime("%m/%d/%Y %I:%M %p"),
        'permissions': perms
    }


def edit_user(username, data):
    db.session.execute(text(q.DELETE_USER_PERMS_SQL), {"username": username})
    db.session.execute(
        text(q.UPDATE_USER_SQL),
        {
            "original_username" : username,
            "username": data["username"],
            "display_name": data["display_name"],
            "email": data.get("email"),
            "homepage": data.get("homepage"),
            "password": data.get("password") or None
        }
    )
    print("Inserted data ")
    for perm in data.get("permissions", []):
        db.session.execute(text(q.INSERT_USER_PERM_SQL), {"username":data["username"] , "perm_name": perm})
    db.session.commit()
    print("perm inserted")
    result = db.session.execute(text(q.GET_USER_SQL), {"username": data["username"]}).mappings().fetchone()
    return {
        "username": result['name'],
        "display_name": result["display_name"],
        "email": result["email"],
        "homepage": result["homepage"],
        "created_at": result["created_at"].strftime("%m/%d/%Y %I:%M %p"),
        "permissions": result["permissions"].split(",") if result["permissions"] else [],
    }
