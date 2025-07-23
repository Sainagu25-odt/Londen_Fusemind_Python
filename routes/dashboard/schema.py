from flask_restx import fields, Namespace

api = Namespace("Dashboard", description="Dashboard Metrics API")

dashboard_response = api.model("DashboardResponse", {
    "policy_holders": fields.Integer(description="Number of policy holders"),
    "non_insurance": fields.Integer(description="Number of non-insurance responders"),
    "total_responders": fields.Integer(description="Total number of responders"),
})