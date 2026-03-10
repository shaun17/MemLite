from pathlib import Path

from memolite.cli import build_parser


def test_cli_supports_migration_commands():
    parser = build_parser()

    export_args = parser.parse_args(["export", "--output", "snapshot.json"])
    import_args = parser.parse_args(["import", "--input", "snapshot.json"])
    reconcile_args = parser.parse_args(["reconcile", "--output", "report.json"])
    repair_args = parser.parse_args(["repair", "--output", "repair.json"])

    assert export_args.command == "export"
    assert export_args.output == Path("snapshot.json")
    assert import_args.command == "import"
    assert import_args.input == Path("snapshot.json")
    assert reconcile_args.command == "reconcile"
    assert repair_args.command == "repair"
