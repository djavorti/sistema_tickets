from app.extensions import db
from datetime import datetime

from app.extensions import db
from datetime import datetime

class Ticket(db.Model):
    __tablename__ = 'tickets'

    id = db.Column(db.String(20), primary_key=True)
    status = db.Column(db.String(50), nullable=False, default="Pendiente")
    tipo = db.Column(db.String(50))
    medio = db.Column(db.String(50))
    pid = db.Column(db.String(50))
    asunto = db.Column(db.String(100))
    detalle = db.Column(db.Text)
    sede = db.Column(db.String(100))

    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'))
    cliente = db.relationship('Cliente', back_populates='tickets')

    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id], back_populates='tickets')

    asignado_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    asignado = db.relationship('Usuario', foreign_keys=[asignado_id])

    historial = db.relationship('Historial', back_populates='ticket')

    fecha_inicio = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_fin = db.Column(db.DateTime, nullable=True)
    actualizacion = db.Column(db.Text)