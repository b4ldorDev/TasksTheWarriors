from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tu-clave-secreta-aqui'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tareas.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Modelos de base de datos
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    matricula = db.Column(db.String(20), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    es_admin = db.Column(db.Boolean, default=False)
    tareas = db.relationship('TareaUsuario', backref='usuario', lazy=True)

class Tarea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_limite = db.Column(db.DateTime, nullable=True)
    asignaciones = db.relationship('TareaUsuario', backref='tarea', lazy=True)

class TareaUsuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    tarea_id = db.Column(db.Integer, db.ForeignKey('tarea.id'), nullable=False)
    completada = db.Column(db.Boolean, default=False)
    fecha_completada = db.Column(db.DateTime, nullable=True)

# Crear tablas y datos iniciales
def init_db():
    with app.app_context():
        db.create_all()
        
        # Crear usuario admin si no existe
        if not Usuario.query.filter_by(matricula='ADMIN').first():
            admin = Usuario(
                matricula='ADMIN',
                nombre='Profesor Administrador',
                password_hash=generate_password_hash('admin123'),
                es_admin=True
            )
            db.session.add(admin)
        
        # Crear estudiantes de ejemplo si no existen
        estudiantes_ejemplo = [
            ('A0100200', 'Juan Pérez'),
            ('A0100201', 'María García'),
            ('A0100202', 'Carlos López'),
            ('A0100203', 'Ana Martínez'),
            ('A0100204', 'Luis González')
        ]
        
        for matricula, nombre in estudiantes_ejemplo:
            if not Usuario.query.filter_by(matricula=matricula).first():
                estudiante = Usuario(
                    matricula=matricula,
                    nombre=nombre,
                    password_hash=generate_password_hash(matricula.lower()),  # password = matrícula en minúsculas
                    es_admin=False
                )
                db.session.add(estudiante)
        
        db.session.commit()

# Rutas
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    matricula = request.form['matricula'].upper()
    password = request.form['password']
    
    usuario = Usuario.query.filter_by(matricula=matricula).first()
    
    if usuario and check_password_hash(usuario.password_hash, password):
        session['user_id'] = usuario.id
        session['es_admin'] = usuario.es_admin
        session['nombre'] = usuario.nombre
        return redirect(url_for('dashboard'))
    else:
        flash('Matrícula o contraseña incorrectos')
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    if session['es_admin']:
        return redirect(url_for('admin_dashboard'))
    else:
        return redirect(url_for('student_dashboard'))

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session or not session['es_admin']:
        return redirect(url_for('index'))
    
    tareas = Tarea.query.all()
    estudiantes = Usuario.query.filter_by(es_admin=False).all()
    
    # Estadísticas por tarea
    stats = []
    for tarea in tareas:
        total_asignados = TareaUsuario.query.filter_by(tarea_id=tarea.id).count()
        completadas = TareaUsuario.query.filter_by(tarea_id=tarea.id, completada=True).count()
        stats.append({
            'tarea': tarea,
            'total_asignados': total_asignados,
            'completadas': completadas,
            'porcentaje': (completadas/total_asignados*100) if total_asignados > 0 else 0
        })
    
    return render_template('admin_dashboard.html', stats=stats, estudiantes=estudiantes)

@app.route('/student/dashboard')
def student_dashboard():
    if 'user_id' not in session or session['es_admin']:
        return redirect(url_for('index'))
    
    user_id = session['user_id']
    mis_tareas = db.session.query(TareaUsuario, Tarea).join(Tarea).filter(TareaUsuario.usuario_id == user_id).all()
    
    return render_template('student_dashboard.html', mis_tareas=mis_tareas)

@app.route('/admin/crear_tarea', methods=['GET', 'POST'])
def crear_tarea():
    if 'user_id' not in session or not session['es_admin']:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        titulo = request.form['titulo']
        descripcion = request.form['descripcion']
        fecha_limite = request.form['fecha_limite']
        estudiantes_ids = request.form.getlist('estudiantes')
        
        # Crear tarea
        tarea = Tarea(
            titulo=titulo,
            descripcion=descripcion,
            fecha_limite=datetime.strptime(fecha_limite, '%Y-%m-%d') if fecha_limite else None
        )
        db.session.add(tarea)
        db.session.flush()
        
        # Asignar a estudiantes
        for estudiante_id in estudiantes_ids:
            asignacion = TareaUsuario(usuario_id=int(estudiante_id), tarea_id=tarea.id)
            db.session.add(asignacion)
        
        db.session.commit()
        flash('Tarea creada exitosamente')
        return redirect(url_for('admin_dashboard'))
    
    estudiantes = Usuario.query.filter_by(es_admin=False).all()
    return render_template('crear_tarea.html', estudiantes=estudiantes)

@app.route('/student/completar_tarea/<int:tarea_usuario_id>')
def completar_tarea(tarea_usuario_id):
    if 'user_id' not in session or session['es_admin']:
        return redirect(url_for('index'))
    
    tarea_usuario = TareaUsuario.query.get_or_404(tarea_usuario_id)
    
    if tarea_usuario.usuario_id != session['user_id']:
        flash('No tienes permiso para modificar esta tarea')
        return redirect(url_for('student_dashboard'))
    
    tarea_usuario.completada = not tarea_usuario.completada
    tarea_usuario.fecha_completada = datetime.utcnow() if tarea_usuario.completada else None
    
    db.session.commit()
    flash('Tarea actualizada')
    return redirect(url_for('student_dashboard'))

@app.route('/admin/reporte/<int:estudiante_id>')
def reporte_estudiante(estudiante_id):
    if 'user_id' not in session or not session['es_admin']:
        return redirect(url_for('index'))
    
    estudiante = Usuario.query.get_or_404(estudiante_id)
    tareas_estudiante = db.session.query(TareaUsuario, Tarea).join(Tarea).filter(TareaUsuario.usuario_id == estudiante_id).all()
    
    total_tareas = len(tareas_estudiante)
    completadas = sum(1 for ta, t in tareas_estudiante if ta.completada)
    porcentaje = (completadas/total_tareas*100) if total_tareas > 0 else 0
    
    return render_template('reporte_estudiante.html', 
                         estudiante=estudiante, 
                         tareas_estudiante=tareas_estudiante,
                         total_tareas=total_tareas,
                         completadas=completadas,
                         porcentaje=porcentaje)

# Crear templates HTML (se guardarán en carpeta templates/)
templates = {
    'base.html': '''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sistema de Tareas - Robótica</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="#">🤖 Sistema de Tareas Robótica</a>
            {% if session.user_id %}
            <div class="navbar-nav ms-auto">
                <span class="navbar-text me-3">{{ session.nombre }}</span>
                <a class="nav-link" href="{{ url_for('logout') }}">Cerrar Sesión</a>
            </div>
            {% endif %}
        </div>
    </nav>
    
    <div class="container mt-4">
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                {% for message in messages %}
                    <div class="alert alert-info alert-dismissible fade show" role="alert">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        {% block content %}{% endblock %}
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>''',
    
    'login.html': '''{% extends "base.html" %}

{% block content %}
<div class="row justify-content-center">
    <div class="col-md-6">
        <div class="card">
            <div class="card-header">
                <h3 class="text-center">Iniciar Sesión</h3>
            </div>
            <div class="card-body">
                <form method="POST" action="{{ url_for('login') }}">
                    <div class="mb-3">
                        <label for="matricula" class="form-label">Matrícula</label>
                        <input type="text" class="form-control" id="matricula" name="matricula" required>
                        <small class="form-text text-muted">Estudiantes usen su matrícula, Admin use "ADMIN"</small>
                    </div>
                    <div class="mb-3">
                        <label for="password" class="form-label">Contraseña</label>
                        <input type="password" class="form-control" id="password" name="password" required>
                        <small class="form-text text-muted">Estudiantes: su matrícula en minúsculas, Admin: admin123</small>
                    </div>
                    <button type="submit" class="btn btn-primary w-100">Ingresar</button>
                </form>
            </div>
        </div>
    </div>
</div>
{% endblock %}''',
    
    'admin_dashboard.html': '''{% extends "base.html" %}

{% block content %}
<div class="row">
    <div class="col-md-12">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h2>Panel de Administración</h2>
            <a href="{{ url_for('crear_tarea') }}" class="btn btn-success">➕ Nueva Tarea</a>
        </div>
        
        <div class="row">
            <div class="col-md-8">
                <h4>Estadísticas por Tarea</h4>
                <div class="table-responsive">
                    <table class="table table-striped">
                        <thead>
                            <tr>
                                <th>Tarea</th>
                                <th>Asignados</th>
                                <th>Completadas</th>
                                <th>Progreso</th>
                                <th>Fecha Límite</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for stat in stats %}
                            <tr>
                                <td>{{ stat.tarea.titulo }}</td>
                                <td>{{ stat.total_asignados }}</td>
                                <td>{{ stat.completadas }}</td>
                                <td>
                                    <div class="progress">
                                        <div class="progress-bar" role="progressbar" 
                                             style="width: {{ stat.porcentaje }}%">
                                            {{ "%.0f"|format(stat.porcentaje) }}%
                                        </div>
                                    </div>
                                </td>
                                <td>{{ stat.tarea.fecha_limite.strftime('%d/%m/%Y') if stat.tarea.fecha_limite else 'Sin límite' }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
            
            <div class="col-md-4">
                <h4>Reportes por Estudiante</h4>
                <div class="list-group">
                    {% for estudiante in estudiantes %}
                    <a href="{{ url_for('reporte_estudiante', estudiante_id=estudiante.id) }}" 
                       class="list-group-item list-group-item-action">
                        {{ estudiante.nombre }}
                        <small class="text-muted d-block">{{ estudiante.matricula }}</small>
                    </a>
                    {% endfor %}
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}''',
    
    'student_dashboard.html': '''{% extends "base.html" %}

{% block content %}
<div class="row">
    <div class="col-md-12">
        <h2>Mis Tareas</h2>
        
        <div class="row">
            {% for tarea_usuario, tarea in mis_tareas %}
            <div class="col-md-6 mb-3">
                <div class="card {% if tarea_usuario.completada %}border-success{% else %}border-warning{% endif %}">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <h5 class="mb-0">{{ tarea.titulo }}</h5>
                        <span class="badge {% if tarea_usuario.completada %}bg-success{% else %}bg-warning{% endif %}">
                            {% if tarea_usuario.completada %}✓ Completada{% else %}⏳ Pendiente{% endif %}
                        </span>
                    </div>
                    <div class="card-body">
                        <p class="card-text">{{ tarea.descripcion }}</p>
                        {% if tarea.fecha_limite %}
                        <p class="text-muted"><small>Fecha límite: {{ tarea.fecha_limite.strftime('%d/%m/%Y') }}</small></p>
                        {% endif %}
                        {% if tarea_usuario.completada %}
                        <p class="text-success"><small>Completada el: {{ tarea_usuario.fecha_completada.strftime('%d/%m/%Y %H:%M') }}</small></p>
                        {% endif %}
                        
                        <a href="{{ url_for('completar_tarea', tarea_usuario_id=tarea_usuario.id) }}" 
                           class="btn {% if tarea_usuario.completada %}btn-outline-warning{% else %}btn-success{% endif %}">
                            {% if tarea_usuario.completada %}Marcar como Pendiente{% else %}Marcar como Completada{% endif %}
                        </a>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
        
        {% if not mis_tareas %}
        <div class="alert alert-info">
            No tienes tareas asignadas aún.
        </div>
        {% endif %}
    </div>
</div>
{% endblock %}''',
    
    'crear_tarea.html': '''{% extends "base.html" %}

{% block content %}
<div class="row justify-content-center">
    <div class="col-md-8">
        <div class="card">
            <div class="card-header">
                <h3>Crear Nueva Tarea</h3>
            </div>
            <div class="card-body">
                <form method="POST">
                    <div class="mb-3">
                        <label for="titulo" class="form-label">Título de la Tarea</label>
                        <input type="text" class="form-control" id="titulo" name="titulo" required>
                    </div>
                    
                    <div class="mb-3">
                        <label for="descripcion" class="form-label">Descripción</label>
                        <textarea class="form-control" id="descripcion" name="descripcion" rows="3"></textarea>
                    </div>
                    
                    <div class="mb-3">
                        <label for="fecha_limite" class="form-label">Fecha Límite (Opcional)</label>
                        <input type="date" class="form-control" id="fecha_limite" name="fecha_limite">
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">Asignar a Estudiantes</label>
                        <div class="row">
                            {% for estudiante in estudiantes %}
                            <div class="col-md-6">
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" 
                                           name="estudiantes" value="{{ estudiante.id }}" id="est{{ estudiante.id }}">
                                    <label class="form-check-label" for="est{{ estudiante.id }}">
                                        {{ estudiante.nombre }} ({{ estudiante.matricula }})
                                    </label>
                                </div>
                            </div>
                            {% endfor %}
                        </div>
                    </div>
                    
                    <div class="d-flex justify-content-between">
                        <a href="{{ url_for('admin_dashboard') }}" class="btn btn-secondary">Cancelar</a>
                        <button type="submit" class="btn btn-primary">Crear Tarea</button>
                    </div>
                </form>
            </div>
        </div>
    </div>
</div>
{% endblock %}''',
    
    'reporte_estudiante.html': '''{% extends "base.html" %}

{% block content %}
<div class="row">
    <div class="col-md-12">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h2>Reporte: {{ estudiante.nombre }}</h2>
            <a href="{{ url_for('admin_dashboard') }}" class="btn btn-secondary">Volver</a>
        </div>
        
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h5 class="card-title">{{ total_tareas }}</h5>
                        <p class="card-text">Tareas Asignadas</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h5 class="card-title text-success">{{ completadas }}</h5>
                        <p class="card-text">Completadas</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h5 class="card-title text-warning">{{ total_tareas - completadas }}</h5>
                        <p class="card-text">Pendientes</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h5 class="card-title">{{ "%.0f"|format(porcentaje) }}%</h5>
                        <p class="card-text">Progreso</p>
                    </div>
                </div>
            </div>
        </div>
        
        <h4>Detalle de Tareas</h4>
        <div class="table-responsive">
            <table class="table table-striped">
                <thead>
                    <tr>
                        <th>Tarea</th>
                        <th>Estado</th>
                        <th>Fecha Límite</th>
                        <th>Fecha Completada</th>
                    </tr>
                </thead>
                <tbody>
                    {% for tarea_usuario, tarea in tareas_estudiante %}
                    <tr>
                        <td>
                            <strong>{{ tarea.titulo }}</strong>
                            {% if tarea.descripcion %}
                            <br><small class="text-muted">{{ tarea.descripcion }}</small>
                            {% endif %}
                        </td>
                        <td>
                            <span class="badge {% if tarea_usuario.completada %}bg-success{% else %}bg-warning{% endif %}">
                                {% if tarea_usuario.completada %}✓ Completada{% else %}⏳ Pendiente{% endif %}
                            </span>
                        </td>
                        <td>{{ tarea.fecha_limite.strftime('%d/%m/%Y') if tarea.fecha_limite else 'Sin límite' }}</td>
                        <td>{{ tarea_usuario.fecha_completada.strftime('%d/%m/%Y %H:%M') if tarea_usuario.fecha_completada else '-' }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>
{% endblock %}'''
}

if __name__ == '__main__':
    # Crear carpeta templates si no existe
    import os
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    # Guardar templates
    for filename, content in templates.items():
        with open(f'templates/{filename}', 'w', encoding='utf-8') as f:
            f.write(content)
    
    init_db()
    app.run(debug=True)