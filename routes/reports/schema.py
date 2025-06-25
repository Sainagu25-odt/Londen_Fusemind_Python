from flask_restx import reqparse, fields


# login_model = auth_ns.model('Login', {
#     'username': fields.String(required=True),
#     'password': fields.String(required=True)
# })





# Show only these in Swagger
swagger_parser = reqparse.RequestParser()
swagger_parser.add_argument('date_from', type=str, required=True, help='Start date (MM/DD/YYYY)')
swagger_parser.add_argument('date_to', type=str, required=True, help='End date (MM/DD/YYYY)')
swagger_parser.add_argument('report_type', type=str, required=False, help='Type of report')


# Request parser for optional query parameters
report_parser = reqparse.RequestParser()
report_parser.add_argument('report_type', type=str, required=False)
report_parser.add_argument('report_group', type=str, required=False, default='downloaded_at')
report_parser.add_argument('date_from', type=str, required=False)
report_parser.add_argument('date_to', type=str, required=False)
report_parser.add_argument('sort', type=str, required=False)
report_parser.add_argument('dir', type=str, required=False, default='asc')
report_parser.add_argument('startIndex', type=int, required=False, default=0)
report_parser.add_argument('results', type=int, required=False, default=25)
report_parser.add_argument('filter', action='split', required=False)
report_parser.add_argument('like', action='split', required=False)