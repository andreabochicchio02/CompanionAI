from flask import Flask
from .routes import index
from .routes import chatLLM
from .routes import dashboard

def create_app():
    app = Flask(__name__)

    app.register_blueprint(index.bp)
    app.register_blueprint(chatLLM.bp)
    app.register_blueprint(dashboard.bp)

    return app