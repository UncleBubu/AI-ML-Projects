import os

# Fake env BEFORE the app imports config, so tests never touch real secrets.
os.environ.update(
    SUPABASE_URL="http://localhost:54321",
    SUPABASE_SERVICE_ROLE_KEY="test-service-key-for-unit-tests-only.eyJ.abc",
    PAYSTACK_SECRET_KEY="sk_test_secret",
    DISABLE_SCHEDULER="true",
)
