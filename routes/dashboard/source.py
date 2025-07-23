from flask import jsonify
from flask_restx import Namespace, Resource

from models.dashboard import get_dashboard_stats
from routes.dashboard.schema import dashboard_response, api as dashboard_ns

@dashboard_ns.route("")
class DashboardAPI(Resource):
    @dashboard_ns.response(200, "Success", dashboard_response)
    @dashboard_ns.response(500, "Internal Server Error")
    def get(self):
        """Get dashboard summary: policy holders, non-insurance, total responders"""
        try:
            stats = get_dashboard_stats()
            return stats, 200
        except Exception as e:
            return {"error": str(e)}, 500