import re
from datetime import datetime

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import (
    StringField,
    PasswordField,
    BooleanField,
    SubmitField,
    SelectField,
    TextAreaField,
    HiddenField,
)
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, Optional


def strong_password(form, field):
    password = field.data or ""
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters long.")
    if not re.search(r"[A-Za-z]", password):
        raise ValidationError("Password must contain at least one letter.")
    if not re.search(r"[0-9]", password):
        raise ValidationError("Password must contain at least one number.")


class RegisterForm(FlaskForm):
    name = StringField("Full name", validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Password", validators=[DataRequired(), strong_password])
    confirm_password = PasswordField(
        "Confirm password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    submit = SubmitField("Create account")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = BooleanField("Remember me")
    submit = SubmitField("Log in")


class ForgotPasswordForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    submit = SubmitField("Send reset link")


class ResetPasswordForm(FlaskForm):
    password = PasswordField("New password", validators=[DataRequired(), strong_password])
    confirm_password = PasswordField(
        "Confirm new password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    submit = SubmitField("Reset password")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Current password", validators=[DataRequired()])
    new_password = PasswordField("New password", validators=[DataRequired(), strong_password])
    confirm_password = PasswordField(
        "Confirm new password",
        validators=[DataRequired(), EqualTo("new_password", message="Passwords must match.")],
    )
    submit = SubmitField("Change password")


class ResendVerificationForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    submit = SubmitField("Resend verification email")


class DeleteAccountForm(FlaskForm):
    password = PasswordField("Confirm your password", validators=[DataRequired()])
    submit = SubmitField("Permanently delete my account")


class ProfileForm(FlaskForm):
    location = StringField("Location", validators=[Length(max=150)])
    current_role = StringField("Current role", validators=[Length(max=150)])
    target_role = StringField("Target role", validators=[Length(max=150)])
    years_experience = StringField("Years of experience")
    education_level = SelectField(
        "Education level",
        choices=[
            ("", "Select..."),
            ("high_school", "High School"),
            ("associate", "Associate Degree"),
            ("bachelor", "Bachelor's Degree"),
            ("master", "Master's Degree"),
            ("phd", "PhD"),
            ("bootcamp", "Bootcamp"),
            ("self_taught", "Self-taught"),
            ("other", "Other"),
        ],
        validators=[Optional()],
    )
    remote_preference = SelectField(
        "Remote preference",
        choices=[
            ("", "Select..."),
            ("remote", "Remote"),
            ("hybrid", "Hybrid"),
            ("onsite", "On-site"),
            ("flexible", "Flexible"),
        ],
        validators=[Optional()],
    )
    preferred_industries = StringField("Preferred industries (comma-separated)")
    preferred_locations = StringField("Preferred locations (comma-separated)")
    bio = TextAreaField("Summary / bio", validators=[Length(max=2000)])
    submit = SubmitField("Save profile")

    def validate_years_experience(self, field):
        if field.data in (None, ""):
            return
        try:
            value = int(field.data)
        except ValueError:
            raise ValidationError("Years of experience must be a whole number.")
        if value < 0 or value > 60:
            raise ValidationError("Years of experience must be between 0 and 60.")


class AddSkillForm(FlaskForm):
    skill_name = StringField("Skill", validators=[DataRequired(), Length(max=120)])
    proficiency = SelectField(
        "Proficiency",
        choices=[
            ("", "Not specified"),
            ("beginner", "Beginner"),
            ("intermediate", "Intermediate"),
            ("advanced", "Advanced"),
            ("expert", "Expert"),
        ],
        validators=[Optional()],
    )
    years_experience = StringField("Years")
    submit = SubmitField("Add skill")

    def validate_years_experience(self, field):
        if field.data in (None, ""):
            return
        try:
            value = int(field.data)
        except ValueError:
            raise ValidationError("Years must be a whole number.")
        if value < 0 or value > 60:
            raise ValidationError("Years must be between 0 and 60.")


class AddCertificationForm(FlaskForm):
    name = StringField("Certification name", validators=[DataRequired(), Length(max=150)])
    issuing_organization = StringField("Issuing organization", validators=[Length(max=150)])
    year_obtained = StringField("Year obtained")
    submit = SubmitField("Add certification")

    def validate_year_obtained(self, field):
        if field.data in (None, ""):
            return
        try:
            value = int(field.data)
        except ValueError:
            raise ValidationError("Year must be a whole number.")
        if value < 1950 or value > 2100:
            raise ValidationError("Please enter a realistic year.")


class AdminAddCategoryForm(FlaskForm):
    name = StringField("Category name", validators=[DataRequired(), Length(max=100)])
    description = StringField("Description", validators=[Length(max=255)])
    submit = SubmitField("Add category")


class AdminAddSkillForm(FlaskForm):
    name = StringField("Skill name", validators=[DataRequired(), Length(max=120)])
    category_id = SelectField("Category", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Add skill")


class AdminAddAliasForm(FlaskForm):
    alias = StringField("Alias", validators=[DataRequired(), Length(max=120)])
    submit = SubmitField("Add alias")


class AdminAssignCategoryForm(FlaskForm):
    category_id = SelectField("Category", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Assign category")


class ResumeUploadForm(FlaskForm):
    file = FileField(
        "Resume file",
        validators=[
            FileRequired(message="Please choose a file to upload."),
            FileAllowed(["pdf", "docx", "txt"], message="Only PDF, DOCX, or TXT files are allowed."),
        ],
    )
    submit = SubmitField("Upload resume")


class JobAnalyzeForm(FlaskForm):
    job_text = TextAreaField("Paste job description", validators=[Optional(), Length(max=20000)])
    file = FileField(
        "Or upload a file",
        validators=[
            Optional(),
            FileAllowed(["pdf", "docx", "txt"], message="Only PDF, DOCX, or TXT files are allowed."),
        ],
    )
    submit = SubmitField("Analyze job")

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators=extra_validators):
            return False
        has_text = bool(self.job_text.data and self.job_text.data.strip())
        has_file = bool(self.file.data)
        if not has_text and not has_file:
            self.job_text.errors.append("Paste a job description or upload a file.")
            return False
        return True


class DataImportForm(FlaskForm):
    file = FileField(
        "Job dataset file",
        validators=[
            FileRequired(message="Please choose a file to upload."),
            FileAllowed(["csv", "xlsx", "json"], message="Only CSV, XLSX, or JSON files are allowed."),
        ],
    )
    submit = SubmitField("Import dataset")


class RoleSearchForm(FlaskForm):
    title = StringField("Role title", validators=[DataRequired(), Length(max=150)])
    submit = SubmitField("Search")


class MatchAnalyzeForm(FlaskForm):
    resume_id = SelectField("Resume", coerce=int, validators=[DataRequired()])
    job_id = SelectField("Job", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Analyze match")


class JobSearchForm(FlaskForm):
    query = StringField("Title or company", validators=[Optional(), Length(max=150)])
    location = StringField("Location", validators=[Optional(), Length(max=150)])
    remote_status = SelectField(
        "Work arrangement",
        choices=[("", "Any"), ("remote", "Remote"), ("hybrid", "Hybrid"), ("onsite", "On-site")],
        validators=[Optional()],
    )
    employment_type = SelectField(
        "Employment type",
        choices=[
            ("", "Any"),
            ("full_time", "Full-time"),
            ("part_time", "Part-time"),
            ("contract", "Contract"),
            ("internship", "Internship"),
            ("temporary", "Temporary"),
        ],
        validators=[Optional()],
    )
    max_experience = StringField("Max years of experience required", validators=[Optional()])
    min_salary = StringField("Min salary (USD/year)", validators=[Optional()])
    submit = SubmitField("Search")

    def validate_max_experience(self, field):
        if field.data in (None, ""):
            return
        try:
            int(field.data)
        except ValueError:
            raise ValidationError("Must be a whole number.")

    def validate_min_salary(self, field):
        if field.data in (None, ""):
            return
        try:
            int(field.data)
        except ValueError:
            raise ValidationError("Must be a whole number.")


class SaveJobForm(FlaskForm):
    submit = SubmitField("Save job")


class UpdateSavedJobForm(FlaskForm):
    status = SelectField(
        "Status",
        choices=[
            ("saved", "Saved"),
            ("applied", "Applied"),
            ("interview", "Interview"),
            ("offer", "Offer"),
            ("rejected", "Rejected"),
        ],
        validators=[DataRequired()],
    )
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=2000)])
    application_date = StringField("Application date (YYYY-MM-DD)", validators=[Optional()])
    interview_date = StringField("Interview date (YYYY-MM-DD)", validators=[Optional()])
    submit = SubmitField("Update")

    def _validate_date(self, field):
        if not field.data:
            return
        try:
            datetime.strptime(field.data.strip(), "%Y-%m-%d")
        except ValueError:
            raise ValidationError("Use YYYY-MM-DD format.")

    def validate_application_date(self, field):
        self._validate_date(field)

    def validate_interview_date(self, field):
        self._validate_date(field)


class QuickMatchForm(FlaskForm):
    resume_id = SelectField("Resume", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Check my fit")


class AskAssistantForm(FlaskForm):
    question = TextAreaField("Ask a question", validators=[DataRequired(), Length(max=2000)])
    job_id = HiddenField()
    submit = SubmitField("Ask")


class UpdateRoadmapSkillForm(FlaskForm):
    status = SelectField(
        "Status",
        choices=[("not_started", "Not started"), ("learning", "Learning"), ("completed", "Completed")],
        validators=[DataRequired()],
    )
    submit = SubmitField("Update")


class AdminAddLearningResourceForm(FlaskForm):
    skill_id = SelectField("Skill", coerce=int, validators=[DataRequired()])
    title = StringField("Title", validators=[DataRequired(), Length(max=200)])
    url = StringField("URL", validators=[DataRequired(), Length(max=500)])
    resource_type = SelectField(
        "Type",
        choices=[
            ("documentation", "Documentation"),
            ("tutorial", "Tutorial"),
            ("course", "Course"),
            ("book", "Book"),
            ("practice_platform", "Practice platform"),
        ],
        validators=[DataRequired()],
    )
    submit = SubmitField("Add resource")
