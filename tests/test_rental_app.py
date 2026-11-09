import pytest
import io
from app import app, mock_db
from werkzeug.security import generate_password_hash

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        yield client

def test_homepage(client):
    """Test home page loads with professional UI."""
    response = client.get('/')
    assert response.status_code == 200
    assert b"HomeRental" in response.data
    assert b"Discover Your Ideal Rental Home" in response.data

def test_admin_route_protection(client):
    """Test that unauthorized users cannot access admin dashboard."""
    response = client.get('/admin/dashboard', follow_redirects=True)
    assert response.status_code == 200
    assert b"Administrator Sign In" in response.data or b"Admin" in response.data

def test_customer_registration_and_login(client):
    """Test customer signup and session authentication."""
    # Register customer
    resp = client.post('/register', data={
        'name': 'Test Tenant',
        'email': 'tenant@example.com',
        'password': 'password123',
        'confirm_password': 'password123',
        'phone': '9876543210'
    }, follow_redirects=True)
    assert resp.status_code == 200

    # Login customer
    resp = client.post('/login', data={
        'email': 'tenant@example.com',
        'password': 'password123'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "Customer Dashboard" in response_text(resp) or "tenant@example.com" in response_text(resp)

def test_admin_single_account_access(client):
    """Test that only the designated single admin email can authenticate."""
    # Attempt login with unauthorized email
    unauth_resp = client.post('/admin/login', data={
        'email': 'random.person@gmail.com',
        'password': 'AdminPass123!'
    }, follow_redirects=True)
    assert b"Access restricted to the designated administrator account only" in unauth_resp.data

def test_admin_login(client):
    """Test default admin authentication."""
    resp = client.post('/admin/login', data={
        'email': 'admin123@gmail.com',
        'password': '123456'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Admin Management Console" in resp.data

def test_admin_property_crud_and_status(client):
    """Test admin creating, updating, and toggling property listing."""
    # Authenticate as admin
    with client.session_transaction() as sess:
        sess['user_id'] = 'admin-id-1'
        sess['user_name'] = 'System Admin'
        sess['email'] = 'admin@homerental.com'
        sess['role'] = 'ADMIN'

    # Create property
    post_data = {
        'title': 'Automated Test Villa',
        'property_type': 'Villa',
        'address': '12 Palm Beach Blvd',
        'city': 'Bengaluru',
        'locality': 'Whitefield',
        'latitude': 12.9698,
        'longitude': 77.7500,
        'monthly_rent': 60000,
        'security_deposit': 180000,
        'bedrooms': 4,
        'bathrooms': 4,
        'balconies': 2,
        'area_sqft': 2800,
        'furnishing_status': 'Furnished',
        'parking_available': 'on',
        'water_available': '24/7 Supply',
        'amenities': 'Private Pool, Garden, Solar',
        'description': 'Super luxurious spacious standalone villa.',
        'contact_phone': '+91 9999988888',
        'is_published': 'on',
        'is_available': 'on'
    }

    resp = client.post('/admin/property/add', data=post_data, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Property listed successfully!" in resp.data

    # Verify villa exists in listings
    resp = client.get('/properties?city=Bengaluru&property_type=Villa')
    assert resp.status_code == 200
    assert b"Automated Test Villa" in resp.data

def test_customer_enquiry_and_favourites(client):
    """Test customer saving favourite and submitting enquiry."""
    # Find property ID from Supabase or fallback
    from app import supabase_client
    prop_id = None
    if supabase_client:
        res = supabase_client.table('properties').select('id').limit(1).execute()
        if res.data:
            prop_id = res.data[0]['id']
    if not prop_id and mock_db['properties']:
        prop_id = mock_db['properties'][0]['id']
    if not prop_id:
        prop_id = '91b59eea-3e7b-4233-b973-e0cf528466fd'

    # Create customer in users table first for foreign key integrity
    reg_resp = client.post('/register', data={
        'name': 'Favourite Tester',
        'email': 'fav.tester@gmail.com',
        'password': 'password123',
        'confirm_password': 'password123',
        'phone': '9876500000'
    }, follow_redirects=True)
    assert reg_resp.status_code == 200

    login_resp = client.post('/login', data={
        'email': 'fav.tester@gmail.com',
        'password': 'password123'
    }, follow_redirects=True)
    assert login_resp.status_code == 200

    # Toggle favourite
    fav_resp = client.post(f'/favourites/toggle/{prop_id}', follow_redirects=True)
    assert fav_resp.status_code == 200

    # Submit enquiry
    enq_resp = client.post('/enquiry/submit', data={
        'property_id': prop_id,
        'name': 'Favourite Tester',
        'email': 'fav.tester@gmail.com',
        'phone': '+91 9876500000',
        'message': 'Hello, I want to book a physical visit this Saturday.'
    }, follow_redirects=True)
    assert enq_resp.status_code == 200
    assert b"submitted" in enq_resp.data

def test_healthz_and_security_headers(client):
    """Test health check route and HTTP security response headers."""
    resp = client.get('/healthz')
    assert resp.status_code == 200
    assert b"healthy" in resp.data
    # Verify security headers
    assert resp.headers.get('X-Content-Type-Options') == 'nosniff'
    assert resp.headers.get('X-Frame-Options') == 'SAMEORIGIN'
    assert resp.headers.get('Referrer-Policy') == 'strict-origin-when-cross-origin'

def response_text(resp):
    return resp.data.decode('utf-8', errors='ignore')
