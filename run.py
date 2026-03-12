"""
Production entry point voor Menu Maker.

Gebruik:
    python run.py              # Start op http://localhost:5001 (Waitress)
    python run.py --port 8080  # Custom poort
    python run.py --host 0.0.0.0  # Beschikbaar op lokaal netwerk
    python run.py --debug      # Development mode (Flask debugger)
"""

import argparse
import os
import sys

# Windows UTF-8 fix
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


def main():
    parser = argparse.ArgumentParser(description="Menu Maker Server")
    parser.add_argument("--port", type=int, default=5001, help="Poort (default: 5001)")
    parser.add_argument("--host", default="localhost", help="Host (default: localhost, gebruik 0.0.0.0 voor netwerk)")
    parser.add_argument("--debug", action="store_true", help="Development mode met Flask debugger")
    args = parser.parse_args()

    from app import app

    print()
    print("=" * 50)
    print("  Menu Maker")
    print(f"  http://{args.host}:{args.port}")
    print("=" * 50)

    if not os.getenv("GEMINI_API_KEY"):
        print("\n  ! GEMINI_API_KEY niet gevonden in .env")
        print("    Zet de key in .env: GEMINI_API_KEY=jouw_key")

    if not os.getenv("SECRET_KEY"):
        print("\n  ! Tip: zet SECRET_KEY in .env voor stabiele sessies")

    if args.debug:
        print(f"\n  Mode: Development (Flask debugger)")
        print()
        app.run(debug=True, host=args.host, port=args.port)
    else:
        print(f"\n  Mode: Production (Waitress, 4 threads)")
        print()
        from waitress import serve
        serve(app, host=args.host, port=args.port, threads=4)


if __name__ == "__main__":
    main()
