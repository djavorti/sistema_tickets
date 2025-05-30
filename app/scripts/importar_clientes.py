import csv
from app.extensions import db
from app.models.cliente import Cliente
from app import create_app

def importar_clientes(csv_path):
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            # Verificamos si ya existe un cliente con ese nombre para evitar duplicados
            if Cliente.query.filter_by(nombre=row['nombre']).first():
                print(f"Cliente '{row['nombre']}' ya existe. Saltando.")
                continue

            cliente = Cliente(nombre=row['nombre'])
            db.session.add(cliente)
        
        db.session.commit()
        print("Importación de clientes completada.")

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        importar_clientes("app/static/clientes.csv")