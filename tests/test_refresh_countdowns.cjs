const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const start = html.indexOf('    function getChartRefreshDates(');
const end = html.indexOf('    window.addEventListener("resize", scheduleRender)', start);
assert(start >= 0 && end > start);
const now = new Date('2026-09-23T10:15:00Z');
class Clock extends Date { constructor(...args) { super(...(args.length ? args : [now])); } }
const charts = [
  {chartKey:'stack-overflow', refresh:{nextAttemptAt:'2026-10-02T10:15:00Z',attemptKind:'scheduled'}},
  {chartKey:'wikipedia', refresh:{nextAttemptAt:'2026-09-25T10:15:00Z',attemptKind:'catch-up'}},
  {chartKey:'ai-content-meta-review', refresh:{nextAttemptAt:'2026-09-28T09:30:00Z',attemptKind:'scheduled'}},
  {chartKey:'imperva-traffic', refresh:{nextAttemptAt:null,status:'manual'}},
];
const labels = charts.map(chart=>({dataset:{chartUpdate:chart.chartKey}}));
const hero = {};
const context = vm.createContext({Date:Clock, Intl, Math, Object, Number,
  window:{__DASHBOARD_READABLE_DATA__:{charts}},
  dashboardChartInfo:key=>charts.find(chart=>chart.chartKey===key),
  document:{querySelectorAll:()=>labels,getElementById:()=>hero}
});
vm.runInContext(html.slice(start,end), context);
vm.runInContext('updateHeroRefreshCountdown()', context);
assert.equal(labels[1].innerHTML,'Update: <strong>2d 0h 0m 0s</strong>');
assert.match(labels[1].title,/^Catch-up attempt:/);
assert.equal(labels[3].innerHTML,'Update: Manual');
assert.equal(hero.innerHTML,'Next update in <strong>2d 0h 0m 0s</strong>');
charts[1].refresh.nextAttemptAt='2026-09-22T10:15:00Z';
vm.runInContext('updateHeroRefreshCountdown()', context);
assert.equal(labels[1].innerHTML,'Update: <strong>Due</strong>');
assert.equal(hero.innerHTML,'Next update <strong>due</strong>');
assert.equal(labels[1].dataset.nextUpdate,'2026-09-22T10:15:00.000Z');
charts[1].refresh.nextAttemptAt='2026-10-10T10:15:00Z';
charts[1].refresh.attemptKind='scheduled';
vm.runInContext('updateHeroRefreshCountdown()', context);
assert.equal(hero.innerHTML,'Next update in <strong>4d 23h 15m 0s</strong>');
console.log('Countdown checks passed: catch-up priority, earliest schedule, manual label and overdue attempts never rolled forward.');