from app.extensions import db
from datetime import datetime
from app.utils import zona_ecuador

class SesionActiva(db.Model):
    __tablename__ = 'sesiones_activas'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False, unique=True)
    fecha_inicio = db.Column(db.DateTime, default=datetime.now(zona_ecuador))
    ultima_actividad = db.Column(db.DateTime, default=datetime.now(zona_ecuador))  # NUEVO CAMPO

    usuario = db.relationship("Usuario", backref="sesion_activa", uselist=False)