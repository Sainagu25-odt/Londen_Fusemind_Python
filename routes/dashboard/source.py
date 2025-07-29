from flask import current_app, request
from flask_restx import  Resource
from models.dashboard import get_dashboard_stats
from models.reports_source import fetch_feed_manager_data
from utils.token import token_required
from routes.dashboard.schema import dashboard_response, api as dashboard_ns
from utils.auth import require_permission


@dashboard_ns.route("")
class DashboardAPI(Resource):
    @token_required(current_app)
    @require_permission("dashboard")
    @dashboard_ns.response(200, "Success", dashboard_response)
    @dashboard_ns.response(500, "Internal Server Error")
    def get(self):
        try:
            stats = get_dashboard_stats()

            # 2. Optional query parameters for feed manager (same as reports API)
            date_from = request.args.get("date_from")
            date_to = request.args.get("date_to")
            start_index = int(request.args.get("startIndex", 0))
            page_size = int(request.args.get("results", 10))
            sort = request.args.get("sort")
            dir_ = request.args.get("dir", "desc")

            # 3. Fetch feed manager data
            feed_manager_data = fetch_feed_manager_data(
                date_from=date_from,
                date_to=date_to,
                start_index=start_index,
                page_size=page_size,
                sort=sort,
                dir_=dir_
            )

            # 4. Combine results
            return {
                "policy_holders": stats["policy_holders"],
                "non_insurance": stats["non_insurance"],
                "total_responders": stats["total_responders"],
                "feed_manager": feed_manager_data
            }, 200

        except Exception as e:
            return {"error": str(e)}, 500

