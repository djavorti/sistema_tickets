from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime
from app.extensions import db
from app.models import Ticket, Usuario, Cliente, Historial
from app.utils import zona_ecuador
from sqlalchemy import extract

ticket_bp = Blueprint('ticket_bp', __name__)


@ticket_bp.route('/crear_ticket', methods=['GET', 'POST'])
def crear_ticket():
    if 'usuario' not in session:
        flash("Debes iniciar sesión para crear tickets.")
        return redirect(url_for('auth_bp.login'))

    usuario_logueado = Usuario.query.filter_by(usuario=session['usuario']).first()
    ingeniero_turno = Usuario.query.filter_by(tipo='ingeniero', de_turno=True).first()

    if request.method == 'POST':
        # Recoger datos del formulario
        id_tt = request.form['id_tt']
        status = request.form['status']
        tipo = request.form['tipo']
        medio = request.form['medio']
        asunto = request.form['asunto']
        detalle = request.form['detalle']
        pid = request.form['pid']
        sede = request.form['sede']
        tt_remedy = request.form['tt_remedy']
        actualizacion = request.form['actualizacion']
        cliente_nombre = request.form['cliente']
        fecha_inicio = datetime.now(zona_ecuador)

        cliente = Cliente.query.filter_by(nombre=cliente_nombre).first()

        # Lógica para asignar el ticket:
        if (usuario_logueado.tipo != 'ingeniero' or usuario_logueado.de_turno):
            # Ingeniero de turno puede elegir
            asignado_id = request.form['asignado']
            asignado = Usuario.query.get(asignado_id)
        else:
            # Usuario no es ingeniero de turno: asignar automáticamente
            asignado = ingeniero_turno

        # Crear el nuevo ticket
        nuevo_ticket = Ticket(
            id=id_tt,
            status=status,
            tipo=tipo,
            medio=medio,
            asunto=asunto,
            tt_remedy = tt_remedy,
            detalle=detalle,
            fecha_inicio=fecha_inicio,
            pid=pid,
            sede=sede,
            cliente=cliente,
            usuario=usuario_logueado,
            asignado=asignado,
            actualizacion=actualizacion
        )

        db.session.add(nuevo_ticket)
        db.session.commit()

        flash('Ticket creado exitosamente', 'success')
        return redirect(url_for('dashboard_bp.dashboard'))

    # GET: preparar formulario
    clientes = Cliente.query.all()
    ingenieros = Usuario.query.filter_by(tipo='ingeniero').all()

    hoy = datetime.now(zona_ecuador)
    base_id = hoy.strftime('%Y%m%d')
    tickets_mes = Ticket.query.filter(
        extract('year', Ticket.fecha_inicio) == hoy.year,
        extract('month', Ticket.fecha_inicio) == hoy.month
    ).count()
    nuevo_id_tt = f"{base_id}-{tickets_mes + 1:03}"

    return render_template(
        'crear_ticket.html',
        id_tt=nuevo_id_tt,
        status="Pendiente",
        fecha_inicio=hoy.strftime('%Y-%m-%d %H:%M:%S'),
        clientes=clientes,
        ingenieros=ingenieros,
        usuario_logueado=usuario_logueado  # <-- pasamos esto al template
    )

@ticket_bp.route('/editar_ticket/<ticket_id>', methods=['GET', 'POST'])
def editar_ticket(ticket_id):
    if 'usuario' not in session:
        flash("Debes iniciar sesión para editar tickets.")
        return redirect(url_for('auth_bp.login'))

    ticket = Ticket.query.get_or_404(ticket_id)
    clientes = Cliente.query.all()
    ingenieros = Usuario.query.filter_by(tipo='ingeniero').all()
    historial = Historial.query.filter_by(ticket_id=ticket_id).order_by(Historial.fecha_hora.desc()).all()

    if request.method == 'POST':
        
        print(request.form)  # Ver qué datos llegan

        cambios = []

        # Valores anteriores
        anterior_status = ticket.status
        anterior_tipo = ticket.tipo
        anterior_medio = ticket.medio
        anterior_detalle = ticket.detalle
        anterior_pid = ticket.pid
        anterior_sede = ticket.sede
        anterior_cliente = ticket.cliente.nombre if ticket.cliente else ""
        anterior_asignado = f"{ticket.asignado.nombre} {ticket.asignado.apellido}" if ticket.asignado else ""
        anterior_actualizacion = ticket.actualizacion
        anterior_tt_remedy = ticket.tt_remedy

        # Nuevos valores del formulario
        nuevo_status = request.form['status']
        nuevo_tipo = request.form['tipo']
        nuevo_medio = request.form['medio']
        nuevo_detalle = request.form['detalle']
        nuevo_pid = request.form['pid']
        nuevo_sede = request.form['sede']
        nuevo_cliente = Cliente.query.filter_by(nombre=request.form['cliente']).first()
        asignado_id = request.form.get('asignado')
        if asignado_id:
            nuevo_asignado = Usuario.query.get(asignado_id)
        else:
            nuevo_asignado = ticket.asignado  # Mantener el asignado anterior si no viene en el formulario
        nuevo_actualizacion = request.form.get('actualizacion', '').strip()
        nuevo_tt_remedy = request.form.get('tt_remedy', '').strip()

        # Comparar campos y registrar cambios
        if nuevo_status != anterior_status:
            # Si cambia a 'Finalizado', registrar fecha de fin
            if nuevo_status.lower() == "terminado":
                ticket.fecha_fin = datetime.now(zona_ecuador)
            cambios.append(f"Estado: '{anterior_status}' → '{nuevo_status}'")
            ticket.status = nuevo_status
            
        if nuevo_tipo != anterior_tipo:
            cambios.append(f"Tipo: '{anterior_tipo}' → '{nuevo_tipo}'")
            ticket.tipo = nuevo_tipo

        if nuevo_medio != anterior_medio:
            cambios.append(f"Medio: '{anterior_medio}' → '{nuevo_medio}'")
            ticket.medio = nuevo_medio

        if nuevo_detalle != anterior_detalle:
            cambios.append(f"Detalle: '{anterior_detalle}' → '{nuevo_detalle}'")
            ticket.detalle = nuevo_detalle

        if nuevo_pid != anterior_pid:
            cambios.append(f"PID: '{anterior_pid}' → '{nuevo_pid}'")
            ticket.pid = nuevo_pid

        if nuevo_sede != anterior_sede:
            cambios.append(f"Sede: '{anterior_sede}' → '{nuevo_sede}'")
            ticket.sede = nuevo_sede

        if nuevo_tt_remedy != anterior_tt_remedy:
            cambios.append(f"TT Remedy: '{anterior_tt_remedy}' → '{nuevo_tt_remedy}'")
            ticket.tt_remedy = nuevo_tt_remedy

        if nuevo_cliente and nuevo_cliente.nombre != anterior_cliente:
            cambios.append(f"Cliente: '{anterior_cliente}' → '{nuevo_cliente.nombre}'")
            ticket.cliente = nuevo_cliente

        if nuevo_asignado and f"{nuevo_asignado.nombre} {nuevo_asignado.apellido}" != anterior_asignado:
            cambios.append(f"Asignado: '{anterior_asignado}' → '{nuevo_asignado.nombre} {nuevo_asignado.apellido}'")
            ticket.asignado = nuevo_asignado

        if nuevo_actualizacion != anterior_actualizacion:
            cambios.append(f"Actualización: {nuevo_actualizacion}")
            ticket.actualizacion = nuevo_actualizacion

        # Registrar historial si hay cambios
        if cambios:
            nuevo_historial = Historial(
                ticket_id=ticket.id,
                usuario=Usuario.query.filter_by(usuario=session['usuario']).first(),
                cambio="\n".join(cambios),
                fecha_hora=datetime.now(zona_ecuador)  # → como datetime, no string
            )
            db.session.add(nuevo_historial)

        db.session.commit()
        flash('Ticket actualizado correctamente.')
        return redirect(url_for('ticket_bp.editar_ticket', ticket_id=ticket.id))

    return render_template(
        'editar_ticket.html',
        ticket=ticket,
        clientes=clientes,
        ingenieros=ingenieros,
        historial=historial
    )

