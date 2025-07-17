import os
import uuid
import logging
import pandas as pd
from typing import Optional
from io import BytesIO
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

class SupabaseService:
    def __init__(self):
        self.client = None
        if SUPABASE_URL and SUPABASE_KEY:
            self.client = create_client(SUPABASE_URL, SUPABASE_KEY)
            logger.info("Supabase client initialized")
        else:
            logger.warning("Supabase URL or key not set")
    
    def upload_file(self, file_path: str) -> str:
        """Upload file to Supabase storage bucket with better error handling"""
        try:
            if not self.client:
                logger.warning("Supabase client not available")
                return "Foto tersimpan (tanpa upload)"
            
            # Generate unique filename
            file_extension = os.path.splitext(file_path)[1]
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            
            # Read the image file
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            # Upload to Supabase storage bucket
            bucket_name = "photo"
            try:
                logger.info(f"Uploading to bucket: {bucket_name}")
                
                # Upload to Supabase storage bucket
                response = self.client.storage.from_(bucket_name).upload(
                    path=unique_filename,
                    file=file_data,
                    file_options={"content-type": "image/jpeg"}
                )
                
                if response:
                    # Get public URL
                    public_url = self.client.storage.from_(bucket_name).get_public_url(unique_filename)
                    logger.info(f"Successfully uploaded to Supabase: {public_url}")
                    return public_url
                else:
                    logger.error("Supabase upload failed: No response")
                    return "Foto tersimpan (gagal upload)"
                    
            except Exception as upload_error:
                error_str = str(upload_error)
                if "row-level security policy" in error_str.lower():
                    logger.error("Supabase RLS policy blocking upload. Please disable RLS for the 'photo' bucket or create appropriate policies.")
                    return "Foto tersimpan (RLS policy blocking upload)"
                elif "bucket not found" in error_str.lower():
                    logger.error("Supabase bucket 'photo' not found. Please create the bucket in your Supabase dashboard.")
                    return "Foto tersimpan (bucket tidak ditemukan)"
                else:
                    logger.error(f"Supabase upload error: {upload_error}")
                    return "Foto tersimpan (error sistem)"
                
        except Exception as e:
            logger.error(f"Supabase upload error: {e}")
            return "Foto tersimpan (error sistem)"
    
    def get_odp_dataframe(self) -> Optional[pd.DataFrame]:
        """Get ODP data from Supabase storage"""
        if not self.client:
            logger.error("Supabase client not available")
            return None
        
        try:
            bucket_name = "odp"
            files = self.client.storage.from_(bucket_name).list()
            if not files or len(files) == 0:
                logger.error("No ODP file found in bucket")
                return None
            
            filename = files[0]['name'] if isinstance(files[0], dict) else str(files[0])
            response = self.client.storage.from_(bucket_name).download(filename)
            file_bytes = response  # response sudah bytes
            df = pd.read_csv(BytesIO(file_bytes))
            return df
        except Exception as e:
            logger.error(f"Failed to download/read ODP file from Supabase: {e}")
            return None 