from functools import wraps
from flask import g, abort


def require_permission(permission_name):
    def wrapper(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(g, 'permissions'):
                return {"message": "Permissions not set in token"}, 401
            if permission_name not in g.permissions:
                return {"message": "Permission denied"}, 401
            return f(*args, **kwargs)
        return decorated
    return wrapper