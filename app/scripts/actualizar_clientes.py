import csv
import re
from app.extensions import db
from app.models.cliente import Cliente
from app import create_app

def tiene_palabra_comun_de_4_letras_o_mas(nombre1, nombre2):
    palabras1 = set(w.lower() for w in re.findall(r'\b\w{4,}\b', nombre1))
    palabras2 = set(w.lower() for w in re.findall(r'\b\w{4,}\b', nombre2))
    return len(palabras1 & palabras2) > 0

def importar_clientes(csv_path):
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')  # ; como delimitador

        nombres_en_csv = set()
        csv_data = []

        for row in reader:
            nombre = row['nombre'].strip()
            correo = row['correo'].strip()
            nombres_en_csv.add(nombre)
            csv_data.append((nombre, correo))

        # Paso 1: agregar o actualizar
        for nombre_csv, correo_csv in csv_data:
            cliente_existente = Cliente.query.filter_by(nombre=nombre_csv).first()
            if cliente_existente:
                if cliente_existente.email != correo_csv:
                    cliente_existente.email = correo_csv
                    print(f"Cliente '{nombre_csv}' actualizado con nuevo correo.")
            else:
                nuevo_cliente = Cliente(nombre=nombre_csv, email=correo_csv)
                db.session.add(nuevo_cliente)
                print(f"Cliente '{nombre_csv}' agregado.")

        db.session.commit()

        # Paso 2: eliminar o renombrar
        todos_los_clientes = Cliente.query.all()
        eliminados = 0
        renombrados = 0
        nombres_csv_usados = set()

        for cliente in todos_los_clientes:
            if cliente.nombre not in nombres_en_csv:
                # Intentar encontrar un nombre similar
                similar_en_csv = None
                for nombre_csv, correo_csv in csv_data:
                    if nombre_csv in nombres_csv_usados:
                        continue  # Ya fue usado para renombrar otro cliente

                    if tiene_palabra_comun_de_4_letras_o_mas(cliente.nombre, nombre_csv):
                        similar_en_csv = (nombre_csv, correo_csv)
                        nombres_csv_usados.add(nombre_csv)
                        break

                if similar_en_csv:
                    nuevo_nombre, nuevo_correo = similar_en_csv
                    print(f"Renombrando '{cliente.nombre}' a '{nuevo_nombre}'.")
                    cliente.nombre = nuevo_nombre
                    cliente.email = nuevo_correo
                    renombrados += 1
                else:
                    if cliente.tickets:
                        print(f"No se puede eliminar '{cliente.nombre}' porque tiene tickets asociados.")
                    else:
                        db.session.delete(cliente)
                        eliminados += 1
                        print(f"Cliente '{cliente.nombre}' eliminado (no está en CSV).")

        db.session.commit()
        print(f"Importación completa. {renombrados} renombrados, {eliminados} eliminados.")

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        importar_clientes("app/static/clientes.csv")