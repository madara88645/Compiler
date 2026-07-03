"""Destructive operations must escalate to high risk; ordinary ones must not.

Regression for the inverted risk model: "Deploy to production and wipe the old
database" was only rated medium (the same level as a routine task), while safe
requests were over-flagged. Genuinely destructive, irreversible operations
(wipe/drop/truncate a database, rm -rf, etc.) should be high risk with a
backup/dry-run recommendation — without flagging every "delete".
"""

from app.compiler import compile_text_v2
from app.heuristics import detect_destructive_operation


# --- Must escalate to HIGH ---------------------------------------------------


def test_wipe_production_database_is_high():
    ir = compile_text_v2("Deploy my app to production and wipe the old database")
    assert ir.policy.risk_level == "high"
    assert "destructive_operation" in ir.metadata.get("policy_reasons", [])
    assert "backup_before_destructive" in ir.policy.sanitization_rules


def test_drop_table_is_destructive():
    assert detect_destructive_operation("Drop the production users table") is True


def test_rm_rf_is_destructive():
    assert detect_destructive_operation("Just rm -rf the data directory to clean up") is True


def test_truncate_table_is_destructive():
    assert detect_destructive_operation("truncate the users table before reseeding") is True


def test_sql_delete_from_is_destructive():
    assert detect_destructive_operation("Run DELETE FROM users where 1=1") is True


def test_terraform_destroy_is_destructive():
    assert detect_destructive_operation("Run terraform destroy on the prod workspace") is True


def test_rm_rf_flag_order_agnostic():
    assert detect_destructive_operation("just rm -fr /var/www to clean up") is True


def test_factory_reset_is_destructive():
    assert detect_destructive_operation("factory reset the device before returning it") is True


def test_git_clean_force_is_destructive():
    assert detect_destructive_operation("run git clean -fdx to wipe untracked files") is True


# --- Must NOT over-escalate ---------------------------------------------------


def test_plain_deploy_is_not_destructive():
    assert detect_destructive_operation("Deploy my app to production") is False


def test_deleting_a_temp_file_is_not_destructive():
    assert detect_destructive_operation("Delete the temporary file in the build folder") is False


def test_production_database_without_destructive_verb_is_not_destructive():
    assert detect_destructive_operation("The production database is slow after deploy") is False


def test_dropping_a_dependency_is_not_destructive():
    assert detect_destructive_operation("Drop the unused npm dependency from package.json") is False


def test_drop_database_connection_pool_is_not_destructive():
    assert detect_destructive_operation("Drop the database connection pool when idle") is False


def test_truncate_database_connection_pool_label_text_is_not_destructive():
    assert (
        detect_destructive_operation(
            "Truncate the database connection pool label text to 40 characters"
        )
        is False
    )


def test_truncate_table_cell_text_is_not_destructive():
    assert detect_destructive_operation("Truncate the table cell text to 40 characters") is False


def test_plain_deploy_stays_medium_not_high():
    ir = compile_text_v2("Deploy my app to production")
    assert ir.policy.risk_level != "high"
