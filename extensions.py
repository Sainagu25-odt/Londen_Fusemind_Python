from flask_sqlalchemy import SQLAlchemy
from flask_restx import Api

db = SQLAlchemy()
api = Api(title="My API", version="1.0", doc="/swagger", description="Login, Dashboard, Reports APIs")
