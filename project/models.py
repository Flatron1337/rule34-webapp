from datetime import datetime, timezone
from .extensions import db

class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_ip = db.Column(db.String(45), nullable=False, index=True)
    post_id = db.Column(db.Integer, nullable=False)
    file_url = db.Column(db.String(500), nullable=False)
    preview_url = db.Column(db.String(500), nullable=False)
    tags = db.Column(db.Text, nullable=True)
    media_type = db.Column(db.String(10), default='image')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint('user_ip', 'post_id', name='unique_user_fav'),
    )