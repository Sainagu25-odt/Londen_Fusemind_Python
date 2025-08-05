import logging
import os
import re

from flask_restx import Namespace, Resource, fields, reqparse

from flask import request, jsonify, current_app, g, send_file
from sqlalchemy.exc import SQLAlchemyError

from models.campaigns import soft_delete_campaign, get_campaigns, undelete_campaign, \
    get_campaign_edit_data, add_criterion, add_campaign, get_dropdowns_for_datasources, build_campaign_request_response, \
    insert_pull_list, get_global_active_pulls, get_campaign_counts, get_global_campaign_counts, \
    save_campaign_criteria, delete_criteria_row, get_campaign_record_data, copy_campaign, add_new_criteria_simple, \
    get_add_criteria_dropdowns, get_legend_values, get_subquery_dialog_options, create_subquery_campaign
from extensions import db
from sqlalchemy import text

from routes.campain_manager.dropdown_service import get_criteria_options
from routes.campain_manager.schema import campaign_edit_response, criteria_model, \
    pull_item_model, active_pulls_response_model, pull_request_parser, \
    campaign_response, counts_response, add_criteria_response
from sql.campaigns_sql import GET_CAMPAIGN_LIST_FILENAME
from utils.auth import require_permission
from utils.token import token_required

# Define the namespace
campaign_ns = Namespace('campaigns', description='Campaign related operations')

#list campaign api
campaign_ns.models[campaign_response.name] = campaign_response
@campaign_ns.route('')
class CampaignList(Resource):
    @token_required(current_app)
    @require_permission("cms")
    @campaign_ns.doc(params={'include_deleted': 'Set to true to include deleted campaigns'})
    @campaign_ns.marshal_with(campaign_response)
    def get(self):
        try:
            include_deleted = request.args.get('include_deleted', 'false').lower() == 'true'
            campaigns = get_campaigns(include_deleted)
            return campaigns, 200
        except Exception as e:
            return {'error': str(e)}, 500


#delete campaign api
@campaign_ns.route('/<int:campaign_id>/delete')
class DeleteCampaign(Resource):
    @token_required(current_app)
    @require_permission("cms")
    @campaign_ns.doc(description="Soft delete a campaign")
    def get(self, campaign_id):
        try:
            soft_delete_campaign(campaign_id)
            return {'message': f'Campaign {campaign_id} soft deleted'}, 200
        except Exception as e:
            return {'error': str(e)}, 500


campaign_ns.models[campaign_edit_response.name] = campaign_edit_response
campaign_ns.models[criteria_model.name] = criteria_model
#undelete campaign api
@campaign_ns.route('/<int:campaign_id>/undelete')
class DeleteCampaign(Resource):
    @token_required(current_app)
    @require_permission("cms")
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

#edit campaign api
@campaign_ns.route("/<int:campaign_id>/edit")
@campaign_ns.doc(params={"show_counts": "Set to 1 to include counts"})
class EditCampaign(Resource):
    @token_required(current_app)
    @require_permission("cms")
    @campaign_ns.expect(edit_parser)
    @campaign_ns.marshal_with(edit_response)
    def get(self, campaign_id):
        args = edit_parser.parse_args()
        try:
            return get_campaign_edit_data(campaign_id, args["show_counts"])
        except Exception as e:
            current_app.logger.error(f"EditCampaign failed: {e}")
            return {"message": "Failed to retrieve campaign"}, 500



add_crit_model = campaign_ns.model('NewCriterion', {
    "column_name": fields.String(required=True),
    "sql_type": fields.String(required=True),
    "sql_value": fields.String(required=True),
    "or_next": fields.Boolean(required=False, default=False),
})


@campaign_ns.route('/<int:campaign_id>/save')
class SaveCampaign(Resource):
    @token_required(current_app)
    @require_permission("cms")
    def post(self, campaign_id):
        try:
            data = request.get_json()
            criteria_list = data.get("criteria", [])

            if not isinstance(criteria_list, list):
                return {"message": "Invalid data format for criteria"}, 400

            save_campaign_criteria(campaign_id, criteria_list)
            db.session.commit()
            return {"message": "Campaign criteria saved successfully"}, 200

        except SQLAlchemyError as e:
            db.session.rollback()
            return {"message": "Database error", "error": str(e)}, 500

        except Exception as e:
            db.session.rollback()
            return {"message": "Unexpected error", "error": str(e)}, 500

# delete criteria with id
@campaign_ns.route('/<int:campaign_id>/deleteCriteria/<int:row_id>')
class DeleteCriterion(Resource):
    @token_required(current_app)
    @require_permission("cms")
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
    @require_permission("cms")
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


#add campaign api
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
    @require_permission("cms")
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



#pulls
@campaign_ns.route("/<int:campaign_id>/request")
class CampaignPullRequest(Resource):
    @token_required(current_app)
    @require_permission("cms")
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
    @require_permission("cms")
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
    @require_permission("cms")
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
    @token_required(current_app)
    @require_permission("cms")
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

# Schema for global campaign counts
global_count_model = campaign_ns.model("GlobalCount", {
    "campaign_id": fields.Integer(description="Campaign ID"),
    "total": fields.Integer(description="Total count for campaign")
})

# counts for each campaign_id
campaign_ns.models[counts_response.name] = counts_response
@campaign_ns.route('/<int:campaign_id>/counts')
class CountsResource(Resource):
    @token_required(current_app)
    @require_permission("cms")
    @campaign_ns.doc(params={
        'exclude': 'Comma-separated list of campaign_list IDs to exclude',
        'household': 'Boolean flag to get household counts (true/false)'
    })
    @campaign_ns.marshal_with(counts_response)
    def get(self, campaign_id):
        exclude = request.args.get('exclude')
        household = request.args.get('household', 'false').lower() == 'true'
        try:
            data = get_campaign_counts(campaign_id, exclude, household)
            return data, 200
        except SQLAlchemyError as e:
            return {"error" : str(e)}, 500
        except Exception as e:
            return {"error" : str(e)}, 500

@campaign_ns.route('/counts')
class GlobalCampaignCounts(Resource):
    @token_required(current_app)
    @require_permission("cms")
    @campaign_ns.marshal_list_with(global_count_model)
    def get(self):
        try:
            show_counts = request.args.get('show_counts')
            if show_counts != '1':
                return []
            return get_global_campaign_counts(), 200
        except Exception as e:
            return {"error" : str(e)}, 500



# download pull
@campaign_ns.route("/pull/<int:id>/download")
class DownloadPullFile(Resource):
    @token_required(current_app)
    @require_permission("cms")
    def get(self, id):
        try:
            # Fetch filename from DB
            row = db.session.execute(text(GET_CAMPAIGN_LIST_FILENAME), {"id": id}).mappings().first()
            if not row:
                return {"message": "Campaign list not found"}, 404

            original_filename = row["file_name"]
            current_app.logger.info(f"Original filename from DB: {original_filename}")

            # Sanitize filename
            sanitized_filename = re.sub(r"[ ,:]", "", original_filename)
            current_app.logger.info(f"Sanitized filename: {sanitized_filename}")

            # Ensure 'lists' folder exists, create if missing
            lists_folder = os.path.join(current_app.root_path, "lists")
            if not os.path.exists(lists_folder):
                os.makedirs(lists_folder)
                current_app.logger.info(f"Created missing folder: {lists_folder}")

            # Full path for the zip file
            file_path = os.path.join(lists_folder, f"{sanitized_filename}.zip")
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


# copy campaign
@campaign_ns.route('/<int:campaign_id>/copy')
@campaign_ns.response(404, 'Campaign not found')
class CampaignCopy(Resource):
    @token_required(current_app)
    @require_permission("cms")
    @campaign_ns.doc('copy_campaign')
    def get(self, campaign_id):
        try:
            new_campaign_id = copy_campaign(campaign_id)
            if not new_campaign_id:
                return {"error": f"Campaign ID {campaign_id} not found"}, 404
            return {"message": "Campaign copied successfully", "new_campaign_id": new_campaign_id}, 200
        except Exception as e:
            return {"error": {str(e)}}, 500


#response for add criteria
add_criteria_response = campaign_ns.model('AddCriteriaResponse', {
    'status': fields.String,
    'data': fields.Integer
})
@campaign_ns.route("/addCriteria")
class AddCriteriaResource(Resource):
    @campaign_ns.marshal_with(add_criteria_response)
    def post(self):
        try:
            data = request.get_json()
            criterion_id = add_new_criteria_simple(data["cid"])
            return {"status": "ok", "data": criterion_id}, 200
        except Exception as e:
            return {"error" : e}, 500

add_criteria_dropdown = campaign_ns.model('AddCriteriaDropdown', {
    'columns': fields.List(fields.String),
    'operators': fields.List(fields.Raw),
    'values': fields.List(fields.String)
})

add_criteria_dropdown_response = campaign_ns.model('AddCriteriaDropdownResponse', {
    'status': fields.String,
    'data': fields.Nested(add_criteria_dropdown)
})
@campaign_ns.route("/criteria/dropdowns")
class CriteriaDropdownsResource(Resource):
    @campaign_ns.marshal_with(add_criteria_dropdown_response)
    def post(self):
        try:
            """Get dropdowns (columns, operators, values) for Add Criteria"""
            data = request.get_json()
            result = get_add_criteria_dropdowns(data["cid"])
            return {"status": "ok", "data": result}, 200
        except Exception as e:
            return {"error" : str(e)}, 500

# Nested model for each legend item
legend_item = campaign_ns.model('LegendItem', {
    'value': fields.String,
    'total': fields.Integer
})

legend_response = campaign_ns.model('LegendResponse', {
    'status': fields.String,
    'data': fields.List(fields.Nested(legend_item))
})
campaign_ns.models[legend_response.name] = legend_response
@campaign_ns.route("/legend")
class LegendResource(Resource):
    @campaign_ns.marshal_with(legend_response)
    def post(self):
        try:
            data = request.get_json()
            if "cid" not in data:
                return {"status": "error", "message": "'cid' is required"}, 400

            if "col" not in data or not data["col"]:
                return {"status": "error", "message": "'col' is required to fetch legend values"}, 400

            values = get_legend_values(data["cid"], data["col"])
            return {"status": "ok", "data": values}, 200
        except Exception as e:
            return {"error" : str(e)}, 500

subquery_dialog_response = campaign_ns.model('SubqueryDialogResponse', {
    'status': fields.String,
    'data': fields.Nested(campaign_ns.model('SubqueryOption', {
        'table': fields.List(fields.String),
        'operator' : fields.List(fields.String),
        'label': fields.List(fields.String)
    }))
})
campaign_ns.models[subquery_dialog_response.name] = subquery_dialog_response
@campaign_ns.route('/subqueryDialog')
class SubqueryDialogResource(Resource):
    @campaign_ns.marshal_with(subquery_dialog_response)
    def post(self):
        try:
            data = request.get_json()
            options = get_subquery_dialog_options(data["cid"])
            return {"status" : "oK", "data" : options}, 200
        except Exception as e:
            return {"error" : str(e)}, 500


new_subquery_response = campaign_ns.model('NewSubqueryResponse', {
    'status': fields.String,
    'data': fields.Integer
})

@campaign_ns.route('/newSubquery')
class NewSubqueryResource(Resource):
    @campaign_ns.marshal_with(new_subquery_response)
    def post(self):
        try:
            data = request.get_json()
            cid = data["cid"]
            table = data["table"]
            label = data["label"]
            method = data["method"]
            new_subquery_id = create_subquery_campaign(cid, table, label, method)
            return {"status": "ok", "data": new_subquery_id}, 200
        except Exception as e:
            return {"error" : str(e)}, 500









