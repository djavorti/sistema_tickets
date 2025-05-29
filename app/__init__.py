from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from app.config import Config

from app.models.usuario import Usuario
from app.models.ticket import Ticket
from app.models.cliente import Cliente
from app.extensions import db, migrate



def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)

    # Importar blueprints
    from app.routes.auth_routes import auth_bp
    from app.routes.ticket_routes import ticket_bp
    from app.routes.dashboard_routes import dashboard_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(ticket_bp)
    app.register_blueprint(dashboard_bp)

    return app