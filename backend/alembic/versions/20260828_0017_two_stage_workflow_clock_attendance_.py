"""two stage workflow, clock attendance, activity log, field locking

Revision ID: 5bd89ea6fac5
Revises: 397a42c378ab
Create Date: 2026-08-28 00:17:58.120203
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '5bd89ea6fac5'
down_revision: str | None = '397a42c378ab'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the two-stage workflow, clock attendance, activity log and locking.

    Every new NOT NULL column carries a ``server_default`` so the migration
    backfills existing rows instead of failing on a live database. Historic
    assignments become FIELD_INVESTIGATION / ACTIVE, which is what they were.
    """
    op.create_table('attendance_sessions',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('employee_id', sa.Uuid(), nullable=True),
    sa.Column('work_date', sa.Date(), nullable=False),
    sa.Column('clock_in_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('clock_out_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('worked_minutes', sa.Integer(), nullable=True),
    sa.Column('is_open', sa.Boolean(), nullable=False),
    sa.Column('auto_closed', sa.Boolean(), nullable=False),
    sa.Column('clock_in_ip', sa.String(length=64), nullable=True),
    sa.Column('clock_out_ip', sa.String(length=64), nullable=True),
    sa.Column('clock_in_note', sa.Text(), nullable=True),
    sa.Column('clock_out_note', sa.Text(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], name=op.f('fk_attendance_sessions_employee_id_employees'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_attendance_sessions_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_attendance_sessions'))
    )
    with op.batch_alter_table('attendance_sessions', schema=None) as batch_op:
        batch_op.create_index('ix_attendance_sessions_open', ['user_id', 'is_open'], unique=False)
        batch_op.create_index('ix_attendance_sessions_user_date', ['user_id', 'work_date'], unique=False)

    with op.batch_alter_table('attendance', schema=None) as batch_op:
        batch_op.add_column(sa.Column('derived_from_clock', sa.Boolean(), nullable=False, server_default=sa.false()))

    with op.batch_alter_table('case_assignments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('stage', sa.Enum('FIELD_INVESTIGATION', 'OFFICE_PROCESSING', 'REVIEW', name='assignmentstage', native_enum=False, length=32), nullable=False, server_default='FIELD_INVESTIGATION'))
        batch_op.add_column(sa.Column('state', sa.Enum('ACTIVE', 'COMPLETED', 'RELEASED', 'CANCELLED', name='assignmentstate', native_enum=False, length=16), nullable=False, server_default='ACTIVE'))
        batch_op.add_column(sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index('ix_case_assignments_case_stage', ['case_id', 'stage', 'state'], unique=False)

    with op.batch_alter_table('case_field_value_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('change_reason', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('was_locked', sa.Boolean(), nullable=False, server_default=sa.false()))

    with op.batch_alter_table('case_field_values', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_locked', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('unlocked_by_id', sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column('unlocked_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('unlock_reason', sa.Text(), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_case_field_values_unlocked_by_id_users'), 'users', ['unlocked_by_id'], ['id'], ondelete='SET NULL')

    with op.batch_alter_table('cases', schema=None) as batch_op:
        batch_op.add_column(sa.Column('office_staff_id', sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column('office_assigned_by_id', sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column('visit_status', sa.Enum('NOT_STARTED', 'VISIT_SCHEDULED', 'VISIT_IN_PROGRESS', 'VISITED', 'INFORMATION_COLLECTED', 'FORM_COMPLETED', 'SUBMITTED_TO_OFFICE', name='visitstatus', native_enum=False, length=32), nullable=False, server_default='NOT_STARTED'))
        batch_op.add_column(sa.Column('visit_scheduled_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('visit_started_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('visited_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('visit_remarks', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('field_submitted_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('office_assigned_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('office_started_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index('ix_cases_company_category', ['company_id', 'category', 'status'], unique=False)
        batch_op.create_index('ix_cases_office_status', ['office_staff_id', 'status'], unique=False)
        batch_op.create_foreign_key(batch_op.f('fk_cases_office_staff_id_users'), 'users', ['office_staff_id'], ['id'], ondelete='SET NULL')
        batch_op.create_foreign_key(batch_op.f('fk_cases_office_assigned_by_id_users'), 'users', ['office_assigned_by_id'], ['id'], ondelete='SET NULL')

    with op.batch_alter_table('user_activity', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_label', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('module', sa.String(length=48), nullable=False, server_default='Session'))
        batch_op.add_column(sa.Column('summary', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('detail', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('case_id', sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column('entity_type', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('entity_id', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('entity_label', sa.String(length=255), nullable=True))
        batch_op.create_index('ix_user_activity_action_created', ['activity_type', 'created_at'], unique=False)
        batch_op.create_index('ix_user_activity_case', ['case_id', 'created_at'], unique=False)
        batch_op.create_index('ix_user_activity_module', ['module', 'created_at'], unique=False)
        batch_op.create_foreign_key(batch_op.f('fk_user_activity_case_id_cases'), 'cases', ['case_id'], ['id'], ondelete='SET NULL')

    # ### end Alembic commands ###

    # --- data backfill ----------------------------------------------------
    # Everything the client supplied is locked retroactively, so cases that
    # were imported before this release get the same protection as new ones.
    op.execute(
        "UPDATE case_field_values SET is_locked = 1 "
        "WHERE source = 'BANK_SUPPLIED'"
    )
    # Only the newest assignment per case is still live; the rest are history.
    op.execute(
        "UPDATE case_assignments SET state = 'RELEASED' "
        "WHERE id NOT IN ("
        "  SELECT id FROM ("
        "    SELECT id FROM case_assignments a "
        "    WHERE a.created_at = ("
        "      SELECT MAX(b.created_at) FROM case_assignments b "
        "      WHERE b.case_id = a.case_id"
        "    )"
        "  ) newest"
        ")"
    )
    # A case already past the investigator's desk belongs in the office queue.
    op.execute(
        "UPDATE cases SET status = 'AWAITING_OFFICE_ASSIGNMENT', "
        "field_submitted_at = submitted_at "
        "WHERE status = 'REPORT_SUBMITTED'"
    )
    op.execute(
        "UPDATE cases SET visit_status = 'SUBMITTED_TO_OFFICE' "
        "WHERE submitted_at IS NOT NULL"
    )
    # Older activity rows predate the summary columns; give them readable text
    # so the log does not show blank lines for historic logins.
    op.execute(
        "UPDATE user_activity SET module = 'Authentication', "
        "summary = CASE activity_type WHEN 'LOGIN' THEN 'Signed in' "
        "WHEN 'LOGOUT' THEN 'Signed out' ELSE activity_type END "
        "WHERE summary IS NULL"
    )
    op.execute(
        "UPDATE user_activity SET user_label = ("
        "  SELECT u.full_name FROM users u WHERE u.id = user_activity.user_id"
        ") WHERE user_label IS NULL"
    )


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user_activity', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_user_activity_case_id_cases'), type_='foreignkey')
        batch_op.drop_index('ix_user_activity_module')
        batch_op.drop_index('ix_user_activity_case')
        batch_op.drop_index('ix_user_activity_action_created')
        batch_op.drop_column('entity_label')
        batch_op.drop_column('entity_id')
        batch_op.drop_column('entity_type')
        batch_op.drop_column('case_id')
        batch_op.drop_column('detail')
        batch_op.drop_column('summary')
        batch_op.drop_column('module')
        batch_op.drop_column('user_label')

    with op.batch_alter_table('cases', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_cases_office_assigned_by_id_users'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('fk_cases_office_staff_id_users'), type_='foreignkey')
        batch_op.drop_index('ix_cases_office_status')
        batch_op.drop_index('ix_cases_company_category')
        batch_op.drop_column('office_started_at')
        batch_op.drop_column('office_assigned_at')
        batch_op.drop_column('field_submitted_at')
        batch_op.drop_column('visit_remarks')
        batch_op.drop_column('visited_at')
        batch_op.drop_column('visit_started_at')
        batch_op.drop_column('visit_scheduled_at')
        batch_op.drop_column('visit_status')
        batch_op.drop_column('office_assigned_by_id')
        batch_op.drop_column('office_staff_id')

    with op.batch_alter_table('case_field_values', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_case_field_values_unlocked_by_id_users'), type_='foreignkey')
        batch_op.drop_column('unlock_reason')
        batch_op.drop_column('unlocked_at')
        batch_op.drop_column('unlocked_by_id')
        batch_op.drop_column('is_locked')

    with op.batch_alter_table('case_field_value_history', schema=None) as batch_op:
        batch_op.drop_column('was_locked')
        batch_op.drop_column('change_reason')

    with op.batch_alter_table('case_assignments', schema=None) as batch_op:
        batch_op.drop_index('ix_case_assignments_case_stage')
        batch_op.drop_column('completed_at')
        batch_op.drop_column('accepted_at')
        batch_op.drop_column('state')
        batch_op.drop_column('stage')

    with op.batch_alter_table('attendance', schema=None) as batch_op:
        batch_op.drop_column('derived_from_clock')

    with op.batch_alter_table('attendance_sessions', schema=None) as batch_op:
        batch_op.drop_index('ix_attendance_sessions_user_date')
        batch_op.drop_index('ix_attendance_sessions_open')

    op.drop_table('attendance_sessions')
    # ### end Alembic commands ###
