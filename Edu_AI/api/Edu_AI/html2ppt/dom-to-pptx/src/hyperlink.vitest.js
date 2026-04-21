import { describe, expect, it } from 'vitest';
import { extractAnchorHyperlink } from './index.js';

describe('extractAnchorHyperlink', () => {
  it('returns a relative file hyperlink for local game launches', () => {
    const anchor = {
      tagName: 'A',
      getAttribute: (name) => (name === 'href' ? 'games/slide-08-drag-match.html' : ''),
      closest: () => null,
    };

    expect(extractAnchorHyperlink(anchor)).toEqual({
      url: 'games/slide-08-drag-match.html',
    });
  });
});
