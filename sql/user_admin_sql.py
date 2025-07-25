
GET_USERS_SQL = """
SELECT 
    l.name,
    l.display_name,
    l.email,
	l.homepage,
    l.created_at,
    STRING_AGG(lp.permission_name, ',') AS permissions
FROM logins l
LEFT JOIN login_permissions lp ON l.name = lp.login_name
GROUP BY l.name, l.display_name, l.email,l.homepage, l.created_at
ORDER BY l.created_at DESC;
"""

CHECK_USER_SQL = """
SELECT name FROM logins WHERE name = :username
"""

INSERT_USER_SQL = """
INSERT INTO logins (name, password, display_name, email, homepage, created_at)
VALUES (:username, :password, :display_name, :email, :homepage, :created_at)
"""

DELETE_USER_PERMS_SQL = """
DELETE FROM login_permissions WHERE login_name = :username
"""

INSERT_USER_PERM_SQL = """
INSERT INTO login_permissions (login_name, permission_name)
VALUES (:username, :perm_name)
"""