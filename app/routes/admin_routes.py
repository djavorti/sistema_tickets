from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.extensions import db
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.models.configuracion import Configuracion

admin_bp = Blueprint('admin_bp', __name__)

# Mapeo de entidades para facilitar el manejo dinámico
ENTITY_MAP = {
    'usuario': Usuario,
    'cliente': Cliente
}

@admin_bp.route('/admin')
def admin_dashboard():
    # Verificar si el usuario tiene permisos de administrador
    if 'usuario' not in session:
        return redirect(url_for('auth_bp.login'))

    usuario_actual = Usuario.query.filter_by(usuario=session['usuario']).first()
    if not usuario_actual or usuario_actual.tipo not in ['admin', 'jefe']:
        flash("Access denied. You do not have permission to view this page.", "danger")
        return redirect(url_for('dashboard_bp.dashboard'))

    usuarios = Usuario.query.filter_by(is_deleted=False).all()  # Filtrar usuarios no eliminados
    clientes = Cliente.query.filter_by(is_deleted=False).all()  # Filtrar clientes no eliminados

    return render_template('admin_dashboard.html', usuarios=usuarios, clientes=clientes)

@admin_bp.route('/admin/create/<entity_type>', methods=['POST'])
def create_entity(entity_type):
    entity_class = ENTITY_MAP.get(entity_type)
    if not entity_class:
        flash("Tipo de entidad no válido.", "danger")
        return redirect(url_for('admin_bp.admin_dashboard'))

    entity = entity_class()
    for column in entity_class.__table__.columns:
        if column.name in request.form and column.name != 'id' and column.name != 'de_turno':
            setattr(entity, column.name, request.form[column.name])
    if entity_type == 'usuario' and 'password' in request.form:
        entity.set_password(request.form['password'])

    db.session.add(entity)
    db.session.commit()
    flash(f"{entity_type.capitalize()} creado correctamente.", "success")
    return redirect(url_for('admin_bp.admin_dashboard'))

@admin_bp.route('/admin/edit/<entity_type>/<int:entity_id>', methods=['GET', 'POST'])
def edit_entity(entity_type, entity_id):
    entity_class = ENTITY_MAP.get(entity_type)
    if not entity_class:
        flash("Tipo de entidad no válido.", "danger")
        return redirect(url_for('admin_bp.admin_dashboard'))

    entity = entity_class.query.get(entity_id)
    if not entity:
        flash(f"{entity_type.capitalize()} no encontrado.", "danger")
        return redirect(url_for('admin_bp.admin_dashboard'))

    # Bloquear edición del usuario logueado
    if entity_type == 'usuario' and entity.usuario == session.get('usuario'):
        flash("No puedes editar tu propio usuario.", "danger")
        return redirect(url_for('admin_bp.admin_dashboard'))

    if request.method == 'POST':
        for column in entity_class.__table__.columns:
            if column.name in request.form and column.name != 'id' and column.name != 'de_turno':
                setattr(entity, column.name, request.form[column.name])
        if entity_type == 'usuario' and 'password' in request.form and request.form['password']:
            entity.set_password(request.form['password'])

        db.session.commit()
        flash(f"{entity_type.capitalize()} actualizado correctamente.", "success")
        return redirect(url_for('admin_bp.admin_dashboard'))

    fields = [
        {
            'name': column.name,
            'label': column.name.capitalize(),
            'type': 'text' if column.type.python_type == str else 'number',
            'value': getattr(entity, column.name),
            'placeholder': column.name.capitalize(),
            'required': not column.nullable
        }
        for column in entity_class.__table__.columns if column.name != 'password_hash' and column.name != 'de_turno'
    ]

    return render_template('edit_entity.html', entity=entity, entity_type=entity_type, fields=fields)


@admin_bp.route('/admin/delete/<entity_type>/<int:entity_id>', methods=['POST'])
def delete_entity(entity_type, entity_id):
    entity_class = ENTITY_MAP.get(entity_type)
    if not entity_class:
        flash("Tipo de entidad no válido.", "danger")
        return redirect(url_for('admin_bp.admin_dashboard'))

    entity = entity_class.query.get(entity_id)
    if not entity:
        flash(f"{entity_type.capitalize()} no encontrado.", "danger")
        return redirect(url_for('admin_bp.admin_dashboard'))

    # Bloquear eliminación del usuario logueado
    if entity_type == 'usuario' and entity.usuario == session.get('usuario'):
        flash("No puedes eliminar tu propio usuario.", "danger")
        return redirect(url_for('admin_bp.admin_dashboard'))

    # Marcar como eliminado
    entity.is_deleted = True
    db.session.commit()
    flash(f"{entity_type.capitalize()} eliminado correctamente.", "success")
    return redirect(url_for('admin_bp.admin_dashboard'))

@admin_bp.route('/admin/configuracion', methods=['POST'])
def actualizar_configuracion():
    clave = request.form.get('clave')
    valor = request.form.get('valor')

    print(f"Clave: {clave}, Valor: {valor}")  # Depuración

    configuracion = Configuracion.query.filter_by(clave=clave).first()
    if configuracion:
        configuracion.valor = valor
        print(f"Actualizando configuración: {configuracion.clave} = {configuracion.valor}")  # Depuración
    else:
        configuracion = Configuracion(clave=clave, valor=valor)
        db.session.add(configuracion)
        print(f"Creando nueva configuración: {configuracion.clave} = {configuracion.valor}")  # Depuración

    db.session.commit()
    flash("Configuración actualizada correctamente.", "success")
    return redirect(url_for('admin_bp.admin_dashboard'))

@admin_bp.route('/admin/empleado_mes', methods=['POST'])
def actualizar_empleado_mes():
    nombre = request.form.get('nombre')
    foto = request.form.get('foto')

    # Actualizar el nombre
    configuracion_nombre = Configuracion.query.filter_by(clave='empleado_mes_nombre').first()
    if configuracion_nombre:
        configuracion_nombre.valor = nombre
    else:
        configuracion_nombre = Configuracion(clave='empleado_mes_nombre', valor=nombre)
        db.session.add(configuracion_nombre)

    # Actualizar la foto
    configuracion_foto = Configuracion.query.filter_by(clave='empleado_mes_foto').first()
    if configuracion_foto:
        configuracion_foto.valor = foto
    else:
        configuracion_foto = Configuracion(clave='empleado_mes_foto', valor=foto)
        db.session.add(configuracion_foto)

    db.session.commit()
    flash("Empleado del Mes actualizado correctamente.", "success")
    return redirect(url_for('admin_bp.admin_dashboard'))