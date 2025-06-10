import csv
import re
import difflib
from collections import defaultdict
from app.extensions import db
from app.models.cliente import Cliente
from app import create_app

def normalizar_nombre(nombre):
    nombre = nombre.upper().strip()
    nombre = re.sub(r'\s*\([A-Z0-9\s]+\)\s*$', '', nombre)
    nombre = re.sub(r'\s+', ' ', nombre)
    return nombre

def es_nombre_similar(nombre1, nombre2, umbral=0.85):
    s1 = normalizar_nombre(nombre1)
    s2 = normalizar_nombre(nombre2)
    # Considerar iguales si uno es prefijo del otro (por ejemplo: SEMEDIC y SEMEDIC/SAVERCORP)
    if s1 == s2 or s1 in s2 or s2 in s1:
        return True
    ratio = difflib.SequenceMatcher(None, s1, s2).ratio()
    return ratio >= umbral

def importar_clientes(csv_path):
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        nombres_en_csv = set()
        csv_data = []

        for row in reader:
            nombre = row['nombre'].strip()
            correo = row['correo'].strip()
            nombres_en_csv.add(nombre)
            csv_data.append((nombre, correo))

        todos_los_clientes = Cliente.query.all()
        nombres_csv_usados = set()
        renombrados = 0
        eliminados = 0
        duplicados_eliminados = 0
        creados = 0

        # Paso 1: Renombrar clientes existentes si hay nombre similar en CSV
        for cliente in todos_los_clientes:
            if cliente.nombre not in nombres_en_csv:
                similar_en_csv = None
                for nombre_csv, correo_csv in csv_data:
                    if nombre_csv in nombres_csv_usados:
                        continue
                    if es_nombre_similar(cliente.nombre, nombre_csv):
                        similar_en_csv = (nombre_csv, correo_csv)
                        break
                if similar_en_csv:
                    nuevo_nombre, nuevo_correo = similar_en_csv
                    ya_existe = Cliente.query.filter_by(nombre=nuevo_nombre).first()
                    if ya_existe and ya_existe.id != cliente.id:
                        print(f"No se puede renombrar '{cliente.nombre}' a '{nuevo_nombre}' porque ya existe otro cliente con ese nombre.")
                        continue
                    print(f"Renombrando '{cliente.nombre}' a '{nuevo_nombre}'.")
                    cliente.nombre = nuevo_nombre
                    cliente.email = nuevo_correo
                    nombres_csv_usados.add(nuevo_nombre)
                    renombrados += 1

        db.session.commit()

        # Paso 2: Crear nuevos clientes que están en CSV pero no en la BD
        for nombre_csv, correo_csv in csv_data:
            if nombre_csv in nombres_csv_usados:
                continue
            cliente_existente = Cliente.query.filter_by(nombre=nombre_csv).first()
            if cliente_existente:
                if cliente_existente.email != correo_csv:
                    cliente_existente.email = correo_csv
                    print(f"Cliente '{nombre_csv}' actualizado con nuevo correo.")
            else:
                nuevo_cliente = Cliente(nombre=nombre_csv, email=correo_csv)
                db.session.add(nuevo_cliente)
                creados += 1
                print(f"Cliente '{nombre_csv}' agregado.")

        db.session.commit()

        # Paso 3: Eliminar clientes que ya no están en el CSV y no fueron renombrados
        for cliente in Cliente.query.all():
            if cliente.nombre not in nombres_en_csv and cliente.nombre not in nombres_csv_usados:
                if cliente.tickets:
                    print(f"No se puede eliminar '{cliente.nombre}' porque tiene tickets asociados.")
                else:
                    db.session.delete(cliente)
                    eliminados += 1
                    print(f"Cliente '{cliente.nombre}' eliminado (no está en CSV).")

        db.session.commit()

        # Paso 4: Eliminar duplicados (mantener el más antiguo o el que tenga tickets)
        print("Revisando duplicados...")
        clientes_por_nombre = defaultdict(list)
        for cliente in Cliente.query.all():
            clientes_por_nombre[cliente.nombre].append(cliente)

        for nombre, lista in clientes_por_nombre.items():
            if len(lista) > 1:
                lista.sort(key=lambda c: c.id)
                a_conservar = None
                for cliente in lista:
                    if cliente.tickets:
                        a_conservar = cliente
                        break
                if not a_conservar:
                    a_conservar = lista[0]
                for cliente in lista:
                    if cliente.id != a_conservar.id:
                        if cliente.tickets:
                            print(f"OJO: Cliente duplicado '{cliente.nombre}' con ID {cliente.id} tiene tickets. No se eliminará.")
                        else:
                            db.session.delete(cliente)
                            duplicados_eliminados += 1
                            print(f"Cliente duplicado '{cliente.nombre}' (ID {cliente.id}) eliminado.")

        db.session.commit()

        print(f"Importación completa. {creados} creados, {renombrados} renombrados, {eliminados} eliminados, {duplicados_eliminados} duplicados eliminados.")

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        importar_clientes("app/static/clientes.csv")