// @vitest-environment jsdom

import { afterEach, describe, expect, it } from 'vitest';
import { getMockMode, setMockMode } from './DevModeToggle';

describe('DevModeToggle state', () => {
  afterEach(() => {
    localStorage.clear();
    setMockMode(false);
  });

  it('defaults to live mode on initial load', () => {
    expect(getMockMode()).toBe(false);
  });

  it('ignores attempts to enable demo mode', () => {
    setMockMode(true);

    expect(getMockMode()).toBe(false);
    expect(localStorage.getItem('marketpy_mock_mode')).toBe('false');
  });
});
