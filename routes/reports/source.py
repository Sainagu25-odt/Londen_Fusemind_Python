from logging import exception

from flask_restx import Namespace, Resource, fields, reqparse

from flask import request, jsonify, current_app, g

from models.reports_source import get_responder_data, fetch_feed_manager_data
from routes.reports.schema import get_responder_file_models,get_feedManager_models
from utils.auth import require_permission

from utils.token import token_required

reports_ns = Namespace('reports', description='Reports APIs')

record_model, response_model = get_responder_file_models(reports_ns)

@reports_ns.route('/responderFile')
class ResponderFile(Resource):
    @token_required(current_app)
    @require_permission("sysreports")
    @reports_ns.doc(description="Get responder file report")
    @reports_ns.marshal_with(response_model)
    def get(self):
        try:
            result = get_responder_data()
            return result, 200
        except Exception as e:
            reports_ns.abort(500, f"ResponderFile API Error: {str(e)}")



feed_manager_record_model, feed_manager_response_model = get_feedManager_models(reports_ns)

@reports_ns.route("/feedManager")
class FeedManager(Resource):
    @token_required(current_app)
    @require_permission("sysreports")
    @reports_ns.doc(params={
        "date_from": "Start date (YYYY-MM-DD), optional",
        "date_to": "End date (YYYY-MM-DD), optional",
        "startIndex": "Start index for pagination (default 0)",
        "results": "Page size (default 25)",
        "sort": "Sort key (e.g., downloaded_at)",
        "dir": "Sort direction (asc or desc)"
    })
    @reports_ns.marshal_with(feed_manager_response_model)
    def get(self):
        try:
            date_from = request.args.get("date_from")
            date_to = request.args.get("date_to")
            start_index = int(request.args.get("startIndex", 0))
            page_size = int(request.args.get("results", 25))
            sort = request.args.get("sort")
            dir_ = request.args.get("dir", "asc")

            return fetch_feed_manager_data(
                date_from=date_from,
                date_to=date_to,
                start_index=start_index,
                page_size=page_size,
                sort=sort,
                dir_=dir_
            ), 200

        except Exception as e:
            reports_ns.abort(500, f"FeedManager API Error: {str(e)}")




