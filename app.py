from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
import threading
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'clave-secreta-robotica-2024')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tareas.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuración de email
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('EMAIL_USER', 'test@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('EMAIL_PASS', 'password')
app.config['PROFESOR_EMAIL'] = os.environ.get('PROFESOR_EMAIL', 'profesor@tec.mx')

db = SQLAlchemy(app)

# Modelos de base de datos
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    matricula = db.Column(db.String(20), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=True)
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

# Funciones de Email
def enviar_email(destinatario, asunto, cuerpo):
    """Enviar email de forma asíncrona"""
    def enviar():
        try:
            if app.config['MAIL_USERNAME'] == 'test@gmail.com':
                print(f"📧 [DEMO] Email a {destinatario}: {asunto}")
                return
                
            msg = MimeMultipart()
            msg['From'] = app.config['MAIL_USERNAME']
            msg['To'] = destinatario
            msg['Subject'] = asunto
            
            msg.attach(MimeText(cuerpo, 'html'))
            
            server = smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT'])
            server.starttls()
            server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
            text = msg.as_string()
            server.sendmail(app.config['MAIL_USERNAME'], destinatario, text)
            server.quit()
            
            print(f"✅ Email enviado a {destinatario}")
        except Exception as e:
            print(f"❌ Error enviando email: {e}")
    
    threading.Thread(target=enviar).start()

def notificar_tarea_completada(estudiante_nombre, tarea_titulo):
    """Notificar al profesor cuando un estudiante completa una tarea"""
    asunto = f"🎉 Tarea Completada - {estudiante_nombre}"
    cuerpo = f"""
    <html>
    <body style="font-family: Arial, sans-serif;">
        <div style="background: linear-gradient(45deg, #1e3a8a, #dc2626); color: white; padding: 20px; text-align: center;">
            <h1>🤖 Sistema Tareas Robótica</h1>
        </div>
        <div style="padding: 20px;">
            <h2>✅ Tarea Completada</h2>
            <p><strong>Estudiante:</strong> {estudiante_nombre}</p>
            <p><strong>Tarea:</strong> {tarea_titulo}</p>
            <p><strong>Fecha:</strong> {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
            
            <div style="background: #d1f2eb; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <p>✅ El estudiante ha marcado esta tarea como completada.</p>
                <p>📊 Puedes revisar el progreso en el panel de administración.</p>
            </div>
        </div>
    </body>
    </html>
    """
    enviar_email(app.config['PROFESOR_EMAIL'], asunto, cuerpo)

def enviar_nueva_tarea_email(estudiante_email, estudiante_nombre, tarea_titulo, descripcion, dias_limite):
    """Notificar a estudiante de nueva tarea asignada"""
    asunto = f"📋 Nueva Tarea: {tarea_titulo}"
    cuerpo = f"""
    <html>
    <body style="font-family: Arial, sans-serif;">
        <div style="background: linear-gradient(45deg, #1e3a8a, #dc2626); color: white; padding: 20px; text-align: center;">
            <h1>🤖 Sistema Tareas Robótica</h1>
        </div>
        <div style="padding: 20px;">
            <h2>📋 Nueva Tarea Asignada</h2>
            <p>Hola <strong>{estudiante_nombre}</strong>,</p>
            
            <div style="background: #e3f2fd; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <h3 style="color: #1976d2;">{tarea_titulo}</h3>
                <p><strong>Descripción:</strong> {descripcion or 'Sin descripción adicional'}</p>
                <p><strong>Plazo:</strong> {dias_limite} días</p>
            </div>
            
            <p>🚀 Recuerda marcar la tarea como completada cuando termines.</p>
        </div>
    </body>
    </html>
    """
    enviar_email(estudiante_email, asunto, cuerpo)

def notificar_recordatorio_tarea(estudiante_email, estudiante_nombre, tarea_titulo, dias_restantes):
    """Enviar recordatorio a estudiante de tarea próxima a vencer"""
    asunto = f"⏰ RECORDATORIO: {tarea_titulo}"
    cuerpo = f"""
    <html>
    <body style="font-family: Arial, sans-serif;">
        <div style="background: #ffc107; color: black; padding: 20px; text-align: center;">
            <h1>⏰ RECORDATORIO URGENTE</h1>
        </div>
        <div style="padding: 20px;">
            <h2>🚨 Tarea próxima a vencer</h2>
            <p>Hola <strong>{estudiante_nombre}</strong>,</p>
            
            <div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 5px solid #ffc107;">
                <h3>📋 {tarea_titulo}</h3>
                <p><strong>⚠️ Vence en: {dias_restantes} días</strong></p>
            </div>
            
            <p>📅 No olvides completar tu tarea a tiempo!</p>
        </div>
    </body>
    </html>
    """
    enviar_email(estudiante_email, asunto, cuerpo)

def verificar_recordatorios():
    """Verificar tareas que necesitan recordatorio (2 días antes de vencer)"""
    try:
        fecha_limite = datetime.now() + timedelta(days=2)
        
        tareas_proximas = db.session.query(TareaUsuario, Tarea, Usuario).join(Tarea).join(Usuario).filter(
            Tarea.fecha_limite.isnot(None),
            Tarea.fecha_limite <= fecha_limite,
            Tarea.fecha_limite > datetime.now(),
            TareaUsuario.completada == False
        ).all()
        
        for tarea_usuario, tarea, usuario in tareas_proximas:
            if usuario.email:
                dias_restantes = (tarea.fecha_limite - datetime.now()).days
                notificar_recordatorio_tarea(usuario.email, usuario.nombre, tarea.titulo, dias_restantes)
    except Exception as e:
        print(f"❌ Error verificando recordatorios: {e}")

def iniciar_verificador_recordatorios():
    """Iniciar verificador de recordatorios"""
    def verificar_periodicamente():
        while True:
            with app.app_context():
                verificar_recordatorios()
            time.sleep(3600)  # Cada hora
    
    threading.Thread(target=verificar_periodicamente, daemon=True).start()

# Crear tablas y datos iniciales
def init_db():
    with app.app_context():
        db.create_all()
        
        # Admin
        if not Usuario.query.filter_by(matricula='ADMIN').first():
            admin = Usuario(
                matricula='ADMIN',
                nombre='Angel Monroy',
                email=app.config['amonroy@tec.mx'],
                password_hash=generate_password_hash('admin123'),
                es_admin=True
            )
            db.session.add(admin)
        
        estudiantes_ejemplo = [
            ('A01773550','Everardo'),
            ('A01770860', 'Regina'),
            ('A01773554', 'Camila'),
            ('A01771236', 'Arturo'),
            ('A01770705', 'Diego'),
            ('A01770524', 'Charly'),
            ('A01770979',  'JP'),
            ('A01773315', 'Richie'), 
            ('A01773495', 'Tello'),
            ('A01773374', 'Ileana') 
        ]
        
        for matricula, nombre in estudiantes_ejemplo:
            if not Usuario.query.filter_by(matricula=matricula).first():
                email = f"{matricula.lower()}@tec.mx"
                estudiante = Usuario(
                    matricula=matricula,
                    nombre=nombre,
                    email=email,
                    password_hash=generate_password_hash(matricula.lower()),
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
        
        tarea = Tarea(
            titulo=titulo,
            descripcion=descripcion,
            fecha_limite=datetime.strptime(fecha_limite, '%Y-%m-%d') if fecha_limite else None
        )
        db.session.add(tarea)
        db.session.flush()
        
        for estudiante_id in estudiantes_ids:
            asignacion = TareaUsuario(usuario_id=int(estudiante_id), tarea_id=tarea.id)
            db.session.add(asignacion)
        
        db.session.commit()
        
        # Enviar emails a estudiantes
        if fecha_limite:
            estudiantes_asignados = Usuario.query.filter(Usuario.id.in_(estudiantes_ids)).all()
            for estudiante in estudiantes_asignados:
                if estudiante.email:
                    dias_limite = (datetime.strptime(fecha_limite, '%Y-%m-%d') - datetime.now()).days
                    enviar_nueva_tarea_email(estudiante.email, estudiante.nombre, titulo, descripcion, dias_limite)
        
        flash(f'Tarea creada y enviada a {len(estudiantes_ids)} estudiantes por email')
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
    
    if tarea_usuario.completada:
        usuario = Usuario.query.get(session['user_id'])
        tarea = Tarea.query.get(tarea_usuario.tarea_id)
        notificar_tarea_completada(usuario.nombre, tarea.titulo)
        flash('✅ Tarea completada y profesor notificado')
    else:
        flash('Tarea marcada como pendiente')
    
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

# Templates HTML
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
            <a class="navbar-brand" href="#">🤖 Sistema Tareas - Proyecto Robótica</a>
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
                        <small class="form-text text-muted">Ever, Ramos, Ileana, JP, Tello, Camila, Diego, Regina | Admin: ADMIN</small>
                    </div>
                    <div class="mb-3">
                        <label for="password" class="form-label">Contraseña</label>
                        <input type="password" class="form-control" id="password" name="password" required>
                        <small class="form-text text-muted">Estudiantes: matrícula en minúsculas | Profesor: admin123</small>
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
                <h4>📊 Estadísticas por Tarea</h4>
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
                <h4>👥 Reportes por Estudiante</h4>
                <div class="list-group">
                    {% for estudiante in estudiantes %}
                    <a href="{{ url_for('reporte_estudiante', estudiante_id=estudiante.id) }}" 
                       class="list-group-item list-group-item-action">
                        {{ estudiante.nombre }}
                        <small class="text-muted d-block">{{ estudiante.matricula }} - {{ estudiante.email }}</small>
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
        <h2>📋 Mis Tareas</h2>
        
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
                        <p class="card-text">{{ tarea.descripcion or 'Sin descripción adicional' }}</p>
                        {% if tarea.fecha_limite %}
                        <p class="text-muted"><small>📅 Fecha límite: {{ tarea.fecha_limite.strftime('%d/%m/%Y') }}</small></p>
                        {% endif %}
                        {% if tarea_usuario.completada %}
                        <p class="text-success"><small>✅ Completada el: {{ tarea_usuario.fecha_completada.strftime('%d/%m/%Y %H:%M') }}</small></p>
                        {% endif %}
                        
                        <a href="{{ url_for('completar_tarea', tarea_usuario_id=tarea_usuario.id) }}" 
                           class="btn {% if tarea_usuario.completada %}btn-outline-warning{% else %}btn-success{% endif %}">
                            {% if tarea_usuario.completada %}Marcar Pendiente{% else %}✅ Marcar Completada{% endif %}
                        </a>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
        
        {% if not mis_tareas %}
        <div class="alert alert-info">
            📭 No tienes tareas asignadas aún.
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
                <h3>➕ Crear Nueva Tarea</h3>
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
                        <label for="fecha_limite" class="form-label">Fecha Límite</label>
                        <input type="date" class="form-control" id="fecha_limite" name="fecha_limite" required>
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
                                        <small class="text-muted d-block">{{ estudiante.email }}</small>
                                    </label>
                                </div>
                            </div>
                            {% endfor %}
                        </div>
                    </div>
                    
                    <div class="d-flex justify-content-between">
                        <a href="{{ url_for('admin_dashboard') }}" class="btn btn-secondary">Cancelar</a>
                        <button type="submit" class="btn btn-primary">✉️ Crear y Enviar por Email</button>
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
            <h2>📊 Reporte: {{ estudiante.nombre }}</h2>
            <a href="{{ url_for('admin_dashboar