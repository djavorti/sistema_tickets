import csv
from app import create_app
from app.extensions import db
from app.models.usuario import Usuario

def importar_usuarios(ruta_csv):
    with open(ruta_csv, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row = {k.strip(): v.strip() for k, v in row.items()}

            # Asegurarse de que no se duplique el usuario
            if Usuario.query.filter_by(usuario=row['usuario']).first():
                print(f"» Usuario '{row['usuario']}' ya existe – se omite")
                continue

            usuario = Usuario(
                id=int(row['id']),
                nombre=row['nombre'],
                apellido=row['apellido'],
                usuario=row['usuario'],
                tipo=row['tipo'] or 'ingeniero'
            )
            usuario.set_password(row['password'])
            db.session.add(usuario)

        db.session.commit()
        print("✔ Importación de usuarios finalizada.")

# --- ESTE BLOQUE ES EL MÁS IMPORTANTE ---
if __name__ == '__main__':
    app = create_app()
    with app.app_context():  # <- Esto asegura que funcione la base de datos
        importar_usuarios("app/static/usuarios.csv")