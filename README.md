pip install -r requirements.txt

rm app.db
rm -rf migrations/
flask db init
flask db migrate -m "Migración inicial"
flask db upgrade
python -m app.scripts.importar_usuarios
python -m app.scripts.importar_clientes
python -m app.scripts.actualizar_clientes
flash run --host=0.0.0.0 --port=5000