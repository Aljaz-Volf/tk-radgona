import json
from datetime import datetime, timezone

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..extensions import db
from ..forms import (
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
    SeasonCreateForm,
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
    NewsArticleImage,
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
from ..services.standings import (
    group_display_key,
    groups_for_display,
    is_separate_league,
    ordered_standings,
    recalculate_group,
)
from ..services.time import local_to_utc, local_today, one_year_after, utc_now_naive, utc_to_local
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


@bp.get("/novice")
def news():
    articles = NewsArticle.query.order_by(NewsArticle.created_at.desc()).all()
    pinned_article = next(
        (article for article in articles if article.is_pinned and article.is_public), None
    )
    return render_template(
        "admin/news/index.html",
        articles=articles,
        pinned_article=pinned_article,
    )


@bp.post("/novice/domaca-stran")
def news_homepage_selection():
    mode = request.form.get("homepage_mode", "latest")
    if mode == "latest":
        NewsArticle.query.update({NewsArticle.is_pinned: False}, synchronize_session=False)
        db.session.commit()
        flash("Domača stran bo prikazovala najnovejšo objavljeno novico.", "success")
        return redirect(url_for("admin.news"))

    if mode != "pinned":
        abort(400)

    try:
        article_id = int(request.form.get("pinned_article_id", ""))
    except (TypeError, ValueError):
        flash("Izberite novico, ki jo želite pripeti.", "error")
        return redirect(url_for("admin.news"))

    article = db.session.get(NewsArticle, article_id)
    if article is None or not article.is_public:
        flash("Pripnete lahko samo že objavljeno novico.", "error")
        return redirect(url_for("admin.news"))

    NewsArticle.query.filter(NewsArticle.id != article.id).update(
        {NewsArticle.is_pinned: False}, synchronize_session=False
    )
    article.is_pinned = True
    record("news.homepage_pin", article, {"title": article.title})
    db.session.commit()
    flash("Izbrana novica je pripeta na domačo stran.", "success")
    return redirect(url_for("admin.news"))


def _news_form(article=None):
    form = NewsForm(obj=article)
    if request.method == "GET":
        if article:
            form.body.data = article.body_html
            form.published_at.data = utc_to_local(article.published_at)
        else:
            form.published_at.data = utc_to_local(utc_now_naive())
    return form


def _save_news_article(article, form):
    uploads = [upload for upload in (form.images.data or []) if upload and upload.filename]
    existing_count = len(article.images) + (1 if article.image_key else 0)
    if existing_count + len(uploads) > 100:
        form.images.errors.append(
            f"Članek ima lahko največ 100 fotografij. Trenutno jih ima {existing_count}."
        )
        return False

    _set_article(article, form)
    db.session.add(article)
    db.session.flush()
    saved_keys = []
    try:
        start_order = len(article.images)
        for offset, upload in enumerate(uploads):
            key, width, height = save_image(upload, f"news/{article.id}")
            saved_keys.append(key)
            db.session.add(
                NewsArticleImage(
                    article=article,
                    storage_key=key,
                    width=width,
                    height=height,
                    sort_order=start_order + offset,
                )
            )
    except ValueError as error:
        db.session.rollback()
        for key in saved_keys:
            delete_image(key)
        form.images.errors.append(str(error))
        return False
    return True


@bp.route("/novice/nova", methods=["GET", "POST"])
def news_create():
    form = _news_form()
    if form.validate_on_submit():
        article = NewsArticle(author=current_user)
        if _save_news_article(article, form):
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
        if _save_news_article(article, form):
            record("news.update", article)
            db.session.commit()
            flash("Članek je posodobljen.", "success")
            return redirect(url_for("admin.news"))
    return render_template("admin/news/form.html", form=form, article=article)


def _set_article(article, form):
    article.title = form.title.data.strip()
    article.slug = unique_slug(NewsArticle, article.title, article.id)
    article.summary = form.summary.data
    article.body_html = sanitize_rich_text(form.body.data)
    article.status = form.status.data
    article.published_at = local_to_utc(form.published_at.data)
    if article.status == "published" and not article.published_at:
        article.published_at = utc_now_naive()


@bp.post("/novice/slika/<int:image_id>/izbrisi")
def news_image_delete(image_id):
    image = db.get_or_404(NewsArticleImage, image_id)
    article_id = image.article_id
    record("news_image.delete", image)
    delete_image(image.storage_key)
    db.session.delete(image)
    db.session.commit()
    flash("Fotografija je odstranjena iz članka.", "success")
    return redirect(url_for("admin.news_edit", article_id=article_id))


@bp.post("/novice/<int:article_id>/izbrisi")
def news_delete(article_id):
    article = db.get_or_404(NewsArticle, article_id)
    record("news.delete", article, {"title": article.title})
    keys = [image.storage_key for image in article.images]
    if article.image_key:
        keys.append(article.image_key)
    for key in set(keys):
        delete_image(key)
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
    if request.method == "GET":
        if member is None:
            form.membership_valid_until.data = one_year_after(local_today())
        form.active_player.data = bool(member and member.player and member.player.active)
    if form.validate_on_submit():
        member = member or Member()
        member.first_name = form.first_name.data.strip()
        member.last_name = form.last_name.data.strip()
        member.phone = form.phone.data.strip() if form.phone.data else None
        member.membership_number = form.membership_number.data.strip() if form.membership_number.data else None
        member.membership_valid_until = form.membership_valid_until.data
        member.active = form.active.data
        db.session.add(member)
        db.session.flush()

        player = member.player
        if player is not None:
            player.display_name = member.full_name
            player.slug = unique_slug(Player, player.display_name, player.id)
            player.active = bool(form.active_player.data)
            db.session.add(player)
        elif form.active_player.data:
            player = Player(
                member=member,
                display_name=member.full_name,
                slug=unique_slug(Player, member.full_name),
                active=True,
            )
            db.session.add(player)

        record(
            "member.update" if member_id else "member.create",
            member,
            {"active_player": bool(form.active_player.data)},
        )
        db.session.commit()
        flash("Član je shranjen.", "success")
        return redirect(url_for("admin.members"))
    return render_template("admin/members/form.html", form=form, member=member)


@bp.get("/liga")
def seasons():
    seasons = Season.query.order_by(Season.starts_on.desc()).all()
    active_player_ids = {player.id for player in Player.query.filter_by(active=True).all()}
    rows = []
    for season in seasons:
        season_groups = groups_for_display(season.groups)
        assigned_ids = {
            membership.player_id
            for group in season_groups
            for membership in group.memberships
        }
        rows.append(
            {
                "season": season,
                "groups": [
                    {
                        "group": group,
                        "player_count": len({membership.player_id for membership in group.memberships}),
                    }
                    for group in season_groups
                ],
                "player_count": len(assigned_ids),
                "unassigned_count": len(active_player_ids - assigned_ids),
                "is_past": season.ends_on < local_today(),
            }
        )
    return render_template("admin/league/index.html", season_rows=rows)


@bp.route("/liga/sezona/nova", methods=["GET", "POST"])
@bp.route("/liga/sezona/<int:season_id>/uredi", methods=["GET", "POST"])
def season_form(season_id=None):
    season = db.get_or_404(Season, season_id) if season_id else None
    if season is not None:
        form = SeasonForm(obj=season)
        if request.method == "GET" and season.setup_pending:
            form.is_published.data = season.publish_after_setup
        if form.validate_on_submit():
            requested_publication = form.is_published.data
            form.populate_obj(season)
            season.slug = unique_slug(Season, season.name, season.id)
            if season.setup_pending:
                season.publish_after_setup = requested_publication
                season.is_published = False
            elif season.is_current:
                Season.query.filter(Season.id != season.id).update({Season.is_current: False})
            db.session.add(season)
            db.session.flush()
            record("season.update", season)
            db.session.commit()
            flash("Sezona je shranjena.", "success")
            return redirect(url_for("admin.seasons"))
        return render_template("admin/league/season_form.html", form=form, season=season)

    previous_season = Season.query.order_by(Season.starts_on.desc()).first()
    previous_groups = (
        sorted(previous_season.groups, key=lambda item: (item.sort_order, item.id))
        if previous_season else []
    )
    if previous_groups:
        default_leagues = [
            {
                "name": group.name,
                "max_players": group.max_players,
                "source_group_id": group.id,
            }
            for group in previous_groups
        ]
    else:
        default_leagues = [
            {"name": name, "max_players": 8, "source_group_id": None}
            for name in ("1. Liga", "2. Liga", "3. Liga", "4. Liga", "Ženska Liga")
        ]

    form = SeasonCreateForm()
    league_error = None
    league_rows = default_leagues
    if request.method == "POST":
        names = request.form.getlist("league_name")
        maximums = request.form.getlist("league_max_players")
        sources = request.form.getlist("league_source_group_id")
        league_rows = []
        if not (len(names) == len(maximums) == len(sources)):
            league_error = "Podatki o ligah niso popolni."
        else:
            seen_names = set()
            for name, raw_maximum, raw_source in zip(names, maximums, sources):
                clean_name = name.strip()
                try:
                    maximum = int(raw_maximum)
                    source_group_id = int(raw_source) if raw_source else None
                except ValueError:
                    league_error = "Največje število igralcev mora biti veljavno število."
                    maximum = 8
                    source_group_id = None
                league_rows.append(
                    {
                        "name": clean_name,
                        "max_players": maximum,
                        "source_group_id": source_group_id,
                    }
                )
                normalized = clean_name.casefold()
                if not clean_name:
                    league_error = "Vsaka liga mora imeti ime."
                elif normalized in seen_names:
                    league_error = "Imena lig se ne smejo ponavljati."
                elif not 1 <= maximum <= 64:
                    league_error = "Liga ima lahko od 1 do 64 igralcev."
                seen_names.add(normalized)
        if not league_rows:
            league_error = "Dodajte vsaj eno ligo."

    if form.validate_on_submit():
        if league_error:
            return render_template(
                "admin/league/season_create.html",
                form=form,
                league_rows=league_rows,
                default_leagues=default_leagues,
                previous_season=previous_season,
                league_error=league_error,
            )

        season = Season(
            name=form.name.data.strip(),
            slug=unique_slug(Season, form.name.data),
            starts_on=form.starts_on.data,
            ends_on=form.ends_on.data,
            win_points=form.win_points.data,
            loss_points=form.loss_points.data,
            is_current=form.is_current.data,
            is_published=False,
            publish_after_setup=form.is_published.data,
            setup_pending=True,
            promotions_per_boundary=form.promotions_per_boundary.data if form.apply_promotions.data else 0,
        )
        db.session.add(season)
        db.session.flush()

        source_groups = {
            group.id: group
            for group in (previous_season.groups if previous_season else [])
        }
        created_groups = []
        for sort_order, row in enumerate(league_rows):
            source_group_id = row["source_group_id"] if row["source_group_id"] in source_groups else None
            group = LeagueGroup(
                season=season,
                name=row["name"],
                sort_order=sort_order,
                max_players=row["max_players"],
                source_group_id=source_group_id,
            )
            db.session.add(group)
            created_groups.append(group)
        db.session.flush()

        if form.carry_players.data:
            active_player_ids = {player.id for player in Player.query.filter_by(active=True).all()}
            transferred = set()
            for group in created_groups:
                if not group.source_group:
                    continue
                seed = 1
                for player_id in _ordered_group_player_ids(group.source_group):
                    if player_id not in active_player_ids or player_id in transferred:
                        continue
                    if seed > group.max_players:
                        break
                    db.session.add(LeagueMembership(group=group, player_id=player_id, seed=seed))
                    transferred.add(player_id)
                    seed += 1

        record("season.create", season, {"leagues": len(created_groups)})
        db.session.commit()
        flash("Sezona in lige so pripravljene. Potrdite predlagane premike.", "success")
        return redirect(url_for("admin.season_movements", season_id=season.id))

    return render_template(
        "admin/league/season_create.html",
        form=form,
        league_rows=league_rows,
        default_leagues=default_leagues,
        previous_season=previous_season,
        league_error=league_error,
    )


@bp.route("/liga/sezona/<int:season_id>/skupina/nova", methods=["GET", "POST"])
@bp.route("/liga/skupina/<int:group_id>/uredi", methods=["GET", "POST"])
def group_form(season_id=None, group_id=None):
    group = db.get_or_404(LeagueGroup, group_id) if group_id else None
    season = group.season if group else db.get_or_404(Season, season_id)
    form = GroupForm(obj=group)
    if form.validate_on_submit():
        if group is None:
            next_order = max((item.sort_order for item in season.groups), default=-1) + 1
            group = LeagueGroup(season=season, sort_order=next_order)
        group.name = form.name.data.strip()
        group.max_players = form.max_players.data
        db.session.add(group)
        db.session.flush()
        record("league_group.update" if group_id else "league_group.create", group)
        db.session.commit()
        flash("Liga je shranjena.", "success")
        return redirect(url_for("admin.season_players", season_id=season.id))
    return render_template("admin/league/group_form.html", form=form, group=group, season=season)


def _ordered_group_player_ids(group):
    standings = ordered_standings(group)
    ordered = [row.player_id for row in standings]
    existing = set(ordered)
    memberships = sorted(
        group.memberships,
        key=lambda item: (item.seed is None, item.seed or 0, item.player.display_name.casefold()),
    )
    ordered.extend(item.player_id for item in memberships if item.player_id not in existing)
    return ordered


def _season_player_setup(season):
    groups = sorted(season.groups, key=lambda group: (group.sort_order, group.id))
    all_memberships = (
        LeagueMembership.query.join(LeagueGroup)
        .filter(LeagueGroup.season_id == season.id)
        .all()
    )
    active_players = Player.query.filter_by(active=True).order_by(Player.display_name).all()
    players_by_id = {player.id: player for player in active_players}
    for membership in all_memberships:
        players_by_id[membership.player_id] = membership.player

    group_index = {group.id: index for index, group in enumerate(groups)}
    memberships_by_player = {}
    for membership in sorted(
        all_memberships,
        key=lambda item: (group_index.get(item.group_id, 999), item.seed is None, item.seed or 0),
    ):
        memberships_by_player.setdefault(membership.player_id, membership)

    previous_season = (
        Season.query.filter(Season.starts_on < season.starts_on)
        .order_by(Season.starts_on.desc())
        .first()
    )
    previous_groups = sorted(previous_season.groups, key=lambda group: (group.sort_order, group.id)) if previous_season else []
    previous_group_index = {group.id: index for index, group in enumerate(previous_groups)}

    historical_memberships = (
        LeagueMembership.query.join(LeagueGroup)
        .join(Season)
        .filter(Season.starts_on < season.starts_on)
        .order_by(Season.starts_on.desc())
        .all()
    )
    history_by_player = {}
    for membership in historical_memberships:
        history_by_player.setdefault(membership.player_id, membership)

    previous_info = {}
    if previous_season:
        for group in previous_groups:
            for membership in group.memberships:
                previous_info[membership.player_id] = {
                    "name": group.name,
                    "index": previous_group_index[group.id],
                    "season": previous_season.name,
                }
    for player_id, membership in history_by_player.items():
        if player_id in previous_info:
            continue
        matching_index = next(
            (index for index, group in enumerate(groups) if group.name == membership.group.name),
            min(membership.group.sort_order, max(len(groups) - 1, 0)),
        )
        previous_info[player_id] = {
            "name": membership.group.name,
            "index": matching_index,
            "season": membership.group.season.name,
        }

    player_rows = {}
    for player in players_by_id.values():
        info = previous_info.get(player.id)
        player_rows[player.id] = {
            "player": player,
            "is_new": info is None,
            "previous_name": info["name"] if info else "",
            "previous_index": info["index"] if info else None,
            "previous_season": info["season"] if info else "",
            "previous_label": (
                "Lani" if info and previous_season and info["season"] == previous_season.name
                else info["season"] if info else ""
            ),
        }

    group_columns = []
    assigned_ids = set()
    for group in groups:
        members = [
            membership
            for membership in all_memberships
            if membership.group_id == group.id and memberships_by_player.get(membership.player_id) is membership
        ]
        members.sort(key=lambda item: (item.seed is None, item.seed or 0, item.player.display_name.casefold()))
        player_ids = [membership.player_id for membership in members]
        assigned_ids.update(player_ids)
        group_columns.append(
            {
                "group": group,
                "group_index": group_index[group.id],
                "players": [player_rows[player_id] for player_id in player_ids],
                "capacity": group.max_players,
            }
        )
    group_columns.sort(key=lambda column: group_display_key(column["group"]))

    unassigned = [row for player_id, row in player_rows.items() if player_id not in assigned_ids]
    unassigned.sort(key=lambda row: row["player"].display_name.casefold())

    suggestion = {"groups": {str(group.id): [] for group in groups}, "unassigned": []}
    suggested_entries = {group.id: [] for group in groups}
    used = set()
    if previous_season and groups:
        for source_index, previous_group in enumerate(previous_groups):
            ranked_ids = _ordered_group_player_ids(previous_group)
            total = len(ranked_ids)
            for rank, player_id in enumerate(ranked_ids, 1):
                if player_id not in player_rows or player_id in used:
                    continue
                target_index = min(source_index, len(groups) - 1)
                if rank <= 2 and source_index > 0:
                    target_index = min(source_index - 1, len(groups) - 1)
                elif rank > max(total - 2, 2) and source_index < len(groups) - 1:
                    target_index = source_index + 1
                suggested_entries[groups[target_index].id].append((source_index, rank, player_id))
                used.add(player_id)

    overflow = []
    for group in groups:
        entries = sorted(suggested_entries[group.id])
        suggestion["groups"][str(group.id)] = [entry[2] for entry in entries[:group.max_players]]
        overflow.extend(entry[2] for entry in entries[group.max_players:])
    suggestion["unassigned"] = sorted(
        [player_id for player_id in player_rows if player_id not in used] + overflow,
        key=lambda player_id: player_rows[player_id]["player"].display_name.casefold(),
    )

    assignments = {
        "groups": {
            str(column["group"].id): [row["player"].id for row in column["players"]]
            for column in group_columns
        },
        "unassigned": [row["player"].id for row in unassigned],
    }
    return {
        "groups": groups,
        "group_columns": group_columns,
        "unassigned": unassigned,
        "player_rows": player_rows,
        "assignments": assignments,
        "suggestion": suggestion,
        "previous_season": previous_season,
    }


@bp.route("/liga/sezona/<int:season_id>/igralci", methods=["GET", "POST"])
def season_players(season_id):
    season = db.get_or_404(Season, season_id)
    setup = _season_player_setup(season)
    if request.method == "POST":
        try:
            payload = json.loads(request.form.get("assignments", ""))
            group_payload = payload["groups"]
            raw_unassigned = payload.get("unassigned", [])
            if not isinstance(group_payload, dict) or not isinstance(raw_unassigned, list):
                raise ValueError("Neveljavna oblika razvrstitve.")
            unassigned = [int(player_id) for player_id in raw_unassigned]
            if len(unassigned) != len(set(unassigned)):
                raise ValueError("Igralec je razvrščen več kot enkrat.")
            groups_by_id = {group.id: group for group in setup["groups"]}
            valid_group_ids = set(groups_by_id)
            if {int(group_id) for group_id in group_payload} != valid_group_ids:
                raise ValueError("Neveljaven seznam lig.")

            target_by_player = {player_id: None for player_id in unassigned}
            seed_by_player = {}
            for raw_group_id, raw_player_ids in group_payload.items():
                group_id = int(raw_group_id)
                if not isinstance(raw_player_ids, list):
                    raise ValueError("Neveljaven seznam igralcev.")
                player_ids = [int(player_id) for player_id in raw_player_ids]
                if len(player_ids) > groups_by_id[group_id].max_players:
                    raise ValueError(
                        f"{groups_by_id[group_id].name} ima lahko največ "
                        f"{groups_by_id[group_id].max_players} igralcev."
                    )
                for seed, player_id in enumerate(player_ids, 1):
                    if player_id in target_by_player:
                        raise ValueError("Igralec je razvrščen več kot enkrat.")
                    target_by_player[player_id] = group_id
                    seed_by_player[player_id] = seed

            expected_player_ids = set(setup["player_rows"])
            if set(target_by_player) != expected_player_ids:
                raise ValueError("Razvrstitev ne vsebuje vseh igralcev.")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            flash(str(error) or "Razvrstitve ni bilo mogoče shraniti.", "error")
            return redirect(url_for("admin.season_players", season_id=season.id))

        memberships = (
            LeagueMembership.query.join(LeagueGroup)
            .filter(LeagueGroup.season_id == season.id)
            .all()
        )
        by_player = {}
        for membership in memberships:
            by_player.setdefault(membership.player_id, []).append(membership)

        for player_id, target_group_id in target_by_player.items():
            existing = by_player.get(player_id, [])
            if target_group_id is None:
                for membership in existing:
                    db.session.delete(membership)
                continue
            keep = next((item for item in existing if item.group_id == target_group_id), None)
            if keep is None:
                keep = existing[0] if existing else LeagueMembership(player_id=player_id)
            keep.group_id = target_group_id
            keep.seed = seed_by_player[player_id]
            db.session.add(keep)
            for membership in existing:
                if membership is not keep:
                    db.session.delete(membership)

        db.session.flush()
        for group in setup["groups"]:
            recalculate_group(group)
        record("season.players_sort", season, {"groups": group_payload})
        db.session.commit()
        flash("Razvrstitev igralcev je shranjena.", "success")
        return redirect(url_for("admin.seasons"))

    return render_template(
        "admin/league/player_sort.html",
        season=season,
        **setup,
    )


def _season_movement_setup(season):
    groups = sorted(season.groups, key=lambda group: (group.sort_order, group.id))
    ladder_groups = [group for group in groups if not is_separate_league(group)]
    separate_groups = [group for group in groups if is_separate_league(group)]
    memberships_by_group = {}
    assigned_player_ids = set()
    for group in groups:
        memberships = sorted(
            group.memberships,
            key=lambda item: (item.seed is None, item.seed or 0, item.player.display_name.casefold()),
        )
        memberships_by_group[group.id] = memberships
        assigned_player_ids.update(item.player_id for item in memberships)

    move_count = season.promotions_per_boundary
    boundaries = []
    proposal_by_value = {}
    proposed_player_ids = set()
    if move_count:
        for upper, lower in zip(ladder_groups, ladder_groups[1:]):
            upper_members = memberships_by_group[upper.id]
            lower_members = memberships_by_group[lower.id]
            demotions = []
            promotions = []
            for membership in upper_members[-move_count:]:
                if membership.player_id in proposed_player_ids:
                    continue
                value = f"{membership.player_id}:{upper.id}:{lower.id}"
                proposal = {
                    "value": value,
                    "membership": membership,
                    "source": upper,
                    "target": lower,
                    "rank": membership.seed or upper_members.index(membership) + 1,
                    "direction": "down",
                }
                demotions.append(proposal)
                proposal_by_value[value] = proposal
                proposed_player_ids.add(membership.player_id)
            for membership in lower_members[:move_count]:
                if membership.player_id in proposed_player_ids:
                    continue
                value = f"{membership.player_id}:{lower.id}:{upper.id}"
                proposal = {
                    "value": value,
                    "membership": membership,
                    "source": lower,
                    "target": upper,
                    "rank": membership.seed or lower_members.index(membership) + 1,
                    "direction": "up",
                }
                promotions.append(proposal)
                proposal_by_value[value] = proposal
                proposed_player_ids.add(membership.player_id)
            boundaries.append(
                {
                    "upper": upper,
                    "lower": lower,
                    "demotions": demotions,
                    "promotions": promotions,
                }
            )

    unassigned_players = [
        player
        for player in Player.query.filter_by(active=True).order_by(Player.display_name).all()
        if player.id not in assigned_player_ids
    ]
    return {
        "groups": groups,
        "ladder_groups": ladder_groups,
        "separate_groups": separate_groups,
        "boundaries": boundaries,
        "proposal_by_value": proposal_by_value,
        "proposal_count": len(proposal_by_value),
        "remaining_count": max(0, len(assigned_player_ids) - len(proposal_by_value)),
        "unassigned_players": unassigned_players,
    }


@bp.route("/liga/sezona/<int:season_id>/premiki", methods=["GET", "POST"])
def season_movements(season_id):
    season = db.get_or_404(Season, season_id)
    if not season.setup_pending:
        return redirect(url_for("admin.season_players", season_id=season.id))
    setup = _season_movement_setup(season)

    if request.method == "POST":
        selected_values = [] if request.form.get("skip_moves") else request.form.getlist("moves")
        if len(selected_values) != len(set(selected_values)) or any(
            value not in setup["proposal_by_value"] for value in selected_values
        ):
            flash("Izbrani premiki niso veljavni.", "error")
            return redirect(url_for("admin.season_movements", season_id=season.id))

        selected = [setup["proposal_by_value"][value] for value in selected_values]
        projected_counts = {group.id: len(group.memberships) for group in setup["groups"]}
        for proposal in selected:
            projected_counts[proposal["source"].id] -= 1
            projected_counts[proposal["target"].id] += 1
        overflowing = [
            group
            for group in setup["groups"]
            if projected_counts[group.id] > group.max_players
        ]
        if overflowing:
            flash(
                "Premikov ni mogoče potrditi, ker bi bila presežena kapaciteta: "
                + ", ".join(group.name for group in overflowing),
                "error",
            )
            return redirect(url_for("admin.season_movements", season_id=season.id))

        original_group = {
            membership.player_id: membership.group_id
            for group in setup["groups"]
            for membership in group.memberships
        }
        original_seed = {
            membership.player_id: membership.seed or 999
            for group in setup["groups"]
            for membership in group.memberships
        }
        for proposal in selected:
            proposal["membership"].group_id = proposal["target"].id
        db.session.flush()

        ladder_index = {group.id: index for index, group in enumerate(setup["ladder_groups"])}
        for group in setup["groups"]:
            memberships = LeagueMembership.query.filter_by(group_id=group.id).all()

            def movement_order(membership):
                source_index = ladder_index.get(original_group.get(membership.player_id), 999)
                target_index = ladder_index.get(group.id, 999)
                if source_index < target_index:
                    section = 0  # Relegated from the stronger league.
                elif source_index == target_index:
                    section = 1
                else:
                    section = 2  # Promoted from the lower league.
                return section, original_seed.get(membership.player_id, 999), membership.player.display_name.casefold()

            for seed, membership in enumerate(sorted(memberships, key=movement_order), 1):
                membership.seed = seed
            recalculate_group(group)

        season.setup_pending = False
        season.is_published = season.publish_after_setup
        if season.is_current:
            Season.query.filter(Season.id != season.id).update({Season.is_current: False})
        record(
            "season.moves_confirm",
            season,
            {"moves": selected_values, "skipped": bool(request.form.get("skip_moves"))},
        )
        db.session.commit()
        flash(
            f"Premiki so potrjeni ({len(selected_values)}). Sezona je pripravljena.",
            "success",
        )
        return redirect(url_for("admin.seasons"))

    return render_template("admin/league/movements.html", season=season, **setup)


def _match_form(match=None):
    form = MatchForm(obj=match)
    form.season_id.choices = [(item.id, item.name) for item in Season.query.order_by(Season.starts_on.desc())]
    all_groups = LeagueGroup.query.join(Season).order_by(Season.starts_on.desc(), LeagueGroup.sort_order).all()
    display_groups = []
    groups_by_season = {}
    for item in all_groups:
        groups_by_season.setdefault(item.season_id, []).append(item)
    for season_groups in groups_by_season.values():
        display_groups.extend(groups_for_display(season_groups))
    form.group_id.choices = [(item.id, f"{item.season.name} — {item.name}") for item in display_groups]
    players = Player.query.filter_by(active=True).order_by(Player.display_name).all()
    if match:
        for player in (match.player1, match.player2):
            if player not in players:
                players.append(player)
        players.sort(key=lambda player: player.display_name.casefold())
    form.player1_id.choices = [(0, "Izberi igralca"), *[(item.id, item.display_name) for item in players]]
    form.player2_id.choices = list(form.player1_id.choices)
    return form


def _player_initials(name):
    parts = name.split()
    initials_from = parts[:1] + (parts[-1:] if len(parts) > 1 else [])
    return "".join(part[0] for part in initials_from if part)[:2].upper()


def _match_player_picker_data(match=None):
    players = Player.query.filter_by(active=True).order_by(Player.display_name).all()
    if match:
        for player in (match.player1, match.player2):
            if player not in players:
                players.append(player)
    player_data = {
        str(player.id): {
            "id": player.id,
            "name": player.display_name,
            "initials": _player_initials(player.display_name),
        }
        for player in players
    }

    completed_matches = Match.query.filter_by(status="completed").all()
    groups = {}
    all_groups = (
        LeagueGroup.query.join(Season)
        .order_by(Season.starts_on.desc(), LeagueGroup.sort_order, LeagueGroup.id)
        .all()
    )
    groups_by_season = {}
    for group in all_groups:
        groups_by_season.setdefault(group.season_id, []).append(group)
    all_groups = [
        group
        for season_groups in groups_by_season.values()
        for group in groups_for_display(season_groups)
    ]
    for group in all_groups:
        standings = ordered_standings(group)
        standing_by_player = {row.player_id: row for row in standings}
        rank_by_player = {row.player_id: rank for rank, row in enumerate(standings, 1)}
        memberships = sorted(
            group.memberships,
            key=lambda item: (item.seed is None, item.seed or 0, item.player.display_name.casefold()),
        )
        group_players = []
        for fallback_rank, membership in enumerate(memberships, 1):
            if str(membership.player_id) not in player_data:
                continue
            standing = standing_by_player.get(membership.player_id)
            group_players.append(
                {
                    **player_data[str(membership.player_id)],
                    "rank": rank_by_player.get(membership.player_id, membership.seed or fallback_rank),
                    "points": standing.points if standing else 0,
                }
            )
        group_players.sort(key=lambda player: (player["rank"], player["name"].casefold()))

        history = {}
        for played_match in completed_matches:
            if played_match.group_id != group.id or (match and played_match.id == match.id):
                continue
            pair_key = ":".join(
                str(player_id)
                for player_id in sorted((played_match.player1_id, played_match.player2_id))
            )
            history[pair_key] = history.get(pair_key, 0) + 1
        groups[str(group.id)] = {
            "id": group.id,
            "name": group.name,
            "season": group.season.name,
            "players": group_players,
            "history": history,
        }
    return {"players": player_data, "groups": groups}


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
    return render_template(
        "admin/league/match_form.html",
        form=form,
        match=match,
        player_picker_data=_match_player_picker_data(match),
    )


@bp.route("/tekme/<int:match_id>/rezultat", methods=["GET", "POST"])
def match_result(match_id):
    match = db.get_or_404(Match, match_id)
    form = MatchResultForm()
    if request.method == "GET" and match.sets:
        form.score.data = ", ".join(f"{item.player1_games}-{item.player2_games}" for item in match.sets)
        for number, item in enumerate(match.sets[:3], 1):
            getattr(form, f"set{number}_player1").data = item.player1_games
            getattr(form, f"set{number}_player2").data = item.player2_games
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

