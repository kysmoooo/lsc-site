from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
import mysql.connector
from mysql.connector import Error
import requests
import os
import traceback
from datetime import datetime
import pytz

PARIS_TZ = pytz.timezone("Europe/Paris")

def now_paris():
    return datetime.now(PARIS_TZ)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "e70347e86f09c362df99758723597361e12fd197d16a3275e21504b4df99cbcc")

# Configuration MySQL
DB_CONFIG = {
    'host': os.environ.get("DB_HOST", "crossover.proxy.rlwy.net"),
    'port': int(os.environ.get("DB_PORT", 46654)),
    'database': os.environ.get("DB_NAME", "railway"),
    'user': os.environ.get("DB_USER", "root"),
    'password': os.environ.get("DB_PASSWORD", "UwowmkIANctHZtapEPZLuzeNCRnuMkAD"),
    'connection_timeout': 5,
    'autocommit': True
}

# Configuration Discord
DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "1481295358431727616")
DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "")
DISCORD_REDIRECT_URI = os.environ.get("DISCORD_REDIRECT_URI", "https://lix-site-ltd-mp-production.up.railway.app/callback")
DISCORD_GUILD_ID = "1477019441815359540"
BOT_TOKEN = os.environ.get("DISCORD_TOKEN")


# Login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Classe User
class User(UserMixin):
    def __init__(self, id, username, discord_id):
        self.id = id
        self.username = username
        self.discord_id = discord_id

@login_manager.user_loader
def load_user(user_id):
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return None
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, username, discord_id FROM users WHERE id=%s", (int(user_id),))
        user = cur.fetchone()
        cur.close()
        if user:
            return User(user['id'], user['username'], user['discord_id'])
        return None
    except Exception as e:
        print(f"❌ Erreur load_user: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_db_connection():
    """Retourne une nouvelle connexion MySQL"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Error as e:
        print(f"❌ Erreur de connexion MySQL: {e}")
        return None

# Gestionnaire d'erreurs 404
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

# Gestionnaire d'erreurs général
@app.errorhandler(Exception)
def handle_exception(e):
    print(f"❌ Erreur: {str(e)}")
    traceback.print_exc()
    return "Une erreur interne est survenue", 500

# Route principale
@app.route("/")
def index():
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return render_template("index.html", products=[], personnel=[], error="Connexion DB échouée")
        
        cur = conn.cursor(dictionary=True)
        
        cur.execute("SELECT id, name, price, description, category, image_url FROM products")
        products = cur.fetchall()
        
        cur.execute("SELECT id, name, role, discord_id FROM personnel")
        personnel = cur.fetchall()
        
        cur.close()
        
        return render_template("index.html", products=products, personnel=personnel)
    
    except Exception as e:
        print(f"❌ Erreur index: {e}")
        return render_template("index.html", products=[], personnel=[])
    finally:
        if conn:
            conn.close()

# Route personnel
@app.route("/personnel")
def personnel_page():
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return render_template("personnel.html", personnel=[])
        
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, name, role, discord_id FROM personnel ORDER BY role")
        personnel = cur.fetchall()
        cur.close()
        
        return render_template("personnel.html", personnel=personnel)
    
    except Exception as e:
        print(f"❌ Erreur personnel: {e}")
        return render_template("personnel.html", personnel=[])
    finally:
        if conn:
            conn.close()
# ========== ROUTES DIRECTION ==========
@app.route("/api/direction/login", methods=["POST"])
def direction_login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, username, name, role FROM personnel WHERE username=%s AND password=%s AND role='Directeur'", (username, password))
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    if user:
        session['direction_id'] = user['id']
        return jsonify({"success": True, "user": user})
    return jsonify({"success": False})

@app.route("/api/direction/logout", methods=["POST"])
def direction_logout():
    session.pop('direction_id', None)
    return jsonify({"success": True})

@app.route("/api/employes/create", methods=["POST"])
def create_employe():
    if 'direction_id' not in session:
        return jsonify({"success": False, "error": "Non autorisé"}), 401
    
    data = request.get_json()
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("INSERT INTO personnel (username, password, name, role, active) VALUES (%s, %s, %s, 'employe', '1')", 
                    (data['username'], data['password'], data['name']))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
    finally:
        cur.close()
        conn.close()

# ========== ROUTES EMPLOYE ==========
@app.route("/api/employe/login", methods=["POST"])
def employe_login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, username, name, role FROM personnel WHERE username=%s AND password=%s AND active='1'", (username, password))
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    if user:
        session['employe_id'] = user['id']
        return jsonify({"success": True, "user": user})
    return jsonify({"success": False})

@app.route("/api/employe/logout", methods=["POST"])
def employe_logout():
    session.pop('employe_id', None)
    return jsonify({"success": True})

# ========== ROUTES SERVICES ==========

def format_paris(dt):
    """Convertit un datetime MySQL (naive, UTC ou local) en heure Paris"""
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)  # ou PARIS_TZ.localize(dt) si MySQL est déjà en heure locale
    return dt.astimezone(PARIS_TZ).strftime("%d/%m/%Y %H:%M")

@app.route("/api/services/count")
def get_services_count():
    """Retourne le nombre d'employés actuellement en service"""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"count": 0})
        
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT COUNT(DISTINCT employe_id) as count
            FROM services s1
            WHERE action = 'debut'
            AND NOT EXISTS (
                SELECT 1 FROM services s2
                WHERE s2.employe_id = s1.employe_id
                AND s2.action = 'fin'
                AND s2.heure > s1.heure
            )
        """)
        result = cur.fetchone()
        return jsonify({"count": result['count'] if result else 0})
    
    except Exception as e:
        print(f"❌ Erreur get_services_count: {e}")
        return jsonify({"count": 0})
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.route("/api/services/can-start")
def can_start_service():
    """Vérifie si un nouvel employé peut prendre son service (moins de 2 personnes en service)"""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"can_start": False, "count": 0})
        
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT COUNT(DISTINCT employe_id) as count
            FROM services s1
            WHERE action = 'debut'
            AND NOT EXISTS (
                SELECT 1 FROM services s2
                WHERE s2.employe_id = s1.employe_id
                AND s2.action = 'fin'
                AND s2.heure > s1.heure
            )
        """)
        result = cur.fetchone()
        count = result['count'] if result else 0
        return jsonify({"can_start": count < 2, "count": count})
    
    except Exception as e:
        print(f"❌ Erreur can_start_service: {e}")
        return jsonify({"can_start": False, "count": 0})
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.route("/api/services/employe/<int:employe_id>")
def get_services_employe(employe_id):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify([])

        cur = conn.cursor(dictionary=True)

        # Récupérer tous les débuts avec leur fin correspondante
        cur.execute("""
            SELECT 
                d.heure as debut,
                (SELECT f.heure FROM services f 
                 WHERE f.employe_id = d.employe_id 
                 AND f.action = 'fin' 
                 AND f.heure > d.heure 
                 ORDER BY f.heure ASC LIMIT 1
                ) as fin
            FROM services d
            WHERE d.employe_id = %s AND d.action = 'debut'
            ORDER BY d.heure DESC
            LIMIT 50
        """, (employe_id,))

        rows = cur.fetchall()
        result = []
        for row in rows:
            debut_dt = row['debut']
            fin_dt = row['fin']

            # Conversion des timezone
            if debut_dt and debut_dt.tzinfo is None:
                debut_dt = pytz.utc.localize(debut_dt)
            if fin_dt and fin_dt.tzinfo is None:
                fin_dt = pytz.utc.localize(fin_dt)

            duree_min = None
            duree_str = "En cours"
            court = False
            
            if fin_dt:
                duree_min = int((fin_dt - debut_dt).total_seconds() // 60)
                h, m = divmod(duree_min, 60)
                duree_str = f"{h}h {m}min" if h > 0 else f"{m}min"
                court = duree_min < 60
            else:
                # Service en cours - calculer la durée depuis le début
                now_utc = datetime.now(pytz.utc)
                duree_min = int((now_utc - debut_dt).total_seconds() // 60)
                h, m = divmod(duree_min, 60)
                duree_str = f"{h}h {m}min (en cours)" if h > 0 else f"{m}min (en cours)"
                court = duree_min < 60

            result.append({
                "debut": debut_dt.astimezone(PARIS_TZ).strftime("%d/%m/%Y %H:%M") if debut_dt else "—",
                "fin": fin_dt.astimezone(PARIS_TZ).strftime("%d/%m/%Y %H:%M") if fin_dt else "En cours",
                "duree_min": duree_min,
                "duree_str": duree_str,
                "court": court
            })

        return jsonify(result)

    except Exception as e:
        print(f"❌ Erreur get_services_employe: {e}")
        traceback.print_exc()
        return jsonify([])
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.route('/api/services/force-end/<int:employe_id>', methods=['POST'])
def force_end_service(employe_id):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "error": "Erreur de connexion DB"}), 500

        cur = conn.cursor(dictionary=True)

        # Vérifier si l'employé existe
        cur.execute("SELECT id, name, role, discord_id FROM personnel WHERE id=%s", (employe_id,))
        employe = cur.fetchone()
        if not employe:
            return jsonify({"success": False, "error": "Employé non trouvé"}), 404

        # Vérifier si déjà en service
        cur.execute("""
            SELECT action FROM services
            WHERE employe_id = %s
            ORDER BY heure DESC LIMIT 1
        """, (employe_id,))
        last = cur.fetchone()

        if not last or last["action"] != "debut":
            return jsonify({"success": False, "error": "Cet employé n'est pas en service"}), 400

        # Ajouter une fin de service forcée
        cur.execute("""
            INSERT INTO services (employe_id, action)
            VALUES (%s, 'fin')
        """, (employe_id,))
        conn.commit()

        # Récupérer le début du service
        cur.execute("""
            SELECT heure FROM services
            WHERE employe_id=%s AND action='debut'
            ORDER BY heure DESC LIMIT 1
        """, (employe_id,))
        debut_row = cur.fetchone()

        # Calculer la durée
        duree_str = "—"
        if debut_row:
            debut_dt = debut_row['heure']
            if debut_dt.tzinfo is None:
                debut_dt = pytz.utc.localize(debut_dt)
            fin_dt = datetime.now(pytz.utc)
            diff = int((fin_dt - debut_dt).total_seconds())
            h, rem = divmod(diff, 3600)
            m, s = divmod(rem, 60)
            duree_str = f"{h}h {m}min {s}s"

        # 🔴 WEBHOOK DISCORD - Assurez-vous que ce webhook est configuré
        WEBHOOK = "https://discord.com/api/webhooks/1492868954937491556/PzNesc-qQY5RvnacdU4u3QM43-5_eyxqgSqq1V1P7fGX8AQTzGJsxUY-7WiXY25yRk2X"
        
        if WEBHOOK and WEBHOOK != "TON_WEBHOOK_ICI":
            embed = {
                "title": "⛔ Service forcé par la direction",
                "color": 15158332,
                "fields": [
                    {
                        "name": "👤 Employé",
                        "value": f"{employe['name']} ({employe['role']})",
                        "inline": True
                    },
                    {
                        "name": "🕐 Fin forcée",
                        "value": now_paris().strftime("%d/%m/%Y %H:%M"),
                        "inline": True
                    },
                    {
                        "name": "⏱️ Durée",
                        "value": duree_str,
                        "inline": False
                    }
                ],
                "footer": {"text": "LTD Mirror Park — Direction"},
                "timestamp": now_paris().isoformat()
            }
            
            # Envoyer le webhook de manière asynchrone (ne pas bloquer la réponse)
            try:
                requests.post(WEBHOOK, json={"embeds": [embed]}, timeout=2)
            except:
                pass  # Ignorer les erreurs webhook

        return jsonify({"success": True, "message": "Service terminé avec succès"})

    except Exception as e:
        print("❌ force_end_service:", e)
        traceback.print_exc()
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route("/api/services")
def get_all_services():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify([])

        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT 
                p.id,
                p.name,
                (SELECT action FROM services s2 
                WHERE s2.employe_id = p.id 
                ORDER BY s2.heure DESC LIMIT 1
                ) as last_action,
                MAX(CASE 
                    WHEN s.action='debut' 
                    AND DATE(CONVERT_TZ(s.heure, 'UTC', 'Europe/Paris')) = DATE(CONVERT_TZ(NOW(), 'UTC', 'Europe/Paris'))
                    THEN s.heure END
                ) as debut_service,
                MAX(CASE 
                    WHEN s.action='fin' 
                    AND DATE(CONVERT_TZ(s.heure, 'UTC', 'Europe/Paris')) = DATE(CONVERT_TZ(NOW(), 'UTC', 'Europe/Paris'))
                    THEN s.heure END
                ) as fin_service,
                TIMESTAMPDIFF(MINUTE,
                    (SELECT heure FROM services s3
                    WHERE s3.employe_id = p.id AND s3.action = 'debut'
                    ORDER BY s3.heure DESC LIMIT 1),
                    NOW()
                ) as duree_actuelle,
                TIMESTAMPDIFF(MINUTE,
                    (SELECT s4.heure FROM services s4
                    WHERE s4.employe_id = p.id AND s4.action = 'debut'
                    AND s4.heure < (
                        SELECT heure FROM services s5
                        WHERE s5.employe_id = p.id AND s5.action = 'fin'
                        ORDER BY s5.heure DESC LIMIT 1
                    )
                    ORDER BY s4.heure DESC LIMIT 1),
                    (SELECT heure FROM services s5
                    WHERE s5.employe_id = p.id AND s5.action = 'fin'
                    ORDER BY s5.heure DESC LIMIT 1)
                ) as duree_dernier_service,
                COUNT(CASE 
                    WHEN s.action='debut'
                    AND YEARWEEK(CONVERT_TZ(s.heure, 'UTC', 'Europe/Paris'), 1) 
                        = YEARWEEK(CONVERT_TZ(NOW(), 'UTC', 'Europe/Paris'), 1)
                THEN 1 END) as total_services
            FROM personnel p
            LEFT JOIN services s ON p.id = s.employe_id
            WHERE p.active = '1'
            GROUP BY p.id, p.name
            ORDER BY p.name
        """)

        services = cur.fetchall()

        result = []
        for row in services:
            en_service = row["last_action"] == "debut"
            result.append({
                "id": row["id"],  # ⚠️ AJOUTE CETTE LIGNE !
                "name": row["name"],
                "en_service": en_service,
                "debut_service": format_paris(row["debut_service"]),
                "fin_service": format_paris(row["fin_service"]),
                "total_services": row["total_services"],
                "duree": row["duree_actuelle"] if en_service else row["duree_dernier_service"]
            })

        return jsonify(result)

    except Exception as e:
        print(f"❌ Erreur get_all_services: {e}")
        traceback.print_exc()
        return jsonify([])
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route("/api/services/status")
def service_status():
    employe_id = request.args.get('employe_id')
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT action, heure FROM services 
        WHERE employe_id=%s 
        ORDER BY heure DESC LIMIT 1
    """, (employe_id,))
    last = cur.fetchone()
    cur.close()
    conn.close()
    
    if last and last['action'] == 'debut':
        debut_dt = last['heure']
        if debut_dt.tzinfo is None:
            debut_dt = pytz.utc.localize(debut_dt)
        return jsonify({"en_service": True, "debut": debut_dt.isoformat()})
    return jsonify({"en_service": False})

@app.route("/api/services/stats")
def get_services_stats():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify([])
        
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT 
                p.name,
                COUNT(CASE WHEN s.action = 'debut' THEN 1 END) as total_services,
                SUM(
                    CASE 
                        WHEN s.action = 'fin' THEN
                            TIMESTAMPDIFF(SECOND,
                                (SELECT s2.heure FROM services s2 
                                 WHERE s2.employe_id = s.employe_id 
                                 AND s2.action = 'debut' 
                                 AND s2.heure < s.heure 
                                 ORDER BY s2.heure DESC LIMIT 1),
                                s.heure
                            )
                        ELSE 0
                    END
                ) as total_seconds,
                COUNT(
                    CASE 
                        WHEN s.action = 'fin' AND 
                            TIMESTAMPDIFF(MINUTE,
                                (SELECT s2.heure FROM services s2 
                                 WHERE s2.employe_id = s.employe_id 
                                 AND s2.action = 'debut' 
                                 AND s2.heure < s.heure 
                                 ORDER BY s2.heure DESC LIMIT 1),
                                s.heure
                            ) < 60
                        THEN 1 
                    END
                ) as short_services
            FROM personnel p
            LEFT JOIN services s ON p.id = s.employe_id
            WHERE p.active = '1'
            GROUP BY p.id, p.name
            ORDER BY total_seconds DESC
        """)
        rows = cur.fetchall()

        result = []
        for row in rows:
            total_sec = int(row["total_seconds"] or 0)
            hours = total_sec // 3600
            minutes = (total_sec % 3600) // 60
            seconds = total_sec % 60

            if hours > 0:
                temps_str = f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                temps_str = f"{minutes}m {seconds}s"
            else:
                temps_str = f"{seconds}s"

            result.append({
                "name": row["name"],
                "total_services": int(row["total_services"] or 0),
                "short_services": int(row["short_services"] or 0),
                "total_seconds": total_sec,
                "temps_formate": temps_str
            })

        return jsonify(result)

    except Exception as e:
        print(f"❌ Erreur get_services_stats: {e}")
        traceback.print_exc()
        return jsonify([])
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route("/api/services/toggle", methods=["POST"])
def toggle_service():
    data = request.get_json()
    employe_id = data.get('employe_id')

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    # Récupérer le dernier statut
    cur.execute("SELECT action FROM services WHERE employe_id=%s ORDER BY heure DESC LIMIT 1", (employe_id,))
    last = cur.fetchone()

    # Récupérer les infos de l'employé
    cur.execute("SELECT name, role FROM personnel WHERE id=%s", (employe_id,))
    employe = cur.fetchone()

    SERVICE_WEBHOOK = "https://discord.com/api/webhooks/1492868954937491556/PzNesc-qQY5RvnacdU4u3QM43-5_eyxqgSqq1V1P7fGX8AQTzGJsxUY-7WiXY25yRk2X"

    if last and last['action'] == 'debut':
        # --- FIN DE SERVICE ---
        cur.execute("INSERT INTO services (employe_id, action) VALUES (%s, 'fin')", (employe_id,))
        conn.commit()

        # Calculer la durée
        cur.execute("""
            SELECT heure FROM services 
            WHERE employe_id=%s AND action='debut' 
            ORDER BY heure DESC LIMIT 1
        """, (employe_id,))
        debut_row = cur.fetchone()
        duree_str = "—"
        if debut_row:
            debut_dt = debut_row['heure']
            if debut_dt.tzinfo is None:
                debut_dt = pytz.utc.localize(debut_dt)
            fin_dt = datetime.now(pytz.utc)
            diff = int((fin_dt - debut_dt).total_seconds())
            h, rem = divmod(diff, 3600)
            m, s = divmod(rem, 60)
            duree_str = f"{h}h {m}min {s}sec"

        embed = {
            "title": "🔴 Fin de service",
            "color": 15158332,  # Rouge
            "fields": [
                {"name": "👤 Employé", "value": f"{employe['name']} ({employe['role']})", "inline": True},
                {"name": "🕐 Heure de fin", "value": now_paris().strftime("%d/%m/%Y %H:%M"), "inline": True},
                {"name": "⏱️ Durée totale", "value": duree_str, "inline": False},
            ],
            "footer": {"text": "LTD Mirror Park — Logs Services"},
            "timestamp": now_paris().isoformat()
        }

        requests.post(SERVICE_WEBHOOK, json={"embeds": [embed]})
        cur.close()
        conn.close()
        return jsonify({"en_service": False})

    else:
        # --- DÉBUT DE SERVICE ---
        cur.execute("INSERT INTO services (employe_id, action) VALUES (%s, 'debut')", (employe_id,))
        conn.commit()

        cur.execute("SELECT heure FROM services WHERE employe_id=%s ORDER BY heure DESC LIMIT 1", (employe_id,))
        debut = cur.fetchone()

        embed = {
            "title": "🟢 Début de service",
            "color": 3066993,
            "fields": [
                {"name": "👤 Employé", "value": f"{employe['name']} ({employe['role']})", "inline": True},
                {"name": "🕐 Heure de début", "value": now_paris().strftime("%d/%m/%Y %H:%M"), "inline": True},
            ],
            "footer": {"text": "LTD Mirror Park — Logs Services"},
            "timestamp": now_paris().isoformat()
        }

        requests.post(SERVICE_WEBHOOK, json={"embeds": [embed]})
        cur.close()
        conn.close()

        # ✅ Retourner l'heure en ISO avec timezone UTC explicite
        debut_dt = debut['heure']
        if debut_dt.tzinfo is None:
            debut_dt = pytz.utc.localize(debut_dt)
        
        return jsonify({"en_service": True, "debut": debut_dt.isoformat()})

# ========== ROUTES ANNONCES ==========
@app.route("/api/annonces/historique")
def annonces_historique():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify([])
        
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT
                a.id,
                a.date_affichage, 
                p.name as employe_name
            FROM annonces_affichage a
            JOIN personnel p ON a.employe_id = p.id
            ORDER BY a.date_affichage DESC 
            LIMIT 50
        """)
        history = cur.fetchall()
        
        # Convertir les datetime en string pour JSON
        result = []
        for row in history:
            result.append({
                "id": row["id"],
                "employe_name": row["employe_name"],
                "date_affichage": format_paris(row["date_affichage"]) if row["date_affichage"] else ""
            })
        
        return jsonify(result)

    except Exception as e:
        print(f"❌ Erreur annonces_historique: {e}")
        traceback.print_exc()
        return jsonify([])  # Retourne [] plutôt qu'une erreur 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route('/api/annonces/historique/<int:id>', methods=['DELETE'])
def delete_historique(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM annonces_affichage WHERE id = %s', (id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'success': True})

@app.route("/api/annonces", methods=["GET"])
def get_all_annonces():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify([])
        
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, titre, image_url, texte FROM annonces ORDER BY id DESC")
        annonces = cur.fetchall()
        
        return jsonify(annonces if annonces else [])
    
    except Exception as e:
        print(f"❌ Erreur get_all_annonces: {e}")
        traceback.print_exc()
        return jsonify([])
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route("/api/annonce", methods=["GET", "POST"])
def handle_annonce():
    conn = None
    cur = None
    try:
        if request.method == "POST":
            data = request.get_json()
            if not data:
                return jsonify({"success": False, "error": "Données manquantes"}), 400
            
            annonce_id = data.get('id')  # None = nouvelle annonce
            titre = data.get('titre', '')
            image_url = data.get('image_url', '')
            texte = data.get('texte', '')
            
            conn = get_db_connection()
            if not conn:
                return jsonify({"success": False, "error": "Erreur de connexion DB"}), 500
            
            cur = conn.cursor()
            
            if annonce_id:
                # Mettre à jour une annonce existante
                cur.execute("""
                    UPDATE annonces 
                    SET titre = %s, image_url = %s, texte = %s, updated_at = NOW()
                    WHERE id = %s
                """, (titre, image_url, texte, annonce_id))
            else:
                # Créer une nouvelle annonce
                cur.execute("""
                    INSERT INTO annonces (titre, image_url, texte) 
                    VALUES (%s, %s, %s)
                """, (titre, image_url, texte))
            
            conn.commit()
            return jsonify({"success": True})
        
        # GET - Retourner la première annonce (compatibilité)
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, titre, image_url, texte FROM annonces ORDER BY id DESC LIMIT 1")
        annonce = cur.fetchone()
        
        return jsonify(annonce or {
            "id": None,
            "titre": "Bienvenue au LTD Mirror Park",
            "image_url": "https://i.goopics.net/ofpiwy.png",
            "texte": "Bienvenue dans notre établissement !"
        })
        
    except Exception as e:
        print(f"❌ Erreur handle_annonce: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.route("/api/annonce/<int:annonce_id>", methods=["DELETE"])
def delete_annonce(annonce_id):
    if 'direction_id' not in session:
        return jsonify({"success": False, "error": "Non autorisé"}), 401
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM annonces WHERE id = %s", (annonce_id,))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.route("/api/annonces/confirm", methods=["POST"])
def annonce_confirm():
    conn = None
    cur = None
    try:
        data = request.get_json()
        employe_id = data.get('employe_id')

        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "error": "Erreur DB"}), 500

        cur = conn.cursor(dictionary=True)

        # Récupérer les infos de l'employé
        cur.execute("SELECT name, role FROM personnel WHERE id = %s", (employe_id,))
        employe = cur.fetchone()

        if not employe:
            return jsonify({"success": False, "error": "Données introuvables"}), 404

        # Enregistrer la confirmation en historique
        cur.execute("INSERT INTO annonces_affichage (employe_id) VALUES (%s)", (employe_id,))
        conn.commit()

        # ✅ Fermer et rouvrir le curseur pour éviter "Unread result"
        cur.close()
        cur = conn.cursor(dictionary=True)

        # Envoi webhook Discord
        ADVERT_WEBHOOK = "https://discord.com/api/webhooks/1492893145778753836/o4nsA6zOKf5WTyBKiHdh9-cAHaMcWs5VRJg5uF2BO6IjHP6TVcHE8Y49HfYDUGN2HRk_"

        embed = {
            "title": f"📢 Advert confirmée le {now_paris().strftime('%d/%m/%Y %H:%M')}",
            "color": 3066993,
            "fields": [
                {
                    "name": "👤 Employé",
                    "value": f"{employe['name']} ({employe['role']})",
                    "inline": True
                }
            ],
            "footer": {"text": "LTD Mirror Park — Logs Adverts"},
            "timestamp": now_paris().isoformat()
        }

        embed["fields"] = [f for f in embed["fields"] if f.get("value")]

        response = requests.post(ADVERT_WEBHOOK, json={"embeds": [embed]})

        if response.status_code in (200, 204):
            return jsonify({"success": True})
        else:
            print(f"❌ Webhook error: {response.status_code} — {response.text}")
            return jsonify({"success": False, "error": f"Webhook Discord: {response.status_code}"}), 500

    except Exception as e:
        print(f"❌ Erreur annonce_confirm: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route("/api/annonces/last", methods=["GET"])
def get_last_advert():
    """Retourne la date du dernier advert confirmé (tous employés confondus)"""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"last": None})
        
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT date_affichage 
            FROM annonces_affichage 
            ORDER BY date_affichage DESC 
            LIMIT 1
        """)
        row = cur.fetchone()
        
        if row and row["date_affichage"]:
            dt = row["date_affichage"]
            if dt.tzinfo is None:
                dt = pytz.utc.localize(dt)
            return jsonify({"last": dt.isoformat()})
        
        return jsonify({"last": None})
    
    except Exception as e:
        print(f"❌ Erreur get_last_advert: {e}")
        return jsonify({"last": None})
    finally:
        if cur: cur.close()
        if conn: conn.close()

def format_date(value):
    if not value:
        return "—"
    
    # Si déjà datetime
    if hasattr(value, "strftime"):
        return value.strftime("%d/%m/%Y")
    
    # Si string
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").strftime("%d/%m/%Y")
        except:
            return value  # fallback si format bizarre
    
    return "—"

@app.route("/api/absences")
def get_absences():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify([])

        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT nom, prenom, date_debut, date_fin, raison
            FROM absences
            ORDER BY date_debut DESC
        """)
        rows = cur.fetchall()

        result = []
        for row in rows:
            result.append({
                "nom": row["nom"],
                "prenom": row["prenom"],
                "date_debut": format_date(row["date_debut"]),
                "date_fin": format_date(row["date_fin"]),
                "raison": row["raison"] or ""
            })

        return jsonify(result)

    except Exception as e:
        print(f"❌ Erreur get_absences: {e}")
        traceback.print_exc()
        return jsonify([])
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.route("/direction")
def direction_page():
    return render_template("direction.html")

@app.route("/employe")
def employe_page():
    return render_template("employe.html")

@app.route("/pricing")
def pricing_page():
    return render_template("pricing.html")

def is_user_in_guild(user_id):
    url = f"https://discord.com/api/v10/guilds/{DISCORD_GUILD_ID}/members/{user_id}"

    headers = {
        "Authorization": f"Bot {BOT_TOKEN}"
    }

    r = requests.get(url, headers=headers)

    return r.status_code == 200

@app.context_processor
def inject_discord_status():

    if current_user.is_authenticated:
        status = is_user_in_guild(current_user.discord_id)
    else:
        status = False

    return dict(discord_status=status)

# Route recrutement
@app.route("/recrutement")
@login_required
def recrutement():

    discord_status = is_user_in_guild(current_user.discord_id)

    return render_template(
        "recrutement.html",
        discord_status=discord_status
    )

@app.route("/commande")
@login_required
def commande():

    discord_status = is_user_in_guild(current_user.discord_id)
    
    return render_template(
        "commande.html",
        discord_status=discord_status
    )

# Ajouter cette route après les autres routes
@app.route("/api/submit_order", methods=["POST"])
def submit_order():
    """Route pour valider une commande et envoyer un embed Discord"""
    try:
        data = request.get_json()
        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "error": "Erreur DB"}), 500

        cur = conn.cursor()
        customer_name = data.get('customer_name')
        customer_phone = data.get('customer_phone', 'Non renseigné')
        delivery_method = data.get('delivery_method')
        items = data.get('items', [])
        total_price = data.get('total_price')
        total_weight = data.get('total_weight')
        order_date = data.get('order_date')
        discord_id = current_user.discord_id if current_user.is_authenticated else None

        cur.execute("""
        INSERT INTO orders (customer_name, customer_phone, delivery_method, total_price, total_weight, order_date, discord_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            customer_name,
            customer_phone,
            delivery_method,
            total_price,
            total_weight,
            order_date,
            discord_id
        ))

        order_id = cur.lastrowid
        # Construire la liste des produits pour l'embed
        products_list = []
        for item in items:
            cur.execute("""
            INSERT INTO order_items (order_id, product_name, quantity, price, weight)
            VALUES (%s, %s, %s, %s, %s)
            """, (
                order_id,
                item['name'],
                item['quantity'],
                item['totalPrice'],
                item['totalWeight']
            ))
            products_list.append(
                f"• **{item['name']}** x{item['quantity']} - "
                f"{item['totalPrice']:.2f}$ ({item['totalWeight']:.2f}kg)"
            )
        
        products_text = "\n".join(products_list) if products_list else "Aucun produit"
        
        # Limiter la longueur de l'embed (Discord limite à 4096 caractères)
        if len(products_text) > 3500:
            products_text = products_text[:3500] + "\n... (liste tronquée)"
        
        # Webhook Discord pour les commandes
        order_webhook = "https://discord.com/api/webhooks/1490703932937474208/Icjx9IWSqEEtMHyIsWaKsGfjjd15wnI5UDWI4-r3naqRQ53y1TrVn_7ewpjAfEH6hef3"
        
        embed = {
            "title": "🛒 NOUVEAU Click & Collect",
            "color": 15158332,
            "description": f"**Client :** {customer_name}\n"
                          f"**Téléphone :** {customer_phone}\n"
                          f"**Livraison :** {delivery_method}\n"
                          f"**Date :** {order_date}\n\n"
                          f"**📦 Produits commandés :**\n{products_text}\n\n"
                          f"**⚖️ Poids total :** {total_weight:.2f} kg\n"
                          f"**💰 Total à payer :** {total_price:.2f}$",
            "footer": {
                "text": "LTD Mirror Park - Click & Collect"
            },
            "timestamp": now_paris().isoformat()
        }
        
        # Ajouter un champ pour les infos supplémentaires si nécessaire
        if customer_phone != "Non renseigné":
            embed["fields"] = [
                {
                    "name": "📞 Contact client",
                    "value": customer_phone,
                    "inline": True
                }
            ]
        conn.commit()
        cur.close()
        conn.close()
        # Envoyer l'embed
        response = requests.post(order_webhook, json={"embeds": [embed]})
        
        if response.status_code == 204 or response.status_code == 200:
            return jsonify({
                "success": True,
                "message": "Click & Collect validé et envoyé sur Discord"
            })
        else:
            print(f"❌ Erreur webhook: {response.status_code} - {response.text}")
            return jsonify({
                "success": False,
                "error": f"Erreur d'envoi Discord: {response.status_code}"
            }), 500
            
    except Exception as e:
        print(f"❌ Erreur submit_order: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/avis")
def avis():
    return render_template("avis.html")

@app.route("/submit_review", methods=["POST"])
def submit_review():

    firstname = request.form.get("firstname")
    lastname = request.form.get("lastname")
    employee_id = request.form.get("employee_id")
    stars = request.form.get("stars")
    message = request.form.get("message")

    conn = get_db_connection()

    cur = conn.cursor(dictionary=True)

    # récupérer l'employé
    cur.execute("SELECT name, discord_id, role FROM personnel WHERE id=%s",(employee_id,))
    employee = cur.fetchone()

    if not employee:
        return jsonify({"success":False,"message":"Employé introuvable"})

    # enregistrer l'avis
    cur.execute("""
    INSERT INTO reviews(firstname,lastname,employee_id,stars,message)
    VALUES(%s,%s,%s,%s,%s)
    """,(firstname,lastname,employee_id,stars,message))

    conn.commit()

    cur.close()
    conn.close()

    # étoiles
    stars_text = "⭐"*int(stars)

    # WEBHOOK DISCORD
    webhook = "https://discord.com/api/webhooks/1482122375767265390/FH6mWGeh1XODdmTUA_EJHEDSAD-r8XXjEMCSENF7xamXkMrPIhxlOyLlxC5qrSzwK7bm"

    embed = {
        "title":"Nouvel avis client",
        "color":15844367,
        "description":f"""
                        👤 Client : **{firstname} {lastname}**

                        👨‍💼 Employé : <@{employee['discord_id']}>
                        🎖️ Grade : {employee['role']}

                        ⭐ Note : {stars_text}

                        💬 Message :
                        {message}
                        """,
                        }

    requests.post(webhook,json={"embeds":[embed]})

    return jsonify({
        "success":True,
        "message":"Avis envoyé merci !"
    })

# Route candidature
@app.route("/recruit", methods=["POST"])
@login_required
def recruit():
    if not is_user_in_guild(current_user.discord_id):
        return jsonify({
            "success": False,
            "error": "Vous devez être sur le Discord pour postuler"
        }), 403
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Non connecté"}), 401
    
    conn = None
    try:
        # Récupérer les données du formulaire
        fullname = request.form.get("name")
        dob = request.form.get("dob")
        rib = request.form.get("rib")
        tel = request.form.get("tel")
        experience = request.form.get("exp")
        dispo = request.form.get("dispo")
        motivations = request.form.get("motivation")
        
        # Validation basique
        if not all([fullname, dob, rib, tel, experience, dispo, motivations]):
            return jsonify({"success": False, "error": "Tous les champs sont requis"}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "error": "Erreur de connexion DB"}), 500
        
        cur = conn.cursor()
        
        # Insérer la candidature avec tous les champs
        cur.execute("""
            INSERT INTO recruitment 
            (username, fullname, discord_id, dob, rib, tel, experience, dispo, motivations) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            current_user.username,  # pseudo Discord
            fullname,
            current_user.discord_id,
            dob,
            rib,
            tel,
            experience,
            dispo,
            motivations
        ))
        
        conn.commit()
        cur.close()
        
        return jsonify({
            "success": True, 
            "message": "Candidature envoyée avec succès!"
        })
    
    except Exception as e:
        print(f"❌ Erreur recruit: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        if conn:
            conn.close()

# OAuth Discord
@app.route("/login")
def login():
    discord_auth_url = f"https://discord.com/api/oauth2/authorize?client_id={DISCORD_CLIENT_ID}&redirect_uri={DISCORD_REDIRECT_URI}&response_type=code&scope=identify"
    return redirect(discord_auth_url)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    
    # Échange du code contre un token
    data = {
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": DISCORD_REDIRECT_URI
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    try:
        # Récupération du token
        r = requests.post("https://discord.com/api/oauth2/token", data=data, headers=headers, timeout=10)
        if r.status_code != 200:
            return "Erreur d'authentification Discord", 400
        
        token = r.json()["access_token"]
        
        # Récupération des infos utilisateur
        user_req = requests.get("https://discord.com/api/users/@me", 
                               headers={"Authorization": f"Bearer {token}"}, 
                               timeout=10)
        discord_user = user_req.json()
        
        # Connexion/inscription en base
        conn = get_db_connection()
        if not conn:
            return "Erreur DB", 500
        
        cur = conn.cursor(dictionary=True)
        
        # Vérifier si l'utilisateur existe
        cur.execute("SELECT id FROM users WHERE discord_id=%s", (discord_user["id"],))
        existing = cur.fetchone()
        
        if existing:
            user_id = existing["id"]
        else:
            # Créer nouvel utilisateur
            cur.execute("INSERT INTO users(username, discord_id) VALUES (%s, %s)", 
                        (discord_user["username"], discord_user["id"]))
            conn.commit()
            user_id = cur.lastrowid
        
        cur.close()
        conn.close()
        
        # Créer session
        user = User(user_id, discord_user["username"], discord_user["id"])
        login_user(user)
        session["user_id"] = user_id
        
        return redirect(url_for("index"))
    
    except Exception as e:
        print(f"❌ Erreur callback Discord: {e}")
        return f"Erreur: {str(e)}", 500

@app.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("index"))

@app.route("/api/personnel")
def api_personnel():
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify([])
        
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, name, role, discord_id FROM personnel")
        personnel = cur.fetchall()
        cur.close()
        
        return jsonify(personnel)
    
    except Exception as e:
        print(f"❌ Erreur API personnel: {e}")
        return jsonify([])
    finally:
        if conn:
            conn.close()

# Route ping
@app.route("/ping")
def ping():
    return "pong"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)