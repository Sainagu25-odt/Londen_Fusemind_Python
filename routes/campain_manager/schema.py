from flask_restx import fields, Model, reqparse

from extensions import api

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




CountResponseItem = api.model("CountResponseItem", {
    "state": fields.String(required=True, description="State name"),
    "total": fields.Integer(required=True, description="Total count in state")
})

HouseholdResponse = api.model("HouseholdResponse", {
    "total_households": fields.Integer,
    "total_duplicates": fields.Integer
})

CountResponseWrapper = api.model("CountResponseWrapper", {
    "state_counts": fields.List(fields.Nested(CountResponseItem)),
    "total_count": fields.Integer
})

CampaignRecordResponse = api.model('CampaignRecordResponse', {
    'data': fields.Raw
})