import re
import unicodedata

import bleach


ALLOWED_TAGS = [
    "p", "br", "strong", "em", "ul", "ol", "li", "blockquote", "h2", "h3", "h4", "a"
]
ALLOWED_ATTRIBUTES = {"a": ["href", "title", "rel"]}


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "vsebina"


def unique_slug(model, value: str, current_id=None) -> str:
    base = slugify(value)
    candidate = base
    number = 2
    while True:
        from ..extensions import db

        with db.session.no_autoflush:
            query = model.query.filter_by(slug=candidate)
            if current_id is not None:
                query = query.filter(model.id != current_id)
            if not query.first():
                return candidate
        candidate = f"{base}-{number}"
        number += 1


def sanitize_rich_text(value: str) -> str:
    cleaned = bleach.clean(value, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, protocols=["http", "https", "mailto"], strip=True)
    return bleach.linkify(cleaned)

