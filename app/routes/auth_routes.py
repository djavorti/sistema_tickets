from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app import db
from app.models.usuario import Usuario
from app.models.sesion_activa import SesionActiva
from app.models import Ticket, Historial
from datetime import datetime
from app.utils import zona_ecuador

def reasignar_tickets_pendientes_al_turno(user):
    # Obtener ingenieros y sesiones activas
    sesiones_activas = {s.usuario_id for s in SesionActiva.query.all()}
    ingenieros = Usuario.query.filter_by(tipo='ingeniero').all()

    # Obtener ingeniero de turno
    ingeniero_turno = next((i for i in ingenieros if getattr(i, 'de_turno', False)), None)
    if ingeniero_turno is None or ingeniero_turno.id not in sesiones_activas:
        ingeniero_turno = next((i for i in ingenieros if i.id in sesiones_activas), None)
    if ingeniero_turno is None:
        ingeniero_turno = ingenieros[0] if ingenieros else None

    if ingeniero_turno:
        # Obtener tickets pendientes asignados al usuario que hace logout
        tickets_pendientes = Ticket.query.filter_by(asignado_id=user.id, status='Pendiente').all()

        for ticket in tickets_pendientes:
            cambio = f"Asignado: '{user.nombre} {user.apellido}' → '{ingeniero_turno.nombre} {ingeniero_turno.apellido}' por logout"
            historial = Historial(
                ticket_id=ticket.id,
                usuario=user,
                cambio=cambio,
                fecha_hora=datetime.now(zona_ecuador)
            )
            db.session.add(historial)
            ticket.asignado_id = ingeniero_turno.id

        db.session.commit()

auth_bp = Blueprint('auth_bp', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        password = request.form['password']

        user = Usuario.query.filter_by(usuario=usuario).first()

        if user and user.check_password(password):
            session['usuario'] = user.usuario
            session['tipo'] = user.tipo
            session['de_turno'] = user.de_turno
            session['usuario_id'] = user.id

            # Registrar o actualizar sesión activa con ultima_actividad
            sesion = SesionActiva.query.filter_by(usuario_id=user.id).first()
            if not sesion:
                sesion = SesionActiva(usuario_id=user.id, fecha_inicio=datetime.now(zona_ecuador), ultima_actividad=datetime.now(zona_ecuador))
                db.session.add(sesion)
            else:
                sesion.fecha_inicio = datetime.now(zona_ecuador)
                sesion.ultima_actividad = datetime.now(zona_ecuador)
            db.session.commit()

            return redirect(url_for('dashboard_bp.dashboard'))
        else:
            flash('Usuario o contraseña incorrectos.')

    return render_template('login.html')

@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    if 'usuario' in session:
        user = Usuario.query.filter_by(usuario=session['usuario']).first()
        if user:
            # Borrar sesión activa
            SesionActiva.query.filter_by(usuario_id=user.id).delete()
            db.session.commit()
            # Reasignar tickets pendientes
            reasignar_tickets_pendientes_al_turno(user)

    session.pop('usuario', None)
    session.pop('tipo', None)
    session.pop('de_turno', None)
    session.pop('usuario_id', None)
    return redirect(url_for('auth_bp.login'))

from flask import jsonify

@auth_bp.route('/check_session')
def check_session():
    if 'usuario_id' not in session:
        
        return jsonify({'active': False})
        
    sesion = SesionActiva.query.filter_by(usuario_id=session['usuario_id']).first()
    return jsonify({'active': bool(sesion)})