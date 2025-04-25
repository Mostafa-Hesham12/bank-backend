from supabase import create_client, ClientOptions
import os
from dotenv import load_dotenv

load_dotenv()

# Configure client options
client_options = ClientOptions(
    auto_refresh_token=False,
    persist_session=False
)

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY"),
    options=client_options
)