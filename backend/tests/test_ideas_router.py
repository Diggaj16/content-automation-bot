"""
DB-backed tests for the /ideas Gate 1 router — real Postgres, real FastAPI
TestClient. Covers listing/pagination/grouping and the sibling-discard
behaviour on approval (built this session): approving one idea must
hard-delete its still-pending siblings from the same article without
touching their approval_status, and must never schedule the
rejection-summary background task for them.
"""
import uuid

from app.db.models import ApprovalStatus
from app.db.orm import Idea, RawContent


def _make_article(db, **overrides) -> RawContent:
    defaults = dict(
        url=f"https://example.com/{uuid.uuid4().hex}",
        normalized_url=f"https://example.com/{uuid.uuid4().hex}",
        source_name="Test Source",
        title="Test Article",
        full_text="word " * 500,
        word_count=500,
    )
    defaults.update(overrides)
    article = RawContent(**defaults)
    db.add(article)
    db.commit()
    return article


def _make_idea(db, article_id, **overrides) -> Idea:
    defaults = dict(
        platform="linkedin",
        angle="Some angle",
        agent_reasoning="Test reasoning",
        source_article_id=article_id,
        approval_status=ApprovalStatus.PENDING.value,
    )
    defaults.update(overrides)
    idea = Idea(**defaults)
    db.add(idea)
    db.commit()
    return idea


class TestListIdeas:
    def test_filters_by_default_pending_status(self, client, db_session):
        article = _make_article(db_session)
        pending = _make_idea(db_session, article.id)
        _make_idea(db_session, article.id, approval_status=ApprovalStatus.APPROVED.value)

        resp = client.get("/ideas")

        assert resp.status_code == 200
        body = resp.json()
        ids = [d["id"] for d in body["data"]]
        assert str(pending.id) in ids
        assert body["total"] == 1

    def test_empty_status_returns_all(self, client, db_session):
        article = _make_article(db_session)
        _make_idea(db_session, article.id, approval_status=ApprovalStatus.PENDING.value)
        _make_idea(db_session, article.id, approval_status=ApprovalStatus.APPROVED.value)

        resp = client.get("/ideas", params={"status": ""})

        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_joins_source_article(self, client, db_session):
        article = _make_article(db_session, title="A specific headline")
        _make_idea(db_session, article.id)

        resp = client.get("/ideas")

        data = resp.json()["data"]
        assert data[0]["source_article"]["title"] == "A specific headline"
        assert data[0]["source_article_id"] == str(article.id)

    def test_pagination(self, client, db_session):
        article = _make_article(db_session)
        for _ in range(5):
            _make_idea(db_session, article.id)

        resp = client.get("/ideas", params={"limit": 2, "page": 2})

        body = resp.json()
        assert len(body["data"]) == 2
        assert body["total"] == 5
        assert body["total_pages"] == 3


class TestApproveIdeaSiblingDiscard:
    def test_approving_one_idea_deletes_pending_siblings(self, client, db_session):
        article = _make_article(db_session)
        chosen = _make_idea(db_session, article.id, angle="Chosen angle")
        sib1 = _make_idea(db_session, article.id, angle="Sibling 1")
        sib2 = _make_idea(db_session, article.id, angle="Sibling 2")

        resp = client.patch(
            f"/ideas/{chosen.id}", json={"approval_status": "approved"}
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["approval_status"] == "approved"
        assert body["discarded_siblings"] == 2

        remaining_ids = {i.id for i in db_session.query(Idea).all()}
        assert remaining_ids == {chosen.id}
        assert db_session.get(Idea, sib1.id) is None
        assert db_session.get(Idea, sib2.id) is None

    def test_does_not_delete_siblings_already_decided(self, client, db_session):
        article = _make_article(db_session)
        chosen = _make_idea(db_session, article.id)
        already_approved = _make_idea(
            db_session, article.id, approval_status=ApprovalStatus.APPROVED.value
        )
        already_rejected = _make_idea(
            db_session, article.id, approval_status=ApprovalStatus.REJECTED.value
        )

        resp = client.patch(
            f"/ideas/{chosen.id}", json={"approval_status": "approved"}
        )

        assert resp.status_code == 200
        assert resp.json()["discarded_siblings"] == 0
        assert db_session.get(Idea, already_approved.id) is not None
        assert db_session.get(Idea, already_rejected.id) is not None

    def test_does_not_delete_ideas_from_other_articles(self, client, db_session):
        article_a = _make_article(db_session)
        article_b = _make_article(db_session)
        chosen = _make_idea(db_session, article_a.id)
        unrelated = _make_idea(db_session, article_b.id)

        resp = client.patch(
            f"/ideas/{chosen.id}", json={"approval_status": "approved"}
        )

        assert resp.status_code == 200
        assert resp.json()["discarded_siblings"] == 0
        assert db_session.get(Idea, unrelated.id) is not None

    def test_rejecting_does_not_discard_siblings(self, client, db_session):
        article = _make_article(db_session)
        idea = _make_idea(db_session, article.id)
        sibling = _make_idea(db_session, article.id)

        resp = client.patch(
            f"/ideas/{idea.id}", json={"approval_status": "rejected"}
        )

        assert resp.status_code == 200
        assert resp.json()["discarded_siblings"] == 0
        assert db_session.get(Idea, sibling.id) is not None

    def test_edited_angle_is_saved(self, client, db_session):
        article = _make_article(db_session)
        idea = _make_idea(db_session, article.id, angle="Original angle")

        resp = client.patch(
            f"/ideas/{idea.id}",
            json={"approval_status": "approved", "edited_angle": "Edited angle"},
        )

        assert resp.status_code == 200
        assert resp.json()["edited_angle"] == "Edited angle"

    def test_unknown_idea_returns_404(self, client):
        resp = client.patch(
            f"/ideas/{uuid.uuid4()}", json={"approval_status": "approved"}
        )
        assert resp.status_code == 404
