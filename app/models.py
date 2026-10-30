from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from flask import current_app
from flask_login import UserMixin
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager


def utcnow():
    return datetime.now(timezone.utc)


user_roles = db.Table(
    "user_roles",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class TimestampMixin:
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class Role(db.Model):
    __tablename__ = "roles"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255))


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_login_at = db.Column(db.DateTime(timezone=True))
    roles = db.relationship("Role", secondary=user_roles, lazy="selectin", backref="users")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password, method="scrypt")

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def has_any_role(self, *names: str) -> bool:
        return any(role.name in names for role in self.roles)

    def get_reset_token(self) -> str:
        serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
        return serializer.dumps({"user_id": self.id, "password_hash": self.password_hash[-16:]}, salt="password-reset")

    @staticmethod
    def verify_reset_token(token: str, max_age: int = 3600):
        serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
        try:
            data = serializer.loads(token, salt="password-reset", max_age=max_age)
        except (BadSignature, SignatureExpired):
            return None
        user = db.session.get(User, data.get("user_id"))
        if not user or user.password_hash[-16:] != data.get("password_hash"):
            return None
        return user


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Member(TimestampMixin, db.Model):
    __tablename__ = "members"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), unique=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(40))
    membership_number = db.Column(db.String(40), unique=True)
    membership_valid_until = db.Column(db.Date)
    active = db.Column(db.Boolean, nullable=False, default=True)
    user = db.relationship("User", backref=db.backref("member", uselist=False))

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class Player(TimestampMixin, db.Model):
    __tablename__ = "players"
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("members.id", ondelete="SET NULL"), unique=True)
    display_name = db.Column(db.String(160), nullable=False, index=True)
    slug = db.Column(db.String(180), unique=True, nullable=False, index=True)
    bio = db.Column(db.Text)
    active = db.Column(db.Boolean, nullable=False, default=True)
    member = db.relationship("Member", backref=db.backref("player", uselist=False))


class Season(TimestampMixin, db.Model):
    __tablename__ = "seasons"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(140), unique=True, nullable=False, index=True)
    starts_on = db.Column(db.Date, nullable=False)
    ends_on = db.Column(db.Date, nullable=False)
    is_current = db.Column(db.Boolean, nullable=False, default=False, index=True)
    is_published = db.Column(db.Boolean, nullable=False, default=False)
    win_points = db.Column(db.Integer, nullable=False, default=2)
    loss_points = db.Column(db.Integer, nullable=False, default=0)
    rules = db.Column(db.Text)
    __table_args__ = (
        CheckConstraint("ends_on >= starts_on", name="valid_dates"),
        CheckConstraint("win_points >= 0", name="nonnegative_win_points"),
        CheckConstraint("loss_points >= 0", name="nonnegative_loss_points"),
    )


class LeagueGroup(TimestampMixin, db.Model):
    __tablename__ = "league_groups"
    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    season = db.relationship("Season", backref=db.backref("groups", cascade="all, delete-orphan", order_by="LeagueGroup.sort_order"))
    __table_args__ = (UniqueConstraint("season_id", "name"),)


class LeagueMembership(db.Model):
    __tablename__ = "league_memberships"
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("league_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    player_id = db.Column(db.Integer, db.ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True)
    seed = db.Column(db.Integer)
    group = db.relationship("LeagueGroup", backref=db.backref("memberships", cascade="all, delete-orphan"))
    player = db.relationship("Player", backref="league_memberships")
    __table_args__ = (UniqueConstraint("group_id", "player_id"),)


class Match(TimestampMixin, db.Model):
    __tablename__ = "matches"
    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id = db.Column(db.Integer, db.ForeignKey("league_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    player1_id = db.Column(db.Integer, db.ForeignKey("players.id", ondelete="RESTRICT"), nullable=False, index=True)
    player2_id = db.Column(db.Integer, db.ForeignKey("players.id", ondelete="RESTRICT"), nullable=False, index=True)
    winner_id = db.Column(db.Integer, db.ForeignKey("players.id", ondelete="SET NULL"), index=True)
    scheduled_at = db.Column(db.DateTime(timezone=True), index=True)
    played_at = db.Column(db.DateTime(timezone=True))
    status = db.Column(db.String(24), nullable=False, default="scheduled", index=True)
    notes = db.Column(db.Text)
    season = db.relationship("Season", backref="matches")
    group = db.relationship("LeagueGroup", backref="matches")
    player1 = db.relationship("Player", foreign_keys=[player1_id], backref="matches_as_player1")
    player2 = db.relationship("Player", foreign_keys=[player2_id], backref="matches_as_player2")
    winner = db.relationship("Player", foreign_keys=[winner_id])
    __table_args__ = (
        CheckConstraint("player1_id <> player2_id", name="different_players"),
        CheckConstraint("status in ('scheduled','completed','cancelled','walkover')", name="valid_status"),
        Index("ix_matches_schedule_status", "scheduled_at", "status"),
    )


class MatchSet(db.Model):
    __tablename__ = "match_sets"
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True)
    set_number = db.Column(db.Integer, nullable=False)
    player1_games = db.Column(db.Integer, nullable=False)
    player2_games = db.Column(db.Integer, nullable=False)
    tiebreak1 = db.Column(db.Integer)
    tiebreak2 = db.Column(db.Integer)
    match = db.relationship("Match", backref=db.backref("sets", cascade="all, delete-orphan", order_by="MatchSet.set_number"))
    __table_args__ = (
        UniqueConstraint("match_id", "set_number"),
        CheckConstraint("set_number between 1 and 5", name="valid_set_number"),
        CheckConstraint("player1_games >= 0 and player2_games >= 0", name="nonnegative_games"),
    )


class Standing(db.Model):
    __tablename__ = "standings"
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("league_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    player_id = db.Column(db.Integer, db.ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True)
    played = db.Column(db.Integer, nullable=False, default=0)
    wins = db.Column(db.Integer, nullable=False, default=0)
    losses = db.Column(db.Integer, nullable=False, default=0)
    points = db.Column(db.Integer, nullable=False, default=0)
    sets_won = db.Column(db.Integer, nullable=False, default=0)
    sets_lost = db.Column(db.Integer, nullable=False, default=0)
    games_won = db.Column(db.Integer, nullable=False, default=0)
    games_lost = db.Column(db.Integer, nullable=False, default=0)
    group = db.relationship("LeagueGroup", backref=db.backref("standings", cascade="all, delete-orphan"))
    player = db.relationship("Player", backref="standings")
    __table_args__ = (UniqueConstraint("group_id", "player_id"),)

    @property
    def set_difference(self):
        return self.sets_won - self.sets_lost

    @property
    def game_difference(self):
        return self.games_won - self.games_lost


class Court(TimestampMixin, db.Model):
    __tablename__ = "courts"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    surface = db.Column(db.String(50), nullable=False, default="clay")
    active = db.Column(db.Boolean, nullable=False, default=True)
    opening_time = db.Column(db.Time, nullable=False)
    closing_time = db.Column(db.Time, nullable=False)
    slot_minutes = db.Column(db.Integer, nullable=False, default=60)


class Reservation(TimestampMixin, db.Model):
    __tablename__ = "reservations"
    id = db.Column(db.Integer, primary_key=True)
    court_id = db.Column(db.Integer, db.ForeignKey("courts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    starts_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    ends_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    status = db.Column(db.String(24), nullable=False, default="confirmed", index=True)
    kind = db.Column(db.String(24), nullable=False, default="booking")
    title = db.Column(db.String(160))
    notes = db.Column(db.Text)
    court = db.relationship("Court", backref="reservations")
    user = db.relationship("User", backref="reservations")
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="valid_time_range"),
        CheckConstraint("status in ('confirmed','cancelled')", name="valid_status"),
        CheckConstraint("kind in ('booking','maintenance','event')", name="valid_kind"),
        Index("ix_reservations_conflict_lookup", "court_id", "starts_at", "ends_at", "status"),
    )


class NewsCategory(db.Model):
    __tablename__ = "news_categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    slug = db.Column(db.String(90), unique=True, nullable=False)


class NewsArticle(TimestampMixin, db.Model):
    __tablename__ = "news_articles"
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("news_categories.id", ondelete="SET NULL"), index=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), index=True)
    title = db.Column(db.String(220), nullable=False)
    slug = db.Column(db.String(240), unique=True, nullable=False, index=True)
    summary = db.Column(db.Text)
    body_html = db.Column(db.Text, nullable=False)
    image_key = db.Column(db.String(500))
    status = db.Column(db.String(20), nullable=False, default="draft", index=True)
    published_at = db.Column(db.DateTime(timezone=True), index=True)
    is_pinned = db.Column(db.Boolean, nullable=False, default=False, index=True)
    category = db.relationship("NewsCategory", backref="articles")
    author = db.relationship("User", backref="articles")
    __table_args__ = (CheckConstraint("status in ('draft','published')", name="valid_status"),)

    @property
    def is_public(self):
        if not self.published_at or self.status != "published":
            return False
        published_at = self.published_at
        if published_at.tzinfo:
            published_at = published_at.astimezone(timezone.utc).replace(tzinfo=None)
        comparison_time = datetime.now(timezone.utc).replace(tzinfo=None)
        return published_at <= comparison_time

    @property
    def cover_image_key(self):
        if self.image_key:
            return self.image_key
        return self.images[0].storage_key if self.images else None


class NewsArticleImage(TimestampMixin, db.Model):
    __tablename__ = "news_article_images"
    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(
        db.Integer,
        db.ForeignKey("news_articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    storage_key = db.Column(db.String(500), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    article = db.relationship(
        "NewsArticle",
        backref=db.backref(
            "images", cascade="all, delete-orphan", order_by="NewsArticleImage.sort_order"
        ),
    )


class Gallery(TimestampMixin, db.Model):
    __tablename__ = "galleries"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    cover_image_id = db.Column(db.Integer, db.ForeignKey("gallery_images.id", use_alter=True, name="fk_galleries_cover_image_id_gallery_images"))
    is_published = db.Column(db.Boolean, nullable=False, default=False, index=True)
    cover_image = db.relationship("GalleryImage", foreign_keys=[cover_image_id], post_update=True)


class GalleryImage(TimestampMixin, db.Model):
    __tablename__ = "gallery_images"
    id = db.Column(db.Integer, primary_key=True)
    gallery_id = db.Column(db.Integer, db.ForeignKey("galleries.id", ondelete="CASCADE"), nullable=False, index=True)
    storage_key = db.Column(db.String(500), nullable=False)
    caption = db.Column(db.String(300))
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    gallery = db.relationship("Gallery", foreign_keys=[gallery_id], backref=db.backref("images", cascade="all, delete-orphan", order_by="GalleryImage.sort_order"))


class ClubCommittee(TimestampMixin, db.Model):
    __tablename__ = "club_committees"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False, index=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)


class CommitteeMember(TimestampMixin, db.Model):
    __tablename__ = "committee_members"
    id = db.Column(db.Integer, primary_key=True)
    committee_id = db.Column(db.Integer, db.ForeignKey("club_committees.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    position = db.Column(db.String(120), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    committee = db.relationship(
        "ClubCommittee",
        backref=db.backref("members", cascade="all, delete-orphan", order_by="CommitteeMember.sort_order"),
    )


class ClubContent(TimestampMixin, db.Model):
    __tablename__ = "club_content"
    id = db.Column(db.Integer, primary_key=True)
    section_key = db.Column(db.String(80), unique=True, nullable=False, index=True)
    title = db.Column(db.String(180), nullable=False)
    body_html = db.Column(db.Text, nullable=False)
    is_published = db.Column(db.Boolean, nullable=False, default=True)


class SiteSetting(TimestampMixin, db.Model):
    __tablename__ = "site_settings"
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value = db.Column(db.Text)
    value_type = db.Column(db.String(20), nullable=False, default="text")


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action = db.Column(db.String(100), nullable=False, index=True)
    entity_type = db.Column(db.String(100), nullable=False)
    entity_id = db.Column(db.String(100))
    details = db.Column(db.JSON)
    ip_address = db.Column(db.String(64))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    actor = db.relationship("User", backref="audit_logs")

