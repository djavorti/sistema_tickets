from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify
from datetime import datetime
from app.extensions import db
from app.models import Ticket, Cliente, Usuario, Historial, SesionActiva
from app.utils import zona_ecuador
from sqlalchemy import and_, or_
import pandas as pd
import os
from flask import send_file

dashboard_bp = Blueprint('dashboard_bp', __name__)

@dashboard_bp.route('/')
def dashboard():
    if 'usuario' not in session:
        return redirect(url_for('auth_bp.login'))

    hoy = datetime.now(zona_ecuador).date()
    usuario_actual = Usuario.query.filter_by(usuario=session['usuario']).first()

    tickets = Ticket.query.filter(or_(
        Ticket.status != 'Terminado',
        and_(Ticket.status == 'Terminado', Ticket.fecha_fin != None, db.func.date(Ticket.fecha_fin) == hoy)
    )).all()

    conteo_tickets = {}
    for ticket in tickets:
        if ticket.asignado_id:
            conteo_tickets[ticket.asignado_id] = conteo_tickets.get(ticket.asignado_id, 0) + 1

    ingenieros = Usuario.query.filter_by(tipo='ingeniero').all()
    sesiones_activas = {s.usuario_id for s in SesionActiva.query.all()}

    for ing in ingenieros:
        ing.cantidad_tickets = conteo_tickets.get(ing.id, 0)
        ing.es_logueado = ing.id in sesiones_activas

    # Obtener ingeniero de turno explícito
    ingeniero_turno = next((i for i in ingenieros if getattr(i, 'de_turno', False)), None)

    # Orden personalizado
    otros = [i for i in ingenieros if i.id != (ingeniero_turno.id if ingeniero_turno else -1)]
    logueados = sorted([i for i in otros if i.es_logueado], key=lambda x: x.cantidad_tickets)
    no_logueados = sorted([i for i in otros if not i.es_logueado], key=lambda x: x.cantidad_tickets)

    ingenieros_ordenados = ([ingeniero_turno] if ingeniero_turno else []) + logueados + no_logueados

    return render_template('dashboard.html',
                           ingenieros=ingenieros_ordenados,
                           tickets=tickets,
                           fecha_hoy=hoy.strftime('%d/%m/%Y'),
                           nombre_usuario=usuario_actual.nombre,
                           ingeniero_turno_id=ingeniero_turno.id if ingeniero_turno else None)

@dashboard_bp.route('/reasignar_ticket', methods=['POST'])
def reasignar_ticket():
    # Verificación de sesión
    usuario_actual = Usuario.query.filter_by(usuario=session.get('usuario')).first()
    if not usuario_actual:
        return jsonify({"error": "Usuario no autenticado"}), 401

    # Solo ingeniero de turno puede reasignar
    if (usuario_actual.tipo == 'ingeniero' and not usuario_actual.de_turno):
        return jsonify({"error": "No tienes permisos para reasignar tickets."}), 403

    data = request.get_json()
    ticket_id = data.get('ticket_id')
    nuevo_ingeniero = data.get('nuevo_ingeniero')

    if not ticket_id or not nuevo_ingeniero:
        return jsonify({"error": "Faltan datos"}), 400

    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return jsonify({"error": "Ticket no encontrado"}), 404

    if ticket.status == 'Terminado':
        return jsonify({"error": "No se puede reasignar un ticket cerrado."}), 403

    anterior_asignado = f"{ticket.asignado.nombre} {ticket.asignado.apellido}" if ticket.asignado else ""

    nuevo_asignado = Usuario.query.filter_by(usuario=nuevo_ingeniero).first()
    if not nuevo_asignado:
        return jsonify({"error": "Ingeniero no encontrado"}), 404

    if f"{nuevo_asignado.nombre} {nuevo_asignado.apellido}" != anterior_asignado:
        nuevo_historial = Historial(
            ticket_id=ticket.id,
            usuario=usuario_actual,
            cambio=f"Asignado: '{anterior_asignado}' → '{nuevo_asignado.nombre} {nuevo_asignado.apellido}'",
            fecha_hora=datetime.now(zona_ecuador)
        )
        db.session.add(nuevo_historial)
        ticket.asignado_id = nuevo_asignado.id
        db.session.commit()

    return jsonify({"status": "ok"}), 200

@dashboard_bp.route('/historico')
def historico():
    if 'usuario' not in session:
        return redirect(url_for('auth_bp.login'))

    desde_str = request.args.get('desde')
    hasta_str = request.args.get('hasta')

    query = Ticket.query
    if desde_str:
        desde = datetime.strptime(desde_str, '%Y-%m-%d')
        query = query.filter(Ticket.fecha_inicio >= desde)
    if hasta_str:
        hasta = datetime.strptime(hasta_str, '%Y-%m-%d')
        hasta = hasta.replace(hour=23, minute=59, second=59)
        query = query.filter(Ticket.fecha_inicio <= hasta)

    tickets = query.order_by(Ticket.id.desc()).all()
    clientes = {c.id: c.nombre for c in Cliente.query.all()}
    ingenieros = {i.id: f"{i.nombre} {i.apellido}" for i in Usuario.query.filter_by(tipo='ingeniero').all()}

    return render_template('historico_tickets.html', tickets=tickets, clientes=clientes, ingenieros=ingenieros)

@dashboard_bp.route('/descargar_historico')
def descargar_historico():
    if 'usuario' not in session:
        return redirect(url_for('auth_bp.login'))

    desde_str = request.args.get('desde')
    hasta_str = request.args.get('hasta')

    query = Ticket.query
    if desde_str:
        desde = datetime.strptime(desde_str, '%Y-%m-%d')
        query = query.filter(Ticket.fecha_inicio >= desde)
    if hasta_str:
        hasta = datetime.strptime(hasta_str, '%Y-%m-%d')
        hasta = hasta.replace(hour=23, minute=59, second=59)
        query = query.filter(Ticket.fecha_inicio <= hasta)

    tickets = query.order_by(Ticket.id.desc()).all()

    data = []
    for t in tickets:
        data.append({
            "ID": t.id,
            "Status": t.status,
            "Tipo": t.tipo,
            "Medio": t.medio,
            "Asunto": t.asunto,
            "Fecha Inicio": t.fecha_inicio.strftime('%Y-%m-%d %H:%M:%S') if t.fecha_inicio else '',
            "Fecha Fin": t.fecha_fin.strftime('%Y-%m-%d %H:%M:%S') if t.fecha_fin else '',
            "PID": t.pid,
            "Sede": t.sede,
            "Cliente": t.cliente.nombre if t.cliente else '',
            "Asignado": f"{t.asignado.nombre} {t.asignado.apellido}" if t.asignado else ''
        })

    df = pd.DataFrame(data)
    archivo_excel = '/tmp/historico_tickets.xlsx'
    df.to_excel(archivo_excel, index=False)

    return send_file(archivo_excel, as_attachment=True)

@dashboard_bp.route('/ver_ticket/<ticket_id>', methods=['POST'])
def ver_ticket(ticket_id):
    from app.models import Ticket, Cliente, Usuario, Historial
    ticket = Ticket.query.get_or_404(ticket_id)
    clientes = Cliente.query.all()
    ingenieros = Usuario.query.filter_by(tipo='ingeniero').all()
    historial = Historial.query.filter_by(ticket_id=ticket_id).order_by(Historial.fecha_hora.desc()).all()

    readonly = (ticket.status == 'Terminado')

    return render_template('editar_ticket.html',
                           ticket=ticket,
                           clientes=clientes,
                           ingenieros=ingenieros,
                           historial=historial,
                           readonly=readonly)

@dashboard_bp.route('/cambiar_turno', methods=['POST'])
def cambiar_turno():
    data = request.get_json()
    nuevo_turno_id = data.get('usuario_id')

    if not nuevo_turno_id:
        return jsonify({'error': 'Falta ID de usuario'}), 400

    # Desactivar todos los turnos
    Usuario.query.update({Usuario.de_turno: False})

    # Activar el nuevo turno
    ingeniero = Usuario.query.get(nuevo_turno_id)
    if not ingeniero:
        return jsonify({'error': 'Usuario no encontrado'}), 404

    ingeniero.de_turno = True
    db.session.commit()

    return jsonify({'status': 'ok'}), 200