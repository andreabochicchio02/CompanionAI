from flask import Flask
from .routes import index
from .routes import chatLLM

def create_app():
    app = Flask(__name__)

    app.register_blueprint(index.bp)
    app.register_blueprint(chatLLM.bp)

    return app