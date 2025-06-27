from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from app.config import Config

from app.models.usuario import Usuario
from app.models.ticket import Ticket
from app.models.cliente import Cliente
from app.extensions import db, migrate
from flask import Flask, session, redirect, url_for, flash, request
from datetime import datetime, timedelta
from app.models.sesion_activa import SesionActiva
from app.utils import zona_ecuador
import sys
from pytz import timezone




def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)

    # Importar blueprints
    from app.routes.auth_routes import auth_bp
    from app.routes.ticket_routes import ticket_bp
    from app.routes.dashboard_routes import dashboard_bp
    from app.routes.programado_routes import programado_bp
    
    app.register_blueprint(programado_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(ticket_bp)
    app.register_blueprint(dashboard_bp)

    

    from app.routes.auth_routes import reasignar_tickets_pendientes_al_turno

    @app.before_request
    def check_inactividad():
        if 'usuario_id' in session:
            usuario = Usuario.query.get(session['usuario_id'])
            sesion = SesionActiva.query.filter_by(usuario_id=usuario.id).first()
            if not sesion:
                session.clear()
                flash('Sesión cerrada. Por favor, inicia sesión nuevamente.')
                return redirect(url_for('auth_bp.login'))
            if usuario and usuario.tipo == 'ingeniero':
                if sesion.ultima_actividad:
                    if sesion.ultima_actividad.tzinfo is None:
                        sesion_ultima = zona_ecuador.localize(sesion.ultima_actividad)
                    else:
                        sesion_ultima = sesion.ultima_actividad
                    ahora = datetime.now(zona_ecuador)
                    if ahora - sesion_ultima > timedelta(hours=4):
                        # Reasignar tickets pendientes antes de cerrar sesión
                        reasignar_tickets_pendientes_al_turno(usuario)
                        SesionActiva.query.filter_by(usuario_id=usuario.id).delete()
                        db.session.commit()
                        session.clear()
                        flash('Sesión cerrada por inactividad. Por favor, inicia sesión nuevamente.')
                        return redirect(url_for('auth_bp.login'))

    return app
