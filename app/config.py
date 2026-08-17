from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_KEY: str
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    GEMINI_API_KEY: str = ""

    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    PRO_PRICE_INR: int = 99
    PRO_DURATION_DAYS: int = 30
    # Where Razorpay redirects the browser after payment (your frontend)
    FRONTEND_URL: str = "http://localhost:3000"

    # Resend (HTTP-based email API) — used instead of raw SMTP because
    # Render's free tier blocks outbound SMTP ports (25/465/587) entirely.
    # Resend sends over normal HTTPS, which isn't affected by that.
    RESEND_API_KEY: str = ""
    SENDER_EMAIL: str = ""

    # Comma-separated list of allowed frontend origins for CORS.
    # e.g. "https://paperbanao.in,http://localhost:3000"
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    class Config:
        env_file = ".env"

settings = Settings()
