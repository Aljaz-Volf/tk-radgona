from datetime import datetime, timezone

from app.extensions import db
from app.models import NewsArticle, NewsCategory
from tests.conftest import login


def test_admin_can_create_and_publish_news(app, client, admin):
    with app.app_context():
        category = NewsCategory(name="Klub", slug="klub")
        db.session.add(category)
        db.session.commit()
        category_id = category.id
    login(client)
    response = client.post(
        "/admin/novice/nova",
        data={
            "title": "Nova sezona",
            "category_id": category_id,
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
    public = client.get("/novice/nova-sezona")
    assert public.status_code == 200
    assert "Nova sezona" in public.get_data(as_text=True)


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

