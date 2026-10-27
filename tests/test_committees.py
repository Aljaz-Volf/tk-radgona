from app.extensions import db
from app.models import ClubCommittee, CommitteeMember
from tests.conftest import login


def test_admin_can_manage_committees_and_public_page_updates(app, client, admin):
    login(client)
    response = client.post(
        "/admin/organi-kluba/nov",
        data={"name": "Upravni odbor", "sort_order": 10},
    )
    assert response.status_code == 302
    with app.app_context():
        committee = ClubCommittee.query.one()
        committee_id = committee.id
        assert committee.slug == "upravni-odbor"

    response = client.post(
        f"/admin/organi-kluba/{committee_id}/clan/nov",
        data={"name": "Robert Kolar", "position": "predsednik", "sort_order": 10},
    )
    assert response.status_code == 302
    public = client.get("/klub/leadership")
    text = public.get_data(as_text=True)
    assert public.status_code == 200
    assert "Upravni odbor" in text
    assert "Robert Kolar" in text
    assert "predsednik" in text

    with app.app_context():
        member = CommitteeMember.query.one()
        member_id = member.id
    response = client.post(
        f"/admin/organi-kluba/clan/{member_id}/uredi",
        data={"name": "Robert Kolar", "position": "predsednik kluba", "sort_order": 10},
    )
    assert response.status_code == 302
    assert "predsednik kluba" in client.get("/klub/leadership").get_data(as_text=True)
