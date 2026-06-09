"""
Zedd Weather — CLI Interface
Command-line weather risk analysis for all sectors.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

from Zweather.construction.engine import ConstructionEngine
from Zweather.agricultural.engine import AgriculturalEngine
from Zweather.industrial.engine import IndustrialEngine
from Zweather.residential.engine import ResidentialEngine
from Zweather.marine.engine import MarineEngine
from Zweather.aviation.engine import AviationEngine
from Zweather.energy.engine import EnergyEngine
from Zweather.transportation.engine import TransportEngine

logger = logging.getLogger(__name__)

ENGINES: dict[str, Any] = {
    "construction": ConstructionEngine(),
    "agricultural": AgriculturalEngine(),
    "industrial": IndustrialEngine(),
    "residential": ResidentialEngine(),
    "marine": MarineEngine(),
    "aviation": AviationEngine(),
    "energy": EnergyEngine(),
    "transportation": TransportEngine(),
}

SECTORS = list(ENGINES.keys())


def _get_opt(args: argparse.Namespace, name: str) -> Any:
    return getattr(args, name, None)


def _parse_telemetry(args: argparse.Namespace) -> dict:
    t: dict[str, Any] = {
        "temperature": args.temperature,
        "humidity": args.humidity,
        "pressure": args.pressure,
    }
    ws = _get_opt(args, "wind_speed")
    if ws is not None:
        t["wind_speed"] = ws
    precip = _get_opt(args, "precipitation")
    if precip is not None:
        t["precipitation"] = precip
    uv = _get_opt(args, "uv_index")
    if uv is not None:
        t["uv_index"] = uv
    aqi = _get_opt(args, "aqi")
    if aqi is not None:
        t["aqi"] = aqi
    vis = _get_opt(args, "visibility_m")
    if vis is not None:
        t["visibility_m"] = vis
    alt = _get_opt(args, "altitude_m")
    if alt is not None:
        t["altitude_m"] = alt
    sol = _get_opt(args, "solar_irradiance")
    if sol is not None:
        t["solar_irradiance_wm2"] = sol
    return t


def cmd_analyze(args: argparse.Namespace) -> None:
    engine = ENGINES.get(args.sector)
    if not engine:
        print(f"Unknown sector: {args.sector}. Choose from: {', '.join(SECTORS)}")
        sys.exit(1)

    telemetry = _parse_telemetry(args)
    kwargs: dict[str, Any] = {}
    if args.region:
        kwargs["region"] = args.region
    if args.season:
        kwargs["season"] = args.season
    if args.activity:
        kwargs[args.activity_key or "activity"] = args.activity

    result = engine.analyze(telemetry, **kwargs)

    output = {
        "sector": args.sector,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "analysis": result,
    }

    if args.output == "json":
        print(json.dumps(output, indent=2))
    elif args.output == "summary":
        analysis = output["analysis"]
        print(f"{'='*60}")
        print(f"  Zedd Weather — {args.sector.title()} Analysis")
        print(f"{'='*60}")
        print(f"  Region:     {analysis.get('region', 'Midlands')}")
        print(f"  Risk Level: {analysis.get('risk_level', 'N/A').upper()}")
        if "recommendations" in analysis:
            print(f"  Recommendations:")
            for r in analysis["recommendations"]:
                print(f"    • {r}")
        print(f"{'='*60}")


def cmd_list_sectors(args: argparse.Namespace) -> None:
    print("Available sectors:")
    for s in SECTORS:
        print(f"  • {s}")


def cmd_batch(args: argparse.Namespace) -> None:
    telemetry = _parse_telemetry(args)
    results: dict[str, Any] = {}
    for sector in args.sectors or SECTORS:
        engine = ENGINES.get(sector)
        if engine:
            results[sector] = engine.analyze(telemetry)

    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }
    if args.output == "summary":
        for sector, analysis in results.items():
            rl = analysis.get("risk_level", "N/A")
            recs = analysis.get("recommendations", [])
            print(f"[{sector}] Risk: {rl.upper()}")
            for r in recs[:2]:
                print(f"         • {r}")
    else:
        print(json.dumps(output, indent=2))


def cmd_sovereign(args: argparse.Namespace) -> None:
    """Compose or validate an RMPE-2 sovereign weather transition."""
    try:
        from Zweather.sovereign import (
            ComposeTransitionRequest,
            SovereignWeatherEngine,
            WeatherObservation,
            WeatherTransition,
        )
    except ImportError:
        print("Sovereign protocol module not available.")
        sys.exit(1)

    engine = SovereignWeatherEngine()

    if args.sovereign_action == "compose":
        obs = WeatherObservation(
            station_id=args.station_id,
            timestamp=int(datetime.now(timezone.utc).timestamp()),
            temperature_c=args.temperature,
            humidity_pct=args.humidity,
            pressure_hpa=args.pressure,
            wind_speed_ms=args.wind_speed,
            rainfall_mm=args.precipitation,
        )
        request = ComposeTransitionRequest(
            oracle_root=args.oracle_root or "cli-demo-root",
            observation=obs,
            depth_limit=args.depth_limit,
            usage_increment=1,
        )
        transition = engine.compose_transition(request)
        validation = engine.validate_transition(transition)
        output = {
            "transition": transition.model_dump(),
            "validation": validation.model_dump(),
        }
        print(json.dumps(output, indent=2))

    elif args.sovereign_action == "validate":
        import sys as _sys
        data = json.loads(_sys.stdin.read())
        transition = WeatherTransition(**data)
        validation = engine.validate_transition(transition)
        print(json.dumps(validation.model_dump(), indent=2))


def cmd_report(args: argparse.Namespace) -> None:
    """Send an email report for one or all sectors."""
    telemetry: dict[str, Any] = {
        "temperature": args.temperature,
        "humidity": args.humidity,
        "pressure": args.pressure,
    }
    if args.wind_speed is not None:
        telemetry["wind_speed"] = args.wind_speed
    if args.precipitation is not None:
        telemetry["precipitation"] = args.precipitation

    results: dict[str, Any] = {}
    sectors = [args.sector] if args.sector else list(ENGINES.keys())
    for s in sectors:
        engine = ENGINES.get(s)
        if engine:
            kwargs: dict[str, Any] = {}
            if args.region:
                kwargs["region"] = args.region
            if args.season:
                kwargs["season"] = args.season
            if args.activity:
                kwargs["activity"] = args.activity
            results[s] = engine.analyze(telemetry, **kwargs)

    try:
        from Zweather.reporting.email_reporter import send_report
        success = send_report(results, region=args.region or "Midlands")
    except ImportError:
        print("Email reporter module not available.")
        sys.exit(1)

    if success:
        print(f"Report sent successfully for {len(results)} sector(s).")
    else:
        print("Failed to send report. Check SMTP configuration.")
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="zedd",
        description="Zedd Weather — multi-sector weather risk analysis CLI",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # analyze
    ap = sub.add_parser("analyze", help="Analyze weather risk for a sector")
    ap.add_argument("--output", choices=["json", "summary"], default="summary")
    ap.add_argument("sector", choices=SECTORS, help="Sector to analyze")
    ap.add_argument("--temperature", type=float, required=True)
    ap.add_argument("--humidity", type=float, required=True)
    ap.add_argument("--pressure", type=float, required=True)
    ap.add_argument("--wind-speed", type=float)
    ap.add_argument("--precipitation", type=float)
    ap.add_argument("--uv-index", type=float)
    ap.add_argument("--aqi", type=float)
    ap.add_argument("--visibility-m", type=float)
    ap.add_argument("--altitude-m", type=float)
    ap.add_argument("--solar-irradiance", type=float)
    ap.add_argument("--region")
    ap.add_argument("--season", choices=["spring", "summer", "autumn", "winter"])
    ap.add_argument("--activity")
    ap.add_argument("--activity-key", help="Override the kwarg name for activity")
    ap.set_defaults(func=cmd_analyze)

    # list
    lp = sub.add_parser("list", help="List available sectors")
    lp.set_defaults(func=cmd_list_sectors)

    # batch
    bp = sub.add_parser("batch", help="Analyze all sectors at once")
    bp.add_argument("--output", choices=["json", "summary"], default="json")
    bp.add_argument("--temperature", type=float, required=True)
    bp.add_argument("--humidity", type=float, required=True)
    bp.add_argument("--pressure", type=float, required=True)
    bp.add_argument("--wind-speed", type=float)
    bp.add_argument("--precipitation", type=float)
    bp.add_argument("--uv-index", type=float)
    bp.add_argument("--aqi", type=float)
    bp.add_argument("--sectors", nargs="*", choices=SECTORS)
    bp.set_defaults(func=cmd_batch)

    # sovereign
    sp = sub.add_parser("sovereign", help="RMPE-2 sovereign weather protocol")
    sp_sub = sp.add_subparsers(dest="sovereign_action", required=True)
    sp_compose = sp_sub.add_parser("compose", help="Compose a weather coin transition")
    sp_compose.add_argument("--oracle-root", help="Oracle root hash")
    sp_compose.add_argument("--station-id", default="cli-node-1")
    sp_compose.add_argument("--temperature", type=float, required=True)
    sp_compose.add_argument("--humidity", type=float, required=True)
    sp_compose.add_argument("--pressure", type=float, required=True)
    sp_compose.add_argument("--wind-speed", type=float)
    sp_compose.add_argument("--precipitation", type=float)
    sp_compose.add_argument("--depth-limit", type=int, default=8)
    sp_compose.set_defaults(func=cmd_sovereign)
    sp_validate = sp_sub.add_parser("validate", help="Validate a transition from stdin")
    sp_validate.set_defaults(func=cmd_sovereign)

    # report
    rp = sub.add_parser("report", help="Send email report for sectors")
    rp.add_argument("--sector", choices=SECTORS, help="Single sector to report (default: all)")
    rp.add_argument("--temperature", type=float, required=True)
    rp.add_argument("--humidity", type=float, required=True)
    rp.add_argument("--pressure", type=float, required=True)
    rp.add_argument("--wind-speed", type=float)
    rp.add_argument("--precipitation", type=float)
    rp.add_argument("--region")
    rp.add_argument("--season", choices=["spring", "summer", "autumn", "winter"])
    rp.add_argument("--activity")
    rp.set_defaults(func=cmd_report)

    return parser


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
