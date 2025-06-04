from functools import wraps

import jwt
from datetime import datetime, timedelta
from flask import current_app, jsonify, request

from models.user import find_user_by_username


def generate_token( user):
    payload = {
        'name': user["name"],
        'exp': datetime.utcnow() + timedelta(hours=1)
    }
    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm="HS256")

def decode_token( token):
    try:
        return jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None


def token_required(current_app):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Step 1: Extract token from headers
            token = (
                request.headers.get('x-auth-token') or
                request.headers.get('X-Auth-Token') or
                request.headers.get('Authorization')
            )
            if token and token.startswith('Bearer '):
                token = token[7:]

            if not token:
                return jsonify({'error': 'Token is missing!'}), 401

            try:
                # Step 2: Decode token
                data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
                current_user = find_user_by_username(data['name'])
                print(current_user)

                if not current_user:
                    return jsonify({'error': 'User not found!'}), 401

                # Step 3: Refresh token with new expiry
                new_payload = {
                    'name': current_user['name'],
                    'exp': datetime.utcnow() + timedelta(minutes=5)
                }
                new_token = jwt.encode(new_payload, current_app.config['SECRET_KEY'], algorithm="HS256")

            except jwt.ExpiredSignatureError:
                return jsonify({'error': 'Token has expired!'}), 401
            except jwt.InvalidTokenError as e:
                return jsonify({'error': f'Invalid token: {str(e)}'}), 401

            # Step 4: Call actual route with current_user
            kwargs['current_user'] = current_user
            response = f(*args, **kwargs)

            # Step 5: Wrap response properly
            if isinstance(response, tuple):
                resp = jsonify(response[0])
                resp.status_code = response[1]
            else:
                resp = response

            # Step 6: Attach new token to response header and body
            resp.headers['x-auth-token'] = new_token

            try:
                json_data = resp.get_json()
                if isinstance(json_data, dict):
                    json_data['token'] = new_token
                    resp.set_data(jsonify(json_data).get_data())
                elif isinstance(json_data, list):
                    resp.set_data(jsonify({'data': json_data, 'token': new_token}).get_data())
            except Exception as e:
                print(f"[Warning] Could not add token to body: {e}")

            return resp
        return decorated
    return decorator

