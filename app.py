import os
import uuid
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from config import Config

# Supabase Client
supabase_client = None
if Config.SUPABASE_URL and Config.SUPABASE_KEY and "your-project-id" not in Config.SUPABASE_URL:
    try:
        from supabase import create_client
        supabase_client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
    except Exception as e:
        print(f"Warning: Could not connect to Supabase: {e}")

# Fallback in-memory storage if Supabase credentials are not set during initial demo testing
mock_db = {
    "users": [],
    "properties": [],
    "property_images": [],
    "favourites": [],
    "rental_enquiries": [],
    "admin_logs": []
}

app = Flask(__name__)
app.config.from_object(Config)

# Production Reverse Proxy Support (Render, Cloudflare, Nginx)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

@app.after_request
def apply_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

@app.route('/healthz')
def healthz():
    return jsonify({
        'status': 'healthy',
        'service': 'HomeRental PRO',
        'database': 'supabase' if supabase_client else 'in-memory'
    }), 200

# Ensure upload directory exists for local/fallback file handling
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def is_allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS


def log_admin_action(action_text):
    """Safely log administrator actions without foreign key crashes."""
    user_id = session.get('user_id')
    if supabase_client:
        try:
            # Verify if user_id exists in Supabase users table
            admin_id_to_log = None
            if user_id:
                chk = supabase_client.table('users').select('id').eq('id', user_id).execute()
                if chk.data:
                    admin_id_to_log = user_id
                else:
                    # Look up admin by email as fallback
                    admin_by_email = supabase_client.table('users').select('id').eq('email', Config.ADMIN_DEFAULT_EMAIL.lower()).execute()
                    if admin_by_email.data:
                        admin_id_to_log = admin_by_email.data[0]['id']

            supabase_client.table('admin_logs').insert({
                "admin_id": admin_id_to_log,
                "action": action_text
            }).execute()
        except Exception as e:
            print(f"Warning: could not write to admin_logs: {e}")
    else:
        mock_db['admin_logs'].append({
            "id": str(uuid.uuid4()),
            "admin_id": user_id,
            "action": action_text,
            "created_at": "2025-01-01T00:00:00Z"
        })


def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    
    if supabase_client:
        try:
            res = supabase_client.table('users').select('*').eq('id', user_id).limit(1).execute()
            if res.data:
                return res.data[0]
        except Exception as e:
            print(f"Error fetching current user from Supabase: {e}")
            
    # Fallback to mock_db
    for u in mock_db["users"]:
        if u["id"] == user_id:
            return u
    return None


# ====================================================================
# ROLE-BASED ACCESS CONTROL DECORATORS
# ====================================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Admin login required.", "danger")
            return redirect(url_for('admin_login'))
        if session.get('role') != 'ADMIN':
            flash("Access denied. Only Administrators can view this page.", "danger")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


def customer_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Customer login required.", "warning")
            return redirect(url_for('login'))
        if session.get('role') != 'CUSTOMER':
            flash("Admin cannot access customer personal features directly.", "warning")
            return redirect(url_for('admin_dashboard'))
        return f(*args, **kwargs)
    return decorated_function


@app.context_processor
def inject_user():
    return {
        'current_user': get_current_user(),
        'is_logged_in': 'user_id' in session,
        'user_role': session.get('role')
    }


# ====================================================================
# SEED INITIAL ADMIN (Requirement 2 & 9)
# ====================================================================

def seed_default_admin():
    admin_email = Config.ADMIN_DEFAULT_EMAIL
    hashed = generate_password_hash(Config.ADMIN_DEFAULT_PASSWORD)
    admin_data = {
        "id": str(uuid.uuid4()),
        "name": Config.ADMIN_DEFAULT_NAME,
        "email": admin_email,
        "password_hash": hashed,
        "phone": Config.ADMIN_DEFAULT_PHONE,
        "role": "ADMIN",
        "created_at": "2025-01-01T00:00:00Z"
    }

    if supabase_client:
        try:
            check = supabase_client.table('users').select('*').eq('role', 'ADMIN').execute()
            if not check.data:
                supabase_client.table('users').insert({
                    "id": admin_data["id"],
                    "name": admin_data["name"],
                    "email": admin_data["email"],
                    "password_hash": admin_data["password_hash"],
                    "phone": admin_data["phone"],
                    "role": "ADMIN"
                }).execute()
                print("Default admin created in Supabase.")
        except Exception as e:
            print(f"Supabase admin check error (Check schema setup): {e}")

    # Also keep in mock_db for fallback
    admin_user = next((u for u in mock_db["users"] if u["role"] == "ADMIN"), None)
    if not admin_user:
        mock_db["users"].append(admin_data)
    else:
        admin_user["email"] = admin_email
        admin_user["password_hash"] = hashed

        # Seed sample property in mock_db if empty
        prop_id = str(uuid.uuid4())
        mock_db["properties"].append({
            "id": prop_id,
            "title": "Modern 3BHK Luxury Highrise Apartment",
            "property_type": "Apartment",
            "address": "42 Skyline Towers, Outer Ring Road",
            "city": "Bengaluru",
            "locality": "Bellandur",
            "latitude": 12.9304,
            "longitude": 77.6784,
            "monthly_rent": 45000,
            "security_deposit": 150000,
            "bedrooms": 3,
            "bathrooms": 3,
            "balconies": 2,
            "area_sqft": 1750,
            "furnishing_status": "Furnished",
            "parking_available": True,
            "water_available": "24/7 Supply",
            "amenities": ["Swimming Pool", "Gym", "Clubhouse", "24/7 Security", "Power Backup", "Covered Parking"],
            "description": "Stunning high-floor apartment with panoramic views, modular Italian kitchen, premium fittings, and serene club amenities.",
            "contact_phone": "+91 9876543210",
            "is_published": True,
            "is_available": True,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z"
        })
        mock_db["property_images"].append({
            "id": str(uuid.uuid4()),
            "property_id": prop_id,
            "storage_path": "sample1.jpg",
            "image_url": "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?auto=format&fit=crop&w=1200&q=80",
            "is_primary": True,
            "created_at": "2025-01-01T00:00:00Z"
        })
        mock_db["property_images"].append({
            "id": str(uuid.uuid4()),
            "property_id": prop_id,
            "storage_path": "sample2.jpg",
            "image_url": "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?auto=format&fit=crop&w=1200&q=80",
            "is_primary": False,
            "created_at": "2025-01-01T00:00:00Z"
        })


seed_default_admin()


# ====================================================================
# PUBLIC ROUTES
# ====================================================================

@app.route('/')
def index():
    # Fetch published & available properties
    properties = []
    if supabase_client:
        try:
            res = supabase_client.table('properties').select('*, property_images(*)').eq('is_published', True).eq('is_available', True).order('created_at', desc=True).limit(6).execute()
            properties = res.data
        except Exception as e:
            print(f"Error reading properties from Supabase: {e}")
            properties = [p for p in mock_db["properties"] if p.get("is_published") and p.get("is_available")]
    else:
        properties = [p for p in mock_db["properties"] if p.get("is_published") and p.get("is_available")]
        for p in properties:
            p['property_images'] = [img for img in mock_db['property_images'] if img['property_id'] == p['id']]

    return render_template('index.html', properties=properties)


@app.route('/properties')
def properties():
    city = request.args.get('city', '').strip()
    locality = request.args.get('locality', '').strip()
    property_type = request.args.get('property_type', '').strip()
    min_rent = request.args.get('min_rent', type=float)
    max_rent = request.args.get('max_rent', type=float)
    bedrooms = request.args.get('bedrooms', type=int)

    all_props = []
    if supabase_client:
        try:
            query = supabase_client.table('properties').select('*, property_images(*)').eq('is_published', True)
            if city:
                query = query.ilike('city', f'%{city}%')
            if locality:
                query = query.ilike('locality', f'%{locality}%')
            if property_type:
                query = query.eq('property_type', property_type)
            if min_rent is not None:
                query = query.gte('monthly_rent', min_rent)
            if max_rent is not None:
                query = query.lte('monthly_rent', max_rent)
            if bedrooms is not None:
                query = query.eq('bedrooms', bedrooms)
            
            res = query.order('created_at', desc=True).execute()
            all_props = res.data
        except Exception as e:
            print(f"Supabase filter query error: {e}")
            all_props = [p for p in mock_db["properties"] if p.get("is_published")]
    else:
        filtered = [p for p in mock_db["properties"] if p.get("is_published")]
        if city:
            filtered = [p for p in filtered if city.lower() in p["city"].lower()]
        if locality:
            filtered = [p for p in filtered if locality.lower() in p["locality"].lower()]
        if property_type:
            filtered = [p for p in filtered if p["property_type"] == property_type]
        if min_rent is not None:
            filtered = [p for p in filtered if p["monthly_rent"] >= min_rent]
        if max_rent is not None:
            filtered = [p for p in filtered if p["monthly_rent"] <= max_rent]
        if bedrooms is not None:
            filtered = [p for p in filtered if p["bedrooms"] == bedrooms]

        for p in filtered:
            p['property_images'] = [img for img in mock_db['property_images'] if img['property_id'] == p['id']]
        all_props = filtered

    return render_template(
        'properties.html',
        properties=all_props,
        filters={
            'city': city,
            'locality': locality,
            'property_type': property_type,
            'min_rent': min_rent,
            'max_rent': max_rent,
            'bedrooms': bedrooms
        }
    )


@app.route('/property/<property_id>')
def property_details(property_id):
    prop = None
    images = []
    is_favourite = False

    if supabase_client:
        try:
            res = supabase_client.table('properties').select('*, property_images(*)').eq('id', property_id).limit(1).execute()
            if res.data:
                prop = res.data[0]
                images = prop.get('property_images', [])
                if 'user_id' in session and session.get('role') == 'CUSTOMER':
                    fav_res = supabase_client.table('favourites').select('*').eq('customer_id', session['user_id']).eq('property_id', property_id).execute()
                    is_favourite = len(fav_res.data) > 0
        except Exception as e:
            print(f"Error fetching property details: {e}")
    
    if not prop:
        for p in mock_db["properties"]:
            if str(p["id"]) == str(property_id):
                prop = p
                images = [img for img in mock_db["property_images"] if str(img["property_id"]) == str(property_id)]
                if 'user_id' in session and session.get('role') == 'CUSTOMER':
                    is_favourite = any(f["customer_id"] == session["user_id"] and str(f["property_id"]) == str(property_id) for f in mock_db["favourites"])
                break

    if not prop:
        flash("Property not found.", "danger")
        return redirect(url_for('properties'))

    return render_template('property_details.html', property=prop, images=images, is_favourite=is_favourite)


# ====================================================================
# CUSTOMER AUTHENTICATION & DASHBOARD
# ====================================================================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        phone = request.form.get('phone', '').strip()

        if not name or not email or not password:
            flash("All required fields must be filled.", "danger")
            return render_template('register.html')

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template('register.html')

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return render_template('register.html')

        hashed_password = generate_password_hash(password)
        new_user_id = str(uuid.uuid4())

        # Enforce ONLY CUSTOMER role on public registration
        if supabase_client:
            try:
                # Check email existence
                chk = supabase_client.table('users').select('id').eq('email', email).execute()
                if chk.data:
                    flash("Email is already registered. Please login.", "warning")
                    return redirect(url_for('login'))

                supabase_client.table('users').insert({
                    "id": new_user_id,
                    "name": name,
                    "email": email,
                    "password_hash": hashed_password,
                    "phone": phone,
                    "role": "CUSTOMER"
                }).execute()
            except Exception as e:
                flash(f"Error registering user: {e}", "danger")
                return render_template('register.html')
        else:
            if any(u['email'] == email for u in mock_db['users']):
                flash("Email is already registered. Please login.", "warning")
                return redirect(url_for('login'))
            mock_db['users'].append({
                "id": new_user_id,
                "name": name,
                "email": email,
                "password_hash": hashed_password,
                "phone": phone,
                "role": "CUSTOMER",
                "created_at": "2025-01-01T00:00:00Z"
            })

        flash("Registration successful! You can now log in.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        if session.get('role') == 'ADMIN':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('customer_dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = None
        if supabase_client:
            try:
                res = supabase_client.table('users').select('*').eq('email', email).limit(1).execute()
                if res.data:
                    user = res.data[0]
            except Exception as e:
                print(f"Supabase login search failed: {e}")

        if not user:
            for u in mock_db['users']:
                if u['email'] == email:
                    user = u
                    break

        if user and check_password_hash(user['password_hash'], password):
            # Check user role
            if user['role'] != 'CUSTOMER':
                flash("Admin accounts should use the Admin Login portal.", "info")
                return redirect(url_for('admin_login'))

            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['email'] = user['email']
            session['role'] = user['role']
            flash(f"Welcome back, {user['name']}!", "success")

            next_url = request.args.get('next')
            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect(url_for('customer_dashboard'))
        else:
            flash("Invalid email or password.", "danger")

    return render_template('login.html')


@app.route('/logout')
def logout():
    role = session.get('role')
    session.clear()
    flash("You have been securely logged out.", "info")
    if role == 'ADMIN':
        return redirect(url_for('admin_login'))
    return redirect(url_for('login'))


@app.route('/customer/dashboard')
@login_required
@customer_required
def customer_dashboard():
    user_id = session['user_id']
    favourites = []
    enquiries = []
    available_properties = []

    if supabase_client:
        try:
            fav_res = supabase_client.table('favourites').select('*, properties(*, property_images(*))').eq('customer_id', user_id).execute()
            favourites = [f.get('properties') for f in fav_res.data if f.get('properties')]

            enq_res = supabase_client.table('rental_enquiries').select('*, properties(title, locality, city)').eq('customer_id', user_id).order('created_at', desc=True).execute()
            enquiries = enq_res.data

            prop_res = supabase_client.table('properties').select('*, property_images(*)').eq('is_published', True).eq('is_available', True).order('created_at', desc=True).limit(6).execute()
            available_properties = prop_res.data
        except Exception as e:
            print(f"Customer dashboard query error: {e}")
    else:
        fav_prop_ids = [f['property_id'] for f in mock_db['favourites'] if f['customer_id'] == user_id]
        favourites = [p for p in mock_db['properties'] if p['id'] in fav_prop_ids]
        for p in favourites:
            p['property_images'] = [img for img in mock_db['property_images'] if img['property_id'] == p['id']]

        raw_enqs = [e for e in mock_db['rental_enquiries'] if e['customer_id'] == user_id]
        for e in raw_enqs:
            prop = next((p for p in mock_db['properties'] if str(p['id']) == str(e['property_id'])), {})
            e['properties'] = {'title': prop.get('title'), 'locality': prop.get('locality'), 'city': prop.get('city')}
        enquiries = raw_enqs

        # Fetch active available properties for tenant showcase
        available_properties = [p for p in mock_db['properties'] if p.get('is_published') and p.get('is_available')]
        for p in available_properties:
            p['property_images'] = [img for img in mock_db['property_images'] if img['property_id'] == p['id']]

    return render_template(
        'customer_dashboard.html',
        favourites=favourites,
        enquiries=enquiries,
        available_properties=available_properties
    )


@app.route('/customer/profile', methods=['POST'])
@login_required
@customer_required
def update_profile():
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    user_id = session['user_id']

    if not name:
        flash("Name cannot be empty.", "warning")
        return redirect(url_for('customer_dashboard'))

    if supabase_client:
        try:
            supabase_client.table('users').update({'name': name, 'phone': phone}).eq('id', user_id).execute()
        except Exception as e:
            flash(f"Error updating profile: {e}", "danger")
            return redirect(url_for('customer_dashboard'))
    else:
        for u in mock_db['users']:
            if u['id'] == user_id:
                u['name'] = name
                u['phone'] = phone
                break

    session['user_name'] = name
    flash("Profile updated successfully!", "success")
    return redirect(url_for('customer_dashboard'))


@app.route('/favourites/toggle/<property_id>', methods=['POST'])
@login_required
@customer_required
def toggle_favourite(property_id):
    user_id = session['user_id']
    is_fav = False

    if supabase_client:
        try:
            existing = supabase_client.table('favourites').select('*').eq('customer_id', user_id).eq('property_id', property_id).execute()
            if existing.data:
                supabase_client.table('favourites').delete().eq('customer_id', user_id).eq('property_id', property_id).execute()
                is_fav = False
            else:
                supabase_client.table('favourites').insert({'customer_id': user_id, 'property_id': property_id}).execute()
                is_fav = True
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    else:
        found = None
        for idx, fav in enumerate(mock_db['favourites']):
            if fav['customer_id'] == user_id and str(fav['property_id']) == str(property_id):
                found = idx
                break
        if found is not None:
            mock_db['favourites'].pop(found)
            is_fav = False
        else:
            mock_db['favourites'].append({
                'id': str(uuid.uuid4()),
                'customer_id': user_id,
                'property_id': property_id,
                'created_at': '2025-01-01T00:00:00Z'
            })
            is_fav = True

    if request.is_json:
        return jsonify({'success': True, 'is_favourite': is_fav})
    
    flash("Favourites updated.", "success")
    return redirect(request.referrer or url_for('property_details', property_id=property_id))


@app.route('/enquiry/submit', methods=['POST'])
@login_required
@customer_required
def submit_enquiry():
    property_id = request.form.get('property_id')
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    message = request.form.get('message', '').strip()
    customer_id = session['user_id']

    if not property_id or not message:
        flash("Message and property are required.", "danger")
        return redirect(request.referrer or url_for('properties'))

    enquiry_data = {
        "id": str(uuid.uuid4()),
        "property_id": property_id,
        "customer_id": customer_id,
        "name": name or session.get('user_name', ''),
        "email": email or session.get('email', ''),
        "phone": phone,
        "message": message,
        "status": "New",
        "created_at": "2025-01-01T00:00:00Z"
    }

    if supabase_client:
        try:
            supabase_client.table('rental_enquiries').insert({
                "property_id": property_id,
                "customer_id": customer_id,
                "name": enquiry_data["name"],
                "email": enquiry_data["email"],
                "phone": enquiry_data["phone"],
                "message": enquiry_data["message"],
                "status": "New"
            }).execute()
        except Exception as e:
            flash(f"Failed to submit enquiry: {e}", "danger")
            return redirect(url_for('property_details', property_id=property_id))
    else:
        mock_db['rental_enquiries'].append(enquiry_data)

    flash("Your rental enquiry has been submitted! Admin will contact you soon.", "success")
    return redirect(url_for('customer_dashboard'))


# ====================================================================
# ADMIN AUTHENTICATION & MANAGEMENT
# (Sole Administrator: Public Registration Disabled)
# ====================================================================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if 'user_id' in session and session.get('role') == 'ADMIN':
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        # Enforce designated sole admin email restriction
        if email != Config.ADMIN_DEFAULT_EMAIL.lower():
            flash("Unauthorized. Access restricted to the designated administrator account only.", "danger")
            return render_template('admin_login.html')

        admin_user = None
        if supabase_client:
            try:
                res = supabase_client.table('users').select('*').eq('email', email).eq('role', 'ADMIN').limit(1).execute()
                if res.data:
                    admin_user = res.data[0]
            except Exception as e:
                print(f"Supabase admin login query error: {e}")

        if not admin_user:
            for u in mock_db['users']:
                if u['email'].lower() == email and u['role'] == 'ADMIN':
                    admin_user = u
                    break

        if admin_user and check_password_hash(admin_user['password_hash'], password):
            session['user_id'] = admin_user['id']
            session['user_name'] = admin_user['name']
            session['email'] = admin_user['email']
            session['role'] = 'ADMIN'
            flash("Welcome, Administrator!", "success")
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Invalid administrator credentials.", "danger")

    return render_template('admin_login.html')


@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    properties = []
    customers = []
    enquiries = []

    if supabase_client:
        try:
            prop_res = supabase_client.table('properties').select('*, property_images(*)').order('created_at', desc=True).execute()
            properties = prop_res.data

            cust_res = supabase_client.table('users').select('id, name, email, phone, created_at').eq('role', 'CUSTOMER').order('created_at', desc=True).execute()
            customers = cust_res.data

            enq_res = supabase_client.table('rental_enquiries').select('*, properties(title, locality, city), users(name, email)').order('created_at', desc=True).execute()
            enquiries = enq_res.data
        except Exception as e:
            print(f"Supabase fetch for admin dashboard error: {e}")
    else:
        properties = list(mock_db['properties'])
        for p in properties:
            p['property_images'] = [img for img in mock_db['property_images'] if img['property_id'] == p['id']]
        customers = [u for u in mock_db['users'] if u['role'] == 'CUSTOMER']
        enquiries = list(mock_db['rental_enquiries'])
        for e in enquiries:
            prop = next((p for p in mock_db['properties'] if str(p['id']) == str(e['property_id'])), {})
            e['properties'] = {'title': prop.get('title'), 'locality': prop.get('locality'), 'city': prop.get('city')}

    stats = {
        "total_properties": len(properties),
        "available_properties": len([p for p in properties if p.get('is_available')]),
        "total_customers": len(customers),
        "new_enquiries": len([e for e in enquiries if e.get('status') == 'New']),
        "total_enquiries": len(enquiries)
    }

    return render_template(
        'admin_dashboard.html',
        properties=properties,
        customers=customers,
        enquiries=enquiries,
        stats=stats
    )


def handle_image_upload(file, property_id):
    filename = secure_filename(file.filename)
    unique_filename = f"{property_id}_{uuid.uuid4().hex[:8]}_{filename}"

    # Supabase Storage Attempt
    if supabase_client:
        try:
            file_bytes = file.read()
            # upload to storage bucket 'property-images'
            res = supabase_client.storage.from_(Config.SUPABASE_BUCKET).upload(
                path=unique_filename,
                file=file_bytes,
                file_options={"content-type": file.content_type}
            )
            # get public URL
            public_url = supabase_client.storage.from_(Config.SUPABASE_BUCKET).get_public_url(unique_filename)
            return unique_filename, public_url
        except Exception as e:
            print(f"Supabase Storage Upload Error (Falling back to local static/uploads): {e}")
            file.seek(0)

    # Local fallback
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
    file.save(save_path)
    public_url = url_for('static', filename=f"uploads/{unique_filename}")
    return unique_filename, public_url


@app.route('/admin/property/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_property():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        property_type = request.form.get('property_type', '').strip()
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        locality = request.form.get('locality', '').strip()
        latitude = request.form.get('latitude', type=float) or 12.9716
        longitude = request.form.get('longitude', type=float) or 77.5946
        monthly_rent = request.form.get('monthly_rent', type=float)
        security_deposit = request.form.get('security_deposit', type=float)
        bedrooms = request.form.get('bedrooms', type=int)
        bathrooms = request.form.get('bathrooms', type=int)
        balconies = request.form.get('balconies', type=int) or 0
        area_sqft = request.form.get('area_sqft', type=float)
        furnishing_status = request.form.get('furnishing_status', 'Furnished')
        parking_available = True if request.form.get('parking_available') == 'on' else False
        water_available = request.form.get('water_available', '24/7 Supply')
        amenities_raw = request.form.get('amenities', '')
        amenities = [a.strip() for a in amenities_raw.split(',') if a.strip()]
        description = request.form.get('description', '').strip()
        contact_phone = request.form.get('contact_phone', '').strip()
        is_published = True if request.form.get('is_published') == 'on' else False
        is_available = True if request.form.get('is_available') == 'on' else False

        if not title or not city or not monthly_rent or not bedrooms or not area_sqft:
            flash("Please fill in all essential required property details.", "danger")
            return render_template('add_property.html')

        new_prop_id = str(uuid.uuid4())
        prop_record = {
            "id": new_prop_id,
            "title": title,
            "property_type": property_type,
            "address": address,
            "city": city,
            "locality": locality,
            "latitude": latitude,
            "longitude": longitude,
            "monthly_rent": monthly_rent,
            "security_deposit": security_deposit,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "balconies": balconies,
            "area_sqft": area_sqft,
            "furnishing_status": furnishing_status,
            "parking_available": parking_available,
            "water_available": water_available,
            "amenities": amenities,
            "description": description,
            "contact_phone": contact_phone,
            "is_published": is_published,
            "is_available": is_available,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z"
        }

        # Handle multiple uploaded images
        uploaded_files = request.files.getlist('images')
        images_to_insert = []
        is_first = True
        for file in uploaded_files:
            if file and file.filename != '' and is_allowed_file(file.filename):
                storage_path, img_url = handle_image_upload(file, new_prop_id)
                images_to_insert.append({
                    "id": str(uuid.uuid4()),
                    "property_id": new_prop_id,
                    "storage_path": storage_path,
                    "image_url": img_url,
                    "is_primary": is_first,
                    "created_at": "2025-01-01T00:00:00Z"
                })
                is_first = False

        # If no image uploaded, provide standard modern house placeholder
        if not images_to_insert:
            images_to_insert.append({
                "id": str(uuid.uuid4()),
                "property_id": new_prop_id,
                "storage_path": "default_house.jpg",
                "image_url": "https://images.unsplash.com/photo-1570129477492-45c003edd2be?auto=format&fit=crop&w=1200&q=80",
                "is_primary": True,
                "created_at": "2025-01-01T00:00:00Z"
            })

        if supabase_client:
            try:
                supabase_client.table('properties').insert(prop_record).execute()
                for img in images_to_insert:
                    try:
                        supabase_client.table('property_images').insert(img).execute()
                    except Exception as img_err:
                        print(f"Warning: image record insert error: {img_err}")
                log_admin_action(f"Added property: {title} ({new_prop_id})")
            except Exception as e:
                print(f"Supabase property insert error: {e}. Saving to local fallback store...")
                # Graceful fallback: keep property live even if network glitch occurs
                mock_db['properties'].append(prop_record)
                mock_db['property_images'].extend(images_to_insert)
                flash("Property listed successfully! (Saved to local cache due to temporary network delay)", "success")
                return redirect(url_for('admin_dashboard'))
        else:
            mock_db['properties'].append(prop_record)
            mock_db['property_images'].extend(images_to_insert)
            mock_db['admin_logs'].append({
                "id": str(uuid.uuid4()),
                "admin_id": session['user_id'],
                "action": f"Added property: {title}",
                "created_at": "2025-01-01T00:00:00Z"
            })

        flash("Property listed successfully!", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template('add_property.html', property=None)


@app.route('/admin/property/edit/<property_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_property(property_id):
    prop = None
    existing_images = []

    if supabase_client:
        try:
            res = supabase_client.table('properties').select('*, property_images(*)').eq('id', property_id).limit(1).execute()
            if res.data:
                prop = res.data[0]
                existing_images = prop.get('property_images', [])
        except Exception as e:
            print(f"Supabase fetch property error: {e}")
    else:
        for p in mock_db['properties']:
            if str(p['id']) == str(property_id):
                prop = p
                existing_images = [img for img in mock_db['property_images'] if str(img['property_id']) == str(property_id)]
                break

    if not prop:
        flash("Property not found.", "danger")
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        property_type = request.form.get('property_type', '').strip()
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        locality = request.form.get('locality', '').strip()
        latitude = request.form.get('latitude', type=float) or prop.get('latitude')
        longitude = request.form.get('longitude', type=float) or prop.get('longitude')
        monthly_rent = request.form.get('monthly_rent', type=float)
        security_deposit = request.form.get('security_deposit', type=float)
        bedrooms = request.form.get('bedrooms', type=int)
        bathrooms = request.form.get('bathrooms', type=int)
        balconies = request.form.get('balconies', type=int) or 0
        area_sqft = request.form.get('area_sqft', type=float)
        furnishing_status = request.form.get('furnishing_status')
        parking_available = True if request.form.get('parking_available') == 'on' else False
        water_available = request.form.get('water_available', '24/7 Supply')
        amenities_raw = request.form.get('amenities', '')
        amenities = [a.strip() for a in amenities_raw.split(',') if a.strip()]
        description = request.form.get('description', '').strip()
        contact_phone = request.form.get('contact_phone', '').strip()
        is_published = True if request.form.get('is_published') == 'on' else False
        is_available = True if request.form.get('is_available') == 'on' else False

        update_payload = {
            "title": title,
            "property_type": property_type,
            "address": address,
            "city": city,
            "locality": locality,
            "latitude": latitude,
            "longitude": longitude,
            "monthly_rent": monthly_rent,
            "security_deposit": security_deposit,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "balconies": balconies,
            "area_sqft": area_sqft,
            "furnishing_status": furnishing_status,
            "parking_available": parking_available,
            "water_available": water_available,
            "amenities": amenities,
            "description": description,
            "contact_phone": contact_phone,
            "is_published": is_published,
            "is_available": is_available,
        }

        # Upload new images if attached
        uploaded_files = request.files.getlist('images')
        new_images = []
        for file in uploaded_files:
            if file and file.filename != '' and is_allowed_file(file.filename):
                storage_path, img_url = handle_image_upload(file, property_id)
                new_images.append({
                    "id": str(uuid.uuid4()),
                    "property_id": property_id,
                    "storage_path": storage_path,
                    "image_url": img_url,
                    "is_primary": len(existing_images) == 0 and len(new_images) == 0,
                    "created_at": "2025-01-01T00:00:00Z"
                })

        if supabase_client:
            try:
                supabase_client.table('properties').update(update_payload).eq('id', property_id).execute()
                for img in new_images:
                    try:
                        supabase_client.table('property_images').insert(img).execute()
                    except Exception as img_err:
                        print(f"Warning: image update insert error: {img_err}")
                log_admin_action(f"Updated property: {title} ({property_id})")
            except Exception as e:
                print(f"Supabase update error: {e}. Falling back to memory...")
                if prop:
                    prop.update(update_payload)
                mock_db['property_images'].extend(new_images)
                flash("Property updated successfully! (Saved to local cache)", "success")
                return redirect(url_for('admin_dashboard'))
        else:
            prop.update(update_payload)
            mock_db['property_images'].extend(new_images)
            mock_db['admin_logs'].append({
                "id": str(uuid.uuid4()),
                "admin_id": session['user_id'],
                "action": f"Updated property: {title}",
                "created_at": "2025-01-01T00:00:00Z"
            })

        flash("Property updated successfully!", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template('add_property.html', property=prop, images=existing_images)


@app.route('/admin/property/delete/<property_id>', methods=['POST'])
@login_required
@admin_required
def delete_property(property_id):
    if supabase_client:
        try:
            supabase_client.table('properties').delete().eq('id', property_id).execute()
            log_admin_action(f"Deleted property ID: {property_id}")
        except Exception as e:
            flash(f"Error deleting property: {e}", "danger")
            return redirect(url_for('admin_dashboard'))
    else:
        mock_db['properties'] = [p for p in mock_db['properties'] if str(p['id']) != str(property_id)]
        mock_db['property_images'] = [img for img in mock_db['property_images'] if str(img['property_id']) != str(property_id)]
        mock_db['favourites'] = [f for f in mock_db['favourites'] if str(f['property_id']) != str(property_id)]
        mock_db['rental_enquiries'] = [e for e in mock_db['rental_enquiries'] if str(e['property_id']) != str(property_id)]
        log_admin_action(f"Deleted property ID: {property_id}")

    flash("Property listing deleted successfully.", "success")
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/property/toggle-publish/<property_id>', methods=['POST'])
@login_required
@admin_required
def toggle_publish(property_id):
    if supabase_client:
        try:
            cur = supabase_client.table('properties').select('is_published').eq('id', property_id).single().execute()
            new_val = not cur.data['is_published']
            supabase_client.table('properties').update({'is_published': new_val}).eq('id', property_id).execute()
        except Exception as e:
            flash(f"Error toggling publish status: {e}", "danger")
    else:
        for p in mock_db['properties']:
            if str(p['id']) == str(property_id):
                p['is_published'] = not p.get('is_published', True)
                break

    flash("Property publish status toggled.", "success")
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/property/toggle-availability/<property_id>', methods=['POST'])
@login_required
@admin_required
def toggle_availability(property_id):
    if supabase_client:
        try:
            cur = supabase_client.table('properties').select('is_available').eq('id', property_id).single().execute()
            new_val = not cur.data['is_available']
            supabase_client.table('properties').update({'is_available': new_val}).eq('id', property_id).execute()
        except Exception as e:
            flash(f"Error toggling availability status: {e}", "danger")
    else:
        for p in mock_db['properties']:
            if str(p['id']) == str(property_id):
                p['is_available'] = not p.get('is_available', True)
                break

    flash("Property availability updated.", "success")
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/enquiry/status/<enquiry_id>', methods=['POST'])
@login_required
@admin_required
def update_enquiry_status(enquiry_id):
    new_status = request.form.get('status')
    if new_status not in ['New', 'Contacted', 'Resolved']:
        flash("Invalid enquiry status.", "warning")
        return redirect(url_for('admin_dashboard'))

    if supabase_client:
        try:
            supabase_client.table('rental_enquiries').update({'status': new_status}).eq('id', enquiry_id).execute()
        except Exception as e:
            flash(f"Error updating enquiry: {e}", "danger")
    else:
        for e in mock_db['rental_enquiries']:
            if str(e['id']) == str(enquiry_id):
                e['status'] = new_status
                break

    flash(f"Enquiry marked as '{new_status}'.", "success")
    return redirect(url_for('admin_dashboard'))


# ====================================================================
# API ENDPOINT FOR REACT / FRONTEND INTEGRATIONS
# ====================================================================

@app.route('/api/properties')
def api_properties():
    if supabase_client:
        try:
            res = supabase_client.table('properties').select('*, property_images(*)').eq('is_published', True).execute()
            return jsonify({'success': True, 'data': res.data})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    props = [p for p in mock_db['properties'] if p.get('is_published')]
    for p in props:
        p['property_images'] = [img for img in mock_db['property_images'] if img['property_id'] == p['id']]
    return jsonify({'success': True, 'data': props})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1')
    print("\n=======================================================")
    print("   HOME RENTAL PLATFORM (ADMIN & CUSTOMER ROLES)       ")
    print(f"   Default Admin: {Config.ADMIN_DEFAULT_EMAIL}        ")
    print(f"   Admin Pass:    {Config.ADMIN_DEFAULT_PASSWORD}     ")
    print(f"   Listening on:  http://0.0.0.0:{port}                ")
    print("=======================================================\n")
    app.run(host='0.0.0.0', port=port, debug=debug)

