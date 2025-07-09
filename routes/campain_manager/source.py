import logging
import os
import re
from logging import exception

from flask_restx import Namespace, Resource, fields, reqparse

from flask import request, jsonify, current_app, g, send_file
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import BadRequest

from models.campaigns import get_campaign_details, soft_delete_campaign, get_campaigns, undelete_campaign, \
    get_campaign_edit_data, add_criterion, add_campaign, get_dropdowns_for_datasources, build_campaign_request_response, \
    insert_pull_list, get_global_active_pulls,  get_campaign_counts, get_global_campaign_counts, \
    save_campaign_criteria, delete_criteria_row, get_campaign_record_data
from extensions import db
from sqlalchemy import text

from routes.campain_manager.dropdown_service import get_criteria_options
from routes.campain_manager.schema import campaign_edit_response, criteria_model, \
    pull_item_model, active_pulls_response_model, pull_request_parser, \
    CountResponseWrapper, HouseholdResponse, CampaignRecordResponse
from sql.campaigns_sql import GET_CAMPAIGN_LIST_FILENAME
from utils.token import token_required

# Define the namespace
campaign_ns = Namespace('campaigns', description='Campaign related operations')


# ✅ Boolean parser
def str_to_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ['true', '1', 'yes']
    return False

# Request Query Parameters
campaign_parser = reqparse.RequestParser()
campaign_parser.add_argument('include_deleted', type=str_to_bool, default=False, help='Include deleted campaigns', location='args')
campaign_parser.add_argument('show_counts', type=str_to_bool, default=False, help='Show counts in response', location='args')


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
    @token_required(current_app)
    @campaign_ns.doc('get_campaigns')
    @campaign_ns.expect(campaign_parser)
    @campaign_ns.marshal_list_with(campaign_model, envelope='campaigns')
    def get(self):
        """Fetch all active or all campaigns depending on 'include_deleted'"""
        try:
            args = campaign_parser.parse_args()
            include_deleted = args.get('include_deleted', False)
            print(include_deleted)
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
    @token_required(current_app)
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
    @token_required(current_app)
    @campaign_ns.doc(description="Restore (undelete) a campaign")
    def get(self, campaign_id):
        try:
            undelete_campaign(campaign_id)
            return {'message': f'Campaign {campaign_id} restored'}, 200
        except Exception as e:
            return {'error': str(e)}, 500



# Request parser
edit_parser = reqparse.RequestParser()
edit_parser.add_argument("show_counts", type=int, default=0)

# Criteria model
criteria_field = campaign_ns.model("Criterion", {
    "row_id": fields.Integer,
    "column_name": fields.String,
    "operator": fields.String,
    "value": fields.String,
    "is_or": fields.Boolean
})

# Subquery join info
subquery_join_model = campaign_ns.model("SubqueryJoin", {
    "label": fields.String,
    "parent_table": fields.String,
    "child_table": fields.String,
    "parent_field": fields.String,
    "child_field": fields.String
})

# Subquery model
subquery_model = campaign_ns.model("Subquery", {
    "id": fields.Integer,
    "name": fields.String,
    "begin_date": fields.String,
    "deleted": fields.Boolean,
    "criteria": fields.List(fields.Nested(criteria_field)),
    "join": fields.Nested(subquery_join_model)
})

# Final edit response
edit_response = campaign_ns.model("EditCampaignResponse", {
    "id": fields.Integer,
    "name": fields.String,
    "description": fields.String,
    "channel": fields.String,
    "begin_date": fields.String,
    "deleted": fields.Boolean,
    "datasource_table": fields.String,
    "criteria": fields.List(fields.Nested(criteria_field)),
    "subqueries": fields.List(fields.Nested(subquery_model)),
    "counts": fields.Integer
})


@campaign_ns.route("/<int:campaign_id>/edit")
@campaign_ns.doc(params={"show_counts": "Set to 1 to include counts"})
class EditCampaign(Resource):
    @token_required(current_app)
    @campaign_ns.expect(edit_parser)
    @campaign_ns.marshal_with(edit_response)
    def get(self, campaign_id):
        args = edit_parser.parse_args()
        try:
            return get_campaign_edit_data(campaign_id, args["show_counts"])
        except Exception as e:
            current_app.logger.error(f"EditCampaign failed: {e}")
            return {"message": "Failed to retrieve campaign"}, 500

# @campaign_ns.route('/<int:campaign_id>/edit')
# @campaign_ns.doc(params={'show_counts': 'Set to 1 to include counts'})
# class EditCampaign(Resource):
#     @token_required(current_app)
#     @campaign_ns.expect(edit_parser)
#     @campaign_ns.marshal_with(edit_response)
#     def get(self, campaign_id):
#         args = edit_parser.parse_args()
#         return get_campaign_edit_data(campaign_id, args['show_counts'])




add_crit_model = campaign_ns.model('NewCriterion', {
    "column_name": fields.String(required=True),
    "sql_type": fields.String(required=True),
    "sql_value": fields.String(required=True),
    "or_next": fields.Boolean(required=False, default=False),
})

@campaign_ns.route('/<int:campaign_id>/save')
class SaveCampaign(Resource):
    @token_required(current_app)
    def post(self, campaign_id):
        try:
            data = request.get_json()
            criteria_list = data.get("criteria", [])

            if not isinstance(criteria_list, list):
                return {"message": "Invalid data format for criteria"}, 400
            print(criteria_list)

            save_campaign_criteria(campaign_id, criteria_list)
            db.session.commit()
            return {"message": "Campaign criteria saved successfully"}, 200

        except SQLAlchemyError as e:
            db.session.rollback()
            return {"message": "Database error", "error": str(e)}, 500

        except Exception as e:
            db.session.rollback()
            return {"message": "Unexpected error", "error": str(e)}, 500

@campaign_ns.route('/<int:campaign_id>/deleteCriteria/<int:row_id>')
class DeleteCriterion(Resource):
    @token_required(current_app)
    def get(self, campaign_id, row_id):
        try:
            delete_criteria_row(campaign_id, row_id)
            db.session.commit()
            return {"message": f"Criterion row {row_id} deleted successfully"}, 200

        except SQLAlchemyError as e:
            db.session.rollback()
            return {"message": "Database error", "error": str(e)}, 500

        except Exception as e:
            db.session.rollback()
            return {"message": "Unexpected error", "error": str(e)}, 500

@campaign_ns.route('/<int:campaign_id>/newCriteria')
class AddCriterion(Resource):
    @token_required(current_app)
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
    @token_required(current_app)
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
    @campaign_ns.doc(False)  # Hide from Swagger UI
    def get(self):
        try:
            result = get_dropdowns_for_datasources()
            return result, 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500


@campaign_ns.route("/<int:campaign_id>/request")
class CampaignPullRequest(Resource):
    @token_required(current_app)
    def get(self,campaign_id):
        try:
            result = build_campaign_request_response(campaign_id, g.current_user)
            return result, 200  # ensure response order is preserved
        except Exception as e:
            current_app.logger.error(f"Error in campaign request API: {str(e)}")
            return {"error": "Internal server error"}, 500


campaign_ns.models[pull_item_model.name] = pull_item_model
campaign_ns.models[active_pulls_response_model.name] = active_pulls_response_model

@campaign_ns.route("/pull")
class PullInsert(Resource):
    @token_required(current_app)
    @campaign_ns.expect(pull_request_parser)
    @campaign_ns.marshal_with(active_pulls_response_model)
    def get(self):
        args = pull_request_parser.parse_args()
        try:
            return insert_pull_list(args, g.current_user), 200
        except ValueError as ve:
            current_app.logger.warning(f"Validation error: {str(ve)}")
            return {"error": str(ve)}, 400
        except Exception as e:
            current_app.logger.exception("Internal server error in pull insert")
            return {"error": str(e)}, 500

@campaign_ns.route("/pulls")
class PullsAll(Resource):
    @token_required(current_app)
    @campaign_ns.marshal_with(active_pulls_response_model)
    def get(self):
        try:
            return get_global_active_pulls(), 200
        except ValueError as ve:
            current_app.logger.warning(f"Validation error: {str(ve)}")
            return {"error": str(ve)}, 400
        except Exception as e:
            current_app.logger.error(f"Internal server error in pull insert: {str(e)}")
            return {"error": "Internal server error"}, 500



# to show records
@campaign_ns.route('/<int:campaign_id>/records')
@campaign_ns.response(404, 'Campaign not found')
class CampaignRecords(Resource):
    @campaign_ns.doc('get_campaign_records')
    def get(self, campaign_id):
        try:
            page = int(request.args.get('page', 1))
            limit = int(request.args.get('limit', 25))
            result = get_campaign_record_data(campaign_id, page, limit)
            if result is None:
                return {"msg" : f"No records found for Campaign ID {campaign_id}"}
            return {'data': result}, 200
        except Exception as e:
            return {"error": "Internal server error"}, 500


# Schema for state-level counts
state_count_model = campaign_ns.model("StateCount", {
    "state": fields.String(description="State name"),
    "total": fields.Integer(description="Total count for the state")
})

# Schema for total household counts
household_model = campaign_ns.model("HouseholdCount", {
    "total_households": fields.Integer(description="Total households"),
    "total_duplicates": fields.Integer(description="Total duplicates")
})

# Schema for the full campaign count response
campaign_count_response = campaign_ns.model("CampaignCountResponse", {
    "state_counts": fields.List(fields.Nested(state_count_model)),
    "total_count": fields.Integer(description="Total records count"),
    "total_households": fields.Integer(description="Total households"),
    "total_duplicates": fields.Integer(description="Total duplicates")
})

# Schema for global campaign counts
global_count_model = campaign_ns.model("GlobalCount", {
    "campaign_id": fields.Integer(description="Campaign ID"),
    "total": fields.Integer(description="Total count for campaign")
})

# Parser for /<campaign_id>/counts
campaign_parser = reqparse.RequestParser()
campaign_parser.add_argument('household', type=bool, location='args', required=False, help='Group by household')
campaign_parser.add_argument('excludes', type=str, location='args', required=False, help='Comma separated list of excludes')

@campaign_ns.route('/<int:campaign_id>/counts')
class CampaignCounts(Resource):
    @campaign_ns.expect(campaign_parser)
    @campaign_ns.marshal_with(campaign_count_response)
    def get(self, campaign_id):
        args = campaign_parser.parse_args()
        household = args.get('household', False)
        excludes = args.get('excludes')
        return get_campaign_counts(campaign_id, household, excludes)


@campaign_ns.route('/counts')
class GlobalCampaignCounts(Resource):
    @campaign_ns.marshal_list_with(global_count_model)
    def get(self):
        show_counts = request.args.get('show_counts')
        if show_counts != '1':
            return []
        return get_global_campaign_counts()




@campaign_ns.route("/pull/<int:id>/download")
class DownloadPullFile(Resource):
    @token_required(current_app)
    def get(self, id):
        try:
            # Fetch filename from DB
            row = db.session.execute(text(GET_CAMPAIGN_LIST_FILENAME), {"id": id}).mappings().first()
            if not row:
                return {"message": "Campaign list not found"}, 404

            original_filename = row["file_name"]
            print(original_filename)
            current_app.logger.info(f"Original filename from DB: {original_filename}")

            # Sanitize filename
            sanitized_filename = re.sub(r"[ ,:]", "", original_filename)
            print(sanitized_filename)
            current_app.logger.info(f"Sanitized filename: {sanitized_filename}")

            # Ensure 'lists' folder exists, create if missing
            lists_folder = os.path.join(current_app.root_path, "lists")
            print(lists_folder)
            if not os.path.exists(lists_folder):
                os.makedirs(lists_folder)
                current_app.logger.info(f"Created missing folder: {lists_folder}")

            # Full path for the zip file
            file_path = os.path.join(lists_folder, f"{sanitized_filename}.zip")
            print(file_path)
            current_app.logger.info(f"Full file path: {file_path}")

            # If file does not exist, create an empty placeholder zip file
            if not os.path.exists(file_path):
                with open(file_path, "wb") as f:
                    pass  # creates an empty file
                current_app.logger.info(f"Created placeholder file: {file_path}")

            # Now send the file
            return send_file(file_path, as_attachment=True)

        except Exception as e:
            current_app.logger.error(f"DownloadPullFile failed: {e}")
            return {"message": "Download failed"}, 500





