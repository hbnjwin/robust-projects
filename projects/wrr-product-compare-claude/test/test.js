import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { alignParameters, checkDifferent } from '../js/compare.js';
import { parseHash } from '../js/url.js';
import { CATEGORIES, PRODUCTS } from '../js/data.js';

describe('checkDifferent', () => {
  it('returns false when all values are equal', () => {
    assert.equal(checkDifferent([4, 4, 4]), false);
  });

  it('returns true when values differ', () => {
    assert.equal(checkDifferent([4, 8, 4]), true);
  });

  it('returns false with single non-null value', () => {
    assert.equal(checkDifferent([null, 4, null]), false);
  });

  it('returns false when all null', () => {
    assert.equal(checkDifferent([null, null]), false);
  });

  it('returns false when non-null values are same despite nulls', () => {
    assert.equal(checkDifferent([4, null, 4]), false);
  });

  it('returns true for different booleans', () => {
    assert.equal(checkDifferent([true, false, true]), true);
  });

  it('returns false for same booleans', () => {
    assert.equal(checkDifferent([true, true]), false);
  });

  it('returns true for different strings', () => {
    assert.equal(checkDifferent(['a', 'b']), true);
  });
});

describe('alignParameters - same category', () => {
  const p1 = PRODUCTS.find(p => p.id === 1);
  const p2 = PRODUCTS.find(p => p.id === 2);

  it('returns all param groups from the category', () => {
    const result = alignParameters([p1, p2]);
    const catGroups = CATEGORIES['cloud-server'].paramGroups;
    assert.equal(result.length, catGroups.length);
    result.forEach((group, i) => {
      assert.equal(group.groupId, catGroups[i].groupId);
      assert.equal(group.groupName, catGroups[i].groupName);
    });
  });

  it('each param has correct number of values', () => {
    const result = alignParameters([p1, p2]);
    result.forEach(group => {
      group.params.forEach(param => {
        assert.equal(param.values.length, 2);
      });
    });
  });

  it('marks differing params correctly', () => {
    const result = alignParameters([p1, p2]);
    const basicGroup = result.find(g => g.groupId === 'basic');
    const cpuParam = basicGroup.params.find(p => p.paramId === 'cpu');
    assert.equal(cpuParam.values[0], 2);
    assert.equal(cpuParam.values[1], 4);
    assert.equal(cpuParam.isDifferent, true);
  });

  it('marks identical params correctly', () => {
    const result = alignParameters([p1, p2]);
    const secGroup = result.find(g => g.groupId === 'security');
    const ddos = secGroup.params.find(p => p.paramId === 'ddos_protection');
    assert.equal(ddos.isDifferent, false);
  });
});

describe('alignParameters - cross category', () => {
  const server = PRODUCTS.find(p => p.id === 1);
  const storage = PRODUCTS.find(p => p.id === 4);

  it('merges groups from both categories', () => {
    const result = alignParameters([server, storage]);
    const groupIds = result.map(g => g.groupId);
    assert.ok(groupIds.includes('basic'));
    assert.ok(groupIds.includes('service'));
    assert.ok(groupIds.includes('security'));
    assert.ok(groupIds.includes('compute'));
    assert.ok(groupIds.includes('capacity'));
  });

  it('shared params have values for both products', () => {
    const result = alignParameters([server, storage]);
    const serviceGroup = result.find(g => g.groupId === 'service');
    const sla = serviceGroup.params.find(p => p.paramId === 'sla');
    assert.notEqual(sla.values[0], null);
    assert.notEqual(sla.values[1], null);
  });

  it('category-specific params show null for other product', () => {
    const result = alignParameters([server, storage]);
    const computeGroup = result.find(g => g.groupId === 'compute');
    assert.ok(computeGroup);
    computeGroup.params.forEach(param => {
      assert.notEqual(param.values[0], null);
      assert.equal(param.values[1], null);
    });
  });
});

describe('alignParameters - 3+ products', () => {
  it('handles 3 products of same category', () => {
    const prods = PRODUCTS.filter(p => p.category === 'cloud-server');
    const result = alignParameters(prods);
    result.forEach(group => {
      group.params.forEach(param => {
        assert.equal(param.values.length, 3);
      });
    });
  });

  it('handles 4 products mixed categories', () => {
    const prods = [PRODUCTS[0], PRODUCTS[1], PRODUCTS[3], PRODUCTS[4]];
    const result = alignParameters(prods);
    result.forEach(group => {
      group.params.forEach(param => {
        assert.equal(param.values.length, 4);
      });
    });
  });
});

describe('parseHash', () => {
  it('parses product IDs from hash', () => {
    const result = parseHash('ids=1,2,3');
    assert.deepEqual(result.ids, [1, 2, 3]);
    assert.equal(result.filter, '');
  });

  it('parses IDs with search filter', () => {
    const result = parseHash('ids=1,2&q=cpu');
    assert.deepEqual(result.ids, [1, 2]);
    assert.equal(result.filter, 'cpu');
  });

  it('returns empty for no hash', () => {
    const result = parseHash('');
    assert.deepEqual(result.ids, []);
    assert.equal(result.filter, '');
  });

  it('handles encoded Chinese search text', () => {
    const result = parseHash('ids=1,4&q=' + encodeURIComponent('核数'));
    assert.equal(result.filter, '核数');
  });

  it('filters out invalid IDs', () => {
    const result = parseHash('ids=1,abc,3');
    assert.deepEqual(result.ids, [1, 3]);
  });
});

describe('data integrity', () => {
  it('all products reference valid categories', () => {
    PRODUCTS.forEach(p => {
      assert.ok(CATEGORIES[p.category], `Product ${p.id} references invalid category: ${p.category}`);
    });
  });

  it('all products have values for their category params', () => {
    PRODUCTS.forEach(product => {
      const cat = CATEGORIES[product.category];
      cat.paramGroups.forEach(group => {
        group.params.forEach(param => {
          assert.ok(
            product.values[param.paramId] !== undefined,
            `Product ${product.id} (${product.name}) missing value for param: ${param.paramId}`
          );
        });
      });
    });
  });

  it('each category has 30+ params', () => {
    Object.entries(CATEGORIES).forEach(([catId, cat]) => {
      const count = cat.paramGroups.reduce((sum, g) => sum + g.params.length, 0);
      assert.ok(count >= 30, `Category ${catId} has only ${count} params, expected 30+`);
    });
  });

  it('products have unique IDs', () => {
    const ids = PRODUCTS.map(p => p.id);
    assert.equal(new Set(ids).size, ids.length);
  });
});
