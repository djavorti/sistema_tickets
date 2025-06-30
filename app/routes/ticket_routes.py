# File: app/routes/ticket_routes.py
# app/routes/ticket_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime
from app.extensions import db
from app.models import Ticket, Usuario, Cliente, Historial
from app.utils import zona_ecuador
from sqlalchemy import extract
import urllib.parse
from app.models.sesion_activa import SesionActiva

def actualizar_actividad(usuario_id):
    sesion = SesionActiva.query.filter_by(usuario_id=usuario_id).first()
    if sesion:
        sesion.ultima_actividad = datetime.now(zona_ecuador)
        db.session.commit()

def aplicar_cambios_ticket(ticket, usuario_actual, cambios_dict):
    cambios = []
    # --- Estado ---
    if 'status' in cambios_dict and cambios_dict['status'] != ticket.status:
        anterior_status = ticket.status
        nuevo_status = cambios_dict['status']
        if nuevo_status.lower() == "terminado":
            ticket.fecha_fin = datetime.now(zona_ecuador)
        elif anterior_status.lower() == "terminado":
            ticket.fecha_fin = None
        cambios.append(f"Estado: '{anterior_status}' → '{nuevo_status}'")
        ticket.status = nuevo_status

    # --- Tipo ---
    if 'tipo' in cambios_dict and cambios_dict['tipo'] != ticket.tipo:
        cambios.append(f"Tipo: '{ticket.tipo}' → '{cambios_dict['tipo']}'")
        ticket.tipo = cambios_dict['tipo']

    # --- Medio ---
    if 'medio' in cambios_dict and cambios_dict['medio'] != ticket.medio:
        cambios.append(f"Medio: '{ticket.medio}' → '{cambios_dict['medio']}'")
        ticket.medio = cambios_dict['medio']

    # --- Detalle ---
    if 'detalle' in cambios_dict and cambios_dict['detalle'] != ticket.detalle:
        cambios.append(f"Detalle: '{ticket.detalle}' → '{cambios_dict['detalle']}'")
        ticket.detalle = cambios_dict['detalle']

    # --- PID ---
    if 'pid' in cambios_dict and cambios_dict['pid'] != ticket.pid:
        cambios.append(f"PID: '{ticket.pid}' → '{cambios_dict['pid']}'")
        ticket.pid = cambios_dict['pid']

    # --- Sede ---
    if 'sede' in cambios_dict and cambios_dict['sede'] != ticket.sede:
        cambios.append(f"Sede: '{ticket.sede}' → '{cambios_dict['sede']}'")
        ticket.sede = cambios_dict['sede']

    # --- TT Remedy ---
    if 'tt_remedy' in cambios_dict and cambios_dict['tt_remedy'] != ticket.tt_remedy:
        cambios.append(f"TT Remedy: '{ticket.tt_remedy}' → '{cambios_dict['tt_remedy']}'")
        ticket.tt_remedy = cambios_dict['tt_remedy']

    # --- Cliente ---
    if 'cliente' in cambios_dict and cambios_dict['cliente'] and cambios_dict['cliente'] != (ticket.cliente.nombre if ticket.cliente else ""):
        anterior_cliente = ticket.cliente.nombre if ticket.cliente else ""
        cambios.append(f"Cliente: '{anterior_cliente}' → '{cambios_dict['cliente']}'")
        ticket.cliente = Cliente.query.filter_by(nombre=cambios_dict['cliente']).first()

    # --- Asignado ---
    if 'asignado' in cambios_dict and cambios_dict['asignado']:
        anterior_asignado = f"{ticket.asignado.nombre} {ticket.asignado.apellido}" if ticket.asignado else ""
        nuevo_asignado = cambios_dict['asignado']
        if f"{nuevo_asignado.nombre} {nuevo_asignado.apellido}" != anterior_asignado:
            cambios.append(f"Asignado: '{anterior_asignado}' → '{nuevo_asignado.nombre} {nuevo_asignado.apellido}'")
            ticket.asignado = nuevo_asignado

    # --- Actualización ---
    if 'actualizacion' in cambios_dict and cambios_dict['actualizacion']:
        anterior_actualizacion = ticket.actualizacion
        nuevo_actualizacion = cambios_dict['actualizacion']
        if nuevo_actualizacion != anterior_actualizacion:
            if not cambios:
                cambios.append(f"Actualización: {nuevo_actualizacion}")
            else:
                cambios.append(f"Nueva Actualización: {nuevo_actualizacion}")
            ticket.actualizacion = nuevo_actualizacion

    # --- Registrar historial si hay cambios ---
    if cambios:
        nuevo_historial = Historial(
            ticket_id=ticket.id,
            usuario=usuario_actual,
            cambio="\n".join(cambios),
            fecha_hora=datetime.now(zona_ecuador)
        )
        db.session.add(nuevo_historial)
        db.session.commit()
        actualizar_actividad(usuario_actual.id)
    else:
        db.session.commit()
    return cambios


ticket_bp = Blueprint('ticket_bp', __name__)


@ticket_bp.route('/crear_ticket', methods=['GET', 'POST'])
def crear_ticket():
    if 'usuario' not in session:
        flash("Debes iniciar sesión para crear tickets.")
        return redirect(url_for('auth_bp.login'))

    usuario_logueado = Usuario.query.filter_by(usuario=session['usuario']).first()
    ingeniero_turno = Usuario.query.filter_by(tipo='ingeniero', de_turno=True).first()

    if request.method == 'POST':
        # Recoger datos del formulario (excepto id_tt del campo oculto)
        status = request.form['status']
        tipo = request.form['tipo']
        medio = request.form['medio']
        asunto = request.form['asunto']
        # Usar .get() para campos opcionales, proporcionando un valor por defecto si no están presentes
        detalle = request.form.get('detalle', '').strip()
        if not detalle:
            detalle = asunto # Si no se proporciona detalle, se usa el asunto como detalle
        pid = request.form.get('pid', '').strip()
        sede = request.form.get('sede', '').strip()
        tt_remedy = request.form.get('tt_remedy', '').strip()
        actualizacion = request.form.get('actualizacion', '').strip() # Usar .get() para opcional
        cliente_nombre = request.form['cliente']
        # fecha_inicio se genera en el servidor al momento de la creación

        cliente = Cliente.query.filter_by(nombre=cliente_nombre).first()

        # Lógica para asignar el ticket:
        # Si el usuario logueado NO es ingeniero O es ingeniero de turno, puede elegir asignado.
        # Si es ingeniero pero NO de turno, se asigna automáticamente al de turno.
        if usuario_logueado.tipo != 'ingeniero' or usuario_logueado.de_turno:
             # Usuario puede elegir asignado (si el campo 'asignado' existe en el form)
            asignado_id = request.form.get('asignado') # Usar .get() para evitar KeyError si el campo no está presente
            if asignado_id:
                 asignado = Usuario.query.get(asignado_id)
            else:
                 # Esto podría pasar si el campo asignado no se muestra pero el usuario es ingeniero de turno
                 # En este caso, se asigna a sí mismo si es ingeniero de turno, o al de turno si no es él.
                 if usuario_logueado.de_turno:
                     asignado = usuario_logueado
                 else:
                     asignado = ingeniero_turno # Fallback al ingeniero de turno si no se pudo determinar
        else:
            # Usuario es ingeniero pero NO de turno: asignar automáticamente al de turno
            asignado = ingeniero_turno

        # --- Generar el ID del ticket AHORA (en el POST) ---
        hoy = datetime.now(zona_ecuador)
        base_id = hoy.strftime('%Y%m')  # Solo año y mes
        # Buscar todos los tickets del MES actual y extraer el mayor sufijo numérico
        tickets_mes = (
            Ticket.query
            .filter(
                Ticket.id.startswith(base_id),  # Solo filtra por año y mes
                extract('year', Ticket.fecha_inicio) == hoy.year,
                extract('month', Ticket.fecha_inicio) == hoy.month
            )
            .all()
        )
        max_num = 0
        for t in tickets_mes:
            try:
                num = int(t.id.split('-')[-1])
                if num > max_num:
                    max_num = num
            except Exception:
                continue
        nuevo_num = max_num + 1
        # El ID sigue usando el día para el display, pero el correlativo es mensual
        nuevo_id_tt = f"{hoy.strftime('%Y%m%d')}-{nuevo_num:04}"

        # Crear el nuevo ticket
        nuevo_ticket = Ticket(
            id=nuevo_id_tt, # Usar el ID generado en el POST
            status=status,
            tipo=tipo,
            medio=medio,
            asunto=asunto,
            tt_remedy = tt_remedy,
            detalle=detalle,
            fecha_inicio=datetime.now(zona_ecuador), # Generar fecha de inicio en el POST
            pid=pid,
            sede=sede,
            cliente=cliente,
            usuario=usuario_logueado,
            asignado=asignado,
            actualizacion=actualizacion
        )

        # Registrar historial solo si hay una actualización inicial proporcionada
        if actualizacion:
            nuevo_historial = Historial(
                    ticket_id=nuevo_id_tt, # Usar el ID generado en el POST
                    usuario=Usuario.query.filter_by(usuario=session['usuario']).first(),
                    cambio=f"Actualizacion inicial: {actualizacion}",
                    fecha_hora=datetime.now(zona_ecuador)
                )
            db.session.add(nuevo_historial)

        db.session.add(nuevo_ticket)
        db.session.commit()
        actualizar_actividad(usuario_logueado.id)
        flash('Ticket creado exitosamente', 'success')

        # El POST siempre redirige al dashboard
        return redirect(url_for('dashboard_bp.dashboard'))

    # GET: preparar formulario
    clientes = Cliente.query.all()
    clientes_json = [
        {"nombre": c.nombre, "nota": c.nota or ""}
        for c in clientes
    ]
    ingenieros = Usuario.query.filter_by(tipo='ingeniero').all()

    # Generar un ID provisional solo para mostrar en el formulario GET
    hoy = datetime.now(zona_ecuador)
    base_id = hoy.strftime('%Y%m%d')
    # Contar tickets del día actual para el sufijo (esto es solo una estimación para el display)
    tickets_hoy_estimado = Ticket.query.filter(
        extract('year', Ticket.fecha_inicio) == hoy.year,
        extract('month', Ticket.fecha_inicio) == hoy.month,
        extract('day', Ticket.fecha_inicio) == hoy.day
    ).count()
    
    # Generar el ID provisional
    id_tt_provisional = f"{base_id}-{tickets_hoy_estimado + 1:04}"



    return render_template(
        'crear_ticket.html',
        id_tt=id_tt_provisional, # Pasar el ID provisional al template
        status="Pendiente",
        fecha_inicio=hoy.strftime('%Y-%m-%d %H:%M:%S'), # Pasar fecha/hora actual para display
        clientes=clientes_json, # Pasamos la lista de objetos Cliente
        ingenieros=ingenieros,
        usuario_logueado=usuario_logueado
    )

# --- Nueva ruta para preparar el correo proactivo ---
@ticket_bp.route('/prepare_proactive_email', methods=['POST'])
def prepare_proactive_email():
    if 'usuario' not in session:
        return jsonify({'error': 'Usuario no autenticado'}), 401

    usuario_logueado = Usuario.query.filter_by(usuario=session['usuario']).first()
    if not usuario_logueado:
         return jsonify({'error': 'Usuario no encontrado'}), 404

    # Recoger datos de la solicitud AJAX
    cliente_nombre = request.form.get('cliente_nombre')
    asunto = request.form.get('asunto')
    sede = request.form.get('sede')
    tipo = request.form.get('tipo') # Recibir el tipo de ticket

    if not cliente_nombre or not asunto:
         return jsonify({'error': 'Faltan datos del cliente o asunto'}), 400

    cliente = Cliente.query.filter_by(nombre=cliente_nombre).first()
    if not cliente:
        return jsonify({'error': 'Cliente no encontrado'}), 404

    cliente_emails = cliente.email if cliente.email else ''
    ticket_sede = sede if sede else ''

    # Determinar saludo según la hora (0 a 11 -> Buenos días)
    hora_actual = datetime.now(zona_ecuador).hour
    if 0 <= hora_actual < 12:
        greeting = "Buenos días"
    elif 12 <= hora_actual < 18:
        greeting = "Buenas tardes"
    else:
        greeting = "Buenas noches"

    #user_name = f"{usuario_logueado.nombre} {usuario_logueado.apellido}"
    user_name = ""
    # El prefijo del asunto ahora se maneja en el frontend para el campo de texto.
    # Aquí usamos el asunto tal como llega del formulario.

    # Usar \r\n para saltos de línea en mailto body
    # Eliminar paréntesis alrededor de la sede
    email_body = f"{greeting},\r\n\r\nAl momento se detecta pérdida del enlace {ticket_sede}.\r\n\r\nSu gentil ayuda descartando problemas eléctricos o trabajos que afecten a los equipos.\r\n\r\n{user_name}"

    # Direcciones de correo para CC
    # Direcciones de correo para CC
    cc_emails = "tecoymcorpcnoc@claro.com.ec;soporte_empresas@claro.com.ec"

    # Codificar asunto, cuerpo y CC para la URL usando urllib.parse.quote
    encoded_subject = urllib.parse.quote(asunto) # Usar el asunto tal como llega
    encoded_body = urllib.parse.quote(email_body)
    encoded_cc = urllib.parse.quote(cc_emails)

    # Construir la URL mailto con CC
    mailto_url = f"mailto:{cliente_emails}?subject={encoded_subject}&body={encoded_body}&cc={encoded_cc}"

    # Devolver la URL mailto como respuesta JSON
    return jsonify({'mailto_url': mailto_url})

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
        usuario_actual = Usuario.query.filter_by(usuario=session['usuario']).first()
        cambios_dict = {
            'status': request.form['status'],
            'tipo': request.form['tipo'],
            'medio': request.form['medio'],
            'detalle': request.form.get('detalle', '').strip(),
            'pid': request.form.get('pid', '').strip(),
            'sede': request.form.get('sede', '').strip(),
            'tt_remedy': request.form.get('tt_remedy', '').strip(),
            'cliente': request.form['cliente'],
            'actualizacion': request.form.get('actualizacion', '').strip()
        }
        asignado_id = request.form.get('asignado')
        if asignado_id:
            cambios_dict['asignado'] = Usuario.query.get(asignado_id)
        else:
            cambios_dict['asignado'] = ticket.asignado

        aplicar_cambios_ticket(ticket, usuario_actual, cambios_dict)
        flash('Ticket actualizado correctamente.')
        return redirect(url_for('ticket_bp.editar_ticket', ticket_id=ticket.id))

    return render_template(
        'editar_ticket.html',
        ticket=ticket,
        clientes=clientes,
        ingenieros=ingenieros,
        historial=historial
    )
