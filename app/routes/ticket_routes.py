# File: app/routes/ticket_routes.py
# app/routes/ticket_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime
from app.extensions import db
from app.models import Ticket, Usuario, Cliente, Historial
from app.utils import zona_ecuador
from sqlalchemy import extract
import urllib.parse

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
        base_id = hoy.strftime('%Y%m%d')
        # Contar tickets del día actual para el sufijo
        tickets_hoy = Ticket.query.filter(
            extract('year', Ticket.fecha_inicio) == hoy.year,
            extract('month', Ticket.fecha_inicio) == hoy.month,
            extract('day', Ticket.fecha_inicio) == hoy.day
        ).count()
        # Generar el nuevo ID basado en la cuenta del día
        nuevo_id_tt = f"{base_id}-{tickets_hoy + 1:03}"
        # --- Fin Generación de ID en POST ---


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

        flash('Ticket creado exitosamente', 'success')

        # El POST siempre redirige al dashboard
        return redirect(url_for('dashboard_bp.dashboard'))

    # GET: preparar formulario
    clientes = Cliente.query.all()
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
    id_tt_provisional = f"{base_id}-{tickets_hoy_estimado + 1:03}"


    return render_template(
        'crear_ticket.html',
        id_tt=id_tt_provisional, # Pasar el ID provisional al template
        status="Pendiente",
        fecha_inicio=hoy.strftime('%Y-%m-%d %H:%M:%S'), # Pasar fecha/hora actual para display
        clientes=clientes, # Pasamos la lista de objetos Cliente
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
    cc_emails = "tecoymcorpcnoc@claro.com.ec,soporte_empresas@claro.com.ec"

    # Codificar asunto, cuerpo y CC para la URL usando urllib.parse.quote
    encoded_subject = urllib.parse.quote(asunto) # Usar el asunto tal como llega
    encoded_body = urllib.parse.quote(email_body)
    encoded_cc = urllib.parse.quote(cc_emails)

    # Construir la URL mailto con CC
    mailto_url = f"mailto:{cliente_emails}?subject={encoded_subject}&body={encoded_body}&cc={encoded_cc}"

    # Devolver la URL mailto como respuesta JSON
    return jsonify({'mailto_url': mailto_url})

# --- Fin Nueva ruta ---


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
        nuevo_detalle = request.form.get('detalle', '').strip() # Usar .get() para opcional
        nuevo_pid = request.form.get('pid', '').strip() # Usar .get() para opcional
        nuevo_sede = request.form.get('sede', '').strip() # Usar .get() para opcional
        nuevo_cliente = Cliente.query.filter_by(nombre=request.form['cliente']).first()
        asignado_id = request.form.get('asignado')
        if asignado_id:
            nuevo_asignado = Usuario.query.get(asignado_id)
        else:
            nuevo_asignado = ticket.asignado  # Mantener el asignado anterior si no viene en el formulario
        nuevo_actualizacion = request.form.get('actualizacion', '').strip() # Usar .get() para opcional
        nuevo_tt_remedy = request.form.get('tt_remedy', '').strip()


        # Comparar campos y registrar cambios
        if nuevo_status != anterior_status:
            # Si cambia a 'Terminado', registrar fecha de fin
            if nuevo_status.lower() == "terminado":
                ticket.fecha_fin = datetime.now(zona_ecuador)
            # Si cambia de 'Terminado' a otro estado, eliminar fecha_fin
            elif anterior_status.lower() == "terminado":
                 ticket.fecha_fin = None
            cambios.append(f"Estado: '{anterior_status}' → '{nuevo_status}'")
            ticket.status = nuevo_status

        if nuevo_tipo != anterior_tipo:
            cambios.append(f"Tipo: '{anterior_tipo}' → '{nuevo_tipo}'")
            ticket.tipo = nuevo_tipo

        if nuevo_medio != anterior_medio:
            cambios.append(f"Medio: '{anterior_medio}' → '{nuevo_medio}'")
            ticket.medio = nuevo_medio

        # Comparar campos opcionales, solo si el nuevo valor es diferente del anterior
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

        # Solo registrar actualización si el texto ha cambiado y no está vacío
        if nuevo_actualizacion and nuevo_actualizacion != anterior_actualizacion:
             # Si hay cambios en otros campos, la actualización se añade como un cambio más.
             # Si solo cambia la actualización, se registra solo la actualización.
             if not cambios: # Si no hay otros cambios, solo registramos la actualización
                 cambios.append(f"Actualización: {nuevo_actualizacion}")
             else: # Si hay otros cambios, añadimos la actualización al final de la lista de cambios
                 cambios.append(f"Nueva Actualización: {nuevo_actualizacion}")
             ticket.actualizacion = nuevo_actualizacion # Actualizar el campo en el ticket


        # Registrar historial si hay cambios
        if cambios:
            nuevo_historial = Historial(
                ticket_id=ticket.id,
                usuario=Usuario.query.filter_by(usuario=session['usuario']).first(),
                cambio="\n".join(cambios),
                fecha_hora=datetime.now(zona_ecuador)
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
