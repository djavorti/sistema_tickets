import csv
import re
from app.extensions import db
from app.models.cliente import Cliente
from app import create_app

def normalize_text(s):
    s = (s or '').upper()
    s = re.sub(r'[ÁÀÂÄ]', 'A', s)
    s = re.sub(r'[ÉÈÊË]', 'E', s)
    s = re.sub(r'[ÍÌÎÏ]', 'I', s)
    s = re.sub(r'[ÓÒÔÖ]', 'O', s)
    s = re.sub(r'[ÚÙÛÜ]', 'U', s)
    s = re.sub(r'[^A-Z0-9\s]', ' ', s)
    s = re.sub(r'\d+', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

COMMON_WORDS = set([
    'SAN', 'JUAN', 'GESTION', 'HACIENDA', 'HCDA', 'LA', 'UN', 'PLATAFORMA', 'ABRIL', 'VINCES', 'VI'
])

def get_words(s):
    return [w for w in normalize_text(s).split() if len(w) >= 2 and w not in COMMON_WORDS]

def cliente_match_score(nombre_db, nombre_csv):
    db_words = get_words(nombre_db)
    csv_words = get_words(nombre_csv)
    score = 0
    for db_word in db_words:
        if db_word in csv_words:
            score += 10
        else:
            for csv_word in csv_words:
                if db_word in csv_word or csv_word in db_word:
                    score += 5
    return score

def buscar_cliente_existente_o_similar(nombre_csv, clientes_db, min_score=10):
    nombre_csv_norm = normalize_text(nombre_csv)
    # 1. Exacto
    for cliente in clientes_db:
        if normalize_text(cliente.nombre) == nombre_csv_norm:
            return cliente
    # 2. Inclusión (más robusto)
    for cliente in clientes_db:
        nombre_db_norm = normalize_text(cliente.nombre)
        if nombre_db_norm in nombre_csv_norm or nombre_csv_norm in nombre_db_norm:
            return cliente
    # 3. Score
    best = None
    best_score = 0
    for cliente in clientes_db:
        score = cliente_match_score(cliente.nombre, nombre_csv)
        if score > best_score:
            best_score = score
            best = cliente
    return best if best_score >= min_score else None

def importar_clientes(csv_path):
    # ...existing code...
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        # Asegura que siempre sea string, incluso si falta la columna o el valor es None
        csv_data = [
            (
                row['nombre'].strip(),
                row['correo'].strip(),
                (row.get('nota') or '').strip()
            )
            for row in reader
        ]
# ...existing code...
    renombrados = 0
    creados = 0
    eliminados = 0
    duplicados_eliminados = 0
    nombres_en_csv = set(nombre for nombre, _, _ in csv_data)
    ids_renombrados = set()

    # Paso 1: Renombrar o actualizar clientes existentes si hay nombre igual o similar en CSV
    for nombre_csv, correo_csv, nota_csv in csv_data:
        clientes_db = Cliente.query.all()
        cliente_existente = buscar_cliente_existente_o_similar(nombre_csv, clientes_db)
        if cliente_existente:
            if normalize_text(cliente_existente.nombre) != normalize_text(nombre_csv):
                print(f"Renombrando '{cliente_existente.nombre}' a '{nombre_csv}'.")
                cliente_existente.nombre = nombre_csv
                renombrados += 1
            # Actualizar correo si cambió
            if (cliente_existente.email or '').strip() != correo_csv:
                print(f"Actualizando correo de '{nombre_csv}' en DB: '{cliente_existente.email}' -> '{correo_csv}'")
                cliente_existente.email = correo_csv
            # Actualizar nota si cambió
            if hasattr(cliente_existente, "nota") and (cliente_existente.nota or '').strip() != (nota_csv or '').strip():
                print(f"Actualizando nota de '{nombre_csv}' en DB.")
                cliente_existente.nota = nota_csv
            ids_renombrados.add(cliente_existente.id)
            db.session.commit()
        else:
            # Solo crear si no existe ni similar
            nuevo_cliente = Cliente(nombre=nombre_csv, email=correo_csv)
            if hasattr(nuevo_cliente, "nota"):
                nuevo_cliente.nota = nota_csv
            db.session.add(nuevo_cliente)
            creados += 1
            print(f"Cliente '{nombre_csv}' agregado.")
            db.session.commit()

    # Paso 2: Eliminar clientes que ya no están en el CSV (pero NO si hay uno similar en el CSV o fue renombrado)
    clientes_db = Cliente.query.all()
    for cliente in clientes_db:
        if cliente.id in ids_renombrados:
            continue
        existe_en_csv = False
        for nombre_csv in nombres_en_csv:
            if (
                normalize_text(cliente.nombre) == normalize_text(nombre_csv)
                or normalize_text(cliente.nombre) in normalize_text(nombre_csv)
                or normalize_text(nombre_csv) in normalize_text(cliente.nombre)
                or cliente_match_score(cliente.nombre, nombre_csv) >= 10
                or cliente_match_score(nombre_csv, cliente.nombre) >= 10
            ):
                existe_en_csv = True
                break
        if existe_en_csv:
            continue
        if hasattr(cliente, "tickets") and cliente.tickets:
            print(f"No se puede eliminar '{cliente.nombre}' porque tiene tickets asociados.")
        else:
            db.session.delete(cliente)
            eliminados += 1
            print(f"Cliente '{cliente.nombre}' eliminado (no está en CSV).")
    db.session.commit()

    # Paso 3: Eliminar duplicados (mantener el más antiguo o el que tenga tickets)
    from collections import defaultdict
    clientes_db = Cliente.query.all()
    clientes_por_nombre = defaultdict(list)
    for cliente in clientes_db:
        clientes_por_nombre[normalize_text(cliente.nombre)].append(cliente)

    for nombre_norm, lista in clientes_por_nombre.items():
        if len(lista) > 1:
            lista.sort(key=lambda c: c.id)
            a_conservar = None
            for cliente in lista:
                if hasattr(cliente, "tickets") and cliente.tickets:
                    a_conservar = cliente
                    break
            if not a_conservar:
                a_conservar = lista[0]
            for cliente in lista:
                if cliente.id != a_conservar.id:
                    if hasattr(cliente, "tickets") and cliente.tickets:
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