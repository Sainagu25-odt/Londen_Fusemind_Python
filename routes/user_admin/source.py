from flask import current_app, request

from models.user_admin import get_all_users, add_user, edit_user
from routes.user_admin.schema import user_ns, user_list_response, user_response, add_user_request
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
        """Get all the Users"""
        try:
            users = get_all_users()
            return {"users": users}, 200
        except Exception as e:
            return {"error" : str(e)}, 500

    @user_ns.doc(security="Bearer", description="Add a new user")
    @token_required(current_app)
    @require_permission("User Admin")
    @user_ns.expect(add_user_request)
    @user_ns.marshal_with(user_response, code=201)
    def post(self):
        """Add a new user"""
        try:
            data = request.json
            return add_user(data), 200
        except Exception as e:
            return {"error" : str(e)}, 500



@user_ns.route("/<string:username>")
class EditUser(Resource):
    @user_ns.doc(security="Bearer", description="Edit an existing user")
    @token_required(current_app)
    @require_permission("User Admin")
    @user_ns.expect(add_user_request)
    @user_ns.marshal_with(user_response)
    def put(self, username):
        """Edit user by username."""
        try:
            data = request.json
            updated_user = edit_user(username, data)
            return updated_user, 200
        except Exception as e:
            return {"error": str(e)}, 500
