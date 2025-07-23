from flask import current_app
from flask_restx import  Resource
from models.dashboard import get_dashboard_stats
from utils.token import token_required
from routes.dashboard.schema import dashboard_response, api as dashboard_ns

@dashboard_ns.route("")
class DashboardAPI(Resource):
    @token_required(current_app)
    @dashboard_ns.response(200, "Success", dashboard_response)
    @dashboard_ns.response(500, "Internal Server Error")
    def get(self):
        try:
            stats = get_dashboard_stats()
            return stats, 200
        except Exception as e:
            return {"error": str(e)}, 500