from app.extensions import db
from datetime import datetime

class Historial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    cambio = db.Column(db.Text)
    ticket = db.relationship('Ticket', back_populates='historial')
    usuario = db.relationship('Usuario', back_populates='historial')
    fecha_hora = db.Column(db.DateTime, default=datetime.utcnow)