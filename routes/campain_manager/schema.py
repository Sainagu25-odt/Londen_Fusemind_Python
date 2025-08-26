from flask_restx import fields, Model, reqparse

from extensions import api

campaign_response = Model('CampaignResponse', {
    'id': fields.Integer,
     'name': fields.String,
     'description': fields.String,
     'begin_date': fields.String,
     'channel': fields.String,
     'deleted_at': fields.String,
     'campaign_subquery_id': fields.Integer
})

#counts response fields
counts_response = Model('CountsResponse', {
    "campaign_name": fields.String,
    "channel": fields.String,
    'counts': fields.Integer,
    'universe': fields.Integer,
    'states': fields.List(fields.Raw),
    "previous_pulls": fields.List(fields.Raw)
})


criteria_model = Model('Criterion', {
    'column_name': fields.String,
    'operator': fields.String,
    'value': fields.String,
    'is_or': fields.Boolean
})

campaign_edit_response = Model('CampaignEditResponse', {
    'campaign_id': fields.Integer,
    'channels': fields.List(fields.String),
    'criteria': fields.List(fields.Nested(criteria_model)),
    'steps': fields.List(fields.Integer),
    'currentStep': fields.Integer
})

# Parser for /campaign/pull (user-defined fields)
pull_request_parser = reqparse.RequestParser()
pull_request_parser.add_argument("campaign_id", type=int, required=True)
pull_request_parser.add_argument("householding", type=int)
pull_request_parser.add_argument("every_n", type=int)
pull_request_parser.add_argument("num_records", type=int)
pull_request_parser.add_argument("fields", type=str)
pull_request_parser.add_argument("fieldset_id", type=int)
pull_request_parser.add_argument("excluded_pulls", type=str)
pull_request_parser.add_argument("request_email", type=str)

# Pull item schema
pull_item_model = Model("PullItem", {
    "campaign_list_id" : fields.String,
    "campaign": fields.String,
    "list_title": fields.String,
    "requested_by": fields.String,
    "time_requested": fields.String,
    "time_completed": fields.String
})

# Response for pull list APIs
active_pulls_response_model = Model("ActivePullsResponse", {
    "active_pulls": fields.List(fields.Nested(pull_item_model))
})

#response for add criteria
add_criteria_response = Model('AddCriteriaResponse', {
    'status': fields.String,
    'data': fields.Integer
})



# Nested model for each legend item
legend_item = Model('LegendItem', {
    'value': fields.String,
    'total': fields.Integer
})

legend_response = Model('LegendResponse', {
    'status': fields.String,
    'data': fields.List(fields.Nested(legend_item))
})

subquery_dialog_response = Model('SubqueryDialogResponse', {
    'status': fields.String,
    'data': fields.Nested(Model('SubqueryOption', {
        'table': fields.List(fields.String),
        'operator' : fields.List(fields.String),
        'label': fields.List(fields.String)
    }))
})



campaign_list_model = Model("CampaignListPayload", {
    "id": fields.String(required=False, description="Pull ID, blank for new"),
    "campaign_id": fields.Integer(required=True, description="Campaign ID"),
    "name": fields.String(required=False, description="Pull name"),
    "fieldset_id": fields.Integer(required=False, description="Fieldset ID"),
    "householding": fields.Integer(required=False, description="1 or 0"),
    "every_n": fields.Integer(required=False, description="Every N records"),
    "num_records": fields.Integer(required=False, description="Number of records"),
    "fields": fields.String(required=False, description="Comma-separated fields"),
    "record_retrieval": fields.String(required=False, description="every_n or num_records"),
    "request_email": fields.String(required=False),
    "requested_by": fields.String(required=False),
    "excluded_pulls": fields.String(required=False)
})

pull_request_model = Model("CampaignRequestPayload", {
    "campaign_list": fields.Nested(campaign_list_model, required=True),
    "fieldset_type": fields.String(required=True, description="new or existing"),
    "fieldset_name": fields.String(required=False, description="Only if new"),
    "fieldset_selected_fields": fields.String(required=False, description="Comma-separated fields for new fieldset")
})




