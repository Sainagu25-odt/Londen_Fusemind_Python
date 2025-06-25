from flask_restx import Namespace, Resource, fields, reqparse

from flask import request, jsonify, current_app

from models.reports_source import process_feedmanager_report
from routes.reports.schema import report_parser, swagger_parser
from sql.reports_sql import get_reports_responder_file_data
from utils.token import token_required

reports_ns = Namespace('reports', description='Reports APIs')


@reports_ns.route('/responderfile')
class ResponderFile(Resource):
    @token_required(current_app)
    def get(self, current_user):
        try:
            data = get_reports_responder_file_data()
            return jsonify(data), 200
        except Exception as e:
            return {'error' : str(e)}, 500



feed_manager_parser = reqparse.RequestParser()
feed_manager_parser.add_argument('results', type=int, required=True, help='Page size (required)')
feed_manager_parser.add_argument('startIndex', type=int, required=True, help='Pagination start index (required)')
feed_manager_parser.add_argument('sort', type=str, required=True, help='Sort field (required)')
feed_manager_parser.add_argument('dir', type=str, required=True, choices=('asc', 'desc'), help='Sort direction (required)')
feed_manager_parser.add_argument('date_from', type=str, required=False, help='Start date in MM/DD/YYYY format (optional)')
feed_manager_parser.add_argument('date_to', type=str, required=False, help='End date in MM/DD/YYYY format (optional)')
feed_manager_parser.add_argument('report_type', type=str, required=False)
feed_manager_parser.add_argument('report_group', type=str, default='downloaded_at')

@reports_ns.route('/feedManager')
class FeedManagerReport(Resource):
    # @token_required(current_app)
    @reports_ns.expect(feed_manager_parser)
    def get(self):
        try:
            args = feed_manager_parser.parse_args()
            response_data = process_feedmanager_report(args)
            return response_data, 200
        except Exception as e:
            return {'error': str(e)}, 500


response_rates_task1_parser = reqparse.RequestParser()
response_rates_task1_parser.add_argument('id', type = int, required = True)
response_rates_task1_parser.add_argument('results', type=int, required=True, help='Page size (required)')
response_rates_task1_parser.add_argument('startIndex', type=int, required=True, help='Pagination start index (required)')
response_rates_task1_parser.add_argument('sort', type=str, required=True, help='Sort field (required)')
response_rates_task1_parser.add_argument('dir', type=str, required=True, choices=('asc', 'desc'), help='Sort direction (required)')
response_rates_task1_parser.add_argument('report_group', type=str, default='downloaded_at')





# @reports_ns.route('/responseRates')
# class ResponseRates(Resource):
#     @reports_ns.expect(response_rates_task1_parser)
#     def get(self):
#         try:
#             args = response_rates_task1_parser.parse_args()
#             response_data = process_response_rates()



