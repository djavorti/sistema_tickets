from flask import Blueprint, render_template, request, session, redirect, url_for
from app.models import Cliente

programado_bp = Blueprint('programado_bp', __name__)

@programado_bp.route('/trabajos_programados', methods=['GET', 'POST'])
def programado():
    if 'usuario' not in session:
        return redirect(url_for('auth_bp.login'))

    clientes = Cliente.query.all()
    correos_clientes = {c.nombre: c.email for c in clientes}

    if request.method == 'POST':
        # Recoge los datos del formulario
        asunto=request.form.get('asunto')
        crq = request.form.get('crq')
        observacion = request.form.get('observacion')
        fecha_inicio = request.form.get('fecha_inicio')
        fecha_fin = request.form.get('fecha_fin')
        duracion = request.form.get('duracion')
        indisponibilidad = request.form.get('indisponibilidad')
        servicios = request.form.get('servicios')

        # Renderiza la tabla de clientes y servicios
        return render_template(
            'trabajos_programados.html',
            clientes=clientes,
            correos_clientes=correos_clientes,
            asunto=asunto,
            crq=crq,
            observacion=observacion,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            duracion=duracion,
            indisponibilidad=indisponibilidad,
            servicios=servicios,
            mostrar_tabla=True
        )

    return render_template('trabajos_programados.html', clientes=clientes, correos_clientes=correos_clientes, mostrar_tabla=False)