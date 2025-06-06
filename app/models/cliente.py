from app.extensions import db

class Cliente(db.Model):
    __tablename__ = 'clientes'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.Text, nullable=True)  # Nuevo campo

    tickets = db.relationship('Ticket', back_populates='cliente', lazy=True)

    def __repr__(self):
        return f'<Cliente {self.nombre}>'