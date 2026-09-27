import {
  falsyToDefault,
  flaskDateKey,
  entityDisplayName,
  utcDaysBackIso,
} from './dates';

describe('flaskDateKey (IST / offset calendar date)', () => {
  it('uses wall-clock date for +05:30 near midnight (not UTC day)', () => {
    // 2026-09-26 00:30 IST == 2026-09-25 19:00 UTC
    expect(flaskDateKey('2026-09-26T00:30:00+05:30')).toBe('2026-09-26');
    expect(flaskDateKey('2026-09-25T23:30:00+05:30')).toBe('2026-09-25');
  });

  it('handles Z / +00:00 like fromisoformat', () => {
    expect(flaskDateKey('2026-09-25T18:00:00Z')).toBe('2026-09-25');
    expect(flaskDateKey('2026-09-25T18:00:00+00:00')).toBe('2026-09-25');
  });

  it('returns null for empty', () => {
    expect(flaskDateKey('')).toBeNull();
  });

  it('UTC window helpers produce YYYY-MM-DD', () => {
    expect(utcDaysBackIso(0)).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});

describe('falsyToDefault source (Flask: value or "lokal")', () => {
  it('coerces empty/null/undefined to lokal', () => {
    expect(falsyToDefault('', 'lokal')).toBe('lokal');
    expect(falsyToDefault(null, 'lokal')).toBe('lokal');
    expect(falsyToDefault(undefined, 'lokal')).toBe('lokal');
  });

  it('preserves explicit sources', () => {
    expect(falsyToDefault('lokal', 'lokal')).toBe('lokal');
    expect(falsyToDefault('youtube', 'lokal')).toBe('youtube');
    expect(falsyToDefault('sakshi', 'lokal')).toBe('sakshi');
  });
});

describe('entityDisplayName', () => {
  it('skips null name like Flask if name:', () => {
    expect(entityDisplayName({ name: null })).toBeNull();
    expect(entityDisplayName({ name: '' })).toBeNull();
    expect(entityDisplayName({ name: 'MP' })).toBe('MP');
  });
});
