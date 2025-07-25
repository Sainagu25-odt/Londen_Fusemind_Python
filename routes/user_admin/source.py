from flask import current_app

from models.user_admin import get_all_users
from routes.user_admin.schema import user_ns, user_list_response
from flask_restx import  Resource
from utils.auth import require_permission
from utils.token import token_required


@user_ns.route("")
class UserList(Resource):
    @user_ns.doc(security="Bearer", description="Get list of all users")
    @token_required(current_app)
    @require_permission("User Admin")
    @user_ns.marshal_list_with(user_list_response)
    def get(self):
        try:
            users = get_all_users()
            return {"users": users}, 200
        except Exception as e:
            return {"error" : str(e)}, 500
