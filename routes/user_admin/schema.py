from flask_restx import fields, Namespace

user_ns = Namespace("UserAdmin", description="User Admin Related API")

user_model = user_ns.model("User", {
    "username": fields.String,
    "display_name": fields.String,
    "email": fields.String,
    "created_at": fields.String,
    "permissions": fields.List(fields.String)
})

user_list_response = user_ns.model("UserListResponse", {
    "users": fields.List(fields.Nested(user_model))
})