from datetime import datetime

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, MultipleFileField
from wtforms import (
    BooleanField,
    DateField,
    DateTimeLocalField,
    IntegerField,
    PasswordField,
    SelectField,
    SelectMultipleField,
    StringField,
    SubmitField,
    TextAreaField,
    TimeField,
)
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, Optional, ValidationError


IMAGE_TYPES = ["jpg", "jpeg", "png", "webp"]


class LoginForm(FlaskForm):
    identity = StringField("E-pošta ali uporabniško ime", validators=[DataRequired(), Length(max=254)])
    password = PasswordField("Geslo", validators=[DataRequired(), Length(max=256)])
    remember = BooleanField("Zapomni si me")
    submit = SubmitField("Prijava")


class ForgotPasswordForm(FlaskForm):
    email = StringField("E-poštni naslov", validators=[DataRequired(), Email(), Length(max=254)])
    submit = SubmitField("Pošlji navodila")


class ResetPasswordForm(FlaskForm):
    password = PasswordField("Novo geslo", validators=[DataRequired(), Length(min=12, max=256)])
    confirm = PasswordField("Ponovite geslo", validators=[DataRequired(), EqualTo("password")])
    submit = SubmitField("Shrani novo geslo")


class NewsForm(FlaskForm):
    title = StringField("Naslov", validators=[DataRequired(), Length(max=220)])
    category_id = SelectField("Kategorija", coerce=int, validators=[Optional()])
    summary = TextAreaField("Povzetek", validators=[Optional(), Length(max=1000)])
    body = TextAreaField("Vsebina", validators=[DataRequired()])
    image = FileField("Naslovna fotografija", validators=[FileAllowed(IMAGE_TYPES, "Dovoljene so slike JPG, PNG in WebP.")])
    status = SelectField("Stanje", choices=[("draft", "Osnutek"), ("published", "Objavljeno")])
    published_at = DateTimeLocalField("Datum objave", validators=[Optional()], format="%Y-%m-%dT%H:%M")
    submit = SubmitField("Shrani članek")


class CategoryForm(FlaskForm):
    name = StringField("Ime kategorije", validators=[DataRequired(), Length(max=80)])
    submit = SubmitField("Dodaj kategorijo")


class PlayerForm(FlaskForm):
    display_name = StringField("Ime igralca", validators=[DataRequired(), Length(max=160)])
    bio = TextAreaField("Predstavitev", validators=[Optional(), Length(max=3000)])
    active = BooleanField("Aktiven", default=True)
    submit = SubmitField("Shrani igralca")


class MemberForm(FlaskForm):
    first_name = StringField("Ime", validators=[DataRequired(), Length(max=100)])
    last_name = StringField("Priimek", validators=[DataRequired(), Length(max=100)])
    phone = StringField("Telefon", validators=[Optional(), Length(max=40)])
    membership_number = StringField("Članska številka", validators=[Optional(), Length(max=40)])
    membership_valid_until = DateField("Članstvo velja do", validators=[Optional()])
    active = BooleanField("Aktiven član", default=True)
    submit = SubmitField("Shrani člana")


class SeasonForm(FlaskForm):
    name = StringField("Naziv sezone", validators=[DataRequired(), Length(max=120)])
    starts_on = DateField("Začetek", validators=[DataRequired()])
    ends_on = DateField("Konec", validators=[DataRequired()])
    win_points = IntegerField("Točke za zmago", validators=[DataRequired(), NumberRange(min=0, max=20)], default=2)
    loss_points = IntegerField("Točke za poraz", validators=[DataRequired(), NumberRange(min=0, max=20)], default=0)
    rules = TextAreaField("Pravila", validators=[Optional()])
    is_current = BooleanField("Aktualna sezona")
    is_published = BooleanField("Javno objavljena")
    submit = SubmitField("Shrani sezono")

    def validate_ends_on(self, field):
        if self.starts_on.data and field.data < self.starts_on.data:
            raise ValidationError("Konec sezone ne more biti pred začetkom.")


class GroupForm(FlaskForm):
    name = StringField("Ime skupine", validators=[DataRequired(), Length(max=100)])
    player_ids = SelectMultipleField("Igralci", coerce=int, validators=[Optional()])
    submit = SubmitField("Shrani skupino")


class MatchForm(FlaskForm):
    season_id = SelectField("Sezona", coerce=int, validators=[DataRequired()])
    group_id = SelectField("Skupina", coerce=int, validators=[DataRequired()])
    player1_id = SelectField("Igralec 1", coerce=int, validators=[DataRequired()])
    player2_id = SelectField("Igralec 2", coerce=int, validators=[DataRequired()])
    scheduled_at = DateTimeLocalField("Termin", validators=[Optional()], format="%Y-%m-%dT%H:%M")
    notes = TextAreaField("Opombe", validators=[Optional(), Length(max=3000)])
    submit = SubmitField("Shrani tekmo")

    def validate_player2_id(self, field):
        if self.player1_id.data == field.data:
            raise ValidationError("Igralec ne more igrati sam proti sebi.")


class MatchResultForm(FlaskForm):
    score = StringField("Rezultat", validators=[DataRequired(), Length(max=80)], description="Primer: 6-4, 3-6, 10-8")
    played_at = DateTimeLocalField("Odigrano", validators=[Optional()], format="%Y-%m-%dT%H:%M", default=datetime.now)
    notes = TextAreaField("Opombe", validators=[Optional(), Length(max=3000)])
    submit = SubmitField("Vpiši rezultat")


class CourtForm(FlaskForm):
    name = StringField("Naziv igrišča", validators=[DataRequired(), Length(max=100)])
    surface = StringField("Podlaga", validators=[DataRequired(), Length(max=50)], default="peščena")
    opening_time = TimeField("Odprtje", validators=[DataRequired()])
    closing_time = TimeField("Zaprtje", validators=[DataRequired()])
    slot_minutes = IntegerField("Trajanje termina", validators=[DataRequired(), NumberRange(min=30, max=240)], default=60)
    active = BooleanField("Aktivno", default=True)
    submit = SubmitField("Shrani igrišče")


class ReservationForm(FlaskForm):
    court_id = SelectField("Igrišče", coerce=int, validators=[DataRequired()])
    starts_at = DateTimeLocalField("Začetek", validators=[DataRequired()], format="%Y-%m-%dT%H:%M")
    ends_at = DateTimeLocalField("Konec", validators=[DataRequired()], format="%Y-%m-%dT%H:%M")
    notes = TextAreaField("Opomba", validators=[Optional(), Length(max=1000)])
    submit = SubmitField("Rezerviraj")

    def validate_ends_at(self, field):
        if self.starts_at.data and field.data <= self.starts_at.data:
            raise ValidationError("Konec mora biti po začetku rezervacije.")


class CourtBlockForm(FlaskForm):
    court_id = SelectField("Igrišče", coerce=int, validators=[DataRequired()])
    kind = SelectField("Vrsta", choices=[("maintenance", "Vzdrževanje"), ("event", "Dogodek")])
    title = StringField("Naziv", validators=[DataRequired(), Length(max=160)])
    starts_at = DateTimeLocalField("Začetek", validators=[DataRequired()], format="%Y-%m-%dT%H:%M")
    ends_at = DateTimeLocalField("Konec", validators=[DataRequired()], format="%Y-%m-%dT%H:%M")
    notes = TextAreaField("Opomba", validators=[Optional(), Length(max=1000)])
    submit = SubmitField("Blokiraj termin")

    def validate_ends_at(self, field):
        if self.starts_at.data and field.data <= self.starts_at.data:
            raise ValidationError("Konec mora biti po začetku blokade.")


class GalleryForm(FlaskForm):
    title = StringField("Naslov albuma", validators=[DataRequired(), Length(max=180)])
    description = TextAreaField("Opis", validators=[Optional(), Length(max=3000)])
    is_published = BooleanField("Javno objavljen")
    images = MultipleFileField("Fotografije", validators=[FileAllowed(IMAGE_TYPES, "Dovoljene so slike JPG, PNG in WebP.")])
    submit = SubmitField("Shrani album")


class ClubContentForm(FlaskForm):
    section_key = SelectField(
        "Razdelek",
        choices=[
            ("about", "O klubu"),
            ("members", "Člani"),
            ("statute", "Statut kluba"),
            ("membership", "Članstvo in članarina"),
            ("documents", "Dokumenti"),
            ("rules", "Pravila tenisa"),
            ("contact", "Kontakt"),
            ("courts", "Igrišča"),
        ],
    )
    title = StringField("Naslov", validators=[DataRequired(), Length(max=180)])
    body = TextAreaField("Vsebina", validators=[DataRequired()])
    is_published = BooleanField("Objavljeno", default=True)
    submit = SubmitField("Shrani vsebino")


class CommitteeForm(FlaskForm):
    name = StringField("Naziv odbora ali komisije", validators=[DataRequired(), Length(max=160)])
    sort_order = IntegerField("Vrstni red", validators=[DataRequired(), NumberRange(min=0, max=999)], default=0)
    submit = SubmitField("Shrani organ")


class CommitteeMemberForm(FlaskForm):
    name = StringField("Ime in priimek", validators=[DataRequired(), Length(max=160)])
    position = StringField("Funkcija", validators=[DataRequired(), Length(max=120)])
    sort_order = IntegerField("Vrstni red", validators=[DataRequired(), NumberRange(min=0, max=999)], default=0)
    submit = SubmitField("Shrani člana")


class UserRoleForm(FlaskForm):
    roles = SelectMultipleField("Vloge", choices=[("administrator", "Administrator"), ("member", "Član")])
    active = BooleanField("Aktiven račun")
    submit = SubmitField("Shrani dostop")


class UserCreateForm(FlaskForm):
    email = StringField("E-pošta", validators=[DataRequired(), Email(), Length(max=254)])
    username = StringField("Uporabniško ime", validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField("Začasno geslo", validators=[DataRequired(), Length(min=12, max=256)])
    roles = SelectMultipleField("Vloge", choices=[("administrator", "Administrator"), ("member", "Član")], validators=[DataRequired()])
    submit = SubmitField("Ustvari račun")


class SettingsForm(FlaskForm):
    site_name = StringField("Naziv strani", validators=[DataRequired(), Length(max=180)])
    contact_email = StringField("Kontaktni e-poštni naslov", validators=[Optional(), Email(), Length(max=254)])
    contact_phone = StringField("Kontaktni telefon", validators=[Optional(), Length(max=50)])
    meta_description = TextAreaField("SEO opis", validators=[Optional(), Length(max=320)])
    submit = SubmitField("Shrani nastavitve")

