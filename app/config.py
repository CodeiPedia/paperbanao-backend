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

    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 465

    # Comma-separated list of allowed frontend origins for CORS.
    # e.g. "https://paperbanao.in,http://localhost:3000"
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    class Config:
        env_file = ".env"

settings = Settings()

