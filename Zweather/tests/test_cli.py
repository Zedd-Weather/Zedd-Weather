"""
Tests for the Zedd Weather CLI.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from Zweather.cli import build_parser, SECTORS


class TestCLIParser:
    def test_parser_created(self):
        parser = build_parser()
        assert parser is not None

    def test_analyze_subcommand(self):
        parser = build_parser()
        args = parser.parse_args([
            "analyze", "construction",
            "--temperature", "20", "--humidity", "60", "--pressure", "1013",
        ])
        assert args.command == "analyze"
        assert args.sector == "construction"

    def test_analyze_all_flags(self):
        parser = build_parser()
        args = parser.parse_args([
            "analyze", "marine",
            "--temperature", "15", "--humidity", "80", "--pressure", "1008",
            "--wind-speed", "10", "--precipitation", "60",
            "--uv-index", "3", "--aqi", "50",
            "--visibility-m", "5000", "--altitude-m", "100",
            "--solar-irradiance", "400",
            "--region", "glasgow", "--season", "winter",
            "--activity", "fishing", "--activity-key", "vessel_type",
        ])
        assert args.temperature == 15.0
        assert args.humidity == 80.0
        assert args.pressure == 1008.0
        assert args.wind_speed == 10.0
        assert args.precipitation == 60.0
        assert args.uv_index == 3.0
        assert args.aqi == 50.0
        assert args.visibility_m == 5000.0
        assert args.altitude_m == 100.0
        assert args.solar_irradiance == 400.0
        assert args.region == "glasgow"
        assert args.season == "winter"
        assert args.activity == "fishing"
        assert args.activity_key == "vessel_type"

    def test_list_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["list"])
        assert args.command == "list"

    def test_batch_subcommand(self):
        parser = build_parser()
        args = parser.parse_args([
            "batch",
            "--temperature", "18", "--humidity", "65", "--pressure", "1015",
        ])
        assert args.command == "batch"

    def test_batch_with_sectors(self):
        parser = build_parser()
        args = parser.parse_args([
            "batch",
            "--temperature", "18", "--humidity", "65", "--pressure", "1015",
            "--sectors", "construction", "marine",
        ])
        assert args.sectors == ["construction", "marine"]

    def test_sovereign_compose_subcommand(self):
        parser = build_parser()
        args = parser.parse_args([
            "sovereign", "compose",
            "--temperature", "20", "--humidity", "60", "--pressure", "1013",
            "--station-id", "test-node",
        ])
        assert args.command == "sovereign"
        assert args.sovereign_action == "compose"
        assert args.station_id == "test-node"

    def test_sovereign_validate_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["sovereign", "validate"])
        assert args.command == "sovereign"
        assert args.sovereign_action == "validate"

    def test_report_subcommand(self):
        parser = build_parser()
        args = parser.parse_args([
            "report",
            "--temperature", "20", "--humidity", "60", "--pressure", "1013",
        ])
        assert args.command == "report"

    def test_report_with_sector(self):
        parser = build_parser()
        args = parser.parse_args([
            "report",
            "--temperature", "20", "--humidity", "60", "--pressure", "1013",
            "--sector", "energy",
        ])
        assert args.sector == "energy"

    def test_sectors_list(self):
        expected = {
            "construction", "agricultural", "industrial", "residential",
            "marine", "aviation", "energy", "transportation",
        }
        assert set(SECTORS) == expected

    def test_parser_invalid_sector(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([
                "analyze", "invalid_sector",
                "--temperature", "20", "--humidity", "60", "--pressure", "1013",
            ])

    def test_analyze_missing_required(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["analyze", "construction"])

    def test_batch_missing_required(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["batch"])

    def test_invalid_season(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([
                "analyze", "construction",
                "--temperature", "20", "--humidity", "60", "--pressure", "1013",
                "--season", "monsoon",
            ])


class TestCLICommands:
    @patch("Zweather.cli.cmd_analyze")
    def test_analyze_dispatched(self, mock_cmd):
        from Zweather.cli import main
        with patch("sys.argv", ["zedd", "analyze", "construction",
                                "--temperature", "20", "--humidity", "60",
                                "--pressure", "1013"]):
            main()
        mock_cmd.assert_called_once()

    @patch("Zweather.cli.cmd_list_sectors")
    def test_list_dispatched(self, mock_cmd):
        from Zweather.cli import main
        with patch("sys.argv", ["zedd", "list"]):
            main()
        mock_cmd.assert_called_once()

    def test_analyze_output_json(self, capsys):
        from Zweather.cli import cmd_analyze
        import argparse

        parser = build_parser()
        args = parser.parse_args([
            "analyze", "construction",
            "--temperature", "20", "--humidity", "60", "--pressure", "1013",
            "--output", "json",
        ])
        cmd_analyze(args)
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["sector"] == "construction"
        assert "analysis" in output
        assert "risk_level" in output["analysis"]

    def test_analyze_output_summary(self, capsys):
        from Zweather.cli import cmd_analyze
        import argparse

        parser = build_parser()
        args = parser.parse_args([
            "analyze", "construction",
            "--temperature", "20", "--humidity", "60", "--pressure", "1013",
            "--output", "summary",
        ])
        cmd_analyze(args)
        captured = capsys.readouterr()
        assert "Zedd Weather" in captured.out
        assert "Risk Level" in captured.out

    def test_batch_json_output(self, capsys):
        from Zweather.cli import cmd_batch
        import argparse

        parser = build_parser()
        args = parser.parse_args([
            "batch",
            "--temperature", "18", "--humidity", "65", "--pressure", "1015",
            "--output", "json",
        ])
        cmd_batch(args)
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "results" in output
        assert "construction" in output["results"]

    def test_list_sectors(self, capsys):
        from Zweather.cli import cmd_list_sectors
        import argparse

        parser = build_parser()
        args = parser.parse_args(["list"])
        cmd_list_sectors(args)
        captured = capsys.readouterr()
        for s in SECTORS:
            assert s in captured.out

    def test_analyze_with_region(self, capsys):
        from Zweather.cli import cmd_analyze
        import argparse

        parser = build_parser()
        args = parser.parse_args([
            "analyze", "construction",
            "--temperature", "5", "--humidity", "80", "--pressure", "1005",
            "--region", "glasgow", "--season", "winter",
            "--output", "json",
        ])
        cmd_analyze(args)
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["analysis"].get("region", "").lower() == "glasgow" or "scotland" in output["analysis"].get("region", "").lower()

    def test_analyze_all_sectors(self):
        """Verify all 8 sector engines can run via CLI."""
        from Zweather.cli import cmd_analyze
        import argparse

        for sector in SECTORS:
            parser = build_parser()
            args = parser.parse_args([
                "analyze", sector,
                "--temperature", "18", "--humidity", "65", "--pressure", "1015",
                "--output", "json",
            ])
            # Should not raise
            cmd_analyze(args)
