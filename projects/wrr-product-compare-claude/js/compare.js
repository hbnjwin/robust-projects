import { CATEGORIES } from './data.js';

export function alignParameters(products) {
  const categoryIds = [...new Set(products.map(p => p.category))];

  if (categoryIds.length === 1) {
    return alignSameCategory(products, categoryIds[0]);
  }
  return alignCrossCategory(products, categoryIds);
}

function alignSameCategory(products, categoryId) {
  const category = CATEGORIES[categoryId];
  if (!category) return [];

  return category.paramGroups.map(group => ({
    groupId: group.groupId,
    groupName: group.groupName,
    params: group.params.map(param => {
      const values = products.map(p => {
        const val = p.values[param.paramId];
        return val !== undefined ? val : null;
      });
      return {
        paramId: param.paramId,
        paramName: param.paramName,
        unit: param.unit || '',
        type: param.type,
        values,
        isDifferent: checkDifferent(values)
      };
    })
  }));
}

function alignCrossCategory(products, categoryIds) {
  const groupMap = new Map();
  const groupOrder = [];

  categoryIds.forEach(catId => {
    const cat = CATEGORIES[catId];
    if (!cat) return;
    cat.paramGroups.forEach(group => {
      if (!groupMap.has(group.groupId)) {
        groupMap.set(group.groupId, {
          groupId: group.groupId,
          groupName: group.groupName,
          paramMap: new Map()
        });
        groupOrder.push(group.groupId);
      }
      const gm = groupMap.get(group.groupId);
      group.params.forEach(param => {
        if (!gm.paramMap.has(param.paramId)) {
          gm.paramMap.set(param.paramId, {
            paramId: param.paramId,
            paramName: param.paramName,
            unit: param.unit || '',
            type: param.type
          });
        }
      });
    });
  });

  return groupOrder.map(groupId => {
    const group = groupMap.get(groupId);
    const params = [];
    group.paramMap.forEach(paramMeta => {
      const values = products.map(p => {
        const val = p.values[paramMeta.paramId];
        return val !== undefined ? val : null;
      });
      params.push({
        ...paramMeta,
        values,
        isDifferent: checkDifferent(values)
      });
    });
    return {
      groupId: group.groupId,
      groupName: group.groupName,
      params
    };
  });
}

export function checkDifferent(values) {
  const nonNull = values.filter(v => v !== null && v !== undefined);
  if (nonNull.length <= 1) return false;
  return !nonNull.every(v => v === nonNull[0]);
}

export function buildComparisonTable(products) {
  const aligned = alignParameters(products);
  const colCount = products.length + 1;

  const table = document.createElement('table');
  table.className = 'compare-table';

  const thead = document.createElement('thead');
  const headerRow = document.createElement('tr');
  headerRow.className = 'sticky-header';

  const cornerTh = document.createElement('th');
  cornerTh.className = 'param-name-col corner-cell';
  cornerTh.textContent = '参数';
  headerRow.appendChild(cornerTh);

  products.forEach(product => {
    const th = document.createElement('th');
    th.className = 'product-col';
    th.innerHTML = `<div class="th-product-name">${product.name}</div><div class="th-product-sub">${product.subtitle}</div>`;
    headerRow.appendChild(th);
  });

  thead.appendChild(headerRow);
  table.appendChild(thead);

  const tbody = document.createElement('tbody');

  aligned.forEach(group => {
    const groupRow = document.createElement('tr');
    groupRow.className = 'group-header';
    groupRow.dataset.group = group.groupId;
    const groupTd = document.createElement('td');
    groupTd.colSpan = colCount;
    groupTd.innerHTML = `<button class="collapse-toggle"><span class="arrow">&#9660;</span> ${group.groupName}</button>`;
    groupRow.appendChild(groupTd);
    tbody.appendChild(groupRow);

    group.params.forEach(param => {
      const tr = document.createElement('tr');
      tr.className = 'param-row';
      tr.dataset.group = group.groupId;
      tr.dataset.param = param.paramId;
      if (param.isDifferent) tr.classList.add('param-diff');

      const nameTd = document.createElement('td');
      nameTd.className = 'param-name';
      nameTd.textContent = param.paramName;
      tr.appendChild(nameTd);

      param.values.forEach((val) => {
        const td = document.createElement('td');
        td.className = 'param-value';
        td.textContent = formatValue(val, param);

        if (param.isDifferent && val !== null && val !== undefined) {
          const nonNull = param.values.filter(v => v !== null && v !== undefined);
          const allSame = nonNull.every(v => v === val);
          if (!allSame) td.classList.add('value-diff');
        }

        tr.appendChild(td);
      });

      tbody.appendChild(tr);
    });
  });

  table.appendChild(tbody);
  return table;
}

function formatValue(val, param) {
  if (val === null || val === undefined) return '—';
  if (param.type === 'boolean') return val ? '支持' : '不支持';
  if (param.unit && typeof val === 'number') return val + ' ' + param.unit;
  return String(val);
}
