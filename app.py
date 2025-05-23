from flask import Flask, render_template, request, redirect, url_for, jsonify
import mysql.connector
from datetime import datetime
import os

app = Flask(__name__)

# ------------------ CONFIGURACIÓN BD ------------------

def conectar():
    return mysql.connector.connect(
        host="shortline.proxy.rlwy.net",
        user="root",
        password="LqQjAVIFKbBYdsBcYNRcvXWskkcdYpMl",
        database="railway",
        port=50162
    )

# ------------------ RUTAS ------------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/buscar_docente')
def buscar_docente():
    query = request.args.get('q', '').lower()
    conn = conectar()
    cursor = conn.cursor(dictionary=True)
    
    if query:
        cursor.execute("""
            SELECT d.*, 
                   COALESCE(ROUND(AVG(r.valor_calificacion), 1), 'Sin calificaciones') AS promedio
            FROM Docentes d
            LEFT JOIN resenas r ON d.id_docente = r.id_docente
            WHERE LOWER(d.nombre) LIKE %s OR LOWER(d.materias) LIKE %s
            GROUP BY d.id_docente
        """, ('%' + query + '%', '%' + query + '%'))
    else:
        cursor.execute("""
            SELECT d.*, 
                   COALESCE(ROUND(AVG(r.valor_calificacion), 1), 'Sin calificaciones') AS promedio
            FROM Docentes d
            LEFT JOIN resenas r ON d.id_docente = r.id_docente
            GROUP BY d.id_docente
        """)
    
    docentes = cursor.fetchall()
    conn.close()

    return jsonify(docentes)


import traceback

@app.route('/docentes/<int:id_docente>')
def detalle_docente(id_docente):
    try:
        conn = conectar()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM Docentes WHERE id_docente = %s", (id_docente,))
        docente = cursor.fetchone()
        if not docente:
            return "Docente no encontrado", 404

        cursor.execute("""
            SELECT id_resena, resena, fecha, valor_calificacion
            FROM resenas
            WHERE id_docente = %s
            ORDER BY fecha DESC
        """, (id_docente,))
        resenas = cursor.fetchall()

        for r in resenas:
            cursor.execute("""
                SELECT id_comentario, comentario, fecha
                FROM Comentarios
                WHERE id_resena = %s
                ORDER BY fecha ASC
            """, (r['id_resena'],))
            r['comentarios'] = cursor.fetchall()

        calificaciones = []
        for r in resenas:
            try:
                calificaciones.append(float(r['valor_calificacion']))
            except (ValueError, TypeError):
                pass

        promedio = round(sum(calificaciones) / len(calificaciones), 1) if calificaciones else None

        conn.close()

        return render_template('docente.html', docente=docente, promedio=promedio, resenas=resenas)

    except Exception as e:
        traceback.print_exc()
        return f"Error del servidor: {str(e)}", 500


@app.route('/formularios', methods=['GET', 'POST'])
def formularios():
    conn = conectar()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        id_docente = request.form.get('id_docente')
        calificacion = request.form.get('calificacion')
        resena = request.form.get('resena')

        if not id_docente or not calificacion or not resena:
            conn.close()
            return "Faltan datos en el formulario", 400

        try:
            calificacion = float(calificacion)
            id_docente = int(id_docente)

            cursor.execute("""
                INSERT INTO resenas (id_docente, resena, fecha, valor_calificacion)
                VALUES (%s, %s, %s, %s)
            """, (id_docente, resena, datetime.now(), calificacion))
            conn.commit()

        except Exception as e:
            conn.rollback()
            conn.close()
            return f"Error al guardar los datos: {e}", 500

        conn.close()
        return redirect(url_for('detalle_docente', id_docente=id_docente))

    # Método GET
    id_docente = request.args.get('id_docente')
    docente = None
    if id_docente:
        cursor.execute("SELECT * FROM Docentes WHERE id_docente = %s", (id_docente,))
        docente = cursor.fetchone()

    conn.close()
    return render_template('formulario.html', docente=docente)

@app.route('/comentar_resena/<int:id_resena>', methods=['POST'])
def comentar_resena(id_resena):
    comentario = request.form.get('comentario')

    if not comentario or len(comentario.strip()) < 3:
        return "Comentario no válido", 400

    try:
        conn = conectar()
        cursor = conn.cursor()

        # Validar que la reseña existe
        cursor.execute("SELECT id_docente FROM resenas WHERE id_resena = %s", (id_resena,))
        resultado = cursor.fetchone()
        if not resultado:
            conn.close()
            return "Reseña no encontrada", 404

        id_docente = resultado[0]

        # Insertar el comentario
        cursor.execute("""
            INSERT INTO Comentarios (id_resena, comentario, fecha)
            VALUES (%s, %s, NOW())
        """, (id_resena, comentario))

        conn.commit()

    except Exception as e:
        conn.rollback()
        return f"Error al insertar el comentario: {e}", 500

    finally:
        conn.close()

    return redirect(url_for('detalle_docente', id_docente=id_docente))


# ------------------ MAIN ------------------

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
