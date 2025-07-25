from flask_restx import fields, Namespace

user_ns = Namespace("UserAdmin", description="User Admin Related API")

add_user_request = user_ns.model("AddUserRequest", {
    "username": fields.String,
    "display_name": fields.String,
    'password': fields.String,
    "email": fields.String,
    "homepage" : fields.String,
    "permissions": fields.List(fields.String)
})



user_response = user_ns.model("UserResponse", {
    "username": fields.String,
    "display_name": fields.String,
    "email": fields.String,
    "homepage" : fields.String,
    "created_at": fields.String,
    "permissions": fields.List(fields.String)
})

user_list_response = user_ns.model("UserListResponse", {
    "users": fields.List(fields.Nested(user_response))
})


