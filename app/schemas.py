from pydantic import BaseModel, EmailStr
from typing import Optional, List

class SignupRequest(BaseModel):
    username: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class RequestPasswordReset(BaseModel):
    identifier: str  # username or email

class VerifyPasswordReset(BaseModel):
    identifier: str
    otp: str
    new_password: str

class QuestionTypeConfig(BaseModel):
    count: int = 0
    marks: int = 1
    difficulty: str = "Medium"

class GeneratePaperRequest(BaseModel):
    subject: str
    class_name: str
    topics: str = ""
    language: str = "English"
    include_answer_key: bool = True
    source_text: str = ""  # if set (from PDF Extract), questions are built strictly from this text
    mcq: QuestionTypeConfig = QuestionTypeConfig()
    fib: QuestionTypeConfig = QuestionTypeConfig()
    true_false: QuestionTypeConfig = QuestionTypeConfig()
    short_answer: QuestionTypeConfig = QuestionTypeConfig()
    long_answer: QuestionTypeConfig = QuestionTypeConfig()

class SavePaperRequest(BaseModel):
    subject: str
    board: str = "Standard"
    content: str

class ChaptersSaveRequest(BaseModel):
    class_name: str
    subject_name: str
    chapters: List[str]
