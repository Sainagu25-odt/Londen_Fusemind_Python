import logging
import os
import re
import tempfile
import zipfile

from flask_restx import Namespace, Resource, fields, reqparse

from flask import request, jsonify, current_app, g, send_file
from sqlalchemy.exc import SQLAlchemyError

from models.campaigns import soft_delete_campaign, get_campaigns, undelete_campaign, \
    add_criterion, add_campaign, get_dropdowns_for_datasources, build_campaign_request_response, \
    insert_pull_list, get_global_active_pulls, get_campaign_counts, get_global_campaign_counts, \
    save_campaign_criteria, delete_criteria_row, get_campaign_record_data, copy_campaign, add_new_criteria_simple, \
    get_add_criteria_dropdowns, get_legend_values, get_subquery_dialog_options, create_subquery_campaign, \
    get_campaign_by_id, get_criteria_for_campaign, get_campaign_columns
from extensions import db
from sqlalchemy import text

from routes.campain_manager.dropdown_service import get_criteria_options
from routes.campain_manager.schema import campaign_edit_response, criteria_model, \
    pull_item_model, active_pulls_response_model, pull_request_parser, \
    campaign_response, counts_response, add_criteria_response, pull_request_model, campaign_list_model
from sql.campaigns_sql import GET_CAMPAIGN_LIST_FILENAME, SUBQUERY_REF_SQL, GET_DATASOURCE_CAMPAIGN_ID
from utils.auth import require_permission
from utils.token import token_required

import pandas as pd
import io

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


campaign_model = campaign_ns.model('Campaign', {
    'id': fields.Integer,
    'name': fields.String,
    "description": fields.String,
    "channel": fields.String,
    "begin_date": fields.String,
    'datasource': fields.String
})

criterion_model = campaign_ns.model('Criterion', {
    'id': fields.Integer,
    'column_name': fields.String,
    'operator': fields.String,
    'sql_value': fields.String,
    'position': fields.Integer,
    'description': fields.String,
    "is_or": fields.Boolean,
    'count': fields.Integer

})

subquery_model = campaign_ns.model('Subquery', {
    'subquery_campaign_id': fields.Integer,
    'subquery_name': fields.String,
    'criteria': fields.List(fields.Nested(criterion_model))
})

edit_response_model = campaign_ns.model('EditCampaignResponse', {
    'campaign': fields.Nested(campaign_model),
    'criteria': fields.List(fields.Nested(criterion_model)),
    'subqueries': fields.List(fields.Nested(subquery_model)),
    'channels': fields.List(fields.String),
    'show_counts': fields.Boolean
})

@campaign_ns.route('/<int:campaign_id>/edit')
class CampaignEditResource(Resource):
    @token_required(current_app)
    @require_permission("cms")
    @campaign_ns.doc(params={
        'show_counts': 'Optional flag to show step counts'
    })
    @campaign_ns.marshal_with(edit_response_model)
    def get(self, campaign_id):
        show_counts = int(request.args.get('show_counts', 0))

        campaign = get_campaign_by_id(campaign_id)
        if campaign:
            campaign = dict(campaign._mapping)
        else:
            campaign = {'id': None, 'name': '', 'subquery': False, 'datasource': ''}

        criteria_data = get_criteria_for_campaign(campaign_id, show_counts=bool(show_counts), datasource=campaign["datasource"])

        return {
            'campaign': campaign,
            'criteria': criteria_data["criteria"],
            'subqueries': criteria_data["subqueries"],
            'channels': [],  # Placeholder for future logic
            'show_counts': bool(show_counts)
        }



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
            if not isinstance(data, dict):
                return {"message": "Invalid data format"}, 400
            save_campaign_criteria(campaign_id, data)
            db.session.commit()
            return {"message": "Campaign criteria saved successfully"}, 200

        except SQLAlchemyError as e:
            db.session.rollback()
            return {"message": "Database error", "error": str(e)}, 500

        except Exception as e:
            db.session.rollback()
            return {"message": "Unexpected error", "error": str(e)}, 500

# delete criteria with id
@campaign_ns.route('/deleteCriteria/<int:row_id>')
class DeleteCriterion(Resource):
    @token_required(current_app)
    @require_permission("cms")
    def get(self,  row_id):
        try:
            delete_criteria_row(row_id)
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
campaign_ns.models[pull_request_model.name] = pull_request_model
campaign_ns.models[campaign_list_model.name] = campaign_list_model

@campaign_ns.route("/pull")
class PullInsert(Resource):
    @token_required(current_app)
    @require_permission("cms")
    @campaign_ns.expect(pull_request_model)
    @campaign_ns.marshal_with(active_pulls_response_model)
    def post(self):
        args = request.json or {}
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
            list_row = db.session.execute(
                text(GET_CAMPAIGN_LIST_FILENAME),{"cid": id}).fetchone()
            if not list_row:
                return {"error": "Campaign list not found"}, 404

            list_dict = dict(list_row._mapping)

            # --- 2. Generate filename ---
            filename_base = list_dict['name']
            filename_base = re.sub(r"[^0-9A-Za-z-]", "", filename_base)  # sanitize for filesystem
            zip_filename = f"{filename_base}.zip"

            subq_rows = db.session.execute(text(SUBQUERY_REF_SQL), {"campaign_id": id}).fetchall()

            subquery_ids = set()
            for r in subq_rows:
                rdict = dict(r._mapping)
                raw_val = rdict.get("sql_value")
                if raw_val is None:
                    continue
                raw_val_str = str(raw_val).strip()
                sid = None
                try:
                    sid = int(raw_val_str)
                except Exception:
                    parts = [p.strip() for p in re.split(r'[,;]\s*', raw_val_str) if p.strip()]
                    for p in parts:
                        try:
                            sid = int(p)
                            break
                        except Exception:
                            continue
                if sid is not None:
                    subquery_ids.add(sid)

            if not subquery_ids:
                return {"error": "No valid subquery IDs found"}, 404

            # 3. Create temporary directory for Excel files
            with tempfile.TemporaryDirectory() as tmpdir:
                excel_files = []

                for sid in subquery_ids:
                    cache_table = f"cm_subquery_cache_{sid}"
                    table_exists = db.session.execute(
                        text("SELECT to_regclass(:tbl)"), {"tbl": cache_table}
                    ).scalar()
                    if not table_exists:
                        continue

                    # Get main table for this subquery
                    main_table_row = db.session.execute(text(GET_DATASOURCE_CAMPAIGN_ID), {"cid": sid}).fetchone()
                    if not main_table_row:
                        continue
                    table_name = main_table_row._mapping.get("tablename")

                    # Determine key column
                    if table_name in ("noninsurance_policies", "telemarketing_results", "donotcall_phones"):
                        key_col = "phone_number"
                    elif table_name == "donotcall_policies":
                        key_col = "policy"
                    else:
                        continue

                    # Fetch matching rows
                    query = f"""
                                   SELECT t.* FROM {table_name} t
                                   WHERE t.{key_col}::text IN (SELECT child_field FROM {cache_table})
                               """
                    with db.engine.connect() as conn:
                        df = pd.read_sql(query, conn)

                    if not df.empty:
                        excel_path = os.path.join(tmpdir, f"{table_name}_{sid}.xlsx")
                        df.to_excel(excel_path, index=False, engine="openpyxl")
                        excel_files.append(excel_path)

                # 4. Create ZIP in a **permanent temp location** outside TemporaryDirectory
                zip_path = os.path.join(tempfile.gettempdir(), zip_filename)
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for file in excel_files:
                        zf.write(file, os.path.basename(file))

            # 5. Send ZIP file
            return send_file(
                zip_path,
                as_attachment=True,
                download_name=zip_filename,
                mimetype='application/zip'
            )

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
    'position': fields.Integer
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

@campaign_ns.route("/columnLegend")
class ColumnLegendResource(Resource):
    def post(self):
        try:
            data = request.get_json()
            if "cid" not in data:
                return {"status": "error", "message": "'cid' is required"}, 400
            columns = get_campaign_columns(data["cid"])
            return {"column" : columns}, 200
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


def get_campaign_by_name_case_insensitive(name: str):
    sql = "SELECT * FROM campaigns WHERE LOWER(name) = LOWER(:name) LIMIT 1"
    result = db.session.execute(text(sql), {"name": name}).first()
    if result:
        return dict(result._mapping)  # convert Row to dict
    return None

@campaign_ns.route('/<int:campaign_id>/download')
class CampaignDownloadResource(Resource):
    def get(self, campaign_id):
        show_counts = int(request.args.get('show_counts', 1))

        # --- Fetch campaign ---
        campaign = get_campaign_by_id(campaign_id)
        if campaign:
            campaign = dict(campaign._mapping)
        else:
            return {"error": "Campaign not found"}, 404

        base_name = campaign['name']
        counterpart_names = [f"{base_name} Spanish", f"Spanish {base_name}"]

        spanish_campaign = None
        for cname in counterpart_names:
            spanish_campaign = get_campaign_by_name_case_insensitive(cname)
            if spanish_campaign:
                break

        # --- Fetch criteria for English campaign ---
        criteria_data = get_criteria_for_campaign(
            campaign_id,
            show_counts=bool(show_counts),
            datasource=campaign.get("datasource")
        )

        all_criteria = []

        # English campaign criteria
        for c in criteria_data["criteria"]:
            all_criteria.append({
                "Description": c.get("description"),
                "is_or": "OR" if c.get("is_or") else "AND",
                "ENGLISH": c.get("count"),
                "SPANISH": None
            })

        # English subqueries
        for sub in criteria_data.get("subqueries", []):
            for c in sub.get("criteria", []):
                all_criteria.append({
                    "Description": c.get("description"),
                    "is_or": "OR" if c.get("is_or") else "AND",
                    "ENGLISH": c.get("count"),
                    "SPANISH": None
                })

        # --- If Spanish campaign exists, fetch its criteria ---
        if spanish_campaign:
            spanish_criteria_data = get_criteria_for_campaign(
                spanish_campaign['id'],
                show_counts=bool(show_counts),
                datasource=spanish_campaign.get("datasource")
            )

            spanish_rows = []
            for c in spanish_criteria_data["criteria"]:
                spanish_rows.append({
                    "description": c.get("description"),
                    "SPANISH": c.get("count")
                })
            for sub in spanish_criteria_data.get("subqueries", []):
                for c in sub.get("criteria", []):
                    spanish_rows.append({
                        "description": c.get("description"),
                        "SPANISH": c.get("count")
                    })

            # Match by description
            for row in all_criteria:
                for s_row in spanish_rows:
                    if row["Description"] == s_row["description"]:
                        row["SPANISH"] = s_row["SPANISH"]
                        break

        # --- Convert to DataFrame ---
        df_criteria = pd.DataFrame(all_criteria)

        # --- Create Excel in memory ---
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            startrow = 2
            df_criteria.to_excel(writer, sheet_name='Campaign_Data', index=False, startrow=startrow)

            workbook = writer.book
            worksheet = writer.sheets['Campaign_Data']

            # Styles
            campaign_format = workbook.add_format({
                'bold': True,
                'font_size': 13,
                'align': 'left',
                'valign': 'top',
                'text_wrap': True,
                'border': 1
            })
            header_format = workbook.add_format({
                'bold': True,
                'border': 1,
                'align': 'center',
                'valign': 'vcenter'
            })
            data_format = workbook.add_format({'border': 1})

            # Merge campaign name
            num_cols = len(df_criteria.columns)
            worksheet.merge_range(0, 0, 0, num_cols - 1,
                                  f"Campaign_name : {campaign['name']}", campaign_format)

            # Header formatting
            for col_num, col_name in enumerate(df_criteria.columns.tolist()):
                worksheet.write(startrow, col_num, col_name, header_format)

            # Data formatting
            nrows, ncols = df_criteria.shape
            for r in range(nrows):
                for c in range(ncols):
                    val = df_criteria.iat[r, c]
                    if pd.isna(val):
                        worksheet.write_blank(startrow + 1 + r, c, None, data_format)
                    else:
                        worksheet.write(startrow + 1 + r, c, val, data_format)

            # Auto column widths
            for i, col in enumerate(df_criteria.columns):
                max_len = max(len(str(col)), df_criteria[col].dropna().astype(str).map(len).max()) + 2
                worksheet.set_column(i, i, max_len)

        # Reset buffer pointer
        output.seek(0)

        filename = f"{campaign['name']}.xlsx"

        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )







