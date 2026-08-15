from supabase import create_client, Client
from app.config import settings

# Same Supabase project as the Streamlit app â€” this backend reads/writes
# the exact same tables (users, papers, curriculum, payments), so there is
# no data migration required. The Streamlit app can keep running unaffected
# while this backend is being built and tested.
supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

