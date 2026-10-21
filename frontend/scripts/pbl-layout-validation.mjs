// Geometry is measured in the isolated browser, never inferred from generated prose.
const tolerance = 1; // Subpixel rounding, not a design tolerance.
async function rectangles(locator) {
  const count = await locator.count();
  if (!count || count > 100) return null;
  const boxes = [];
  for (let i = 0; i < count; i++) {
    const item = locator.nth(i);
    if (!await item.isVisible()) return null;
    const box = await item.evaluate(element=>{const {x,y,width,height}=element.getBoundingClientRect();return {x,y,width,height}});
    if (!box || box.width <= 0 || box.height <= 0) return null;
    boxes.push(box);
  }
  return boxes;
}
export async function observeLayout(page, locator, assertion, relative) {
  const boxes = await rectangles(locator);
  if (!boxes) return '目标缺失、不可见或匹配数量超过限制';
  if (assertion === 'within_viewport') {
    const viewport = await page.evaluate(()=>({width:innerWidth,height:innerHeight}));
    if (!viewport) return '无法读取检查窗口大小';
    return boxes.every(b => b.x >= -tolerance && b.y >= -tolerance &&
      b.x + b.width <= viewport.width + tolerance && b.y + b.height <= viewport.height + tolerance)
      ? true : '有控件超出当前检查窗口';
  }
  if (assertion === 'not_overlapping') {
    if (boxes.length < 2) return '需要至少两个可见控件才能检查是否重叠';
    for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i], b = boxes[j];
      if (Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x) > tolerance &&
          Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y) > tolerance)
        return '有控件的可见区域相互重叠';
    }
    return true;
  }
  if (assertion === 'above') {
    if (boxes.length !== 1 || !relative) return '上方部件必须唯一，并指定下方控件';
    const lower = await rectangles(relative);
    if (!lower) return '下方控件缺失、不可见或匹配数量超过限制';
    return lower.every(b => boxes[0].y + boxes[0].height <= b.y + tolerance)
      ? true : '上方部件没有完整位于所有指定控件上方';
  }
  throw new Error('未知布局断言');
}
