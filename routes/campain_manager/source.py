import logging
from logging import exception

from flask_restx import Namespace, Resource, fields, reqparse

from flask import request, jsonify, current_app
from sqlalchemy.exc import SQLAlchemyError

from models.campaigns import get_campaign_details, soft_delete_campaign, get_campaigns, undelete_campaign, \
    get_campaign_edit_data, add_criterion, add_campaign, get_dropdowns_for_datasources
from extensions import db
from sqlalchemy import text

from routes.campain_manager.dropdown_service import get_criteria_options
from routes.campain_manager.schema import campaign_edit_response, criteria_model

# Define the namespace
campaign_ns = Namespace('campaigns', description='Campaign related operations')


# ✅ Boolean parser
def str_to_bool(value):
    return str(value).lower() in ['true', '1', 'yes']

# Request Query Parameters
campaign_parser = reqparse.RequestParser()
campaign_parser.add_argument('include_deleted', type=str_to_bool, default=False, help='Include deleted campaigns')
campaign_parser.add_argument('show_counts', type=str_to_bool, default=False, help='Show counts in response')


# response params
# Response model for Swagger (optional)
campaign_model = campaign_ns.model('Campaign', {
    'id': fields.Integer,
    'name': fields.String,
    'description': fields.String,
    'begin_date': fields.String,
    'channel': fields.String,
    'deleted_at': fields.String,
    'campaign_subquery_id': fields.Integer,
    # Add more fields as needed based on DB schema
})

@campaign_ns.route('')
class CampaignList(Resource):
    @campaign_ns.doc('get_campaigns')
    @campaign_ns.expect(campaign_parser)
    @campaign_ns.marshal_list_with(campaign_model, envelope='campaigns')
    def get(self):
        """Fetch all active or all campaigns depending on 'include_deleted'"""
        try:
            args = campaign_parser.parse_args()
            include_deleted = args.get('include_deleted', False)
            response = get_campaigns(include_deleted)
            return response, 200
        except exception as e:
            return str(e), 500



# parser = reqparse.RequestParser()
# parser.add_argument('exclude', type=str, help='Comma-separated list of policy numbers to exclude')
# parser.add_argument('household', type=bool, help='Flag to indicate household metrics')
#
# state_model = campaign_ns.model('StateCount', {
#     'state': fields.String(required=True),
#     'total': fields.Integer(required=True),
#     'total_dups': fields.Integer(required=False)
# })
#
# response_model = campaign_ns.model('CampaignStats', {
#     'counts': fields.Integer(required=True),
#     'universe': fields.Integer(required=True),
#     'states': fields.List(fields.Nested(state_model))
# })
#
# @campaign_ns.route('/<int:campaign_id>')
# @campaign_ns.param('campaign_id', 'Campaign ID')
# class CampaignStatsResource(Resource):
#     @campaign_ns.expect(parser)
#     @campaign_ns.marshal_with(response_model)
#     def get(self, campaign_id):
#         args = parser.parse_args()
#         exclude_list = args.exclude.split(',') if args.exclude else None
#         household = args.household or False
#
#         campaign = Campaign(campaign_id)
#         if household:
#             counts = campaign.household_counts(exclude_list)
#             universe = campaign.household_universe()
#             states = campaign.household_counts_by_state(exclude_list)
#         else:
#             counts = campaign.counts(exclude_list)
#             universe = campaign.universe()
#             states = campaign.counts_by_state(exclude_list)
#
#         formatted = [
#             {'state': s['state'], 'total': s['total'], 'total_dups': s.get('total_dups')}
#             for s in states or []
#         ]
#
#         return {
#             'counts': counts or 0,
#             'universe': universe or 0,
#             'states': formatted
#         }


state_model = campaign_ns.model('State', {
    'state': fields.String,
    'total': fields.Integer,
    'total_dups': fields.Integer(required=False)
})

response_model = campaign_ns.model('CampaignDetail', {
    'counts': fields.Integer,
    'universe': fields.Integer,
    'states': fields.List(fields.Nested(state_model))
})

@campaign_ns.route('/<int:campaign_id>')
class CampaignDetail(Resource):
    @campaign_ns.doc(params={
        'household': 'true or false',
        'exclude': 'comma-separated list of exclusions'
    })
    @campaign_ns.marshal_with(response_model)
    @campaign_ns.response(404, "Campaign not found")
    def get(self, campaign_id):
        """Fetch campaign detail: counts, universe, states breakdown."""
        household = request.args.get('household', 'false').lower() == 'true'
        exclude = request.args.get('exclude')

        campaign = db.session.execute(
            text("SELECT id FROM campaigns WHERE id = :id"),
            {'id': campaign_id}
        ).fetchone()
        if not campaign:
            campaign_ns.abort(404, "Campaign not found")

        return get_campaign_details(campaign_id, household, exclude)



@campaign_ns.route('/<int:campaign_id>/delete')
class DeleteCampaign(Resource):
    @campaign_ns.doc(description="Soft delete a campaign")
    def get(self, campaign_id):
        try:
            soft_delete_campaign(campaign_id)
            return {'message': f'Campaign {campaign_id} soft deleted'}, 200
        except Exception as e:
            return {'error': str(e)}, 500


campaign_ns.models[campaign_edit_response.name] = campaign_edit_response
campaign_ns.models[criteria_model.name] = criteria_model

@campaign_ns.route('/<int:campaign_id>/undelete')
class DeleteCampaign(Resource):
    @campaign_ns.doc(description="Restore (undelete) a campaign")
    def get(self, campaign_id):
        try:
            undelete_campaign(campaign_id)
            return {'message': f'Campaign {campaign_id} restored'}, 200
        except Exception as e:
            return {'error': str(e)}, 500



edit_parser = reqparse.RequestParser()
edit_parser.add_argument('show_counts', type=int, default=0)

criteria_field = campaign_ns.model('Criterion', {
    'column_name': fields.String,
    'operator': fields.String,
    'value': fields.String,
    'is_or': fields.Boolean
})

edit_response = campaign_ns.model('EditCampaignResponse', {
    'id': fields.Integer,
    'name': fields.String,
    'description': fields.String,
    'channel': fields.String,
    'deleted': fields.Boolean,
    'datasource_table': fields.String,
    'criteria': fields.List(fields.Nested(criteria_field)),
    'counts': fields.Integer(required=False)
})

@campaign_ns.route('/<int:campaign_id>/edit')
@campaign_ns.doc(params={'show_counts': 'Set to 1 to include counts'})
class EditCampaign(Resource):
    @campaign_ns.expect(edit_parser)
    @campaign_ns.marshal_with(edit_response)
    def get(self, campaign_id):
        args = edit_parser.parse_args()
        return get_campaign_edit_data(campaign_id, args['show_counts'])

add_crit_model = campaign_ns.model('NewCriterion', {
    "column_name": fields.String(required=True),
    "sql_type": fields.String(required=True),
    "sql_value": fields.String(required=True),
    "or_next": fields.Boolean(required=False, default=False),
})

@campaign_ns.route('/<int:campaign_id>/newCriteria')
class AddCriterion(Resource):
    @campaign_ns.expect(add_crit_model, validate=True)
    @campaign_ns.response(200, 'Criterion added successfully')
    @campaign_ns.response(400, 'Bad Request')
    @campaign_ns.response(500, 'Internal Server Error')
    def post(self, campaign_id):
        """
        Add a criterion to a campaign.
        """
        try:
            data = request.get_json()
            result = add_criterion(campaign_id, data)
            return result, 200
        except KeyError as e:
            logging.error(f"Missing key: {e}")
            return {"error": f"Missing field: {str(e)}"}, 400
        except SQLAlchemyError as e:
            logging.exception("Database error occurred")
            return {"error": "Database operation failed"}, 500
        except Exception as e:
            logging.exception("Unexpected error occurred")
            return {"error": f"Unexpected error: {str(e)}"}, 500


add_campaign_model = campaign_ns.model('NewCampaign', {
    'name': fields.String(required=True),
    'description': fields.String(required=True),
    'channel': fields.String(required=True),
    'datasource': fields.String(required=True),
    'begin_date': fields.String(required=True, description='YYYY-MM-DD')
})

@campaign_ns.route('/addCampaign')
class AddCampaign(Resource):
    @campaign_ns.expect(add_campaign_model, validate=True)
    @campaign_ns.response(200, 'Campaign created successfully')
    @campaign_ns.response(400, 'Bad Request')
    @campaign_ns.response(500, 'Internal Server Error')
    def post(self):
        """
        Add a new campaign.
        """
        try:
            data = request.get_json()
            print(data)
            result = add_campaign(data)
            return result, 200
        except KeyError as e:
            logging.error(f"Missing field: {e}")
            return {"error": f"Missing field: {str(e)}"}, 400
        except SQLAlchemyError:
            logging.exception("Database error occurred")
            return {"error": "Database operation failed"}, 500
        except Exception as e:
            logging.exception("Unexpected error occurred")
            return {"error": f"Unexpected error: {str(e)}"}, 500



@campaign_ns.route('/criteria-options')
class CriteriaOptions(Resource):
    @campaign_ns.doc(False)  # Hide from Swagger UI
    def get(self):
        try:
            root_path = current_app.root_path
            print(root_path)
            options = get_criteria_options(root_path)
            return options, 200
        except Exception as e:
            return {"error": f"Failed to load criteria options: {str(e)}"}, 500





@campaign_ns.route("/form-dropdowns")
class CampaignFormDropdowns(Resource):
    def get(self):
        try:
            result = get_dropdowns_for_datasources()
            return result, 200
        except exception as e:
            return jsonify({"error": str(e)}), 500







