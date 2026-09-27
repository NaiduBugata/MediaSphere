import time
# Hold long enough that a concurrent trigger sees the lock held.
time.sleep(3)
print('COMBINED PIPELINE CYCLE END | exit=0 | inserted=0 | duplicates=0 | fetched=0 | sakshi=0', flush=True)
