"""Run with the backend virtualenv; no credentials in command arguments."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.taku_report_sync import main

if __name__ == '__main__':
    main()
