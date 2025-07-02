from flask_restx import fields


def get_responder_file_models(api):
    record_model = api.model("Record", {
        "state": fields.String(),
        "total": fields.Integer(),
        "policy_holders": fields.Integer(),
        "household_duplicates": fields.Integer(),
        "net": fields.Integer()
    })

    response_model = api.model("ResponderFileResponse", {
        "data": fields.List(fields.Nested(record_model)),
        "fields": fields.Raw()
    })

    return record_model, response_model


def get_feedManager_models(api):
    record_model = api.model("FeedManagerRecord", {
        "filename": fields.String(),
        "processed": fields.String(),
        "records": fields.Integer(),
        "downloaded_at": fields.String(),
        "imported_at": fields.String(),
        "completed_at": fields.String()
    })

    feed_manager_response_model = api.model("FeedManagerResponse", {
        "recordsReturned": fields.Integer(),
        "totalRecords": fields.Integer(),
        "startIndex": fields.Integer(),
        "sort": fields.String(),
        "dir": fields.String(),
        "pageSize": fields.Integer(),
        "records": fields.List(fields.Nested(record_model)),
        "fields": fields.Raw()
    })
    return record_model, feed_manager_response_model

