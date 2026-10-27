from tests.conftest import login


def test_homepage_renders_without_seed_data(client):
    response = client.get("/")
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert "Igrajmo tenis" in text
    assert "Novice še niso objavljene" in text
    assert ">Galerija<" not in text


def test_health_endpoint(client):
    response = client.get("/zdravje")
    assert response.status_code == 200
    assert response.json == {"status": "ok"}


def test_club_navigation_and_membership_fees_render(client):
    response = client.get("/klub/membership")
    text = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Članarina in igralnina" in text
    assert "25,00 €" in text
    assert "SI56 1010 0005 3102 451" in text
    assert "BAKOSI2X" in text
    assert "Partizanska cesta 29" in text

    homepage = client.get("/").get_data(as_text=True)
    for label in ("O klubu", "Organi kluba", "Statut kluba", "Članarina/Igralnina", "Arhiv"):
        assert label in homepage
    assert "<summary>Klub</summary>" in homepage
    assert "<summary>Liga Radgona</summary>" in homepage
    assert ">Člani<" not in homepage


def test_statute_page_handles_missing_pdf_without_broken_link(client):
    response = client.get("/klub/statute")
    assert response.status_code == 200
    assert "PDF statuta še ni naložen" in response.get_data(as_text=True)


def test_unpublished_club_pages_have_honest_empty_state(client):
    for key in ("about",):
        response = client.get(f"/klub/{key}")
        assert response.status_code == 200
        assert "Vsebina je v pripravi" in response.get_data(as_text=True)
    leadership = client.get("/klub/leadership")
    assert leadership.status_code == 200
    assert "Podatki o organih kluba še niso objavljeni" in leadership.get_data(as_text=True)


def test_members_and_gallery_require_login(client, member):
    assert client.get("/klub/members").status_code == 302
    assert client.get("/galerije").status_code == 302
    login(client, "member")
    members = client.get("/klub/members")
    gallery = client.get("/galerije")
    assert members.status_code == 200
    assert "Vsebina je v pripravi" in members.get_data(as_text=True)
    assert gallery.status_code == 200
    homepage = client.get("/").get_data(as_text=True)
    assert ">Člani<" in homepage
    assert ">Galerija<" in homepage
    navigation = homepage.split('<nav id="site-nav"', 1)[1].split("</nav>", 1)[0]
    ordered_labels = (
        ">Domov<",
        "<summary>Klub</summary>",
        ">Rezervacija<",
        "<summary>Liga Radgona</summary>",
        ">Novice<",
        ">Galerija<",
        ">Arhiv<",
    )
    positions = [navigation.index(label) for label in ordered_labels]
    assert positions == sorted(positions)


def test_unknown_page_has_custom_404(client):
    response = client.get("/ne-obstaja")
    assert response.status_code == 404
    assert "Stran ne obstaja" in response.get_data(as_text=True)


def test_admin_index_and_management_pages_render(client, admin):
    login(client)
    urls = [
        "/admin/",
        "/admin/novice",
        "/admin/novice/nova",
        "/admin/igralci",
        "/admin/igralci/nov",
        "/admin/clani",
        "/admin/clani/nov",
        "/admin/liga",
        "/admin/liga/sezona/nova",
        "/admin/tekme",
        "/admin/tekme/nova",
        "/admin/igrisca",
        "/admin/igrisca/novo",
        "/admin/rezervacije",
        "/admin/rezervacije/blokada",
        "/admin/galerije",
        "/admin/galerije/nova",
        "/admin/organi-kluba",
        "/admin/organi-kluba/nov",
        "/admin/vsebina",
        "/admin/vsebina/nova",
        "/admin/uporabniki",
        "/admin/uporabniki/nov",
        "/admin/nastavitve",
    ]
    for url in urls:
        response = client.get(url)
        assert response.status_code == 200, url

