from supabase import create_client, ClientOptions
import os

# Configure client options
client_options = ClientOptions(
    auto_refresh_token=False,
    persist_session=False
)

# Initialize Supabase client using Railway environment variables
supabase = create_client(
    os.environ["SUPABASE_URL"],  # سيقرأ مباشرة من Railway Variables
    os.environ["SUPABASE_KEY"],  # سيقرأ مباشرة من Railway Variables
    options=client_options
)
