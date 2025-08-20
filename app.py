import os
import yaml
from flask import Flask
from flask_cors import CORS
from extensions import db, api
from routes.auth import auth_ns
from routes.campain_manager.source import campaign_ns
from routes.reports.source import reports_ns
from routes.responsers_file.source import responder_ns
from routes.dashboard.source import dashboard_ns
from routes.user_admin.source import user_ns

# 1. Optionally load .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

config_path = os.getenv('APP_CONFIG_PATH')


if not config_path or not os.path.exists(config_path):
    raise FileNotFoundError(
        f"APP_CONFIG_PATH is not set or file does not exist: {config_path}\n"
        "Set APP_CONFIG_PATH to point to your config.yml file."
    )

with open(config_path, 'r') as f:
    config = yaml.safe_load(f)


# Initialize app
app = Flask(__name__)
CORS(app)

app.config['SECRET_KEY'] = config['app']['secret_key']
app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"postgresql://{config['database']['user']}:{config['database']['password']}@"
    f"{config['database']['host']}:{config['database']['port']}/{config['database']['name']}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Init extensions
db.init_app(app)
api.init_app(app)

# Register Namespaces
api.add_namespace(auth_ns, path='/api/auth')
api.add_namespace(dashboard_ns, path='/api/dashboard')
api.add_namespace(user_ns, path='/api/userAdmin')
api.add_namespace(reports_ns, path='/api/reports')
api.add_namespace(campaign_ns, path='/api/campaign')
api.add_namespace(responder_ns, path='/api/responders')

# Run
if __name__ == '__main__':
    debug_mode = os.getenv("FLASK_ENV") == "development"
    print(f"[APP] Starting Flask server (debug={debug_mode})")
    app.run(host='0.0.0.0', port=5000, debug=True)