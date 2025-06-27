from app import create_app, db
from app.models.sesion_activa import SesionActiva
from app.models.usuario import Usuario
from app.routes.auth_routes import reasignar_tickets_pendientes_al_turno
from app.utils import zona_ecuador
from datetime import datetime, timedelta

app = create_app()
with app.app_context():
    ahora = datetime.now(zona_ecuador)
    sesiones = SesionActiva.query.all()
    for sesion in sesiones:
        ultima = sesion.ultima_actividad
        if ultima and (ultima.tzinfo is None):
            ultima = zona_ecuador.localize(ultima)
        usuario = Usuario.query.get(sesion.usuario_id)
        if (
            usuario
            and usuario.tipo == 'ingeniero'
            and ultima
            and ahora - ultima > timedelta(hours=4)
        ):
            reasignar_tickets_pendientes_al_turno(usuario)
            db.session.delete(sesion)
    db.session.commit()
    print("Sesiones inactivas de ingenieros eliminadas.")

#    chmod +x app/scripts/limpiar_sesiones.py
#    python -m app.scripts.limpiar_sesiones