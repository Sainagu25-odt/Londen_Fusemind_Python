from functools import wraps

import jwt
from datetime import datetime, timedelta
from flask import current_app, jsonify, request,make_response, g

from models.user import find_user_by_username


def generate_token( user):
    payload = {
        'name': user["name"],
        'exp': datetime.utcnow() + timedelta(hours=30)
    }
    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm="HS256")

def decode_token( token):
    try:
        return jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None


def token_required(app):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Step 1: Get token from headers
            token = (
                request.headers.get('x-auth-token') or
                request.headers.get('X-Auth-Token') or
                request.headers.get('Authorization')
            )

            if token and token.lower().startswith('bearer '):
                token = token[7:]

            if not token:
                return {'error': 'Token is missing!'}, 401

            try:
                # Step 2: Validate token
                data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
                current_user = find_user_by_username(data['name'])

                if not current_user:
                    return {'error': 'User not found!'}, 401

                # Store user for app-wide access
                g.current_user = current_user

            except jwt.ExpiredSignatureError:
                return {'error': 'Token has expired!'}, 401
            except jwt.InvalidTokenError as e:
                return {'error': f'Invalid token: {str(e)}'}, 401

            # Step 3: Create new token (after validation success)
            new_payload = {
                'name': current_user['name'],
                'exp': datetime.utcnow() + timedelta(minutes=5)  # expires in 1 min
            }
            new_token = jwt.encode(new_payload, app.config['SECRET_KEY'], algorithm="HS256")

            # Step 4: Call original route
            result = f(*args, **kwargs)

            # Step 5: Normalize output
            if isinstance(result, tuple):
                if len(result) == 2:
                    body, status = result
                elif len(result) == 3:
                    body, status, _ = result
                else:
                    raise ValueError("Invalid response format")
            elif isinstance(result, dict):
                body, status = result, 200
            else:
                return result  # Already a response object

            # Step 6: Add token to response
            resp = make_response(jsonify(body), status)
            resp.headers['x-auth-token'] = new_token

            try:
                json_data = resp.get_json()
                if isinstance(json_data, dict):
                    json_data['token'] = new_token
                    resp.set_data(jsonify(json_data).get_data())
            except Exception as e:
                print(f"[Warning] Could not update response body: {e}")

            return resp
        return decorated
    return decorator