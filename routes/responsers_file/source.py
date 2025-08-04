import os

from flask_restx import Namespace, Resource

from models.responders import execute_responder_task

responder_ns = Namespace('Responder', description='Responder File APIs')


@responder_ns.route('/process')
class ResponderProcessAPI(Resource):
    def post(self):
        """
        Trigger responder file import:
        - Downloads ZIP from SFTP
        - Extracts CSV
        - Imports data into import_responder
        - Updates logs and populates responses and responder_file
        """
        try:
            base_dir = os.path.join(os.getcwd(), 'responder_files')
            os.makedirs(base_dir, exist_ok=True)
            execute_responder_task(base_dir=base_dir, debug=True)
            return {"message": "Responder processing completed"}, 200
        except Exception as e:
            return {"error": str(e)}, 500