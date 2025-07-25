
GET_USERS_SQL = """
SELECT 
    l.name,
    l.display_name,
    l.email,
    l.created_at,
    STRING_AGG(lp.permission_name, ',') AS permissions
FROM logins l
LEFT JOIN login_permissions lp ON l.name = lp.login_name
GROUP BY l.name, l.display_name, l.email, l.created_at
ORDER BY l.name;
"""