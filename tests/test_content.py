from datetime import datetime, timedelta, timezone
from io import BytesIO
from zoneinfo import ZoneInfo

from app.extensions import db
from app.models import NewsArticle
from PIL import Image
from tests.conftest import login


def image_upload(filename):
    stream = BytesIO()
    Image.new("RGB", (4, 3), color=(168, 67, 39)).save(stream, format="JPEG")
    stream.seek(0)
    return stream, filename


def test_admin_can_create_and_publish_news(app, client, admin):
    login(client)
    response = client.post(
        "/admin/novice/nova",
        data={
            "title": "Nova sezona",
            "summary": "Potrjeno obvestilo kluba.",
            "body": "<p>Začenjamo novo sezono.</p><script>alert(1)</script>",
            "status": "published",
            "published_at": "2026-03-01T09:00",
        },
    )
    assert response.status_code == 302
    with app.app_context():
        article = NewsArticle.query.one()
        assert article.slug == "nova-sezona"
        assert "<script>" not in article.body_html
        assert article.published_at == datetime(2026, 3, 1, 8, 0)
    public = client.get("/novice/nova-sezona")
    assert public.status_code == 200
    assert "Nova sezona" in public.get_data(as_text=True)


def test_news_form_has_current_date_no_category_and_styled_status(client, admin):
    login(client)
    text = client.get("/admin/novice/nova").get_data(as_text=True)
    today = datetime.now(ZoneInfo("Europe/Ljubljana")).strftime("%Y-%m-%d")
    assert 'name="category_id"' not in text
    assert 'data-news-status' in text
    assert f'value="{today}' in text
    assert 'accept="image/jpeg,image/png,image/webp"' in text
    assert 'data-max-files="100"' in text

    gallery_form = client.get("/admin/galerije/nova").get_data(as_text=True)
    assert 'accept="image/jpeg,image/png,image/webp"' in gallery_form


def test_news_article_accepts_and_displays_multiple_images(app, client, admin):
    login(client)
    response = client.post(
        "/admin/novice/nova",
        data={
            "title": "Fotografije turnirja",
            "body": "<p>Utrinki s turnirja.</p>",
            "status": "published",
            "images": [image_upload("ena.jpg"), image_upload("dve.jpg"), image_upload("tri.jpg")],
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 302
    with app.app_context():
        article = NewsArticle.query.filter_by(slug="fotografije-turnirja").one()
        assert len(article.images) == 3
        assert article.cover_image_key == article.images[0].storage_key

    detail = client.get("/novice/fotografije-turnirja").get_data(as_text=True)
    assert detail.count("data-lightbox-item") == 3
    assert detail.index("article-body") < detail.index("article-photo-gallery")


def test_news_article_rejects_more_than_100_images(app, client, admin):
    login(client)
    response = client.post(
        "/admin/novice/nova",
        data={
            "title": "Preveč fotografij",
            "body": "<p>Preveč.</p>",
            "status": "draft",
            "images": [image_upload(f"slika-{index}.jpg") for index in range(101)],
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert "največ 100 fotografij" in response.get_data(as_text=True)
    with app.app_context():
        assert NewsArticle.query.filter_by(slug="prevec-fotografij").first() is None


def test_home_prefers_pinned_news_then_falls_back_to_latest(app, client, admin):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with app.app_context():
        older = NewsArticle(
            title="Pomembno obvestilo",
            slug="pomembno-obvestilo",
            body_html="<p>Pomembno</p>",
            status="published",
            published_at=now - timedelta(days=2),
            is_pinned=True,
            author_id=admin,
        )
        latest = NewsArticle(
            title="Najnovejša novica",
            slug="najnovejsa-novica",
            body_html="<p>Najnovejše</p>",
            status="published",
            published_at=now - timedelta(days=1),
            author_id=admin,
        )
        db.session.add_all([older, latest])
        db.session.commit()

    homepage = client.get("/").get_data(as_text=True)
    assert "Pomembno obvestilo" in homepage
    assert "Najnovejša novica" not in homepage

    with app.app_context():
        older = NewsArticle.query.filter_by(slug="pomembno-obvestilo").one()
        older.is_pinned = False
        db.session.commit()

    homepage = client.get("/").get_data(as_text=True)
    assert "Najnovejša novica" in homepage
    assert "Pomembno obvestilo" not in homepage


def test_homepage_news_mode_is_managed_separately_from_article_form(app, client, admin):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with app.app_context():
        first = NewsArticle(
            title="Prva novica",
            slug="prva-novica",
            body_html="<p>Prva</p>",
            status="published",
            published_at=now - timedelta(days=1),
            author_id=admin,
        )
        second = NewsArticle(
            title="Druga novica",
            slug="druga-novica",
            body_html="<p>Druga</p>",
            status="published",
            published_at=now,
            author_id=admin,
        )
        db.session.add_all([first, second])
        db.session.commit()
        first_id = first.id
        second_id = second.id

    login(client)
    create_form = client.get("/admin/novice/nova").get_data(as_text=True)
    assert 'name="is_pinned"' not in create_form

    picker = client.get("/admin/novice").get_data(as_text=True)
    assert 'data-mode="latest"' in picker
    assert "Aktualna" in picker
    assert "Pripni" in picker

    response = client.post(
        "/admin/novice/domaca-stran",
        data={"homepage_mode": "pinned", "pinned_article_id": first_id},
    )
    assert response.status_code == 302
    with app.app_context():
        assert NewsArticle.query.filter_by(is_pinned=True).one().id == first_id

    response = client.post(
        "/admin/novice/domaca-stran",
        data={"homepage_mode": "pinned", "pinned_article_id": second_id},
    )
    assert response.status_code == 302
    with app.app_context():
        assert NewsArticle.query.filter_by(is_pinned=True).one().id == second_id

    response = client.post(
        "/admin/novice/domaca-stran",
        data={"homepage_mode": "pinned", "pinned_article_id": second_id},
    )
    assert response.status_code == 302
    with app.app_context():
        assert NewsArticle.query.filter_by(is_pinned=True).one().id == second_id

    response = client.post(
        "/admin/novice/domaca-stran", data={"homepage_mode": "latest"}
    )
    assert response.status_code == 302
    with app.app_context():
        assert NewsArticle.query.filter_by(is_pinned=True).count() == 0


def test_draft_cannot_be_pinned_to_homepage(app, client, admin):
    with app.app_context():
        article = NewsArticle(
            title="Osnutek za domačo stran",
            slug="osnutek-za-domaco-stran",
            body_html="<p>Skrito</p>",
            status="draft",
            author_id=admin,
        )
        db.session.add(article)
        db.session.commit()
        article_id = article.id

    login(client)
    response = client.post(
        "/admin/novice/domaca-stran",
        data={"homepage_mode": "pinned", "pinned_article_id": article_id},
        follow_redirects=True,
    )
    assert "Pripnete lahko samo že objavljeno novico" in response.get_data(as_text=True)
    with app.app_context():
        assert NewsArticle.query.filter_by(is_pinned=True).count() == 0


def test_draft_news_is_not_public(app, client, admin):
    with app.app_context():
        article = NewsArticle(title="Osnutek", slug="osnutek", body_html="<p>Skrito</p>", status="draft", author_id=admin)
        db.session.add(article)
        db.session.commit()
    assert client.get("/novice/osnutek").status_code == 404


def test_admin_can_delete_news(app, client, admin):
    with app.app_context():
        article = NewsArticle(title="Za izbris", slug="za-izbris", body_html="<p>Vsebina</p>", status="draft", author_id=admin)
        db.session.add(article)
        db.session.commit()
        article_id = article.id
    login(client)
    assert client.post(f"/admin/novice/{article_id}/izbrisi").status_code == 302
    with app.app_context():
        assert db.session.get(NewsArticle, article_id) is None

