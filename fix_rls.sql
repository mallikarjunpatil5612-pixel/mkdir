-- ====================================================================
-- FIX: PERMIT FLASK BACKEND TO INSERT, UPDATE, SELECT & DELETE
-- Run this once in your Supabase SQL Editor
-- ====================================================================

-- 1. Disable Row Level Security on all application tables
ALTER TABLE IF EXISTS public.users DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.properties DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.property_images DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.rental_enquiries DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.favourites DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.admin_logs DISABLE ROW LEVEL SECURITY;

-- 2. Grant full permissions to anon and authenticated roles
GRANT ALL ON TABLE public.users TO anon, authenticated, service_role;
GRANT ALL ON TABLE public.properties TO anon, authenticated, service_role;
GRANT ALL ON TABLE public.property_images TO anon, authenticated, service_role;
GRANT ALL ON TABLE public.rental_enquiries TO anon, authenticated, service_role;
GRANT ALL ON TABLE public.favourites TO anon, authenticated, service_role;
GRANT ALL ON TABLE public.admin_logs TO anon, authenticated, service_role;

GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL ROUTINES IN SCHEMA public TO anon, authenticated, service_role;

-- 3. Storage Bucket & Policies for Property Images
INSERT INTO storage.buckets (id, name, public) 
VALUES ('property-images', 'property-images', true)
ON CONFLICT (id) DO UPDATE SET public = true;

-- Drop previous policies if they exist to avoid duplicates
DROP POLICY IF EXISTS "Public Access" ON storage.objects;
DROP POLICY IF EXISTS "Allow All Uploads" ON storage.objects;
DROP POLICY IF EXISTS "Allow All Updates" ON storage.objects;
DROP POLICY IF EXISTS "Allow All Deletes" ON storage.objects;

-- Allow public read access to images
CREATE POLICY "Public Access" 
ON storage.objects FOR SELECT 
USING (bucket_id = 'property-images');

-- Allow image uploads
CREATE POLICY "Allow All Uploads" 
ON storage.objects FOR INSERT 
WITH CHECK (bucket_id = 'property-images');

-- Allow image updates & deletions
CREATE POLICY "Allow All Updates" 
ON storage.objects FOR UPDATE 
USING (bucket_id = 'property-images');

CREATE POLICY "Allow All Deletes" 
ON storage.objects FOR DELETE 
USING (bucket_id = 'property-images');

