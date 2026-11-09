import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

class Config:
    # Flask Session & Cryptographic Key
    SECRET_KEY = os.getenv("SECRET_KEY", "rent-mgmt-secure-secret-key-default-2025")
    
    # Supabase PostgreSQL & Storage Settings
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
    SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "property-images")

    # Designated Single Administrator Credentials
    ADMIN_DEFAULT_EMAIL = os.getenv("ADMIN_DEFAULT_EMAIL", "admin123@gmail.com")
    ADMIN_DEFAULT_PASSWORD = os.getenv("ADMIN_DEFAULT_PASSWORD", "123456")
    ADMIN_DEFAULT_NAME = os.getenv("ADMIN_DEFAULT_NAME", "Administrator")
    ADMIN_DEFAULT_PHONE = os.getenv("ADMIN_DEFAULT_PHONE", "+91 9876543210")

    # Production Cookie & HTTP Security Settings
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = (
        os.getenv("FLASK_ENV") == "production" or 
        os.getenv("RENDER") == "true" or
        os.getenv("SESSION_COOKIE_SECURE", "false").lower() in ("true", "1")
    )
    PERMANENT_SESSION_LIFETIME = 86400 * 7  # 7 days
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
