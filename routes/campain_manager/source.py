from logging import exception

from flask_restx import Namespace, Resource, fields, reqparse

from flask import request, jsonify, current_app

from models.campaigns import get_campaign_details, soft_delete_campaign, get_campaigns, undelete_campaign, \
    get_campaign_edit_data
from extensions import db
from sqlalchemy import text

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


@campaign_ns.route('/<int:campaign_id>/edit')
class CampaignEdit(Resource):
    @campaign_ns.doc(params={'show_counts': 'Set to true to include step counts'})
    @campaign_ns.marshal_with(campaign_edit_response)
    def get(self, campaign_id):
        show_counts = request.args.get('show_counts', 'false').lower() == 'true'
        return get_campaign_edit_data(campaign_id, show_counts)







