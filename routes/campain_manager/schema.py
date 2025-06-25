from flask_restx import fields, Model

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