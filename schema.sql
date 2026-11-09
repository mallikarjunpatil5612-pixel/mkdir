-- ====================================================================
-- HOME RENTAL WEBSITE DATABASE SCHEMA (SUPABASE POSTGRESQL)
-- ROLES: ADMIN and CUSTOMER ONLY
-- ====================================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. USERS TABLE
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    auth_user_id TEXT UNIQUE, -- Supabase auth id or server auth id
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    role VARCHAR(20) NOT NULL CHECK (role IN ('ADMIN', 'CUSTOMER')) DEFAULT 'CUSTOMER',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 2. PROPERTIES TABLE
CREATE TABLE IF NOT EXISTS public.properties (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255) NOT NULL,
    property_type VARCHAR(100) NOT NULL, -- e.g., Apartment, Villa, Independent House, Studio
    address TEXT NOT NULL,
    city VARCHAR(100) NOT NULL,
    locality VARCHAR(150) NOT NULL,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    monthly_rent NUMERIC(12, 2) NOT NULL CHECK (monthly_rent >= 0),
    security_deposit NUMERIC(12, 2) NOT NULL CHECK (security_deposit >= 0),
    bedrooms INTEGER NOT NULL CHECK (bedrooms >= 0),
    bathrooms INTEGER NOT NULL CHECK (bathrooms >= 0),
    balconies INTEGER DEFAULT 0 CHECK (balconies >= 0),
    area_sqft NUMERIC(10, 2) NOT NULL CHECK (area_sqft > 0),
    furnishing_status VARCHAR(50) NOT NULL CHECK (furnishing_status IN ('Furnished', 'Semi-Furnished', 'Unfurnished')),
    parking_available BOOLEAN DEFAULT false,
    water_available VARCHAR(100) DEFAULT '24/7 Supply',
    amenities TEXT[], -- Array of strings e.g., ['Gym', 'Lift', 'Security', 'Power Backup', 'Swimming Pool']
    description TEXT,
    contact_phone VARCHAR(50) NOT NULL,
    is_published BOOLEAN DEFAULT true,
    is_available BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 3. PROPERTY IMAGES TABLE
CREATE TABLE IF NOT EXISTS public.property_images (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property_id UUID NOT NULL REFERENCES public.properties(id) ON DELETE CASCADE,
    storage_path TEXT NOT NULL,
    image_url TEXT NOT NULL,
    is_primary BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 4. FAVOURITES TABLE
CREATE TABLE IF NOT EXISTS public.favourites (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    property_id UUID NOT NULL REFERENCES public.properties(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    UNIQUE(customer_id, property_id)
);

-- 5. RENTAL ENQUIRIES TABLE
CREATE TABLE IF NOT EXISTS public.rental_enquiries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property_id UUID NOT NULL REFERENCES public.properties(id) ON DELETE CASCADE,
    customer_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('New', 'Contacted', 'Resolved')) DEFAULT 'New',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 6. ADMIN LOGS TABLE
CREATE TABLE IF NOT EXISTS public.admin_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    admin_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- INDEXES FOR MAXIMUM QUERY PERFORMANCE
CREATE INDEX IF NOT EXISTS idx_properties_city ON public.properties (city);
CREATE INDEX IF NOT EXISTS idx_properties_locality ON public.properties (locality);
CREATE INDEX IF NOT EXISTS idx_properties_rent ON public.properties (monthly_rent);
CREATE INDEX IF NOT EXISTS idx_properties_bedrooms ON public.properties (bedrooms);
CREATE INDEX IF NOT EXISTS idx_properties_is_published ON public.properties (is_published);
CREATE INDEX IF NOT EXISTS idx_properties_is_available ON public.properties (is_available);
CREATE INDEX IF NOT EXISTS idx_prop_images_property_id ON public.property_images (property_id);
CREATE INDEX IF NOT EXISTS idx_favourites_customer_id ON public.favourites (customer_id);
CREATE INDEX IF NOT EXISTS idx_rental_enquiries_prop ON public.rental_enquiries (property_id);
CREATE INDEX IF NOT EXISTS idx_rental_enquiries_cust ON public.rental_enquiries (customer_id);

-- STORAGE BUCKET CREATION (Run in Supabase SQL editor or create via Storage dashboard)
-- INSERT INTO storage.buckets (id, name, public) VALUES ('property-images', 'property-images', true)
-- ON CONFLICT (id) DO NOTHING;

