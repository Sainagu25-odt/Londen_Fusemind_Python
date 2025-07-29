
from flask_restx import Namespace, Resource, fields
from flask import request, jsonify, current_app
import hashlib, jwt, datetime

from models.user import find_user_by_username, get_permissions_by_username
from utils.token import generate_token,token_required

auth_ns = Namespace('auth', description='Authentication APIs')

login_model = auth_ns.model('Login', {
    'username': fields.String(required=True),
    'password': fields.String(required=True)
})

@auth_ns.route('/login')
class Login(Resource):
    def get(self):
        return {"message": "Please use POST method to login with username and password"}, 200

    @auth_ns.expect(login_model)
    def post(self):
        data = request.json
        username = data.get('username')
        password = data.get('password')
        if not username or not password:
            return {'error': 'Missing fields'}, 400

        user = find_user_by_username(username)
        if user:
            # assuming password is stored as sha256 hash
            hashed_password = hashlib.md5(password.encode()).hexdigest()
            if hashed_password == user['password']:
                permissions = get_permissions_by_username(username)
                token = generate_token(user, permissions)
                return jsonify({"message": "Login successful", "token": token, "permissions" : permissions,
                                "username" : user["display_name"]})
            else:
                return {'message': 'Invalid password'}, 401
        else:
            return {'message': 'User not found'}, 404


@auth_ns.route('/logout')
class Logout(Resource):
    # @token_required(current_app)
    def post(self):
        return {"message": "Logout successful."}, 200


@auth_ns.route('/status')
class Status(Resource):
    @token_required(current_app)
    def get(self, current_user):
        return {"logged_in": True, "name": current_user['name']}, 200


@auth_ns.route('/')
class Home(Resource):
    def get(self):
        return {"message": "Welcome to the Login Backend API"}, 200

