from alembic import op
import sqlalchemy as sa

revision = "0001_initial_core_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("plan", sa.String(length=50), nullable=True),
        sa.Column("api_key", sa.String(length=128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_api_key", "users", ["api_key"], unique=True)

    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=False),
        sa.Column("location_lat", sa.Float(), nullable=False),
        sa.Column("location_lon", sa.Float(), nullable=False),
        sa.Column("technology", sa.String(length=100), nullable=False),
        sa.Column("capacity_mw", sa.Float(), nullable=False),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_projects_user_id", "projects", ["user_id"], unique=False)

    op.create_table(
        "analyses",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("npv_usd", sa.Float(), nullable=True),
        sa.Column("irr_percent", sa.Float(), nullable=True),
        sa.Column("lcoe_usd_mwh", sa.Float(), nullable=True),
        sa.Column("total_capex_usd", sa.Float(), nullable=True),
        sa.Column("total_opex_usd", sa.Float(), nullable=True),
        sa.Column("net_profit_usd", sa.Float(), nullable=True),
        sa.Column("roi_percent", sa.Float(), nullable=True),
        sa.Column("discount_rate_used", sa.Float(), nullable=True),
        sa.Column("country_risk_score", sa.Float(), nullable=True),
        sa.Column("country_risk_grade", sa.String(length=10), nullable=True),
        sa.Column("risk_adjusted_discount_rate", sa.Float(), nullable=True),
        sa.Column("energy_results", sa.JSON(), nullable=True),
        sa.Column("financial_results", sa.JSON(), nullable=True),
        sa.Column("risk_results", sa.JSON(), nullable=True),
        sa.Column("scenarios_results", sa.JSON(), nullable=True),
        sa.Column("sensitivity_results", sa.JSON(), nullable=True),
        sa.Column("monte_carlo_results", sa.JSON(), nullable=True),
        sa.Column("full_report", sa.JSON(), nullable=True),
        sa.Column("narrative_report", sa.Text(), nullable=True),
        sa.Column("processing_time_seconds", sa.Float(), nullable=True),
        sa.Column("data_sources", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("idx_analyses_project", "analyses", ["project_id"], unique=False)
    op.create_index("idx_analyses_user_status", "analyses", ["user_id", "status"], unique=False)

    op.create_table(
        "api_cache",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("cache_key", sa.String(length=512), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("hit_count", sa.Integer(), nullable=True),
    )
    op.create_index("ix_api_cache_cache_key", "api_cache", ["cache_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_api_cache_cache_key", table_name="api_cache")
    op.drop_table("api_cache")
    op.drop_index("idx_analyses_user_status", table_name="analyses")
    op.drop_index("idx_analyses_project", table_name="analyses")
    op.drop_table("analyses")
    op.drop_index("ix_projects_user_id", table_name="projects")
    op.drop_table("projects")
    op.drop_index("ix_users_api_key", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")