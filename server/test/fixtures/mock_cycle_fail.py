import sys
print('COMBINED PIPELINE CYCLE END | exit=1 | inserted=0 | duplicates=0 | fetched=0 | sakshi=0', flush=True)
print('mock_cycle_fail: controlled failure for Phase-3 gate', file=sys.stderr, flush=True)
sys.exit(1)
