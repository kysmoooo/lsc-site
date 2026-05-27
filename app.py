from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
import mysql.connector
from mysql.connector import Error
import requests
import os
import traceback
from datetime import datetime
import pytz
from functools import wraps
from datetime import timedelta

PARIS_TZ = pytz.timezone("Europe/Paris")

def now_paris():
    return datetime.now(PARIS_TZ)

def format_date():
    return now_paris().strftime("%d/%m/%Y à %H:%M:%S")

def date_format(date):
    # Si c'est déjà une string, la parser d'abord
    if isinstance(date, str):
        date = datetime.fromisoformat(date)
    return date.strftime("%d/%m/%Y")
    
app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "e70347e86f09c362df99758723597361e12fd197d16a3275e21504b4df99cbcc")
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = True  # ton site est en HTTPS

# Configuration MySQL
DB_CONFIG = {
    'host': os.environ.get("DB_HOST", "nozomi.proxy.rlwy.net"),
    'port': int(os.environ.get("DB_PORT", 46434)),
    'database': os.environ.get("DB_NAME", "railway"),
    'user': os.environ.get("DB_USER", "root"),
    'password': os.environ.get("DB_PASSWORD", "puPqRYWigeOxenQOZRNhGmsfxKRdbYbP"),
    'connection_timeout': 5,
    'autocommit': True
}

# Configuration Discord
DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "814277691981168680")
DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "nfnAJBlnt1TvBIfPcdAT0Cacn2nSL4rF")
DISCORD_REDIRECT_URI = os.environ.get("DISCORD_REDIRECT_URI", "https://www.lscustoms-gliferp.fr/callback")
DISCORD_GUILD_ID = "925525617863184445"
BOT_TOKEN = os.environ.get("DISCORD_TOKEN")
WEBHOOK_SERVICE = os.environ.get("SERVICE_WEBHOOK", "")
WEBHOOK_ADVERT  = os.environ.get("ADVERT_WEBHOOK",  "")
DIRECTION_PING_ROLE_ID = 1509192397622481077
DIRECTION_ROLE_ID = 1075809086173618266

DEV_MODE = False

# Login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth_discord'

@app.before_request
def make_session_permanent():
    session.permanent = True

# Classe User
class User(UserMixin):
    def __init__(self, id, username, discord_id, avatar):
        self.id = id
        self.username = username
        self.discord_id = discord_id
        self.avatar = avatar

@login_manager.user_loader
def load_user(user_id):
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return None
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, username, discord_id, avatar_url FROM users WHERE id=%s", (int(user_id),))
        user = cur.fetchone()
        cur.close()
        if user:
            return User(user['id'], user['username'], user['discord_id'], user.get('avatar_url'))
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

def require_direction(f):
    """Décorateur pour les routes nécessitant un accès direction"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'direction_id' not in session:
            return jsonify({"success": False, "error": "Non autorisé"}), 401
        return f(*args, **kwargs)
    return decorated_function

def is_user_in_guild(user_id):
    if DEV_MODE:
        return True
    url = f"https://discord.com/api/v10/guilds/{DISCORD_GUILD_ID}/members/{user_id}"
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    try:
        r = requests.get(url, headers=headers)
        return r.status_code == 200
    except:
        return False

@app.context_processor
def inject_discord_status():
    if current_user.is_authenticated:
        status = is_user_in_guild(current_user.discord_id)
    else:
        status = False
    return dict(discord_status=status)

# ========== ROUTES PAGES STATIQUES ==========
@app.route("/")
def index():
    return render_template('index.html')

@app.route("/personnel.html")
def staff_page():
    return render_template('personnel.html')

@app.route("/recrutement.html")
@login_required
def recruitment_page():
    discord_status = is_user_in_guild(current_user.discord_id)
    return render_template(
        "recrutement.html",
        discord_status=discord_status
    )

@app.route("/pricing.html")
def pricing_page():
    return render_template('pricing.html')

@app.route("/employe.html")
def employe_page():
    session.pop('employe_id', None)
    return render_template('employe.html')

@app.route("/direction.html")
def direction_page():
    session.pop('direction_id', None)
    return render_template('direction.html')

@app.route("/commande.html")
@login_required
def clickcollect_page():
    discord_status = is_user_in_guild(current_user.discord_id)
    return render_template(
        "commande.html",
        discord_status=discord_status
    )

@app.route("/css/<path:filename>")
def serve_css(filename):
    return render_template('css', filename)

@app.route("/js/<path:filename>")
def serve_js(filename):
    return render_template('js', filename)

@app.route("/employe/register", methods=["POST"])
@login_required  # doit être connecté Discord
def employe_register():
    data     = request.get_json()
    password = (data.get('password') or '').strip()

    if not password:
        return jsonify({"success": False, "error": "Mot de passe manquant"}), 400

    # Vérifier membre du Discord
    if not is_user_in_guild(current_user.discord_id):
        return jsonify({"success": False, "error": "Vous devez être membre du Discord."}), 403

    username = current_user.username  # pseudo Discord automatique

    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "error": "Erreur DB"}), 500

    try:
        cur = conn.cursor(dictionary=True, buffered=True)
        cur.execute(
            "SELECT id, active FROM staff_profiles WHERE username = %s",
            (username,)
        )
        employe = cur.fetchone()
        
        # ✅ Check if employee exists
        if not employe:
            cur.close()
            conn.close()
            return jsonify({"success": False, "error": f"Aucun profil trouvé pour {username}. Contactez la direction."}), 404

        cur.execute(
            """UPDATE staff_profiles SET password_hash = %s, active = 0 WHERE id = %s""",
            (password, employe['id'],)
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True})

    except Exception as e:
        print(f"❌ Erreur register: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/direction/inscriptions")
@require_direction
def direction_get_inscriptions():
    conn = get_db_connection()
    if not conn:
        return jsonify([])
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """SELECT id, username, created_at
               FROM staff_profiles
               WHERE active = 0
               ORDER BY created_at DESC"""
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(rows)
    except Exception as e:
        print(f"❌ Erreur get inscriptions: {e}")
        return jsonify([])


@app.route("/api/direction/inscriptions/<int:user_id>/<action>", methods=["POST"])
@require_direction
def direction_handle_inscription(user_id, action):
    if action not in ('accept', 'reject'):
        return jsonify({"success": False, "error": "Action invalide"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "error": "Erreur DB"}), 500
    try:
        cur = conn.cursor()
        if action == 'accept':
            cur.execute(
                "UPDATE staff_profiles SET active = 1 WHERE id = %s AND active = 0",
                (user_id,)
            )
        else:
            cur.execute(
                "DELETE FROM staff_profiles WHERE id = %s AND active = 0",
                (user_id,)
            )
        conn.commit()
        affected = cur.rowcount
        cur.close()
        conn.close()
        if affected == 0:
            return jsonify({"success": False, "error": "Introuvable ou déjà traité"}), 404
        return jsonify({"success": True})
    except Exception as e:
        print(f"❌ Erreur handle inscription: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ========== API STAFF ==========
@app.route("/api/staff")
def api_staff():
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify([])
        
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT id, name, role, specialty, photo_url, sort_order, active, category,
                   (SELECT COUNT(*) FROM staff_reviews WHERE staff_profile_id = staff_profiles.id) as review_count,
                   (SELECT AVG(rating) FROM staff_reviews WHERE staff_profile_id = staff_profiles.id) as avg_rating
            FROM staff_profiles
            WHERE active = 1
            ORDER BY sort_order ASC
        """)
        staff = cur.fetchall()
        cur.close()
        
        return jsonify(staff)
    
    except Exception as e:
        print(f"❌ Erreur API staff: {e}")
        return jsonify([])
    finally:
        if conn:
            conn.close()

@app.route("/api/staff-reviews", methods=["POST"])
def submit_staff_review():
    try:
        data = request.get_json()
        staff_id = data.get('staffId')
        staff_name = data.get('staffName')
        rating = data.get('rating')
        comment = data.get('comment')
        reviewer = data.get('reviewer')
        
        if not all([staff_id, rating, comment, reviewer]):
            return jsonify({"success": False, "error": "Champs manquants"}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "error": "Erreur DB"}), 500
        
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO staff_reviews (staff_profile_id, staff_name_snapshot, reviewer_name, rating, comment, discord_sent, discord_sent_at, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (staff_id, staff_name, reviewer, rating, comment, 1, now_paris(), now_paris()))
        conn.commit()
        cur.close()
        conn.close()
        
        # Webhook Discord pour les avis
        webhook = os.environ.get("REVIEW_WEBHOOK", "https://discord.com/api/webhooks/1495174985256272014/b04LBEKNMHVG6XXUFeN_e7Dh6sQv3TuTDJY1J9Mb-chVv1xFDunzUQnHmr2eZ_Srxc5o")
        
        stars_text = "⭐" * int(rating)
        embed = {
            "title": "⭐ Nouvel avis sur le personnel",
            "color": 15844367,
            "description": f"""
👤 Client : **{reviewer}**

👨‍💼 Employé : **{staff_name}**
⭐ Note : {stars_text}

💬 Message :
{comment}
            """
        }
        
        try:
            requests.post(webhook, json={"embeds": [embed]}, timeout=2)
        except:
            pass
        
        return jsonify({"success": True, "message": "Avis envoyé avec succès"})
    
    except Exception as e:
        print(f"❌ Erreur submit_staff_review: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ========== API RECRUTEMENT ==========
@app.route("/api/applications", methods=["POST"])
@login_required
def post_application():
    try:
        data = request.get_json()
        
        if not current_user.is_authenticated:
            return jsonify({"success": False, "error": "Non authentifié"}), 401
        
        if not is_user_in_guild(current_user.discord_id):
            return jsonify({"success": False, "error": "Vous devez être sur le Discord pour postuler"}), 403
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "error": "Erreur DB"}), 500
        
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO applications 
            (username, full_name, discord_tag, avatar_url, birth_date, phone, rib, experience, availability, motivation, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s)
        """, (
            data.get('username'),
            data.get('fullName'),
            data.get('discordTag'),
            data.get('avatarUrl'),
            data.get('birthDate'),
            data.get('phone'),
            data.get('rib'),
            data.get('experience'),
            data.get('availability'),
            data.get('motivation'),
            now_paris()
        ))
        conn.commit()
        application_id = cur.lastrowid
        cur.close()
        conn.close()
        
        webhook = os.environ.get("APPLICATION_WEBHOOK", "")
        if webhook:
            embed = {
                "title": "📝 Nouvelle candidature reçue",
                "color": 3066993,
                "fields": [
                    {"name": "Nom complet", "value": data.get('fullName'), "inline": True},
                    {"name": "Discord", "value": data.get('discordTag'), "inline": True},
                    {"name": "Téléphone", "value": data.get('phone'), "inline": True}
                ]
            }
            try:
                requests.post(webhook, json={"embeds": [embed]}, timeout=2)
            except:
                pass
        
        return jsonify({"success": True, "id": application_id})
    
    except Exception as e:
        print(f"❌ Erreur POST application: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/applications", methods=["GET"])
@require_direction
def get_applications():
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify([])
        
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT id, full_name, discord_tag, status, created_at
            FROM applications
            ORDER BY created_at DESC
        """)
        applications = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify(applications)
    
    except Exception as e:
        print(f"❌ Erreur GET applications: {e}")
        return jsonify([])

@app.route("/api/applications/<int:app_id>")
@require_direction
def get_application_detail(app_id):
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Erreur DB"}), 500
        
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT id, full_name, discord_tag, avatar_url, birth_date, phone, rib, experience, availability, motivation, status, created_at
            FROM applications
            WHERE id = %s
        """, (app_id,))
        application = cur.fetchone()
        cur.close()
        conn.close()
        
        if not application:
            return jsonify({"error": "Candidature non trouvée"}), 404
        
        return jsonify(application)
    
    except Exception as e:
        print(f"❌ Erreur GET application detail: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/applications/<int:app_id>/status", methods=["PATCH"])
@require_direction
def update_application_status(app_id):
    try:
        data = request.get_json()
        new_status = data.get('status')
        
        if new_status not in ['pending', 'accepted', 'rejected', 'closed']:
            return jsonify({"error": "Statut invalide"}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Erreur DB"}), 500
        
        cur = conn.cursor()
        cur.execute("""
            UPDATE applications
            SET status = %s
            WHERE id = %s
        """, (new_status, app_id))
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({"success": True, "status": new_status})
    
    except Exception as e:
        print(f"❌ Erreur PATCH application status: {e}")
        return jsonify({"error": str(e)}), 500

# ========== API GESTION DES ABSENCES ==========
@app.route("/api/absences", methods=["GET"])
@require_direction
def get_absences():
    """Récupère la liste de toutes les absences"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify([])
        
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT id, name, start_date, end_date, motif, created_at
            FROM absences
            ORDER BY start_date DESC
        """)
        absences = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify(absences)
    
    except Exception as e:
        print(f"❌ Erreur GET absences: {e}")
        return jsonify([])

@app.route("/api/absences", methods=["POST"])
@require_direction
def create_absence():
    """Crée une nouvelle absence"""
    try:
        data = request.get_json()
        name = data.get('name')
        start_date = data.get('startDate')
        end_date = data.get('endDate')
        
        if not all([name, start_date, end_date]):
            return jsonify({"success": False, "error": "Champs manquants"}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "error": "Erreur DB"}), 500
        
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO absences (name, start_date, end_date, created_at)
            VALUES (%s, %s, %s, %s)
        """, (name, start_date, end_date, now_paris()))
        conn.commit()
        absence_id = cur.lastrowid
        cur.close()
        conn.close()
        
        return jsonify({"success": True, "id": absence_id})
    
    except Exception as e:
        print(f"❌ Erreur POST absence: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/absences/<int:absence_id>", methods=["DELETE"])
@require_direction
def delete_absence(absence_id):
    """Supprime une absence"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "error": "Erreur DB"}), 500
        
        cur = conn.cursor()
        cur.execute("DELETE FROM absences WHERE id = %s", (absence_id,))
        conn.commit()
        rows_affected = cur.rowcount
        cur.close()
        conn.close()
        
        if rows_affected == 0:
            return jsonify({"success": False, "error": "Absence non trouvée"}), 404
        
        return jsonify({"success": True})
    
    except Exception as e:
        print(f"❌ Erreur DELETE absence: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ─────────────────────────────────────────────────
# AUTH EMPLOYÉ
# ─────────────────────────────────────────────────

def require_employe(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'employe_id' not in session:
            return jsonify({"success": False, "error": "Non autorisé"}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route("/employe/login", methods=["POST"])
def employe_login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Erreur DB"}), 500
    
    cur = conn.cursor(dictionary=True)
    cur.execute(
        "SELECT id, username, name as display_name, role FROM staff_profiles WHERE username=%s AND password_hash=%s AND active=1",
        (username, password)
    )
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    if user:
        session.permanent = True
        session['employe_id'] = user['id']  # Maintenant c'est l'ID de staff_profiles
        return jsonify({
            "success": True,
            "user": {"id": user['id'], "username": user['username'],
                    "displayName": user['display_name'], "role": user['role']}
        })
    return jsonify({"success": False}), 401

# Mettre à jour get_active_debut (pas de changement, déjà utilise services.employe_id)
# Mettre à jour _end_service (pas de changement)

# Modifier employe_me pour utiliser staff_profiles
@app.route("/employe/me")
def employe_me():
    if 'employe_id' in session:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor(dictionary=True)
            # CHANGEMENT ICI
            cur.execute("SELECT id, username, name as display_name, role FROM staff_profiles WHERE id=%s AND active=1", (session['employe_id'],))
            user = cur.fetchone()
            cur.close()
            conn.close()
            if user:
                return jsonify({"user": {
                    "id": user['id'],
                    "username": user['username'],
                    "displayName": user['display_name'],
                    "role": user['role']
                }})
    return jsonify({"user": None})
 
 
# ─────────────────────────────────────────────────
# HELPERS — Logique basée sur paires debut/fin
#
# Un service actif = dernière ligne de l'employé a action='debut'
# Un service terminé = paire debut+fin (même employe_id, fin.heure > debut.heure)
# ─────────────────────────────────────────────────
 
def get_active_debut(conn, employe_id):
    """
    Retourne la ligne 'debut' active (sans 'fin' correspondante après).
    Logique : la dernière ligne de l'employé est un 'debut'.
    """
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT id, heure FROM services
        WHERE employe_id = %s
        ORDER BY heure DESC, id DESC
        LIMIT 1
    """, (employe_id,))
    last = cur.fetchone()
    cur.close()
    if last and last['action'] == 'debut' if 'action' in (last or {}) else False:
        return last
    # Refaire avec action explicite
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT id, heure, action FROM services
        WHERE employe_id = %s
        ORDER BY heure DESC, id DESC
        LIMIT 1
    """, (employe_id,))
    last = cur.fetchone()
    cur.close()
    if last and last['action'] == 'debut':
        return last
    return None
 
def get_last_advert_time(employe_id):
    """Récupère le timestamp du dernier advert confirmé depuis advert_logs"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT done_at FROM advert_logs WHERE employe_id=%s ORDER BY done_at DESC LIMIT 1",
            (employe_id,)
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row['done_at'] if row else None
    except:
        return None

def get_last_advert_time_global():
    """Récupère le timestamp du dernier advert confirmé (tous employés confondus)"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT done_at FROM advert_logs ORDER BY done_at DESC LIMIT 1"
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row['done_at'] if row else None
    except:
        return None

@app.route("/employe/advert/last-global")
@require_employe
def employe_advert_last_global():
    last = get_last_advert_time_global()
    return jsonify({
        "last_advert_time": last.isoformat() if last else None
    })

# ─── ABSENCE (employé) ───────────────────────────────────────
@app.route("/employe/absence/submit", methods=["POST"])
@require_employe
def employe_absence_submit():
    employe_id = session['employe_id']
    data = request.get_json()
    start_date = data.get('start_date')
    end_date   = data.get('end_date')
    motif      = data.get('motif', '').strip()

    if not all([start_date, end_date, motif]):
        return jsonify({"success": False, "error": "Champs manquants"}), 400
    if end_date < start_date:
        return jsonify({"success": False, "error": "Date de fin invalide"}), 400
    if len(motif) > 150:
        return jsonify({"success": False, "error": "Le motif ne peut pas dépasser 150 caractères"}), 400
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "error": "Erreur DB"}), 500

        # Récupérer le nom de l'employé
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT name FROM staff_profiles WHERE id=%s", (employe_id,))
        emp = cur.fetchone()
        name = emp['name'] if emp else f"Employé #{employe_id}"

        cur.execute("""
            INSERT INTO absences (name, start_date, end_date, motif, created_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (name, start_date, end_date, motif, now_paris()))
        conn.commit()
        absence_id = cur.lastrowid
        cur.close()
        conn.close()

        absence_webhook = os.environ.get("ABSENCE_WEBHOOK", "https://discord.com/api/webhooks/1502415590583832697/ftYUg_BSlOM2RlJFV41xedGhd6gX722HVLJPyUK6czyfqri1ZEAe-izOwsZzgOBaVymr")
        date_1 = date_format(start_date)
        date_2 = date_format(end_date)
        embed = {
            "title": f"Absence déclarée par {name}",
            "color": 15158332,
            "description": f"**{name}** sera absent du :\n{date_1} **au :** {date_2}\n**Pour motif :** {motif}\n",
            "footer": {"text": "LS Customs - Absence"},
            "timestamp": now_paris().isoformat()
        }

        try:
            r = requests.post(absence_webhook, json={"embeds": [embed]}, timeout=2)
            print(f"Webhook response: {r.status_code} - {r.text}")
        except Exception as e:
            print(f"Webhook error: {e}")

        return jsonify({"success": True, "id": absence_id})

    except Exception as e:
        print(f"❌ Erreur employe_absence_submit: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ─────────────────────────────────────────────────
# SERVICE
# ─────────────────────────────────────────────────
 
@app.route("/employe/service/start", methods=["POST"])
@require_employe
def employe_service_start():
    employe_id = session['employe_id']
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "error": "Erreur DB"}), 500
 
        # Vérifier si déjà en service
        debut = get_active_debut(conn, employe_id)
        if debut:
            conn.close()
            return jsonify({"success": False, "error": "Déjà en service"}), 400
 
        # Récupérer nom employé
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT name as display_name FROM staff_profiles WHERE id=%s", (employe_id,))
        emp = cur.fetchone()
        name = emp['display_name'] if emp else 'Employé'
        cur.close()
 
        now = now_paris()
        cur2 = conn.cursor()
        cur2.execute(
            "INSERT INTO services (employe_id, action, heure) VALUES (%s, 'debut', %s)",
            (employe_id, now)
        )
        conn.commit()
        debut_id = cur2.lastrowid
        cur2.close()
        conn.close()
 
        # Stocker heure de début en session pour le timer côté serveur
        session[f'service_start_{employe_id}'] = now.isoformat()
        maintenant = format_date()
        if WEBHOOK_SERVICE:
            embed = {
                "title": "🟢 Prise de service",
                "color": 3066993,
                "description": f"**{name}** a pris son service le **{maintenant}**",
                "timestamp": now.isoformat()
            }
            try:
                requests.post(WEBHOOK_SERVICE, json={"embeds": [embed]}, timeout=2)
            except:
                pass
 
        return jsonify({"success": True, "debut_id": debut_id, "start_time": now.isoformat()})
 
    except Exception as e:
        print(f"❌ Erreur service start: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
 
 
@app.route("/employe/service/end", methods=["POST"])
@require_employe
def employe_service_end():
    employe_id = session['employe_id']
    return _end_service(employe_id)
 
 
def _end_service(employe_id, forced_by=None):
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "error": "Erreur DB"}), 500
 
        debut = get_active_debut(conn, employe_id)
        if not debut:
            conn.close()
            return jsonify({"success": False, "error": "Aucun service actif"}), 404
 
        # Récupérer nom employé
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT name as display_name FROM staff_profiles WHERE id=%s", (employe_id,))
        emp = cur.fetchone()
        name = emp['display_name'] if emp else 'Employé'
        cur.close()
 
        now = now_paris()
        start_time = debut['heure']
        if hasattr(start_time, 'tzinfo') and start_time.tzinfo is None:
            start_time = PARIS_TZ.localize(start_time)
 
        duration = int((now - start_time).total_seconds() / 60)
 
        # Insérer la ligne 'fin'
        cur2 = conn.cursor()
        cur2.execute(
            "INSERT INTO services (employe_id, action, heure) VALUES (%s, 'fin', %s)",
            (employe_id, now)
        )
        conn.commit()
        cur2.close()
        conn.close()
 
        # Nettoyer la session
        session.pop(f'service_start_{employe_id}', None)
 
        h = duration // 60
        m = duration % 60
        dur_str = f"{h}h {m}min" if h > 0 else f"{m}min"
 
        if WEBHOOK_SERVICE:
            forced_txt = f"\n⚠️ Fin forcée par **{forced_by}**" if forced_by else ""
            if h < 1:
                embed = {
                    "title": "🔴 Fin de service",
                    "color": 15158332,
                    "description": f"**{name}** a terminé son service.\n⏱ Durée : **{dur_str}**{forced_txt}",
                    "timestamp": now.isoformat()
                }
                embed2 = {
                    "title": "Service de **Moins d'une heure**",
                    "color": 15158332,
                    "description": f"<@&{DIRECTION_PING_ROLE_ID}> Eh oh {name} à fait moins d'une heure ! ({dur_str})",
                    "timestamp": now.isoformat()
                }
            else:
                embed = {
                    "title": "🔴 Fin de service",
                    "color": 15158332,
                    "description": f"**{name}** a terminé son service.\n⏱ Durée : **{dur_str}**{forced_txt}",
                    "timestamp": now.isoformat()
                }
            try:
                requests.post(WEBHOOK_SERVICE, json={"embeds": [embed]}, timeout=2)

                if h < 1:
                    requests.post(
                        WEBHOOK_SERVICE,
                        json={
                            "content": f"<@&{DIRECTION_PING_ROLE_ID}>",
                            "embeds": [embed2]
                        },
                        timeout=2
                    )

            except Exception as e:
                print(e)
 
        return jsonify({"success": True, "duration_minutes": duration})
 
    except Exception as e:
        print(f"❌ Erreur service end: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
 
 
@app.route("/employe/service/current")
@require_employe
def employe_service_current():
    employe_id = session['employe_id']
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"active": False})
 
        debut = get_active_debut(conn, employe_id)
        conn.close()
 
        if debut:
            last_advert = get_last_advert_time(employe_id)
            return jsonify({
                "active": True,
                "service": {
                    "id": debut['id'],
                    "start_time": debut['heure'].isoformat() if debut['heure'] else None,
                    "last_advert_time": last_advert.isoformat() if last_advert else debut['heure'].isoformat()
                }
            })
        return jsonify({"active": False})
    except Exception as e:
        print(f"❌ service current: {e}")
        return jsonify({"active": False})
 
 
@app.route("/employe/service/count")
def employe_service_count():
    """Compte les employés dont la dernière ligne est un 'debut'"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"count": 0})
 
        cur = conn.cursor(dictionary=True)
        # Pour chaque employé, regarder si sa dernière action est 'debut'
        cur.execute("""
            SELECT COUNT(*) as cnt FROM (
                SELECT employe_id
                FROM services s1
                WHERE s1.id = (
                    SELECT id FROM services s2
                    WHERE s2.employe_id = s1.employe_id
                    ORDER BY heure DESC, id DESC
                    LIMIT 1
                )
                AND s1.action = 'debut'
            ) as actifs
        """)
        row = cur.fetchone()
        cur.close()
        conn.close()
        return jsonify({"count": row['cnt'] if row else 0})
    except Exception as e:
        print(f"❌ service count: {e}")
        return jsonify({"count": 0})
 
 
@app.route("/employe/service/history")
@require_employe
def employe_service_history():
    """
    Reconstruit les paires debut/fin pour afficher l'historique.
    Chaque service = 1 ligne debut + 1 ligne fin (ou en cours si pas de fin).
    """
    employe_id = session['employe_id']
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"services": []})
 
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT id, action, heure
            FROM services
            WHERE employe_id = %s
            ORDER BY heure ASC, id ASC
        """, (employe_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
 
        # Reconstruire les paires debut/fin
        services = []
        pending_debut = None
 
        for row in rows:
            if row['action'] == 'debut':
                pending_debut = row
            elif row['action'] == 'fin' and pending_debut:
                start = pending_debut['heure']
                end = row['heure']
                if hasattr(start, 'tzinfo') and start.tzinfo is None:
                    start = PARIS_TZ.localize(start)
                if hasattr(end, 'tzinfo') and end.tzinfo is None:
                    end = PARIS_TZ.localize(end)
                duration = int((end - start).total_seconds() / 60)
                services.append({
                    "id": pending_debut['id'],
                    "start_time": pending_debut['heure'].isoformat(),
                    "end_time": row['heure'].isoformat(),
                    "duration_minutes": duration
                })
                pending_debut = None
 
        # Service en cours (debut sans fin)
        if pending_debut:
            services.append({
                "id": pending_debut['id'],
                "start_time": pending_debut['heure'].isoformat(),
                "end_time": None,
                "duration_minutes": None
            })
 
        # Trier du plus récent au plus ancien
        services.reverse()
        return jsonify({"services": services[:50]})
 
    except Exception as e:
        print(f"❌ Erreur history: {e}")
        return jsonify({"services": []})
 
 
# ─────────────────────────────────────────────────
# ADVERT
# ─────────────────────────────────────────────────
 
@app.route("/employe/advert/confirm", methods=["POST"])
@require_employe
def employe_advert_confirm():
    employe_id = session['employe_id']
    data = request.get_json()
    advert_id = data.get('advert_id')
    advert_titre = data.get('advert_titre', 'Sans titre')
 
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "error": "Erreur DB"}), 500
 
        debut = get_active_debut(conn, employe_id)
        conn.close()
 
        if not debut:
            return jsonify({"success": False, "error": "Pas de service actif"}), 400
 
        # Récupérer nom employé
        conn2 = get_db_connection()
        cur = conn2.cursor(dictionary=True)
        cur.execute("SELECT name as display_name FROM staff_profiles WHERE id=%s", (employe_id,))
        emp = cur.fetchone()
        name = emp['display_name'] if emp else 'Employé'
 
        now = now_paris()
        cur.execute(
            "INSERT INTO advert_logs (employe_id, employe_name, advert_id, advert_titre, done_at) VALUES (%s, %s, %s, %s, %s)",
            (employe_id, name, "1", "Advert", now)
        )
        conn2.commit()
        cur.close()
        conn2.close()
        maintenant = format_date()
        if WEBHOOK_ADVERT:
            embed = {
                "title": "📢 Advert confirmé",
                "color": 3066993,
                "description": f"**{name}** a fait l'advert le **{maintenant}**.",
                "timestamp": now.isoformat()
            }
            try:
                requests.post(WEBHOOK_ADVERT, json={"embeds": [embed]}, timeout=2)
            except:
                pass
 
        return jsonify({"success": True})
 
    except Exception as e:
        print(f"❌ Erreur advert confirm: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
 
@app.route("/employe/advert/last")
@require_employe
def employe_advert_last():
    employe_id = session['employe_id']
    last = get_last_advert_time(employe_id)
    return jsonify({
        "last_advert_time": last.isoformat() if last else None
    })
 
# ─────────────────────────────────────────────────
# ANNONCES PUBLIQUES
# ─────────────────────────────────────────────────
 
@app.route("/api/annonces/public")
def get_annonces_public():
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify([])
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, titre, image_url, texte FROM annonces ORDER BY updated_at DESC")
        annonces = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(annonces)
    except:
        return jsonify([])
 
 
# ─────────────────────────────────────────────────
# DIRECTION — SUIVI EMPLOYÉS
# ─────────────────────────────────────────────────
 
def get_all_active_services(conn):
    """Retourne la liste des employe_id dont la dernière ligne est 'debut', avec l'heure"""
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT s1.id, s1.employe_id, s1.heure
        FROM services s1
        WHERE s1.id = (
            SELECT id FROM services s2
            WHERE s2.employe_id = s1.employe_id
            ORDER BY heure DESC, id DESC
            LIMIT 1
        )
        AND s1.action = 'debut'
    """)
    rows = cur.fetchall()
    cur.close()
    return rows
 
 
@app.route("/api/direction/services/actifs")
@require_direction
def direction_services_actifs():
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify([])
 
        actifs = get_all_active_services(conn)
 
        # Enrichir avec le nom de l'employé
        result = []
        for s in actifs:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT name as display_name FROM staff_profiles WHERE id=%s", (s['employe_id'],))
            emp = cur.fetchone()
            cur.close()
            name = emp['display_name'] if emp else f"Employé #{s['employe_id']}"
 
            start = s['heure']
            if hasattr(start, 'tzinfo') and start.tzinfo is None:
                start = PARIS_TZ.localize(start)
            duration = int((now_paris() - start).total_seconds() / 60)
 
            result.append({
                "id": s['id'],
                "employe_id": s['employe_id'],
                "employe_name": name,
                "start_time": s['heure'].isoformat(),
                "duration_minutes": duration
            })
 
        conn.close()
        return jsonify(result)
 
    except Exception as e:
        print(f"❌ Erreur services actifs: {e}")
        return jsonify([])
 
 
@app.route("/api/direction/employes/suivi")
@require_direction
def direction_employes_suivi():
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify([])
 
        actifs = get_all_active_services(conn)
        actifs_ids = {s['employe_id'] for s in actifs}
 
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, name as display_name, role FROM staff_profiles WHERE active=1 ORDER BY display_name ASC")
        employes = cur.fetchall()
        cur.close()
 
        result = []
        for emp in employes:
            # Compter les services cette semaine (lignes 'debut' des 7 derniers jours)
            cur2 = conn.cursor(dictionary=True)
            cur2.execute("""
                SELECT COUNT(*) as cnt FROM services
                WHERE employe_id=%s AND action='debut'
                AND heure >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            """, (emp['id'],))
            row = cur2.fetchone()
            cur2.close()
 
            result.append({
                "id": emp['id'],
                "display_name": emp['display_name'],
                "role": emp['role'],
                "services_semaine": row['cnt'] if row else 0,
                "en_service": 1 if emp['id'] in actifs_ids else 0
            })
 
        conn.close()
        return jsonify(result)
 
    except Exception as e:
        print(f"❌ Erreur suivi employés: {e}")
        return jsonify([])
 
 
@app.route("/api/direction/employes/<int:emp_id>/services")
@require_direction
def direction_employe_services(emp_id):
    """Reconstruit les paires debut/fin pour un employé donné"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"services": []})
 
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT id, action, heure FROM services
            WHERE employe_id=%s
            ORDER BY heure ASC, id ASC
        """, (emp_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
 
        services = []
        pending_debut = None
 
        for row in rows:
            if row['action'] == 'debut':
                pending_debut = row
            elif row['action'] == 'fin' and pending_debut:
                start = pending_debut['heure']
                end = row['heure']
                if hasattr(start, 'tzinfo') and start.tzinfo is None:
                    start = PARIS_TZ.localize(start)
                if hasattr(end, 'tzinfo') and end.tzinfo is None:
                    end = PARIS_TZ.localize(end)
                duration = int((end - start).total_seconds() / 60)
                services.append({
                    "id": pending_debut['id'],
                    "start_time": pending_debut['heure'].isoformat(),
                    "end_time": row['heure'].isoformat(),
                    "duration_minutes": duration
                })
                pending_debut = None
 
        if pending_debut:
            services.append({
                "id": pending_debut['id'],
                "start_time": pending_debut['heure'].isoformat(),
                "end_time": None,
                "duration_minutes": None
            })
 
        services.reverse()
        return jsonify({"services": services[:100]})
 
    except Exception as e:
        print(f"❌ Erreur employe services: {e}")
        return jsonify({"services": []})
 
 
@app.route("/api/direction/services/<int:debut_id>/force-end", methods=["POST"])
@require_direction
def direction_force_end_service(debut_id):
    """
    Force la fin de service en insérant une ligne 'fin'.
    debut_id = l'id de la ligne 'debut' active.
    """
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "error": "Erreur DB"}), 500
 
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT employe_id, heure, action FROM services WHERE id=%s",
            (debut_id,)
        )
        service = cur.fetchone()
        cur.close()
 
        if not service or service['action'] != 'debut':
            conn.close()
            return jsonify({"success": False, "error": "Service introuvable ou déjà terminé"}), 404
 
        # Vérifier que c'est bien le dernier debut (actif)
        debut = get_active_debut(conn, service['employe_id'])
        if not debut or debut['id'] != debut_id:
            conn.close()
            return jsonify({"success": False, "error": "Ce service n'est plus actif"}), 400
 
        conn.close()
 
        # Récupérer nom direction
        dir_name = "Direction"
        conn2 = get_db_connection()
        if conn2:
            cur2 = conn2.cursor(dictionary=True)
            cur2.execute("SELECT display_name FROM direction_users WHERE id=%s", (session['direction_id'],))
            d = cur2.fetchone()
            if d:
                dir_name = d['display_name']
            cur2.close()
            conn2.close()
 
        return _end_service(service['employe_id'], forced_by=dir_name)
 
    except Exception as e:
        print(f"❌ Erreur force end: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ========== API AUTH ==========
@app.route("/auth/me")
def auth_me():
    if current_user.is_authenticated:
        avatar_url = None
        if current_user.avatar:
            avatar_url = f"https://cdn.discordapp.com/avatars/{current_user.discord_id}/{current_user.avatar}.png"
        return jsonify({
            "user": {
                "id": current_user.discord_id,
                "username": current_user.username,
                "avatar": avatar_url
            }
        })
    return jsonify({"user": None})

@app.route("/auth/discord")
def auth_discord():
    discord_auth_url = f"https://discord.com/api/oauth2/authorize?client_id={DISCORD_CLIENT_ID}&redirect_uri={DISCORD_REDIRECT_URI}&response_type=code&scope=identify"
    return redirect(discord_auth_url)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    
    data = {
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": DISCORD_REDIRECT_URI
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    try:
        r = requests.post("https://discord.com/api/oauth2/token", data=data, headers=headers, timeout=10)
        if r.status_code != 200:
            return "Erreur d'authentification Discord", 400
        
        token = r.json()["access_token"]
        
        user_req = requests.get("https://discord.com/api/users/@me", 
                               headers={"Authorization": f"Bearer {token}"}, 
                               timeout=10)
        discord_user = user_req.json()
        
        conn = get_db_connection()
        if not conn:
            return "Erreur DB", 500
        
        cur = conn.cursor(dictionary=True)
        
        cur.execute("SELECT id FROM users WHERE discord_id=%s", (discord_user["id"],))
        existing = cur.fetchone()
        
        if existing:
            user_id = existing["id"]
            cur.execute("UPDATE users SET avatar_url=%s WHERE id=%s", 
                        (discord_user.get("avatar"), user_id))
        else:
            cur.execute("INSERT INTO users(username, discord_id, avatar_url) VALUES (%s, %s, %s)", 
                        (discord_user["username"], discord_user["id"], discord_user.get("avatar")))
            conn.commit()
            user_id = cur.lastrowid
        
        cur.close()
        conn.close()
        
        user = User(user_id, discord_user["username"], discord_user["id"], discord_user.get("avatar"))
        login_user(user)
        session["user_id"] = user_id
        
        return redirect(url_for("index"))
    
    except Exception as e:
        print(f"❌ Erreur callback Discord: {e}")
        return f"Erreur: {str(e)}", 500

@app.route("/auth/logout", methods=["POST"])
@login_required
def auth_logout():
    logout_user()
    session.clear()
    return jsonify({"success": True})

# ========== API DIRECTION ==========
@app.route("/direction/me")
def direction_me():
    if 'direction_id' in session:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT id, username, display_name, role FROM direction_users WHERE id=%s", (session['direction_id'],))
            user = cur.fetchone()
            cur.close()
            conn.close()
            if user:
                return jsonify({"user": {"id": user['id'], "displayName": user['display_name'], "role": user['role']}})
    return jsonify({"user": None})

@app.route("/direction/login", methods=["POST"])
def direction_login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Erreur DB"}), 500
    
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, username, display_name, role FROM direction_users WHERE username=%s AND password_hash=%s AND active=1", (username, password))
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    if user:
        session['direction_id'] = user['id']
        return jsonify({"success": True, "user": {"id": user['id'], "displayName": user['display_name'], "role": user['role']}})
    return jsonify({"success": False}), 401

@app.route("/direction/logout", methods=["POST"])
def direction_logout():
    session.pop('direction_id', None)
    return jsonify({"success": True})

# Supprimez complètement l'ancienne route direction/check-by-username et remplacez par :

@app.route("/direction/check-by-username", methods=["POST"])
def direction_check_by_username():
    """Vérifie si un employé a un compte direction avec son username"""
    data = request.get_json()
    username = data.get('username')
    role = data.get('role', '').lower()
    
    print(f"🔍 Vérification direction pour: {username}, rôle: {role}")
    
    # Vérifier le rôle (sécurité côté serveur)
    role_hierarchy = {
        'Mecanicien': 0,
        'Supervision': 1,
        'Direction': 2,
    }
    
    role_level = role_hierarchy.get(role, 0)
    if role_level <= role_hierarchy.get('mecanicien', 1):
        return jsonify({"exists": False, "error": "Droits insuffisants"}), 403
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"exists": False, "error": "Erreur DB"}), 500
    
    try:
        cur = conn.cursor(dictionary=True)
        # Vérifier dans direction_users
        cur.execute(
            "SELECT id, username FROM direction_users WHERE username = %s AND active = 1",
            (username,)
        )
        direction_user = cur.fetchone()
        cur.close()
        conn.close()
        
        if direction_user:
            print(f"✅ Compte direction trouvé pour {username}")
            return jsonify({"exists": True, "direction_id": direction_user['id']})
        else:
            print(f"❌ Aucun compte direction pour {username}")
            return jsonify({"exists": False})
            
    except Exception as e:
        print(f"❌ Erreur check direction by username: {e}")
        return jsonify({"exists": False, "error": str(e)}), 500


@app.route("/direction/auto-login", methods=["POST"])
def direction_auto_login():
    """Connexion automatique à la direction pour un employé autorisé"""
    data = request.get_json()
    username = data.get('username')
    employe_id = data.get('employe_id')
    
    print(f"🔐 Auto-login direction pour: {username}, employe_id: {employe_id}")
    
    if not username:
        return jsonify({"success": False, "error": "Username requis"}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "error": "Erreur DB"}), 500
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # Récupérer l'employé pour vérifier son rôle (double sécurité)
        cur.execute(
            "SELECT id, username, role FROM staff_profiles WHERE id = %s AND username = %s AND active = 1",
            (employe_id, username)
        )
        employe = cur.fetchone()
        
        if not employe:
            cur.close()
            conn.close()
            return jsonify({"success": False, "error": "Employé non trouvé"}), 404
        
        role_hierarchy = {
            'Mecanicien': 0,
            'Supervision': 1,
            'Direction': 2,
        }
        
        role_level = role_hierarchy.get(employe['role'].lower(), 0)
        if role_level <= role_hierarchy.get('mecanicien', 1):
            cur.close()
            conn.close()
            return jsonify({"success": False, "error": "Droits insuffisants pour accéder à la direction"}), 403
        
        # Récupérer le compte direction
        cur.execute(
            "SELECT id, username, display_name, role FROM direction_users WHERE username = %s AND active = 1",
            (username,)
        )
        direction_user = cur.fetchone()
        cur.close()
        conn.close()
        
        if direction_user:
            # Créer la session direction
            session.permanent = True
            session['direction_id'] = direction_user['id']
            # Garder aussi une trace de l'employé original pour le switch back
            session['original_employe_id'] = employe_id
            session['direction_from_employe'] = True
            
            print(f"✅ Session direction créée pour {username}")
            
            return jsonify({
                "success": True,
                "user": {
                    "id": direction_user['id'],
                    "displayName": direction_user['display_name'],
                    "role": direction_user['role']
                }
            })
        else:
            return jsonify({"success": False, "error": "Aucun compte direction associé à cet employé"})
            
    except Exception as e:
        print(f"❌ Erreur auto-login direction: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/direction/switch-back-to-employe", methods=["POST"])
@require_direction
def direction_switch_back_to_employe():
    """Permet de revenir en mode employé depuis la direction"""
    if session.get('direction_from_employe') and session.get('original_employe_id'):
        original_employe_id = session.get('original_employe_id')
        
        # Restaurer la session employé
        session['employe_id'] = original_employe_id
        # Supprimer la session direction
        session.pop('direction_id', None)
        
        return jsonify({"success": True, "redirect": "/employe.html"})
    
    return jsonify({"success": False, "error": "Impossible de revenir en mode employé"})

# ========== API CLICK & COLLECT ==========
@app.route("/api/submit_order", methods=["POST"])
def submit_order():
    try:
        data = request.get_json()
        
        customer_name = data.get('customer_name')
        customer_phone = data.get('customer_phone', 'Non renseigné')
        delivery_method = data.get('delivery_method')
        items = data.get('items', [])
        total_price = data.get('total_price')
        total_weight = data.get('total_weight')
        order_date = data.get('order_date')
        discord_id = current_user.discord_id if current_user.is_authenticated else None
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "error": "Erreur DB"}), 500
        
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO orders (customer_name, customer_phone, delivery_method, total_price, total_weight, order_date, discord_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (customer_name, customer_phone, delivery_method, total_price, total_weight, order_date, discord_id))
        
        order_id = cur.lastrowid
        
        products_list = []
        for item in items:
            cur.execute("""
                INSERT INTO order_items (order_id, product_name, quantity, price, weight)
                VALUES (%s, %s, %s, %s, %s)
            """, (order_id, item['name'], item['quantity'], item['totalPrice'], item['totalWeight']))
            products_list.append(f"• **{item['name']}** x{item['quantity']} - {item['totalPrice']:.2f}$ ({item['totalWeight']:.2f}kg)")
        
        conn.commit()
        cur.close()
        conn.close()
        
        products_text = "\n".join(products_list) if products_list else "Aucun produit"
        if len(products_text) > 3500:
            products_text = products_text[:3500] + "\n... (liste tronquée)"
        
        order_webhook = os.environ.get("ORDER_WEBHOOK", "https://discord.com/api/webhooks/1494093063801405531/6lxcbLMfO4NhnHfUPLIKblQb4OBJxQ9Hku3QPzLGPmpY3WDUzH7quxHlPp0Ob4eKPNmC")
        
        embed = {
            "title": "🛒 NOUVEAU Click & Collect",
            "color": 15158332,
            "description": f"**Client :** {customer_name}\n**Téléphone :** {customer_phone}\n**Livraison :** {delivery_method}\n**Date :** {order_date}\n\n**📦 Produits commandés :**\n{products_text}\n\n**⚖️ Poids total :** {total_weight:.2f} kg\n**💰 Total à payer :** {total_price:.2f}$",
            "footer": {"text": "LS Customs - Click & Collect"},
            "timestamp": now_paris().isoformat()
        }
        
        try:
            requests.post(order_webhook, json={"embeds": [embed]}, timeout=2)
        except:
            pass
        
        return jsonify({"success": True, "message": "Click & Collect validé"})
    
    except Exception as e:
        print(f"❌ Erreur submit_order: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

# ========== API PRICING ==========
@app.route("/api/pricing")
def api_pricing():
    pricing_data = {
        "global": [
            {"title": "Carrosserie", "price": "$50"},
            {"title": "Depannage (/km)", "price": "$100"},
            {"title": "Fourriere", "price": "$150"},
            {"title": "Nettoyage", "price": "$50"},
            {"title": "Pneu", "price": "$100"},
            {"title": "Repa complete", "price": "$250"},
            {"title": "Reparation Moteur", "price": "$200"}
        ],
        "custom": [
            {"title": "Full Perf - Catégorie 1", "price": "$20'000"},
            {"title": "Full Perf - Catégorie 2", "price": "$38'000"},
            {"title": "Full Perf - Catégorie 3", "price": "$67'000"},
            {"title": "Full Perf - Catégorie 4", "price": "$90'000"},
            {"title": "Full Perf - Catégorie 5", "price": "$190'000"}
        ],
        "paint": [
            {"title": "Nacrage (Effet de couleur)", "price": "$450"},
            {"title": "Peinture Perso", "price": "$500"},
            {"title": "Peinture primaire", "price": "$200"},
            {"title": "Peinture secondaire", "price": "$200"}
        ],
        "sales": [
            {"title": "Karcher", "price": "$200"},
            {"title": "Kit de reparation", "price": "$200"},
            {"title": "Moteur", "price": "$700"}
        ]
    }
    return jsonify(pricing_data)

# ========== API GESTION DES ANNONCES ==========
@app.route("/api/annonces", methods=["GET"])
@require_direction
def get_annonces():
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify([])
        
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, titre, image_url, texte, updated_at FROM annonces ORDER BY updated_at DESC")
        annonces = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify(annonces)
    except Exception as e:
        print(f"❌ Erreur GET annonces: {e}")
        return jsonify([])

@app.route("/api/annonces", methods=["POST"])
@require_direction
def create_annonce():
    try:
        data = request.get_json()
        titre = data.get('titre')
        image_url = data.get('image_url')
        texte = data.get('texte')
        
        if not titre or not texte:
            return jsonify({"success": False, "error": "Titre et texte requis"}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "error": "Erreur DB"}), 500
        
        cur = conn.cursor()
        cur.execute("INSERT INTO annonces (titre, image_url, texte) VALUES (%s, %s, %s)", (titre, image_url, texte))
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({"success": True})
    except Exception as e:
        print(f"❌ Erreur POST annonce: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/annonces/<int:annonce_id>", methods=["PUT"])
@require_direction
def update_annonce(annonce_id):
    try:
        data = request.get_json()
        titre = data.get('titre')
        image_url = data.get('image_url')
        texte = data.get('texte')
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "error": "Erreur DB"}), 500
        
        cur = conn.cursor()
        cur.execute("UPDATE annonces SET titre=%s, image_url=%s, texte=%s WHERE id=%s", (titre, image_url, texte, annonce_id))
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({"success": True})
    except Exception as e:
        print(f"❌ Erreur PUT annonce: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/annonces/<int:annonce_id>", methods=["DELETE"])
@require_direction
def delete_annonce(annonce_id):
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "error": "Erreur DB"}), 500
        
        cur = conn.cursor()
        cur.execute("DELETE FROM annonces WHERE id = %s", (annonce_id,))
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({"success": True})
    except Exception as e:
        print(f"❌ Erreur DELETE annonce: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ========== API GESTION DES SANCTIONS ==========
# ========== API GESTION DES SANCTIONS ==========
@app.route("/api/sanctions", methods=["GET"])
@require_direction
def get_sanctions():
    """Récupère la liste de toutes les sanctions"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify([])
        
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT s.id, s.username, s.type, s.reason, s.duration_days, s.created_by, s.created_at,
                   sp.role as employee_role,
                   sp.name as employee_name
            FROM sanctions s
            LEFT JOIN staff_profiles sp ON s.username = sp.username
            ORDER BY s.created_at DESC
        """)
        sanctions = cur.fetchall()
        cur.close()
        conn.close()
        
        # Convertir le type en texte lisible
        type_map = {
            'warning': 'Avertissement',
            'blacklist': 'Blacklist',
            'suspension': 'Mise à pied'
        }
        for s in sanctions:
            s['type_label'] = type_map.get(s['type'], s['type'])
        
        return jsonify(sanctions)
    
    except Exception as e:
        print(f"❌ Erreur GET sanctions: {e}")
        return jsonify([])

@app.route("/api/sanctions/employes", methods=["GET"])
@require_direction
def get_employes_for_sanctions():
    """Récupère la liste des employés actifs pour le sélecteur"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify([])
        
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT id, username, name as display_name, role
            FROM staff_profiles
            WHERE active = 1
            ORDER BY name ASC
        """)
        employes = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify(employes)
    
    except Exception as e:
        print(f"❌ Erreur GET employes: {e}")
        return jsonify([])

@app.route("/api/sanctions", methods=["POST"])
@require_direction
def create_sanction():
    try:
        data = request.get_json()
        print(f"DEBUG sanctions POST: {data}")
        username = data.get('username') or None
        discord_id = data.get('discord_id') or None
        sanction_type = data.get('type', 'warning')
        reason = data.get('reason')
        duration_days = data.get('duration_days', 0)

        # Au moins l'un des deux est requis
        if not username and not discord_id:
            return jsonify({"success": False, "error": "Un nom d'utilisateur ou un ID Discord est requis"}), 400

        if not reason:
            return jsonify({"success": False, "error": "Le motif est requis"}), 400

        if sanction_type not in ['warning', 'blacklist', 'suspension']:
            return jsonify({"success": False, "error": "Type de sanction invalide"}), 400
        
        # Récupérer le nom du direction_user
        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "error": "Erreur DB"}), 500
        
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT display_name FROM direction_users WHERE id = %s", (session['direction_id'],))
        direction_user = cur.fetchone()
        direction_name = direction_user['display_name'] if direction_user else "Direction"
        
        cur.execute("""
            INSERT INTO sanctions (username, discord_id, type, reason, duration_days, created_by, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (username, discord_id, sanction_type, reason, duration_days, direction_name, now_paris()))
        
        conn.commit()
        sanction_id = cur.lastrowid
        cur.close()
        conn.close()
        
        # Envoyer un webhook Discord pour la sanction
        webhook_sanction = os.environ.get("SANCTION_WEBHOOK", "")
        if webhook_sanction:
            type_labels = {
                'warning': '⚠️ Avertissement',
                'blacklist': '🚫 Blacklist',
                'suspension': '⏸️ Mise à pied'
            }
            type_label = type_labels.get(sanction_type, sanction_type)
            duration_text = f"{duration_days} jour(s)" if duration_days > 0 else "Permanent"
            
            embed = {
                "title": f"{type_label} - Nouvelle sanction",
                "color": 15158332 if sanction_type != 'warning' else 15844367,
                "fields": [
                    {"name": "Personne concernée", "value": username if username else "-", "inline": True},
                    {"name": "Id Discord", "value": discord_id or "—", "inline": False},
                    {"name": "Type", "value": type_label, "inline": True},
                    {"name": "Durée", "value": duration_text, "inline": True},
                    {"name": "Motif", "value": reason, "inline": False},
                    {"name": "Créé par", "value": direction_name, "inline": True}
                ],
                "timestamp": now_paris().isoformat()
            }
            try:
                requests.post(webhook_sanction, json={"embeds": [embed]}, timeout=2)
            except:
                pass
        
        return jsonify({"success": True, "id": sanction_id})
    
    except Exception as e:
        print(f"❌ Erreur POST sanction: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/sanctions/<int:sanction_id>", methods=["PUT"])
@require_direction
def update_sanction(sanction_id):
    """Modifie une sanction existante"""
    try:
        data = request.get_json()
        username = data.get('username')
        sanction_type = data.get('type', 'warning')
        reason = data.get('reason')
        duration_days = data.get('duration_days', 0)
        
        if not username or not reason:
            return jsonify({"success": False, "error": "Nom d'utilisateur et motif requis"}), 400
        
        if sanction_type not in ['warning', 'blacklist', 'suspension']:
            return jsonify({"success": False, "error": "Type de sanction invalide"}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "error": "Erreur DB"}), 500
        
        cur = conn.cursor()
        cur.execute("""
            UPDATE sanctions
            SET username = %s, type = %s, reason = %s, duration_days = %s
            WHERE id = %s
        """, (username, sanction_type, reason, duration_days, sanction_id))
        
        conn.commit()
        rows_affected = cur.rowcount
        cur.close()
        conn.close()
        
        if rows_affected == 0:
            return jsonify({"success": False, "error": "Sanction non trouvée"}), 404
        
        return jsonify({"success": True})
    
    except Exception as e:
        print(f"❌ Erreur PUT sanction: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/sanctions/<int:sanction_id>", methods=["DELETE"])
@require_direction
def delete_sanction(sanction_id):
    """Supprime une sanction"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "error": "Erreur DB"}), 500
        
        cur = conn.cursor()
        cur.execute("DELETE FROM sanctions WHERE id = %s", (sanction_id,))
        conn.commit()
        rows_affected = cur.rowcount
        cur.close()
        conn.close()
        
        if rows_affected == 0:
            return jsonify({"success": False, "error": "Sanction non trouvée"}), 404
        
        return jsonify({"success": True})
    
    except Exception as e:
        print(f"❌ Erreur DELETE sanction: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ========== GESTION DES ERREURS ==========
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html') if os.path.exists('templates/404.html') else "Page non trouvée", 404

@app.errorhandler(Exception)
def handle_exception(e):
    print(f"❌ Erreur: {str(e)}")
    traceback.print_exc()
    return "Une erreur interne est survenue", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)