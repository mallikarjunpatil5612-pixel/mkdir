# Home Rental Website — Admin and Customer Only

A production-ready, full-stack Home Rental Management platform designed strictly with **Two Roles: ADMIN and CUSTOMER**. Built with Python Flask backend, Supabase PostgreSQL, Supabase Storage, and a modern Blue & White UI/UX design.

---

## 🚀 Key Features

### 1. Two-Role Architecture
- **ADMIN**:
  - Secure Admin Login & Protected Portal (`/admin/dashboard`)
  - Add, Edit, and Delete rental house listings
  - Upload multiple property images to Supabase Storage (`property-images` bucket)
  - Toggle listing availability (`Available` vs `Occupied`) and visibility (`Published` vs `Unpublished`)
  - View registered customers list
  - Real-time customer enquiry inbox with status lifecycle (`New` ➔ `Contacted` ➔ `Resolved`)
  - Dashboard analytics & metrics (Total Properties, Available, Customers, Enquiries)
- **CUSTOMER**:
  - Customer Registration & Secure Login
  - Granular property search with multi-parameter filters (City, Locality, Type, BHK, Min/Max Rent)
  - Interactive property details with photo gallery & OpenStreetMap Leaflet integration
  - Bookmark & save favorite properties
  - Submit rental inquiries directly to Admin
  - Personal customer dashboard with enquiry tracking and profile updating

---

## 🛠️ Tech Stack & Requirements

- **Backend**: Python 3.10+ / Flask 3.0+
- **Database**: Supabase PostgreSQL
- **Image Storage**: Supabase Storage (`property-images` bucket)
- **Frontend**: Responsive HTML5, CSS3, JavaScript (Blue & White palette with modern card UX) + Leaflet.js
- **Security**: Password hashing (`werkzeug.security`), role-based routing guards, environment-isolated credentials

---

## 💻 One-Terminal Windows PowerShell Setup

Run all the commands below in a single integrated PowerShell terminal:

```powershell
# 1. Create a virtual environment (if not already created)
python -m venv venv

# 2. Activate virtual environment
.\venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and configure your environment variables
Copy-Item .env.example .env

# 5. Run automated tests to verify all routes and role controls
python -m pytest tests/ -v

# 6. Start the Flask application
python app.py
```

The application will be live at: **`http://localhost:5000`**

---

## 🗄️ Supabase PostgreSQL & Storage Setup

1. Open your [Supabase Dashboard](https://supabase.com/dashboard).
2. Go to **SQL Editor** and execute the contents of [`schema.sql`](file:///d:/MK%20project/schema.sql).
3. Go to **Storage**, click **New Bucket**, name it `property-images`, and set it to **Public**.
4. In your project `.env` file, populate:
   ```env
   SUPABASE_URL=https://<your-project-ref>.supabase.co
   SUPABASE_KEY=<your-service-role-or-anon-key>
   SUPABASE_BUCKET=property-images
   ```

*Note: The platform features a built-in persistent fallback mechanism so you can develop and test immediately even prior to configuring Supabase keys.*

---

## 🔑 Default Credentials

- **Admin Login Portal**: `http://localhost:5000/admin/login`
  - **Email**: `admin@homerental.com`
  - **Password**: `AdminPass123!`
- **Customer Sign-in**: `http://localhost:5000/login`
- **Customer Registration**: `http://localhost:5000/register`

---

## 🧪 Testing Suite

Automated integration tests cover all mandatory criteria:
- Admin login & route protection
- Customer registration and login
- Property listing creation, editing, and deletion
- Search filter queries
- Customer enquiries and favourites
- Status updates by administrator

Run:
```powershell
python -m pytest tests/ -v
```

