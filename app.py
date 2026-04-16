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

PARIS_TZ = pytz.timezone("Europe/Paris")

def now_paris():
    return datetime.now(PARIS_TZ)

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "e70347e86f09c362df99758723597361e12fd197d16a3275e21504b4df99cbcc")

# Configuration MySQL
DB_CONFIG = {
    'host': os.environ.get("DB_HOST", "hopper.proxy.rlwy.net"),
    'port': int(os.environ.get("DB_PORT", 32384)),
    'database': os.environ.get("DB_NAME", "railway"),
    'user': os.environ.get("DB_USER", "root"),
    'password': os.environ.get("DB_PASSWORD", "kBBVhpqLHHmSBAlgXtGiFcxWwndvBpOD"),
    'connection_timeout': 5,
    'autocommit': True
}

# Configuration Discord
DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "814277691981168680")
DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "nfnAJBlnt1TvBIfPcdAT0Cacn2nSL4rF")
DISCORD_REDIRECT_URI = os.environ.get("DISCORD_REDIRECT_URI", "https://lsc-site-production-e2c1.up.railway.app/callback")
DISCORD_GUILD_ID = "925525617863184445"
BOT_TOKEN = os.environ.get("DISCORD_TOKEN")

# Login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth_discord'

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

@app.route("/direction.html")
def direction_page():
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
            INSERT INTO staff_reviews (staff_id, staff_name, rating, comment, reviewer, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (staff_id, staff_name, rating, comment, reviewer, now_paris()))
        conn.commit()
        cur.close()
        conn.close()
        
        # Webhook Discord pour les avis
        webhook = os.environ.get("REVIEW_WEBHOOK", "https://discord.com/api/webhooks/1482122375767265390/FH6mWGeh1XODdmTUA_EJHEDSAD-r8XXjEMCSENF7xamXkMrPIhxlOyLlxC5qrSzwK7bm")
        
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
@app.route("/api/applications", methods=["GET", "POST"])
@login_required
def handle_applications():
    if request.method == "POST":
        try:
            data = request.get_json()
            
            # Récupérer l'utilisateur Discord depuis la session
            if not current_user.is_authenticated:
                return jsonify({"success": False, "error": "Non authentifié"}), 401
            
            # Vérifier si l'utilisateur est dans le serveur Discord
            if not is_user_in_guild(current_user.discord_id):
                return jsonify({"success": False, "error": "Vous devez être sur le Discord pour postuler"}), 403
            
            conn = get_db_connection()
            if not conn:
                return jsonify({"success": False, "error": "Erreur DB"}), 500
            
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO applications 
                (full_name, discord_tag, avatar_url, birth_date, phone, rib, experience, availability, motivation, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s)
            """, (
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
            
            # Webhook Discord pour notification
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
    
    # GET - Récupérer toutes les candidatures (pour la direction)
    if 'direction_id' not in session:
        return jsonify({"error": "Non autorisé"}), 401
    
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
def get_application_detail(app_id):
    if 'direction_id' not in session:
        return jsonify({"error": "Non autorisé"}), 401
    
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
def update_application_status(app_id):
    if 'direction_id' not in session:
        return jsonify({"error": "Non autorisé"}), 401
    
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
            SET status = %s, updated_at = %s
            WHERE id = %s
        """, (new_status, now_paris(), app_id))
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({"success": True, "status": new_status})
    
    except Exception as e:
        print(f"❌ Erreur PATCH application status: {e}")
        return jsonify({"error": str(e)}), 500

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
            cur.execute("UPDATE users SET avatar_url=(%s) WHERE id=%s", 
                        (discord_user.get("avatar"), user_id))
        else:
            cur.execute("INSERT INTO users(username, discord_id, avatar_url) VALUES (%s, %s, %s)", 
                        (discord_user["username"], discord_user["id"], discord_user.get("avatar")))
            conn.commit()
            user_id = cur.lastrowid
        
        cur.close()
        conn.close()
        
        # Créer session
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
            cur.execute("SELECT id, username, name, role FROM staff_profiles WHERE id=%s", (session['direction_id'],))
            user = cur.fetchone()
            cur.close()
            conn.close()
            if user:
                return jsonify({"user": {"id": user['id'], "displayName": user['name'], "role": user['role']}})
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
    cur.execute("SELECT id, username, name, role FROM staff_profiles WHERE username=%s AND password=%s AND active=1", (username, password))
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    if user:
        session['direction_id'] = user['id']
        return jsonify({"success": True, "user": {"id": user['id'], "displayName": user['name'], "role": user['role']}})
    return jsonify({"success": False}), 401

@app.route("/direction/logout", methods=["POST"])
def direction_logout():
    session.pop('direction_id', None)
    return jsonify({"success": True})

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
        
        # Webhook Discord pour les commandes
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

# ========== API PRICING (optionnel pour plus tard) ==========
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