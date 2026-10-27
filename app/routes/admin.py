from datetime import datetime, timezone

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..extensions import db
from ..forms import (
    CategoryForm,
    ClubContentForm,
    CommitteeForm,
    CommitteeMemberForm,
    CourtBlockForm,
    CourtForm,
    GalleryForm,
    GroupForm,
    MatchForm,
    MatchResultForm,
    MemberForm,
    NewsForm,
    PlayerForm,
    SeasonForm,
    SettingsForm,
    UserCreateForm,
    UserRoleForm,
)
from ..models import (
    AuditLog,
    ClubCommittee,
    ClubContent,
    CommitteeMember,
    Court,
    Gallery,
    GalleryImage,
    LeagueGroup,
    LeagueMembership,
    Match,
    MatchSet,
    Member,
    NewsArticle,
    NewsCategory,
    Player,
    Reservation,
    Role,
    Season,
    SiteSetting,
    User,
)
from ..services.audit import record
from ..services.content import sanitize_rich_text, unique_slug
from ..services.scoring import parse_score
from ..services.standings import recalculate_group
from ..services.uploads import delete_image, save_image
from ..services.reservations import ReservationConflict, create_reservation


bp = Blueprint("admin", __name__)


@bp.before_request
def require_admin():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=request.full_path))
    if not current_user.has_any_role("administrator"):
        abort(403)


@bp.get("/")
def dashboard():
    now = datetime.now(timezone.utc)
    stats = {
        "members": Member.query.filter_by(active=True).count(),
        "players": Player.query.filter_by(active=True).count(),
        "played_matches": Match.query.filter_by(status="completed").count(),
        "upcoming_matches": Match.query.filter(Match.status == "scheduled", Match.scheduled_at >= now).count(),
        "courts": Court.query.filter_by(active=True).count(),
        "articles": NewsArticle.query.filter_by(status="published").count(),
    }
    activity = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(12).all()
    return render_template("admin/dashboard.html", stats=stats, activity=activity)


@bp.route("/novice", methods=["GET", "POST"])
def news():
    category_form = CategoryForm(prefix="category")
    if category_form.submit.data and category_form.validate_on_submit():
        category = NewsCategory(name=category_form.name.data, slug=unique_slug(NewsCategory, category_form.name.data))
        db.session.add(category)
        record("news.category_create", category)
        db.session.commit()
        flash("Kategorija je dodana.", "success")
        return redirect(url_for("admin.news"))
    articles = NewsArticle.query.order_by(NewsArticle.created_at.desc()).all()
    return render_template("admin/news/index.html", articles=articles, category_form=category_form)


def _news_form(article=None):
    form = NewsForm(obj=article)
    form.category_id.choices = [(0, "Brez kategorije")] + [(item.id, item.name) for item in NewsCategory.query.order_by(NewsCategory.name)]
    if request.method == "GET" and article:
        form.category_id.data = article.category_id or 0
        form.body.data = article.body_html
    return form


@bp.route("/novice/nova", methods=["GET", "POST"])
def news_create():
    form = _news_form()
    if form.validate_on_submit():
        article = NewsArticle(author=current_user)
        _set_article(article, form)
        db.session.add(article)
        db.session.flush()
        record("news.create", article)
        db.session.commit()
        flash("Članek je shranjen.", "success")
        return redirect(url_for("admin.news"))
    return render_template("admin/news/form.html", form=form, article=None)


@bp.route("/novice/<int:article_id>/uredi", methods=["GET", "POST"])
def news_edit(article_id):
    article = db.get_or_404(NewsArticle, article_id)
    form = _news_form(article)
    if form.validate_on_submit():
        _set_article(article, form)
        record("news.update", article)
        db.session.commit()
        flash("Članek je posodobljen.", "success")
        return redirect(url_for("admin.news"))
    return render_template("admin/news/form.html", form=form, article=article)


def _set_article(article, form):
    article.title = form.title.data.strip()
    article.slug = unique_slug(NewsArticle, article.title, article.id)
    article.category_id = form.category_id.data or None
    article.summary = form.summary.data
    article.body_html = sanitize_rich_text(form.body.data)
    article.status = form.status.data
    article.published_at = form.published_at.data
    if article.status == "published" and not article.published_at:
        article.published_at = datetime.now(timezone.utc)
    if form.image.data:
        article.image_key, _, _ = save_image(form.image.data, "news")


@bp.post("/novice/<int:article_id>/izbrisi")
def news_delete(article_id):
    article = db.get_or_404(NewsArticle, article_id)
    record("news.delete", article, {"title": article.title})
    db.session.delete(article)
    db.session.commit()
    flash("Članek je izbrisan.", "success")
    return redirect(url_for("admin.news"))


@bp.get("/igralci")
def players():
    return render_template("admin/players/index.html", players=Player.query.order_by(Player.display_name).all())


@bp.route("/igralci/nov", methods=["GET", "POST"])
@bp.route("/igralci/<int:player_id>/uredi", methods=["GET", "POST"])
def player_form(player_id=None):
    player = db.get_or_404(Player, player_id) if player_id else None
    form = PlayerForm(obj=player)
    if form.validate_on_submit():
        player = player or Player()
        form.populate_obj(player)
        player.slug = unique_slug(Player, player.display_name, player.id)
        db.session.add(player)
        db.session.flush()
        record("player.update" if player_id else "player.create", player)
        db.session.commit()
        flash("Igralec je shranjen.", "success")
        return redirect(url_for("admin.players"))
    return render_template("admin/players/form.html", form=form, player=player)


@bp.get("/clani")
def members():
    return render_template("admin/members/index.html", members=Member.query.order_by(Member.last_name, Member.first_name).all())


@bp.route("/clani/nov", methods=["GET", "POST"])
@bp.route("/clani/<int:member_id>/uredi", methods=["GET", "POST"])
def member_form(member_id=None):
    member = db.get_or_404(Member, member_id) if member_id else None
    form = MemberForm(obj=member)
    if form.validate_on_submit():
        member = member or Member()
        form.populate_obj(member)
        db.session.add(member)
        db.session.flush()
        record("member.update" if member_id else "member.create", member)
        db.session.commit()
        flash("Član je shranjen.", "success")
        return redirect(url_for("admin.members"))
    return render_template("admin/members/form.html", form=form, member=member)


@bp.get("/liga")
def seasons():
    return render_template("admin/league/index.html", seasons=Season.query.order_by(Season.starts_on.desc()).all())


@bp.route("/liga/sezona/nova", methods=["GET", "POST"])
@bp.route("/liga/sezona/<int:season_id>/uredi", methods=["GET", "POST"])
def season_form(season_id=None):
    season = db.get_or_404(Season, season_id) if season_id else None
    form = SeasonForm(obj=season)
    if form.validate_on_submit():
        season = season or Season()
        form.populate_obj(season)
        season.slug = unique_slug(Season, season.name, season.id)
        if season.is_current:
            Season.query.filter(Season.id != (season.id or 0)).update({Season.is_current: False})
        db.session.add(season)
        db.session.flush()
        record("season.update" if season_id else "season.create", season)
        db.session.commit()
        flash("Sezona je shranjena.", "success")
        return redirect(url_for("admin.seasons"))
    return render_template("admin/league/season_form.html", form=form, season=season)


@bp.route("/liga/sezona/<int:season_id>/skupina/nova", methods=["GET", "POST"])
@bp.route("/liga/skupina/<int:group_id>/uredi", methods=["GET", "POST"])
def group_form(season_id=None, group_id=None):
    group = db.get_or_404(LeagueGroup, group_id) if group_id else None
    season = group.season if group else db.get_or_404(Season, season_id)
    form = GroupForm(obj=group)
    form.player_ids.choices = [(player.id, player.display_name) for player in Player.query.filter_by(active=True).order_by(Player.display_name)]
    if request.method == "GET" and group:
        form.player_ids.data = [membership.player_id for membership in group.memberships]
    if form.validate_on_submit():
        group = group or LeagueGroup(season=season)
        group.name = form.name.data
        db.session.add(group)
        db.session.flush()
        selected = set(form.player_ids.data)
        for membership in list(group.memberships):
            if membership.player_id not in selected:
                db.session.delete(membership)
        existing = {membership.player_id for membership in group.memberships}
        for player_id in selected - existing:
            db.session.add(LeagueMembership(group_id=group.id, player_id=player_id))
        record("league_group.update" if group_id else "league_group.create", group)
        recalculate_group(group)
        db.session.commit()
        flash("Skupina je shranjena.", "success")
        return redirect(url_for("admin.seasons"))
    return render_template("admin/league/group_form.html", form=form, group=group, season=season)


def _match_form(match=None):
    form = MatchForm(obj=match)
    form.season_id.choices = [(item.id, item.name) for item in Season.query.order_by(Season.starts_on.desc())]
    form.group_id.choices = [(item.id, f"{item.season.name} — {item.name}") for item in LeagueGroup.query.join(Season).order_by(Season.starts_on.desc())]
    form.player1_id.choices = [(item.id, item.display_name) for item in Player.query.filter_by(active=True).order_by(Player.display_name)]
    form.player2_id.choices = list(form.player1_id.choices)
    return form


@bp.get("/tekme")
def matches():
    return render_template("admin/league/matches.html", matches=Match.query.order_by(Match.scheduled_at.desc()).all())


@bp.route("/tekme/nova", methods=["GET", "POST"])
@bp.route("/tekme/<int:match_id>/uredi", methods=["GET", "POST"])
def match_form(match_id=None):
    match = db.get_or_404(Match, match_id) if match_id else None
    form = _match_form(match)
    if form.validate_on_submit():
        group = db.session.get(LeagueGroup, form.group_id.data)
        if not group or group.season_id != form.season_id.data:
            form.group_id.errors.append("Skupina ne pripada izbrani sezoni.")
        else:
            match = match or Match(status="scheduled")
            form.populate_obj(match)
            db.session.add(match)
            db.session.flush()
            record("match.update" if match_id else "match.create", match)
            db.session.commit()
            flash("Tekma je shranjena.", "success")
            return redirect(url_for("admin.matches"))
    return render_template("admin/league/match_form.html", form=form, match=match)


@bp.route("/tekme/<int:match_id>/rezultat", methods=["GET", "POST"])
def match_result(match_id):
    match = db.get_or_404(Match, match_id)
    form = MatchResultForm()
    if request.method == "GET" and match.sets:
        form.score.data = ", ".join(f"{item.player1_games}-{item.player2_games}" for item in match.sets)
        form.played_at.data = match.played_at
        form.notes.data = match.notes
    if form.validate_on_submit():
        try:
            sets, winner_number = parse_score(form.score.data)
        except ValueError as error:
            form.score.errors.append(str(error))
        else:
            match.sets.clear()
            db.session.flush()
            for number, item in enumerate(sets, 1):
                match.sets.append(MatchSet(set_number=number, player1_games=item.player1_games, player2_games=item.player2_games, tiebreak1=item.tiebreak1, tiebreak2=item.tiebreak2))
            match.winner_id = match.player1_id if winner_number == 1 else match.player2_id
            match.played_at = form.played_at.data or datetime.now(timezone.utc)
            match.notes = form.notes.data
            match.status = "completed"
            record("match.result", match, {"score": form.score.data})
            recalculate_group(match.group)
            db.session.commit()
            flash("Rezultat in lestvica sta posodobljena.", "success")
            return redirect(url_for("admin.matches"))
    return render_template("admin/league/result_form.html", form=form, match=match)


@bp.get("/igrisca")
def courts():
    return render_template("admin/courts/index.html", courts=Court.query.order_by(Court.name).all())


@bp.route("/igrisca/novo", methods=["GET", "POST"])
@bp.route("/igrisca/<int:court_id>/uredi", methods=["GET", "POST"])
def court_form(court_id=None):
    court = db.get_or_404(Court, court_id) if court_id else None
    form = CourtForm(obj=court)
    if form.validate_on_submit():
        court = court or Court()
        form.populate_obj(court)
        db.session.add(court)
        db.session.flush()
        record("court.update" if court_id else "court.create", court)
        db.session.commit()
        flash("Igrišče je shranjeno.", "success")
        return redirect(url_for("admin.courts"))
    return render_template("admin/courts/form.html", form=form, court=court)


@bp.get("/rezervacije")
def reservations():
    items = Reservation.query.order_by(Reservation.starts_at.desc()).limit(250).all()
    return render_template("admin/reservations/index.html", reservations=items)


@bp.route("/rezervacije/blokada", methods=["GET", "POST"])
def reservation_block():
    form = CourtBlockForm()
    form.court_id.choices = [(court.id, court.name) for court in Court.query.filter_by(active=True).order_by(Court.name)]
    if form.validate_on_submit():
        court = db.session.get(Court, form.court_id.data)
        try:
            reservation = create_reservation(
                court=court,
                user=current_user,
                starts_at=form.starts_at.data,
                ends_at=form.ends_at.data,
                kind=form.kind.data,
                title=form.title.data,
                notes=form.notes.data,
            )
            record("reservation.block", reservation)
            db.session.commit()
            flash("Termin je blokiran.", "success")
            return redirect(url_for("admin.reservations"))
        except (ReservationConflict, ValueError) as error:
            db.session.rollback()
            flash(str(error), "error")
    return render_template("admin/reservations/form.html", form=form)


@bp.post("/rezervacije/<int:reservation_id>/preklic")
def reservation_cancel(reservation_id):
    reservation = db.get_or_404(Reservation, reservation_id)
    reservation.status = "cancelled"
    record("reservation.admin_cancel", reservation)
    db.session.commit()
    flash("Termin je preklican.", "success")
    return redirect(url_for("admin.reservations"))


@bp.get("/galerije")
def galleries():
    return render_template("admin/galleries/index.html", galleries=Gallery.query.order_by(Gallery.created_at.desc()).all())


@bp.route("/galerije/nova", methods=["GET", "POST"])
@bp.route("/galerije/<int:gallery_id>/uredi", methods=["GET", "POST"])
def gallery_form(gallery_id=None):
    gallery = db.get_or_404(Gallery, gallery_id) if gallery_id else None
    form = GalleryForm(obj=gallery)
    if form.validate_on_submit():
        gallery = gallery or Gallery()
        gallery.title = form.title.data
        gallery.slug = unique_slug(Gallery, gallery.title, gallery.id)
        gallery.description = form.description.data
        gallery.is_published = form.is_published.data
        db.session.add(gallery)
        db.session.flush()
        for upload in form.images.data or []:
            if upload and upload.filename:
                key, width, height = save_image(upload, f"galleries/{gallery.id}")
                image = GalleryImage(gallery=gallery, storage_key=key, width=width, height=height, sort_order=len(gallery.images))
                db.session.add(image)
                db.session.flush()
                if not gallery.cover_image_id:
                    gallery.cover_image_id = image.id
        record("gallery.update" if gallery_id else "gallery.create", gallery)
        db.session.commit()
        flash("Galerija je shranjena.", "success")
        return redirect(url_for("admin.galleries"))
    return render_template("admin/galleries/form.html", form=form, gallery=gallery)


@bp.post("/galerije/slika/<int:image_id>/izbrisi")
def gallery_image_delete(image_id):
    image = db.get_or_404(GalleryImage, image_id)
    gallery_id = image.gallery_id
    if image.gallery.cover_image_id == image.id:
        image.gallery.cover_image_id = None
    record("gallery_image.delete", image)
    delete_image(image.storage_key)
    db.session.delete(image)
    db.session.commit()
    flash("Fotografija je odstranjena iz albuma.", "success")
    return redirect(url_for("admin.gallery_form", gallery_id=gallery_id))


@bp.get("/vsebina")
def content():
    return render_template("admin/content/index.html", sections=ClubContent.query.order_by(ClubContent.section_key).all())


@bp.route("/vsebina/nova", methods=["GET", "POST"])
@bp.route("/vsebina/<int:content_id>/uredi", methods=["GET", "POST"])
def content_form(content_id=None):
    section = db.get_or_404(ClubContent, content_id) if content_id else None
    form = ClubContentForm(obj=section)
    if request.method == "GET" and section:
        form.body.data = section.body_html
    if form.validate_on_submit():
        existing = ClubContent.query.filter_by(section_key=form.section_key.data).first()
        if existing and existing.id != (section.id if section else None):
            form.section_key.errors.append("Ta razdelek že obstaja.")
        else:
            section = section or ClubContent()
            section.section_key = form.section_key.data
            section.title = form.title.data
            section.body_html = sanitize_rich_text(form.body.data)
            section.is_published = form.is_published.data
            db.session.add(section)
            db.session.flush()
            record("content.update" if content_id else "content.create", section)
            db.session.commit()
            flash("Vsebina je shranjena.", "success")
            return redirect(url_for("admin.content"))
    return render_template("admin/content/form.html", form=form, section=section)


@bp.get("/organi-kluba")
def committees():
    items = ClubCommittee.query.order_by(ClubCommittee.sort_order, ClubCommittee.name).all()
    return render_template("admin/committees/index.html", committees=items)


@bp.route("/organi-kluba/nov", methods=["GET", "POST"])
@bp.route("/organi-kluba/<int:committee_id>/uredi", methods=["GET", "POST"])
def committee_form(committee_id=None):
    committee = db.get_or_404(ClubCommittee, committee_id) if committee_id else None
    form = CommitteeForm(obj=committee)
    if form.validate_on_submit():
        committee = committee or ClubCommittee()
        committee.name = form.name.data.strip()
        committee.sort_order = form.sort_order.data
        committee.slug = unique_slug(ClubCommittee, committee.name, committee.id)
        db.session.add(committee)
        db.session.flush()
        record("committee.update" if committee_id else "committee.create", committee)
        db.session.commit()
        flash("Organ kluba je shranjen.", "success")
        return redirect(url_for("admin.committees"))
    return render_template("admin/committees/form.html", form=form, committee=committee)


@bp.post("/organi-kluba/<int:committee_id>/izbrisi")
def committee_delete(committee_id):
    committee = db.get_or_404(ClubCommittee, committee_id)
    record("committee.delete", committee, {"name": committee.name})
    db.session.delete(committee)
    db.session.commit()
    flash("Organ kluba je izbrisan.", "success")
    return redirect(url_for("admin.committees"))


@bp.route("/organi-kluba/<int:committee_id>/clan/nov", methods=["GET", "POST"])
@bp.route("/organi-kluba/clan/<int:member_id>/uredi", methods=["GET", "POST"])
def committee_member_form(committee_id=None, member_id=None):
    member = db.get_or_404(CommitteeMember, member_id) if member_id else None
    committee = member.committee if member else db.get_or_404(ClubCommittee, committee_id)
    form = CommitteeMemberForm(obj=member)
    if form.validate_on_submit():
        member = member or CommitteeMember(committee=committee)
        member.name = form.name.data.strip()
        member.position = form.position.data.strip()
        member.sort_order = form.sort_order.data
        db.session.add(member)
        db.session.flush()
        record("committee_member.update" if member_id else "committee_member.create", member)
        db.session.commit()
        flash("Član organa je shranjen.", "success")
        return redirect(url_for("admin.committees"))
    return render_template("admin/committees/member_form.html", form=form, committee=committee, member=member)


@bp.post("/organi-kluba/clan/<int:member_id>/izbrisi")
def committee_member_delete(member_id):
    member = db.get_or_404(CommitteeMember, member_id)
    record("committee_member.delete", member, {"name": member.name})
    db.session.delete(member)
    db.session.commit()
    flash("Član organa je odstranjen.", "success")
    return redirect(url_for("admin.committees"))


@bp.get("/uporabniki")
def users():
    return render_template("admin/users/index.html", users=User.query.order_by(User.username).all())


@bp.route("/uporabniki/nov", methods=["GET", "POST"])
def user_create():
    form = UserCreateForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        username = form.username.data.strip()
        if User.query.filter((User.email == email) | (User.username == username)).first():
            form.email.errors.append("Uporabnik s tem naslovom ali uporabniškim imenom že obstaja.")
        else:
            roles = Role.query.filter(Role.name.in_(form.roles.data)).all()
            user = User(email=email, username=username, roles=roles)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.flush()
            record("user.create", user, {"roles": form.roles.data})
            db.session.commit()
            flash("Uporabniški račun je ustvarjen.", "success")
            return redirect(url_for("admin.users"))
    return render_template("admin/users/create_form.html", form=form)


@bp.route("/uporabniki/<int:user_id>/dostop", methods=["GET", "POST"])
def user_access(user_id):
    user = db.get_or_404(User, user_id)
    form = UserRoleForm()
    if request.method == "GET":
        form.roles.data = [role.name for role in user.roles]
        form.active.data = user.is_active
    if form.validate_on_submit():
        roles = Role.query.filter(Role.name.in_(form.roles.data)).all()
        if user.id == current_user.id and (not form.active.data or "administrator" not in form.roles.data):
            form.roles.errors.append("Svojemu računu ne morete odvzeti skrbniškega dostopa.")
        else:
            user.roles = roles
            user.is_active = form.active.data
            record("user.access_update", user, {"roles": form.roles.data, "active": user.is_active})
            db.session.commit()
            flash("Dostop je posodobljen.", "success")
            return redirect(url_for("admin.users"))
    return render_template("admin/users/access_form.html", form=form, user=user)


@bp.route("/nastavitve", methods=["GET", "POST"])
def settings():
    stored = {item.key: item.value for item in SiteSetting.query.all()}
    form = SettingsForm(data=stored if request.method == "GET" else None)
    if form.validate_on_submit():
        for key in ("site_name", "contact_email", "contact_phone", "meta_description"):
            setting = SiteSetting.query.filter_by(key=key).first() or SiteSetting(key=key)
            setting.value = getattr(form, key).data or ""
            db.session.add(setting)
        db.session.flush()
        target = SiteSetting.query.first()
        record("settings.update", target, {"keys": ["site_name", "contact_email", "contact_phone", "meta_description"]})
        db.session.commit()
        flash("Nastavitve so shranjene.", "success")
        return redirect(url_for("admin.settings"))
    return render_template("admin/settings.html", form=form)

