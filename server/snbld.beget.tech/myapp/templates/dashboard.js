const DAYS = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс'];
const CYCLE = [null, 'full', 'half'];

// Offline cache helpers
function cacheSet(k,v){try{localStorage.setItem('dash_'+k,JSON.stringify({d:Date.now(),v:v}))}catch(e){}}
function cacheGet(k){try{var r=JSON.parse(localStorage.getItem('dash_'+k));return r&&Date.now()-r.d<3600000?r.v:null}catch(e){return null}}

const S = {
  year: new Date().getFullYear(),
  month: new Date().getMonth() + 1,
  pYear: new Date().getFullYear(),
  pMonth: new Date().getMonth() + 1,
  aYear: new Date().getFullYear(),
  aMonth: new Date().getMonth() + 1,
  employees: [],
  shifts: [],
  revenues: {},
  purchases: [],
  arrivals: [],
  specialDays: [],
  me: null,
  myAvatar: null,
  myEmpId: null,
  token: localStorage.getItem('dashboard_token') || '',
  user: localStorage.getItem('dashboard_user') || ''
};

let activeTab = 'schedule';

function toast(msg, type='success') {
  const c = document.getElementById('toastContainer');
  const t = document.createElement('div');
  t.className = 'toast toast-'+type;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => t.remove(), 3000);
}

function api(path, opts) {
  opts = opts || {};
  opts.headers = opts.headers || {};
  opts.headers['Authorization'] = 'Bearer ' + (localStorage.getItem('dashboard_token') || '');
  if (opts.body) opts.headers['Content-Type'] = 'application/json';
  var controller = new AbortController();
  opts.signal = controller.signal;
  setTimeout(function(){ controller.abort(); }, 20000);
  return fetch(path, opts).then(r => {
    if (r.status === 401) { doLogout(); throw new Error('Unauthorized'); }
    return r.json();
  });
}

function checkAuth() {
  if (!localStorage.getItem('dashboard_token')) { window.location.href = '/dashboard/login'; return false; }
  S.token = localStorage.getItem('dashboard_token');
  S.user = localStorage.getItem('dashboard_user') || '';
  return true;
}

function doLogout() {
  localStorage.removeItem('dashboard_token');
  localStorage.removeItem('dashboard_user');
  window.location.href = '/dashboard/login';
}

function switchTab(tab) {
  activeTab = tab;
  location.hash = tab;
  const titles = {schedule:'График',revenue:'Выручка',purchase:'Закуп',arrivals:'Приход'};
  document.getElementById('pageTitle').textContent = titles[tab]||tab;
  document.querySelectorAll('.fab-menu button').forEach(b => {
    b.classList.toggle('active',
      (b.id==='fabSchedule'&&tab==='schedule')||
      (b.id==='fabRevenue'&&tab==='revenue')||
      (b.id==='fabPurchase'&&tab==='purchase')||
      (b.id==='fabArrivals'&&tab==='arrivals'));
  });
  var bnIds = {schedule:'bnSchedule',revenue:'bnRevenue',purchase:'bnPurchase',arrivals:'bnArrivals'};
  Object.keys(bnIds).forEach(function(k){
    var el = document.getElementById(bnIds[k]);
    if(el){el.classList.toggle('active', k===tab); el.setAttribute('aria-selected', k===tab?'true':'false');}
  });
  updateBnSlider();
  var allViews = ['viewSchedule','viewRevenue','viewPurchase','viewArrivals'];
  var activeView = allViews.filter(function(v){return v==='view'+tab.charAt(0).toUpperCase()+tab.slice(1)})[0];
  // Hide all first
  allViews.forEach(function(v){
    if (v !== activeView) document.getElementById(v).classList.add('hidden');
  });
  // Show active after a frame for transition
requestAnimationFrame(function(){
    document.getElementById(activeView).classList.remove('hidden');
    if (tab === 'revenue') loadRevenue();
    else if (tab === 'purchase') loadPurchaseMonth();
    else if (tab === 'arrivals') loadArrivalsMonth();
    else loadSchedule();
    setTimeout(refreshSnakeCache, 200);
  });
}

function updateBnSlider() {
  var nav = document.querySelector('.bottom-nav');
  var btn = document.querySelector('.bottom-nav button.active');
  if (!nav || !btn) return;
  var buttons = nav.querySelectorAll('button');
  var idx = Array.prototype.indexOf.call(buttons, btn);
  if (idx < 0) return;
  var pct = (idx / buttons.length) * 100;
  nav.style.setProperty('--bn-left', 'calc(' + pct + '% + 1px)');
  nav.style.setProperty('--bn-width', 'calc(' + (100 / buttons.length) + '% - 4px)');
}

function toggleFabMenu() {
  const menu = document.getElementById('fabMenu');
  const overlay = document.getElementById('fabOverlay');
  const btn = document.getElementById('fabBtn');
  const open = !menu.classList.contains('open');

  if (open) {
    const r = btn.getBoundingClientRect();
    menu.style.top = (r.bottom + 8) + 'px';
    menu.style.left = r.left + 'px';
    menu.style.right = 'auto';
  }

  menu.classList.toggle('hidden', !open);
  menu.classList.toggle('open', open);
  overlay.classList.toggle('hidden', !open);
  btn.classList.toggle('open', open);
  btn.querySelector('i').className = open ? 'fas fa-times' : 'fas fa-bars';
  const label = btn.parentElement.querySelector('.fab-label');
  if (label) label.textContent = open ? 'закрыть' : 'меню';
}

function closeFabMenu() {
  const menu = document.getElementById('fabMenu');
  const overlay = document.getElementById('fabOverlay');
  const btn = document.getElementById('fabBtn');
  menu.classList.add('hidden');
  menu.classList.remove('open');
  overlay.classList.add('hidden');
  btn.classList.remove('open');
  btn.querySelector('i').className = 'fas fa-bars';
  const label = btn.parentElement.querySelector('.fab-label');
  if (label) label.textContent = 'меню';
}

function changeMonth(d) {
  S.month += d;
  if (S.month > 12) { S.month = 1; S.year++; }
  if (S.month < 1) { S.month = 12; S.year--; }
  loadSchedule();
}

function cycleSpecialDay(dateStr) {
  const existing = (S.specialDays||[]).find(sd => sd.date===dateStr && !sd.employee_id);
  const types = [null, 'holiday'];
  const cur = existing ? existing.day_type : null;
  const idx = types.indexOf(cur);
  const next = types[(idx+1)%types.length];
  if (next) {
    api('/api/dashboard/special-days', {method:'POST', body:JSON.stringify({date:dateStr, day_type:next})}).then(d => {
      if (d.success) loadSchedule();
    });
  } else if (existing) {
    api('/api/dashboard/special-days', {method:'POST', body:JSON.stringify({date:dateStr, day_type:cur})}).then(d => {
      if (d.success) loadSchedule();
    });
  }
}

function goToday() {
  const n = new Date();
  S.year = n.getFullYear();
  S.month = n.getMonth() + 1;
  S.pYear = n.getFullYear();
  S.pMonth = n.getMonth() + 1;
  S.aYear = n.getFullYear();
  S.aMonth = n.getMonth() + 1;
  if (activeTab === 'schedule') loadSchedule();
  else if (activeTab === 'purchase') loadPurchaseMonth();
  else if (activeTab === 'arrivals') loadArrivalsMonth();
  else { switchTab('schedule'); }
}
function sendScheduleScreenshot(weekOffset, el) {
  weekOffset = weekOffset || 0;
  var tiles = document.querySelectorAll('.sch-tile');
  tiles.forEach(function(t) { t.style.pointerEvents = 'none'; t.style.opacity = '0.5'; });
  el.style.opacity = '1';
  var origHTML = el.innerHTML;
  el.querySelector('i').className = 'fas fa-spinner fa-spin';
  el.querySelector('span').textContent = 'Отправка...';

  var today = new Date();
  var dow = today.getDay();
  var monOff = dow === 0 ? -6 : 1 - dow;
  var mon = new Date(today); mon.setDate(today.getDate() + monOff + weekOffset * 7);
  var week = [];
  for (var d = new Date(mon), i = 0; i < 7; i++, d.setDate(d.getDate() + 1)) {
    week.push(d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'));
  }

  var origTable = document.querySelector('#scheduleContainer table.schedule');
  if (!origTable) { tileReset(); return; }

  var cs = getComputedStyle(origTable);
  var cellPad = cs.borderSpacing || '3px';

  var tmp = document.createElement('div');
  tmp.style.cssText = 'position:fixed;left:0;top:0;z-index:99999;background:#1a1a2e;padding:12px;border-radius:8px';

  var hdr = origTable.querySelector('thead');
  var hdrHTML = hdr ? hdr.outerHTML : '';
  var tbody = origTable.querySelector('tbody');
  var rowsHTML = '';
  var found = false;
  if (tbody) {
    tbody.querySelectorAll('tr').forEach(function(tr) {
      if (week.indexOf(tr.getAttribute('data-date')) !== -1) {
        rowsHTML += tr.outerHTML;
        found = true;
      }
    });
  }

  if (!found) { tileReset(); return; }

  tmp.innerHTML = '<table class="schedule" style="border-spacing:' + cellPad + '">' + hdrHTML + '<tbody>' + rowsHTML + '</tbody></table>';
  document.body.appendChild(tmp);

  setTimeout(function() {
    loadHtml2Canvas().then(function() {
    return html2canvas(tmp.firstChild, {
      scale: 2,
      backgroundColor: '#1a1a2e',
      logging: false,
      onclone: function(clonedDoc) {
        clonedDoc.querySelectorAll('tr, td, th').forEach(function(el2) {
          el2.style.backgroundImage = '';
          el2.style.backgroundSize = '';
          el2.style.backgroundRepeat = '';
          el2.style.backgroundPosition = '';
  });
}

function refreshAll() {
  S.employees = [];
  S.shifts = [];
  S.revenues = {};
  S.purchases = [];
  S.arrivals = [];
  if (activeTab === 'revenue') loadRevenue();
  else if (activeTab === 'purchase') loadPurchaseMonth();
  else if (activeTab === 'arrivals') loadArrivalsMonth();
  else loadSchedule();
  loadWeather();
  loadChat();
  toast('Данные обновлены', 'info');
}
    }).then(function(canvas) {
      document.body.removeChild(tmp);
      canvas.toBlob(function(blob) {
        var fd = new FormData();
        fd.append('image', blob, 'schedule.png');
        fetch('/api/dashboard/schedule/send', {
          method: 'POST',
          headers: { 'Authorization': 'Bearer ' + (localStorage.getItem('dashboard_token') || '') },
          body: fd
        }).then(function(r) { return r.json(); }).then(function(d) {
          if (d.success) {
            el.querySelector('i').className = 'fas fa-check';
            el.querySelector('span').textContent = 'Отправлено!';
            setTimeout(function() { tileReset(); }, 2000);
          } else {
            tileReset();
            toast(d.error || 'Ошибка', 'error');
          }
        }).catch(function() { tileReset(); toast('Ошибка сети', 'error'); });
      }, 'image/png');
    }).catch(function(e) {
      document.body.removeChild(tmp);
      console.error('html2canvas:', e);
      tileReset();
    });
    }).catch(function() { document.body.removeChild(tmp); tileReset(); toast('Не удалось загрузить модуль скриншотов', 'error'); });
  }, 150);

  function tileReset() {
    tiles.forEach(function(t) { t.style.pointerEvents = ''; t.style.opacity = ''; });
    el.innerHTML = origHTML;
  }
}
function goTodayPurchase() {
  const n = new Date();
  S.pYear = n.getFullYear();
  S.pMonth = n.getMonth() + 1;
  loadPurchaseMonth();
}
function getTodayStr() {
  const n = new Date();
  return n.getFullYear()+'-'+String(n.getMonth()+1).padStart(2,'0')+'-'+String(n.getDate()).padStart(2,'0');
}

function changePurchaseMonth(d) {
  S.pMonth += d;
  if (S.pMonth > 12) { S.pMonth = 1; S.pYear++; }
  if (S.pMonth < 1) { S.pMonth = 12; S.pYear--; }
  loadPurchaseMonth();
}

function daysIn(y,m) { return new Date(y,m,0).getDate(); }
function mn(m) { return ['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'][m-1]; }
function updateTodayInfo() {
  var n = new Date();
  document.getElementById('wDate').textContent = n.getDate()+' '+mn(n.getMonth()+1).toLowerCase().slice(0,3)+' '+['Воскресенье','Понедельник','Вторник','Среда','Четверг','Пятница','Суббота'][n.getDay()];
  var today = n.getFullYear()+'-'+String(n.getMonth()+1).padStart(2,'0')+'-'+String(n.getDate()).padStart(2,'0');
  // Revenue indicator - check via API if not loaded
  function checkRevDot() {
    var dot = document.getElementById('revDot');
    if (S.revenues[today] !== undefined || !S.user) dot.classList.add('hidden');
    else dot.classList.remove('hidden');
  }
  if (Object.keys(S.revenues).length === 0) {
    api('/api/dashboard/revenue?year='+n.getFullYear()+'&month='+(n.getMonth()+1)).then(function(data){
      if (Array.isArray(data)) data.forEach(function(r){S.revenues[r.date]=r.amount});
      checkRevDot();
    });
  } else { checkRevDot(); }
  // Today workers — fetch shifts if not loaded yet
  function showTodayWorkers() {
  var wEl = document.getElementById('wWorkers');
  if (!wEl) return;
  var todayEmps = (S.shifts||[]).filter(function(s){return s.date===today&&s.shift_type==='full'});
  if (!todayEmps.length || !(S.employees||[]).length) { wEl.innerHTML = '—'; return; }
  var h = '';
  for (var i=0;i<todayEmps.length;i++) {
    var emp = (S.employees||[]).find(function(e){return e.id===todayEmps[i].employee_id});
    if (!emp) continue;
    h += '<span style="display:inline-flex;align-items:center;gap:4px;margin-right:6px;white-space:nowrap">'
      + (emp.avatar
        ? '<img class=ww-avatar alt="'+esc(emp.name)+'" src="/api/dashboard/employees/avatar-img?file='+emp.avatar+'">'
        : '<span class=ww-initial>'+emp.name.charAt(0)+'</span>')
      + '<span>'+emp.name+'</span></span>';
  }
  wEl.innerHTML = h || '—';
  }
  if (S.shifts.length === 0 || S.employees.length === 0) {
    Promise.all([
      api('/api/dashboard/employees').catch(function(){return []}),
      api('/api/dashboard/schedule?year='+n.getFullYear()+'&month='+(n.getMonth()+1)).catch(function(){return []})
    ]).then(function(_ref){
      var emps = _ref[0], shs = _ref[1];
      if (Array.isArray(emps)) S.employees = emps;
      if (Array.isArray(shs)) S.shifts = shs;
      showTodayWorkers();
    });
  } else { showTodayWorkers(); }
}
function esc(s) { const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }
function fmt(n) { return Math.round(n).toLocaleString('ru-RU'); }
function ava(emp, size) {
  size = size || 22;
  if (emp && emp.avatar) {
    return '<img src="/api/dashboard/employees/avatar-img?file='+emp.avatar+'" alt="'+esc(emp.name)+'" style="width:'+size+'px;height:'+size+'px;border-radius:50%;object-fit:cover;border:1px solid var(--card-border)">';
  }
  var colors = ['rgba(74,222,128,.2)','rgba(52,152,219,.2)','rgba(243,156,18,.2)','#9b59b6','#1abc9c'];
  var idx = emp ? S.employees.indexOf(emp) : 0;
  var ci = Math.abs(idx) % colors.length;
  var name = emp ? emp.name : '?';
  return '<span style="display:inline-flex;align-items:center;justify-content:center;width:'+size+'px;height:'+size+'px;border-radius:50%;font-size:'+(size*.35)+'px;font-weight:700;background:'+colors[ci]+'33;color:'+colors[ci]+'">'+esc(name.charAt(0).toUpperCase())+'</span>';
}

function loadSchedule() {
  document.getElementById('scheduleContainer').innerHTML = '<div class=skel style=height:200px;border-radius:8px></div>';
  document.getElementById('monthLabel').textContent = mn(S.month) + ' ' + S.year;

  var promises = [api('/api/dashboard/me').catch(function(){return {}})];
  if (S.employees.length === 0) {
    promises.push(api('/api/dashboard/employees').catch(function(){return []}));
  } else {
    promises.push(Promise.resolve(S.employees));
  }
  promises.push(api('/api/dashboard/schedule?year='+S.year+'&month='+S.month).catch(function(){return []}));
  promises.push(api('/api/dashboard/special-days?year='+S.year+'&month='+S.month).catch(function(){return []}));

  Promise.all(promises).then(([me, emps, shs, sdays]) => {
    S.me = me;
    S.specialDays = sdays || [];
    if (Array.isArray(emps)) S.employees = emps;
    if (Array.isArray(shs)) S.shifts = shs;
    if (me.role === 'admin') document.getElementById('adminSection').classList.remove('hidden');
    document.getElementById('loadingScreen').classList.add('hidden');
    updateTodayInfo();
    requestAnimationFrame(function() { renderSchedule(); });
    renderEmpList();
  });
}

const WMO_RU = {
  0:'ясно',1:'ясно',2:'облачно',3:'пасмурно',
  45:'туман',48:'туман',
  51:'морось',53:'морось',55:'морось',56:'морось',57:'морось',
  61:'дождь',63:'дождь',65:'дождь',66:'дождь',67:'дождь',
  71:'снег',73:'снег',75:'снег',77:'снег',
  80:'ливень',81:'ливень',82:'ливень',
  85:'снег',86:'снег',
  95:'гроза',96:'гроза',99:'гроза'
};
const WMO_ICON = {
  'clear':'<i class="fas fa-sun"></i>', 'ясно':'<i class="fas fa-sun"></i>',
  'cloudy':'<i class="fas fa-cloud-sun"></i>', 'облачно':'<i class="fas fa-cloud-sun"></i>','пасмурно':'<i class="fas fa-cloud"></i>',
  'foggy':'<i class="fas fa-smog"></i>', 'туман':'<i class="fas fa-smog"></i>',
  'drizzle':'<i class="fas fa-cloud-rain"></i>', 'морось':'<i class="fas fa-cloud-rain"></i>',
  'rain':'<i class="fas fa-cloud-showers-heavy"></i>', 'дождь':'<i class="fas fa-cloud-showers-heavy"></i>',
  'snow':'<i class="fas fa-snowflake"></i>', 'снег':'<i class="fas fa-snowflake"></i>',
  'showers':'<i class="fas fa-cloud-rain"></i>', 'ливень':'<i class="fas fa-cloud-rain"></i>',
  'tstorm':'<i class="fas fa-bolt"></i>', 'гроза':'<i class="fas fa-bolt"></i>'
};

function loadWeather() {
  updateTodayInfo();
  fetch('/api/dashboard/weather')
    .then(r => r.json())
    .then(d => {
      const w = document.getElementById('weatherWidget');
      if (d.error || !d.current_weather) {
        w.querySelector('.w-icon').innerHTML = '<i class="fas fa-cloud-sun"></i>';
        document.getElementById('wDesc').textContent = '—';
        document.getElementById('wTemp').textContent = '--°';
        w.classList.remove('hidden');
        return;
      }
      const c = d.current_weather;
      const code = c.weathercode;
      const desc = WMO_RU[code] || 'ясно';
      document.getElementById('wTemp').textContent = Math.round(c.temperature)+'°';
      document.getElementById('wDesc').textContent = desc;
      w.querySelector('.w-icon').innerHTML = WMO_ICON[desc] || '<i class="fas fa-sun"></i>';

      let hourlyHtml = '';
      if (d.hourly && d.hourly.time) {
        const now = new Date();
        const nowLocal = now.getFullYear()+'-'+String(now.getMonth()+1).padStart(2,'0')+'-'+String(now.getDate()).padStart(2,'0')+'T'+String(now.getHours()).padStart(2,'0');
        for (let i = 0; i < d.hourly.time.length; i++) {
          const t = d.hourly.time[i];
          if (t < nowLocal) continue;
          if (hourlyHtml.split('</div>').length > 6) break;
          const h = parseInt(t.slice(11,13));
          const rain = d.hourly.precipitation_probability[i] || 0;
          const hcode = d.hourly.weathercode[i];
          const hdesc = WMO_RU[hcode] || 'ясно';
          hourlyHtml += '<div class="wh-item'+(rain>30?' rainy':'')+'">'
            + '<div class="wh-time">'+String(h).padStart(2,'0')+':00</div>'
            + '<div class="wh-icon">'+WMO_ICON[hdesc]+'</div>'
            + (rain > 0 ? '<div class="wh-rain">'+rain+'%</div>' : '')
            + '</div>';
        }
      }
      document.getElementById('wHourly').innerHTML = hourlyHtml;
      w.classList.remove('hidden');
    })
    .catch(() => {
      const w = document.getElementById('weatherWidget');
      w.querySelector('.w-icon').innerHTML = '<i class="fas fa-cloud-sun"></i>';
      document.getElementById('wDesc').textContent = '—';
      document.getElementById('wTemp').textContent = '--°';
      w.classList.remove('hidden');
    });
}

function loadRevenue() {
  var sk = ''; for (var i=0;i<35;i++) sk+='<div class=skel style=height:52px;border-radius:6px></div>';
  document.getElementById('revenueContainer').innerHTML = '<div class=skel-grid>'+sk+'</div>';

  var promises = [];
  if (S.employees.length === 0) {
    promises.push(api('/api/dashboard/employees').catch(function(){return []}));
  } else {
    promises.push(Promise.resolve(S.employees));
  }
  promises.push(api('/api/dashboard/schedule?year='+S.year+'&month='+S.month).catch(function(){return []}));
  promises.push(api('/api/dashboard/revenue?year='+S.year+'&month='+S.month).catch(function(){return []}));

  Promise.all(promises).then(([emps, shs, revs]) => {
    if (Array.isArray(emps)) S.employees = emps;
    if (Array.isArray(shs)) S.shifts = shs;
    if (Array.isArray(revs)) {
      S.revenues = {};
      for (const r of revs) S.revenues[r.date] = r.amount;
    }
    requestAnimationFrame(function() { renderRevenue(); });
  });
}

/* ==================== SCHEDULE ==================== */
function renderSchedule() {
  const el = document.getElementById('scheduleContainer');
  const wrap = document.querySelector('.table-wrap');
  const sx = wrap ? wrap.scrollLeft : 0;
  const sy = wrap ? wrap.scrollTop : 0;
  const total = daysIn(S.year, S.month);
  const fd = new Date(S.year, S.month-1, 1).getDay();
  const mo = fd === 0 ? 6 : fd - 1;
  const t = new Date();
  const isCM = t.getFullYear() === S.year && t.getMonth()+1 === S.month;
  const td = t.getDate();

  const sm = {};
  for (const s of S.shifts) {
    const day = parseInt(s.date.slice(-2));
    sm[s.employee_id + '_' + day] = s.shift_type;
  }
  const holMap = {}, empSpec = {};
  for (const sd of (S.specialDays||[])) {
    if (!sd.employee_id) holMap[sd.date] = sd.day_type;
    else { if (!empSpec[sd.employee_id]) empSpec[sd.employee_id] = {}; empSpec[sd.employee_id][sd.date] = sd.day_type; }
  }

  let h = '<div class="table-wrap"><table class="schedule"><thead><tr>';
  h += '<th class="date-col">Дата</th>';
  for (const emp of S.employees) {
    h += '<th class="emp-header">'+esc(emp.name)+'</th>';
  }
  h += '</tr></thead><tbody>';

  for (let d = 1; d <= total; d++) {
    const dow = (mo + d - 1) % 7;
    const w = dow >= 5;
    const isT = isCM && d === td;
    const ds = S.year+'-'+String(S.month).padStart(2,'0')+'-'+String(d).padStart(2,'0');

    const holi = holMap[ds]||'';
    const holiIcons = {holiday:'<span title="Выходной" style="font-size:.55rem;margin-left:2px"><i class="fas fa-flag"></i></span>',sick:'<i class="fas fa-briefcase-medical"></i>',vacation:'<i class="fas fa-umbrella-beach"></i>'};
    const dateCls = 'date-name'+(w?' weekend':'')+(isT?' today-cell':'')+(holi?' holiday-row':'');
    h += '<tr data-date="'+ds+'" class="'+(d%7===0||d===total?'week-end':'')+(holi?' holiday-row':'')+'">';
    h += '<td class="'+dateCls+'"'+(S.me&&S.me.role==='admin'?' onclick="cycleSpecialDay(\''+ds+'\')" style="cursor:pointer"':'')+'>'+d+'.'+String(S.month).padStart(2,'0')+' '+DAYS[dow]+(holi?' '+holiIcons[holi]||'' :'')+'</td>';
    for (const emp of S.employees) {
      const st = sm[emp.id+'_'+d] || null;
      const cls = (w?' weekend':'')+(isT?' today-cell':'')+(holi?' holiday-row':'');
      const empDay = (empSpec[emp.id]||{})[ds]||'';
    const badge = empDay==='sick'?'<span class="shift-badge shift-badge-sick"><i class="fas fa-briefcase-medical"></i></span>'
        : empDay==='vacation'?'<span class="shift-badge shift-badge-vac"><i class="fas fa-umbrella-beach"></i></span>'
        : st==='full'?'<span class="shift-badge shift-badge-full">✓</span>'
        : st==='half'?'<span class="shift-badge shift-badge-half">½</span>'
        : '<span class="shift-badge shift-badge-off"></span>';
      h += '<td class="emp-cell '+cls+'" data-eid="'+emp.id+'" data-ds="'+ds+'" onclick="toggle('+emp.id+',\''+ds+'\')">'+badge+'</td>';
    }
    h += '</tr>';
  }
  h += '</tbody></table></div>';
  el.innerHTML = h;
  requestAnimationFrame(() => {
    const w2 = document.querySelector('.table-wrap');
    if (w2) { w2.scrollLeft = sx; w2.scrollTop = sy; }
    if (!sx && !sy) {
      const t = new Date();
      if (S.year === t.getFullYear() && S.month === t.getMonth()+1) {
        const tr = w2?.querySelector(`tbody tr:nth-child(${t.getDate()})`);
        const thead = w2?.querySelector('thead');
        if (tr && thead) {
          w2.scrollTop = tr.offsetTop - w2.clientTop - thead.offsetHeight;
        }
      }
    }
    initSwipe(document.getElementById('viewSchedule'));
    setTimeout(refreshSnakeCache, 50);
  });
}

function toggle(eid, ds) {
  const shift = S.shifts.find(s => s.employee_id === eid && s.date === ds);
  const cur = shift ? shift.shift_type : null;
  const idx = CYCLE.indexOf(cur);
  const next = CYCLE[(idx + 1) % CYCLE.length];

  // Optimistic UI update
  if (next) {
    if (shift) shift.shift_type = next;
    else S.shifts.push({employee_id:eid, date:ds, shift_type:next});
  } else {
    if (shift) S.shifts.splice(S.shifts.indexOf(shift), 1);
  }

  const cell = document.querySelector(`td[data-eid="${eid}"][data-ds="${ds}"]`);
  const prevBadge = cell ? cell.innerHTML : '';
  const badge = next === 'full' ? '<span class="shift-badge shift-badge-full">✓</span>'
    : next === 'half' ? '<span class="shift-badge shift-badge-half">½</span>'
    : '<span class="shift-badge shift-badge-off"></span>';
  if (cell) cell.innerHTML = badge;

  // Debounced server sync
  var key = eid + '_' + ds;
  if (!toggle._queue) toggle._queue = {};
  if (!toggle._timer) toggle._timer = null;
  toggle._queue[key] = { eid: eid, ds: ds, next: next || '', cur: cur, cell: cell, prevBadge: prevBadge };
  clearTimeout(toggle._timer);
  toggle._timer = setTimeout(function() {
    var batch = Object.values(toggle._queue);
    toggle._queue = {};
    var promises = batch.map(function(item) {
      return api('/api/dashboard/schedule', {
        method:'POST',
        body: JSON.stringify({employee_id: item.eid, date: item.ds, shift_type: item.next})
      });
    });
    Promise.all(promises).then(function(results) {
      for (var i = 0; i < results.length; i++) {
        var d = results[i];
        var item = batch[i];
        if (d.success) {
          toast('✓ '+(item.next==='full'?'Полный день':item.next==='half'?'0.5 смены':'Выходной'));
        } else {
          // Rollback
          var s = S.shifts.find(function(s2){return s2.employee_id===item.eid&&s2.date===item.ds});
          if (item.cur) {
            if (s) s.shift_type = item.cur;
            else S.shifts.push({employee_id:item.eid, date:item.ds, shift_type:item.cur});
          } else {
            if (s) S.shifts.splice(S.shifts.indexOf(s), 1);
          }
          if (item.cell) item.cell.innerHTML = item.prevBadge;
          toast(d.error || 'Ошибка сохранения', 'error');
        }
      }
    }).catch(function() {
      batch.forEach(function(item) {
        var s = S.shifts.find(function(s2){return s2.employee_id===item.eid&&s2.date===item.ds});
        if (item.cur) { if (s) s.shift_type = item.cur; else S.shifts.push({employee_id:item.eid, date:item.ds, shift_type:item.cur}); }
        else { if (s) S.shifts.splice(S.shifts.indexOf(s), 1); }
        if (item.cell) item.cell.innerHTML = item.prevBadge;
      });
      toast('Ошибка сети', 'error');
    });
  }, 300);
}

/* ==================== SWIPE ==================== */
let _swipeInited = false;
function initSwipe(el) {
  if (_swipeInited) return;
  _swipeInited = true;
  let sx2 = 0, sy2 = 0;
  el.addEventListener('touchstart', e => {
    sx2 = e.touches[0].clientX;
    sy2 = e.touches[0].clientY;
  }, {passive:true});
  el.addEventListener('touchend', e => {
    const dx = e.changedTouches[0].clientX - sx2;
    const dy = Math.abs(e.changedTouches[0].clientY - sy2);
    if (Math.abs(dx) > 70 && dy < 20) {
      changeMonth(dx > 0 ? -1 : 1);
    }
  }, {passive:true});
}

/* ==================== REVENUE ==================== */
function renderRevenue() {
  const el = document.getElementById('revenueContainer');
  const total = daysIn(S.year, S.month);
  const fd = new Date(S.year, S.month-1, 1).getDay();
  const mo = fd === 0 ? 6 : fd - 1;
  const t = new Date();
  const isCM = t.getFullYear() === S.year && t.getMonth()+1 === S.month;
  const td = t.getDate();

  // One-pass: build dayWorkers, empShifts, empSalary all at once
  const dayWorkers = {};
  const empShifts = {};
  const empSalary = {};
  for (const emp of S.employees) {
    empShifts[emp.id] = {name: emp.name, full: 0, half: 0};
    empSalary[emp.id] = 0;
  }
  for (const s of S.shifts) {
    // dayWorkers
    if (!dayWorkers[s.date]) dayWorkers[s.date] = [];
    dayWorkers[s.date].push({empId: s.employee_id, type: s.shift_type});
    // empShifts
    if (empShifts[s.employee_id]) {
      if (s.shift_type === 'full') empShifts[s.employee_id].full++;
      if (s.shift_type === 'half') empShifts[s.employee_id].half++;
    }
  }
  // Proportional salary: 10% pool divided by shift units (full=3, half=1)
  for (const date in dayWorkers) {
    const rev = S.revenues[date];
    if (!rev) continue;
    const pool = rev * 0.10;
    let totalUnits = 0;
    for (const w of dayWorkers[date]) {
      totalUnits += w.type === 'full' ? 3 : 1;
    }
    if (totalUnits === 0) continue;
    for (const w of dayWorkers[date]) {
      const units = w.type === 'full' ? 3 : 1;
      empSalary[w.empId] += pool * (units / totalUnits);
    }
  }

  // Revenue color: avg-based
  var revVals = Object.values(S.revenues).filter(function(v){return v>0});
  var avgRev = revVals.length ? revVals.reduce(function(a,b){return a+b},0)/revVals.length : 0;

  let revHtml = '<div class="rev-grid">';
  for (let d = 1; d <= total; d++) {
    const dow = (mo + d - 1) % 7;
    const w = dow >= 5;
    const isT = isCM && d === td;
    const ds = S.year+'-'+String(S.month).padStart(2,'0')+'-'+String(d).padStart(2,'0');
    const amt = S.revenues[ds];
    const hasAmt = amt !== undefined && amt !== null;
    var revCls = hasAmt ? (amt >= avgRev*1.1 ? 'rd-amt-high' : amt >= avgRev*0.5 ? 'rd-amt-full' : 'rd-amt-low') : 'rd-amt-empty';
    const workers = dayWorkers[ds] || [];
    let badges = '';
    for (const wkr of workers) {
      const emp = S.employees.find(e => e.id === wkr.empId);
      if (emp) {
        badges += '<span style="display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border-radius:50%;font-size:0.5rem;font-weight:700;opacity:'+(wkr.type==='half'?'.7':'1')+'">'+ava(emp,18)+'</span>';
      }
    }
    revHtml += '<div class="rev-day'+(isT?' today-rev':'')+(w?' weekend':'')+'" onclick="openRevModal(\''+ds+'\','+(hasAmt?amt:0)+')">'
      + '<div class="rd-date">'+d+'.'+String(S.month).padStart(2,'0')+'</div>'
      + '<div class="rd-amount '+revCls+'">'+(hasAmt ? fmt(amt)+'₽' : '—')+'</div>'
      + (badges ? '<div style="display:flex;justify-content:center;gap:1px;line-height:1">'+badges+'</div>' : '')
      + '</div>';
  }
  revHtml += '</div>';

  let totalRev = 0;
  for (const ds in S.revenues) {
    if (ds.startsWith(S.year+'-'+String(S.month).padStart(2,'0'))) {
      totalRev += S.revenues[ds];
    }
  }

  let salaryRows = '';
  let totalFull = 0, totalHalf = 0, grandSalary = 0;
  for (const emp of S.employees) {
    const es = empShifts[emp.id];
    const fullDays = es ? es.full : 0;
    const halfDays = es ? es.half : 0;
    const totalDays = fullDays + halfDays * 0.5;
    const pay = empSalary[emp.id] || 0;

    totalFull += fullDays;
    totalHalf += halfDays;
    grandSalary += pay;

    const initial = esc(emp.name.charAt(0).toUpperCase());
    const avColors = ['rgba(74,222,128,0.15)','rgba(46,204,113,0.15)','rgba(52,152,219,0.15)'];
    const txtColors = ['var(--accent)','#2ecc71','#3498db'];
    const ci = S.employees.indexOf(emp) % 3;
    salaryRows += '<div class="salary-card">'
      + '<div class="sc-row">'
      + '<div class="sc-left">'
      + '<div class="sc-avatar" style="background:'+avColors[ci]+';color:'+txtColors[ci]+'">'+initial+'</div>'
      + '<div class="sc-name">'+esc(emp.name)+'</div>'
      + '</div>'
      + '<div class="sc-salary-box">'
      + '<div class="sc-salary-label">зарплата</div>'
      + '<div class="sc-salary-val">'+fmt(pay)+'₽</div>'
      + '</div>'
      + '</div>'
      + '<div class="sc-divider"></div>'
      + '<div class="sc-stats" style="display:flex;justify-content:space-around">'
      + '<div class="sc-stat"><span class="num">'+fullDays+'</span> полных</div>'
      + '<div class="sc-stat"><span class="num">'+halfDays+'</span> полдня</div>'
      + '<div class="sc-stat"><span class="num">'+totalDays+'</span> дней</div>'
      + '</div>'
      + '</div>';
  }

  // Week profit
  const weeks = [];
  let wStart = 1;
  while (wStart <= total) {
    const wEnd = Math.min(wStart + 6, total);
    let wRev = 0;
    for (let d = wStart; d <= wEnd; d++) {
      const ds = S.year+'-'+String(S.month).padStart(2,'0')+'-'+String(d).padStart(2,'0');
      const r = S.revenues[ds];
      if (r) wRev += r;
    }
    weeks.push({w:wStart, rev:wRev});
    wStart += 7;
  }
  const maxWeekRev = Math.max(...weeks.map(w => w.rev), 0);
  let weekHtml = '<div class="week-strip">';
  for (const w of weeks) {
    const isTop = w.rev > 0 && w.rev === maxWeekRev;
    weekHtml += '<div class="ws-item'+(isTop?' top':'')+'"><div class="ws-num">Нед '+(weeks.indexOf(w)+1)+'</div><div class="ws-val'+(isTop?' high':'')+'">'+(w.rev?fmt(w.rev)+'₽':'—')+'</div></div>';
  }
  weekHtml += '</div>';

  // Employee of month
  let topEmp = null;
  let topScore = 0;
  for (const emp of S.employees) {
    const es = empShifts[emp.id];
    if (!es) continue;
    const score = (es.full + es.half * 0.5) * (empSalary[emp.id] || 0);
    if (score > topScore) { topScore = score; topEmp = emp; }
  }
  let empMonthHtml = '';
  if (topEmp && topScore > 0) {
    const avCs = ['rgba(74,222,128,0.15)','rgba(46,204,113,0.15)','rgba(52,152,219,0.15)'];
    const txCs = ['var(--accent)','#2ecc71','#3498db'];
    const ci = S.employees.indexOf(topEmp) % 3;
    empMonthHtml = '<div class="emp-month"><span class="em-badge"><i class="fas fa-trophy"></i></span>'+ava(topEmp,24)+'<span class="em-name">'+esc(topEmp.name)+'</span><span class="em-stat">лидер месяца</span></div>';
  }

  el.innerHTML = empMonthHtml + revHtml
    + '<div style="margin-top:2px;margin-bottom:2px;font-size:0.68rem;color:var(--text-secondary)"><i class="fas fa-calculator" style="color:var(--accent);margin-right:3px"></i>Зарплата:</div>'
    + '<div class="salary-cards">'
    + salaryRows
    + '</div>'
    + weekHtml
    + '<div class="salary-total">'
    + '<div><div class="st-label">Выручка</div><div class="st-rev"><span>'+fmt(totalRev)+'₽</span></div></div>'
    + '<div style="text-align:right"><div class="st-label">Всего з/п</div><div class="st-salary">'+fmt(grandSalary)+'₽</div></div>'
    + '</div>';
}

/* ==================== REVENUE MODAL ==================== */
let revModalDate = null;

function openRevModal(dateStr, currentAmt) {
  revModalDate = dateStr;
  document.getElementById('revModalTitle').textContent = 'Выручка за ' + dateStr;
  document.getElementById('revAmount').value = currentAmt || 0;
  document.getElementById('revModal').classList.remove('hidden');
}

function closeRevModal(e) {
  if (e && e.target !== e.currentTarget) return;
  document.getElementById('revModal').classList.add('hidden');
}

function saveRevenue() {
  const amt = parseFloat(document.getElementById('revAmount').value);
  if (isNaN(amt) || amt < 0) { toast('Введите сумму', 'error'); return; }
  if (!revModalDate) return;

  api('/api/dashboard/revenue', {
    method:'POST',
    body: JSON.stringify({date: revModalDate, amount: amt})
  }).then(data => {
    if (data.success) {
      S.revenues[data.date] = data.amount;
      closeRevModal();
      renderRevenue();
      updateTodayInfo();
      toast('Выручка '+fmt(amt)+' руб. за '+revModalDate);
    }
  });
}

/* ==================== PURCHASE ==================== */
function loadPurchaseMonth() {
  const el = document.getElementById('purchaseGrid');
  if (!el) return;
  var sk = ''; for (var i=0;i<35;i++) sk+='<div class=skel></div>';
  el.innerHTML = '<div class=skel-grid>'+sk+'</div>';
  document.getElementById('purchaseMonthLabel').textContent = mn(S.pMonth) + ' ' + S.pYear;
  api('/api/dashboard/purchase?year='+S.pYear+'&month='+S.pMonth).then(notes => {
    S.purchases = notes || [];
    renderPurchases();
  });
}

function renderPurchases() {
  const el = document.getElementById('purchaseGrid');
  if (!el) return;
  const total = daysIn(S.pYear, S.pMonth);
  const fd = new Date(S.pYear, S.pMonth-1, 1).getDay();
  const mo = fd === 0 ? 6 : fd - 1;
  const t = new Date();
  const isCM = t.getFullYear() === S.pYear && t.getMonth()+1 === S.pMonth;
  const td = t.getDate();

  const notesMap = {};
  for (const n of S.purchases) notesMap[n.date] = n;

  const colorPalette = ['#4ade80','#2ecc71','#3498db','#f39c12','#9b59b6','#1abc9c'];
  const empColorMap = {};

  let html = '';
  for (let d = 1; d <= total; d++) {
    const dow = (mo + d - 1) % 7;
    const w = dow >= 5;
    const isT = isCM && d === td;
    const ds = S.pYear+'-'+String(S.pMonth).padStart(2,'0')+'-'+String(d).padStart(2,'0');
    const note = notesMap[ds];
    const text = note ? note.text : '';
    const creator = note ? (note.creator_name || '') : '';
    const lines = text ? text.split('\n').filter(l => l.trim()) : [];
    const hasItems = lines.length > 0;

    if (creator && !empColorMap[creator]) {
      const ci = Object.keys(empColorMap).length % colorPalette.length;
      empColorMap[creator] = colorPalette[ci];
    }

    let badge = '';
    if (creator) {
      var cEmp = S.employees.find(function(e){return e.name===creator});
      if (cEmp) badge = ava(cEmp, 16);
      else badge = '<span style="display:inline-flex;align-items:center;justify-content:center;width:10px;height:10px;border-radius:50%;font-size:0.4rem;font-weight:700;background:'+empColorMap[creator]+'15;color:'+empColorMap[creator]+'">'+esc(creator.charAt(0).toUpperCase())+'</span>';
      badge = '<div style="display:flex;justify-content:center;gap:1px;line-height:1">'+badge+'</div>';
    }

    const countText = hasItems ? lines.length+' поз.' : '—';
    const countCls = hasItems ? 'pd-full' : 'pd-empty';

    html += '<div class="pday'+(isT?' today-rev':'')+(w?' weekend':'')+'" onclick="editPurchaseDay(\''+ds+'\')">'
      + '<div class="pd-date">'+d+'.'+String(S.pMonth).padStart(2,'0')+'</div>'
      + '<div class="pd-count '+countCls+'">'+countText+'</div>'
      + badge
      + '</div>';
  }
  el.innerHTML = html;
}

function editPurchaseDay(dateStr) {
  document.getElementById('pmText').dataset.date = dateStr;
  document.getElementById('purchaseModal').classList.remove('hidden');
  loadPurchase();
}

function renderEmpList() {
  const el = document.getElementById('employeeList');
  let h = '';
  for (const e of S.employees) {
    h += '<div class="emp-item">'
      + '<span style="display:flex;align-items:center;gap:6px">'
      + '<label style="cursor:pointer;position:relative">'+ava(e,28)+'<input type="file" accept="image/*" style="display:none" onchange="uploadAvatar(event,'+e.id+')"></label>'
      + esc(e.name)+'</span>'
      +'<button class="del-btn" onclick="delEmp('+e.id+',\''+esc(e.name)+'\')"><i class="fas fa-trash"></i></button></div>';
  }
  el.innerHTML = h;
}

function uploadAvatar(e, empId) {
  const file = e.target.files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append('avatar', file);
  fetch('/api/dashboard/employees/'+empId+'/avatar', {
    method:'POST',
    headers:{'Authorization':'Bearer '+(localStorage.getItem('dashboard_token')||'')},
    body:fd
  }).then(r => r.json()).then(d => {
    if (d.success) {
      const emp = S.employees.find(x => x.id===empId);
      if (emp) emp.avatar = d.avatar;
      renderEmpList();
      loadSchedule();
      toast('Аватар обновлён');
    }
  });
  e.target.value = '';
}

function addEmployee() {
  const inp = document.getElementById('newEmpName');
  const name = inp.value.trim();
  if (!name) return;
  api('/api/dashboard/employees', {method:'POST', body:JSON.stringify({name})}).then(d => {
    if (d.success) { inp.value=''; loadSchedule(); toast('Добавлен '+name); }
  });
}

function delEmp(id, name) {
  if (!confirm('Удалить "'+name+'"?')) return;
  api('/api/dashboard/employees/'+id, {method:'DELETE'}).then(d => { if(d.success) loadSchedule(); });
}

document.getElementById('newEmpName').addEventListener('keydown', e => { if(e.key==='Enter') addEmployee(); });

/* ── Purchase / Speech-to-Text ── */
let recognition = null;
let isRecording = false;

function closePurchase() {
  stopRecognition();
  document.getElementById('purchaseModal').classList.add('hidden');
}

function updatePmStatus(icon, recording) {
  const el = document.getElementById('pmStatus');
  const dot = el.querySelector('.dot');
  dot.classList.toggle('active', recording);
  const icons = {microphone:'<i class="fas fa-microphone"></i>', loading:'<i class="fas fa-spinner fa-spin"></i>', done:'<i class="fas fa-check"></i>', error:'<i class="fas fa-times"></i>'};
  el.innerHTML = '<span class="dot'+(recording?' active':'')+'"></span> '+ (icons[icon]||'<i class="fas fa-microphone"></i>')+ ' '+ (recording?'Говорите...':icon==='done'?'Распознано':icon==='loading'?'Обработка...':icon==='error'?'Не удалось распознать':'Нажмите микрофон или введите текст');
}

function startRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) { toast('Ваш браузер не поддерживает голосовой ввод', 'error'); return; }

  if (isRecording) {
    const raw = document.getElementById('pmText').value.trim();
    stopRecognition();
    if (raw) parseRawPurchase(raw);
    return;
  }

  recognition = new SpeechRecognition();
  recognition.lang = 'ru-RU';
  recognition.continuous = true;
  recognition.interimResults = true;

  const btn = document.getElementById('pmRecBtn');
  isRecording = true;
  btn.innerHTML = '<i class="fas fa-stop"></i> Стоп';
  updatePmStatus('microphone', true);

  let accText = document.getElementById('pmText').value;

  recognition.onresult = (e) => {
    let text = accText;
    for (let i = e.resultIndex; i < e.results.length; i++) {
      text += e.results[i][0].transcript;
    }
    document.getElementById('pmText').value = text;
  };

  recognition.onerror = (e) => {
    console.error('Speech error:', e.error);
    isRecording = false;
    btn.innerHTML = '<i class="fas fa-microphone"></i> Голос';
    updatePmStatus('microphone', false);
  };

  recognition.onend = () => {
    if (!isRecording) return;
    isRecording = false;
    btn.innerHTML = '<i class="fas fa-microphone"></i> Голос';
    updatePmStatus('microphone', false);
  };

  recognition.start();
}

function stopRecognition() {
  if (recognition && isRecording) {
    isRecording = false;
    try { recognition.stop(); } catch(_) {}
    document.getElementById('pmRecBtn').innerHTML = '<i class="fas fa-microphone"></i> Голос';
  }
}

function parseRawPurchase(rawText) {
  updatePmStatus('loading', false);
  document.getElementById('pmRecBtn').disabled = true;
  document.getElementById('pmParseBtn').disabled = true;
  api('/api/dashboard/purchase/parse', {method:'POST', body:JSON.stringify({text: rawText})}).then(d => {
    document.getElementById('pmRecBtn').disabled = false;
    document.getElementById('pmParseBtn').disabled = false;
    if (d.success && d.text) {
      document.getElementById('pmText').value = d.text;
      updatePmStatus('done', false);
      toast('Список готов');
    } else {
      toast(d.error||'Не удалось разобрать', 'error');
      updatePmStatus('error', false);
    }
  }).catch(() => {
    document.getElementById('pmRecBtn').disabled = false;
    document.getElementById('pmParseBtn').disabled = false;
    toast('Сервер недоступен', 'error');
    updatePmStatus('error', false);
  });
}

function parseTyped() {
  const raw = document.getElementById('pmText').value.trim();
  if (!raw) { toast('Введите текст для разбора', 'error'); return; }
  parseRawPurchase(raw);
}


function savePurchase() {
  const text = document.getElementById('pmText').value.trim();
  const ta = document.getElementById('pmText');
  let dateStr = ta.dataset.date;
  if (!dateStr) {
    const today = new Date();
    dateStr = today.getFullYear()+'-'+String(today.getMonth()+1).padStart(2,'0')+'-'+String(today.getDate()).padStart(2,'0');
  }

  api('/api/dashboard/purchase', {method:'POST', body:JSON.stringify({date:dateStr, text})}).then(d => {
    if (d.success) {
      toast(text ? 'Закуп сохранён' : 'Закуп очищен', 'success');
      closePurchase();
      if (activeTab === 'purchase') loadPurchaseMonth();
    } else {
      toast(d.error||'Ошибка сохранения', 'error');
    }
  });
}

function clearPurchase() {
  document.getElementById('pmText').value = '';
  savePurchase();
}

function sendToVK() {
  const text = document.getElementById('pmText').value.trim();
  if (!text) { toast('Введите текст закупа', 'error'); return; }

  const ta = document.getElementById('pmText');
  let dateStr = ta.dataset.date;
  if (!dateStr) {
    const today = new Date();
    dateStr = today.getFullYear()+'-'+String(today.getMonth()+1).padStart(2,'0')+'-'+String(today.getDate()).padStart(2,'0');
  }

  document.getElementById('pmSendOverlay').classList.remove('hidden');

  api('/api/dashboard/purchase/send-vk', {method:'POST', body:JSON.stringify({date:dateStr, text})}).then(d => {
    document.getElementById('pmSendOverlay').classList.add('hidden');
    if (d.success) {
      toast('Закуп отправлен в ВКонтакте', 'success');
      closePurchase();
      if (activeTab === 'purchase') loadPurchaseMonth();
    } else {
      toast(d.error||'Ошибка отправки', 'error');
    }
  }).catch(() => {
    document.getElementById('pmSendOverlay').classList.add('hidden');
    toast('Сервер недоступен', 'error');
  });
}

/* ==================== ARRIVALS ==================== */
function goTodayArrival() {
  const n = new Date();
  S.aYear = n.getFullYear();
  S.aMonth = n.getMonth() + 1;
  loadArrivalsMonth();
}

function changeArrivalMonth(d) {
  S.aMonth += d;
  if (S.aMonth > 12) { S.aMonth = 1; S.aYear++; }
  if (S.aMonth < 1) { S.aMonth = 12; S.aYear--; }
  loadArrivalsMonth();
}

function loadArrivalsMonth() {
  const el = document.getElementById('arrivalGrid');
  if (!el) return;
  var sk = ''; for (var i=0;i<35;i++) sk+='<div class=skel></div>';
  el.innerHTML = '<div class=skel-grid>'+sk+'</div>';
  document.getElementById('arrivalMonthLabel').textContent = mn(S.aMonth) + ' ' + S.aYear;
  api('/api/dashboard/arrivals?year='+S.aYear+'&month='+S.aMonth).then(notes => {
    S.arrivals = notes || [];
    renderArrivals();
  });
}

function renderArrivals() {
  const el = document.getElementById('arrivalGrid');
  if (!el) return;
  const total = daysIn(S.aYear, S.aMonth);
  const fd = new Date(S.aYear, S.aMonth-1, 1).getDay();
  const mo = fd === 0 ? 6 : fd - 1;
  const t = new Date();
  const isCM = t.getFullYear() === S.aYear && t.getMonth()+1 === S.aMonth;
  const td = t.getDate();

  const notesMap = {};
  for (const n of S.arrivals) notesMap[n.date] = n;

  const colorPalette = ['#4ade80','#2ecc71','#3498db','#f39c12','#9b59b6','#1abc9c'];
  const empColorMap = {};

  let html = '';
  for (let d = 1; d <= total; d++) {
    const dow = (mo + d - 1) % 7;
    const w = dow >= 5;
    const isT = isCM && d === td;
    const ds = S.aYear+'-'+String(S.aMonth).padStart(2,'0')+'-'+String(d).padStart(2,'0');
    const note = notesMap[ds];
    const text = note ? note.text : '';
    const creator = note ? (note.creator_name || '') : '';
    const photoCount = note ? (note.photo_count || 0) : 0;
    const lines = text ? text.split('\n').filter(l => l.trim()) : [];
    const hasItems = lines.length > 0;

    if (creator && !empColorMap[creator]) {
      const ci = Object.keys(empColorMap).length % colorPalette.length;
      empColorMap[creator] = colorPalette[ci];
    }

    let badge = '';
    if (creator) {
      var cEmp = S.employees.find(function(e){return e.name===creator});
      if (cEmp) badge = ava(cEmp, 16);
      else badge = '<span style="display:inline-flex;align-items:center;justify-content:center;width:10px;height:10px;border-radius:50%;font-size:0.4rem;font-weight:700;background:'+empColorMap[creator]+'15;color:'+empColorMap[creator]+'">'+esc(creator.charAt(0).toUpperCase())+'</span>';
      badge = '<div style="display:flex;justify-content:center;gap:1px;line-height:1">'+badge+'</div>';
    }

    let countText = hasItems ? lines.length+' поз.' : '—';
    if (photoCount > 0) countText += ' фото'+photoCount;
    const countCls = hasItems ? 'pd-full' : 'pd-empty';

    html += '<div class="pday'+(isT?' today-rev':'')+(w?' weekend':'')+'" onclick="editArrivalDay(\''+ds+'\')">'
      + '<div class="pd-date">'+d+'.'+String(S.aMonth).padStart(2,'0')+'</div>'
      + '<div class="pd-count '+countCls+'">'+countText+'</div>'
      + badge
      + '</div>';
  }
  el.innerHTML = html;
}

function editArrivalDay(dateStr) {
  document.getElementById('amText').dataset.date = dateStr;
  document.getElementById('arrivalModal').classList.remove('hidden');
  loadArrival();
}

function loadArrival() {
  const ta = document.getElementById('amText');
  let dateStr = ta.dataset.date;
  if (!dateStr) {
    const today = new Date();
    dateStr = today.getFullYear()+'-'+String(today.getMonth()+1).padStart(2,'0')+'-'+String(today.getDate()).padStart(2,'0');
  }
  const titleEl = document.querySelector('#arrivalModal .pm-box h3');
  titleEl.innerHTML = '<i class="fas fa-box"></i> ' + esc('Приход на ' + dateStr);

  api('/api/dashboard/arrivals?date='+dateStr).then(d => {
    if (d.text) {
      document.getElementById('amText').value = d.text;
      updateAmStatus('done', false);
    } else {
      document.getElementById('amText').value = '';
      updateAmStatus('microphone', false);
    }
    const idx = S.arrivals.findIndex(n => n.date === dateStr);
    if (idx >= 0) S.arrivals[idx] = d; else S.arrivals.push(d);
    loadArrivalPhotos(dateStr);
  });
}

function loadArrivalPhotos(dateStr) {
  const el = document.getElementById('amPhotos');
  const note = S.arrivals.find(n => n.date === dateStr);
  if (!note || !note.photos || !note.photos.length) { el.innerHTML = ''; return; }

  let h = '';
  for (const fn of note.photos) {
    h += '<div class="am-photo-wrap">'
      + '<img src="/api/dashboard/arrivals/photo?date='+dateStr+'&file='+fn+'" loading="lazy">'
      + '<button class="am-photo-del" onclick="delArrivalPhoto(\''+dateStr+'\',\''+fn+'\')">&times;</button>'
      + '</div>';
  }
  el.innerHTML = h;
}

function delArrivalPhoto(dateStr, filename) {
  if (!confirm('Удалить фото?')) return;
  api('/api/dashboard/arrivals/photos?date='+dateStr+'&file='+filename, {method:'DELETE'}).then(d => {
    if (d.success) {
      toast('Фото удалено');
      loadArrivalPhotos(dateStr);
      if (activeTab === 'arrivals') loadArrivalsMonth();
    } else {
      toast(d.error||'Ошибка', 'error');
    }
  });
}

function updateAmStatus(icon, recording) {
  const el = document.getElementById('amStatus');
  const icons = {microphone:'<i class="fas fa-microphone"></i>', loading:'<i class="fas fa-spinner fa-spin"></i>', done:'<i class="fas fa-check"></i>', error:'<i class="fas fa-times"></i>'};
  el.innerHTML = '<span class="dot'+(recording?' active':'')+'"></span> '+ (icons[icon]||'<i class="fas fa-microphone"></i>')+' '+ (recording?'Говорите...':icon==='done'?'Готово':icon==='loading'?'Обработка...':icon==='error'?'Ошибка':'Введите список или нажмите «Голос»')+'';
}

function saveArrival() {
  const text = document.getElementById('amText').value.trim();
  const ta = document.getElementById('amText');
  let dateStr = ta.dataset.date;
  if (!dateStr) {
    const today = new Date();
    dateStr = today.getFullYear()+'-'+String(today.getMonth()+1).padStart(2,'0')+'-'+String(today.getDate()).padStart(2,'0');
  }

  api('/api/dashboard/arrivals', {method:'POST', body:JSON.stringify({date:dateStr, text})}).then(d => {
    if (d.date) {
      toast(text ? 'Приход сохранён' : 'Приход очищен', 'success');
      closeArrival();
      if (activeTab === 'arrivals') loadArrivalsMonth();
    } else {
      toast(d.error||'Ошибка сохранения', 'error');
    }
  });
}

function clearArrival() {
  document.getElementById('amText').value = '';
  saveArrival();
}

function closeArrival() {
  stopArrivalRecognition();
  document.getElementById('arrivalModal').classList.add('hidden');
}

function openArrivalCamera() {
  document.getElementById('amCamera').click();
}

function uploadArrivalPhoto(e) {
  const file = e.target.files[0];
  if (!file) return;
  const ta = document.getElementById('amText');
  let dateStr = ta.dataset.date;
  if (!dateStr) {
    const today = new Date();
    dateStr = today.getFullYear()+'-'+String(today.getMonth()+1).padStart(2,'0')+'-'+String(today.getDate()).padStart(2,'0');
  }

  // показываем спиннер
  const photosEl = document.getElementById('amPhotos');
  const spin = document.createElement('div');
  spin.className = 'am-uploading';
  spin.id = 'amUploadSpinner';
  photosEl.appendChild(spin);

  const fd = new FormData();
  fd.append('date', dateStr);
  fd.append('photo', file);

  const h = {'Authorization': 'Bearer ' + (localStorage.getItem('dashboard_token') || '')};
  fetch('/api/dashboard/arrivals/photos', {method:'POST', headers:h, body:fd}).then(r => r.json()).then(d => {
    if (d.success) {
      toast('Фото загружено', 'success');
      loadArrivalPhotos(dateStr);
      if (activeTab === 'arrivals') loadArrivalsMonth();
    } else {
      const sp = document.getElementById('amUploadSpinner');
      if (sp) sp.remove();
      toast(d.error||'Ошибка загрузки', 'error');
    }
  }).catch(() => {
    const sp = document.getElementById('amUploadSpinner');
    if (sp) sp.remove();
    toast('Сервер недоступен', 'error');
  });

  e.target.value = '';
}

/* Arrivals speech */
let aRecognition = null;
let aIsRecording = false;

function startArrivalRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) { toast('Браузер не поддерживает', 'error'); return; }

  if (aIsRecording) {
    const raw = document.getElementById('amText').value.trim();
    stopArrivalRecognition();
    if (raw) parseArrivalTyped();
    return;
  }

  aRecognition = new SpeechRecognition();
  aRecognition.lang = 'ru-RU';
  aRecognition.continuous = true;
  aRecognition.interimResults = true;

  const btn = document.getElementById('amRecBtn');
  aIsRecording = true;
  btn.innerHTML = '<i class="fas fa-stop"></i> Стоп';
  updateAmStatus('microphone', true);

  let accText = document.getElementById('amText').value;

  aRecognition.onresult = (e) => {
    let text = accText;
    for (let i = e.resultIndex; i < e.results.length; i++) {
      if (e.results[i] && e.results[i][0]) text += e.results[i][0].transcript;
    }
    document.getElementById('amText').value = text;
  };

  aRecognition.onerror = () => {
    aIsRecording = false;
    btn.innerHTML = '<i class="fas fa-microphone"></i> Голос';
    updateAmStatus('microphone', false);
  };

  aRecognition.onend = () => {
    if (!aIsRecording) return;
    aIsRecording = false;
    btn.innerHTML = '<i class="fas fa-microphone"></i> Голос';
    updateAmStatus('microphone', false);
  };

  aRecognition.start();
}

function stopArrivalRecognition() {
  if (aRecognition && aIsRecording) {
    aIsRecording = false;
    try { aRecognition.stop(); } catch(_) {}
    document.getElementById('amRecBtn').innerHTML = '<i class="fas fa-microphone"></i> Голос';
  }
}

function parseArrivalTyped() {
  const raw = document.getElementById('amText').value.trim();
  if (!raw) { toast('Введите текст для разбора', 'error'); return; }
  updateAmStatus('loading', false);
  document.getElementById('amParseBtn').disabled = true;
  api('/api/dashboard/purchase/parse', {method:'POST', body:JSON.stringify({text: raw})}).then(d => {
    document.getElementById('amParseBtn').disabled = false;
    if (d.success && d.text) {
      document.getElementById('amText').value = d.text;
      updateAmStatus('done', false);
      toast('Список готов');
    } else {
      toast(d.error||'Не удалось разобрать', 'error');
      updateAmStatus('error', false);
    }
  }).catch(() => {
    document.getElementById('amParseBtn').disabled = false;
    toast('Сервер недоступен', 'error');
    updateAmStatus('error', false);
  });
}

function sendArrivalToVK() {
  const text = document.getElementById('amText').value.trim();
  if (!text) { toast('Введите текст', 'error'); return; }

  const ta = document.getElementById('amText');
  let dateStr = ta.dataset.date;
  if (!dateStr) {
    const today = new Date();
    dateStr = today.getFullYear()+'-'+String(today.getMonth()+1).padStart(2,'0')+'-'+String(today.getDate()).padStart(2,'0');
  }

  document.getElementById('amSendOverlay').classList.remove('hidden');

  api('/api/dashboard/arrivals/send-vk', {method:'POST', body:JSON.stringify({date:dateStr, text})}).then(d => {
    document.getElementById('amSendOverlay').classList.add('hidden');
    if (d.success) {
      toast('Приход отправлен в ВКонтакте'+(d.photos_sent?' + '+d.photos_sent+' фото':''));
      closeArrival();
      if (activeTab === 'arrivals') loadArrivalsMonth();
    } else {
      toast(d.error||'Ошибка отправки', 'error');
    }
  }).catch(() => {
    document.getElementById('amSendOverlay').classList.add('hidden');
    toast('Сервер недоступен', 'error');
  });
}

/* ==================== PASSWORD ==================== */
function openPwModal() {
  document.getElementById('pwOld').value = '';
  document.getElementById('pwNew').value = '';
  document.getElementById('pwError').classList.add('hidden');
  document.getElementById('pwModal').classList.remove('hidden');
}
function closePwModal() {
  document.getElementById('pwModal').classList.add('hidden');
}
function changePassword() {
  const oldPw = document.getElementById('pwOld').value;
  const newPw = document.getElementById('pwNew').value;
  const err = document.getElementById('pwError');
  if (!oldPw || !newPw) { err.textContent = 'Заполните оба поля'; err.classList.remove('hidden'); return; }
  if (newPw.length < 3) { err.textContent = 'Минимум 3 символа'; err.classList.remove('hidden'); return; }
  api('/api/dashboard/change-password', {method:'POST', body:JSON.stringify({old_password:oldPw, new_password:newPw})}).then(d => {
    if (d.success) { toast('Пароль изменён', 'success'); closePwModal(); }
    else { err.textContent = d.error||'Ошибка'; err.classList.remove('hidden'); }
  }).catch(() => { err.textContent = 'Сервер недоступен'; err.classList.remove('hidden'); });
}

document.getElementById('pwNew').addEventListener('keydown', e => { if(e.key==='Enter') changePassword(); });

function updateSelfAvatar() {
  var el = document.getElementById('selfAva');
  if (S.myAvatar) {
    el.innerHTML = '<img src="/api/dashboard/employees/avatar-img?file='+S.myAvatar+'">';
  } else {
    el.innerHTML = (S.user||'?').charAt(0).toUpperCase();
  }
}

function uploadSelfAvatar(e) {
  var file = e.target.files[0];
  if (!file) return;
  if (!S.myEmpId) { toast('Сотрудник не найден','error'); return; }
  var fd = new FormData();
  fd.append('avatar', file);
  fetch('/api/dashboard/employees/'+S.myEmpId+'/avatar', {
    method:'POST',
    headers:{'Authorization':'Bearer '+(localStorage.getItem('dashboard_token')||'')},
    body:fd
  }).then(function(r){return r.json()}).then(function(d){
    if (d.success) {
      S.myAvatar = d.avatar;
      updateSelfAvatar();
      loadSchedule();
      toast('Аватар обновлён');
    }
  });
  e.target.value = '';
}

function loadPurchase() {
  const ta = document.getElementById('pmText');
  let dateStr = ta.dataset.date;
  if (!dateStr) {
    const today = new Date();
    dateStr = today.getFullYear()+'-'+String(today.getMonth()+1).padStart(2,'0')+'-'+String(today.getDate()).padStart(2,'0');
  }
  const titleEl = document.querySelector('#purchaseModal .pm-box h3');
  titleEl.innerHTML = '<i class="fas fa-shopping-cart"></i> ' + esc('Закуп на ' + dateStr);

  api('/api/dashboard/purchase?date='+dateStr).then(d => {
    if (d.text) {
      document.getElementById('pmText').value = d.text;
      updatePmStatus('done', false);
    } else {
      document.getElementById('pmText').value = '';
      updatePmStatus('microphone', false);
    }
  });
}

document.addEventListener('DOMContentLoaded', () => {
  if (!checkAuth()) return;
  S.token = localStorage.getItem('dashboard_token') || '';
  const h = {'Authorization':'Bearer '+S.token};
  fetch('/api/dashboard/me', {headers:h}).then(r => {
    if (r.status === 401) { doLogout(); return; }
    return r.json();
  }).then(d => {
    if (!d || d.error) return;
    document.body.classList.add('visible');
    S.user = d.login;
    document.getElementById('userInfo').textContent = d.login;
    document.getElementById('fabSchedule').classList.add('active');
    document.getElementById('loadingScreen').classList.add('hidden');
    if (d.avatar) S.myAvatar = d.avatar;
    S.myEmpId = d.employee_id;
    updateSelfAvatar();
    loadWeather();
    loadChat();
    var hashTab = location.hash.replace('#','');
    if (hashTab && ['schedule','revenue','purchase','arrivals'].includes(hashTab)) switchTab(hashTab);
    else loadSchedule();
    initTooltip();
    setTimeout(updateBnSlider, 100);
  }).catch(() => {});
  var _weatherTimer = setInterval(loadWeather, 3600000);
  var _chatTimer = setInterval(loadChat, 20000);
  function stopTimers(){ clearInterval(_weatherTimer); clearInterval(_chatTimer); }
  function startTimers(){
    if (_weatherTimer) clearInterval(_weatherTimer);
    if (_chatTimer) clearInterval(_chatTimer);
    _weatherTimer = setInterval(loadWeather, 3600000);
    _chatTimer = setInterval(loadChat, 20000);
  }
window.addEventListener('pagehide', function(){ snakeRunning = false; stopTimers(); });
window.addEventListener('pageshow', function(){ snakeRunning = true; snakeStart = performance.now(); startTimers(); });
  startSnakeLoop();
})();
  // Prevent browser pull-to-refresh
  document.addEventListener('touchmove', function(e) {
    if (e.target.closest && (e.target.closest('#revenueContainer') || e.target.closest('#purchaseContainer') || e.target.closest('#arrivalContainer') || e.target.closest('.table-wrap'))) {
      var el = e.target.closest('#revenueContainer') || e.target.closest('#purchaseContainer') || e.target.closest('#arrivalContainer') || e.target.closest('.table-wrap');
      if (el.scrollTop <= 0 && e.touches[0].clientY > e._lastY) { e.preventDefault(); }
      e._lastY = e.touches[0].clientY;
    }
  }, {passive: false});
});

/* ── Chat ── */
function loadChat() {
  api('/api/dashboard/chat?_=' + Date.now()).then(function(msgs) {
    var el = document.getElementById('wChatMsgs');
    var tile = document.getElementById('chatTile');
    if (!el || !tile) return;
    if (!msgs.length) {
      el.innerHTML = '';
      tile.classList.add('hidden');
      tile.querySelector('.chat-dot')?.remove();
      return;
    }
    tile.classList.remove('hidden');
    var h = '';
    for (var i = 0; i < msgs.length; i++) {
      var m = msgs[i];
      var t = new Date(m.created_at);
      var time = String(t.getHours()).padStart(2,'0') + ':' + String(t.getMinutes()).padStart(2,'0');
      h += '<div class="w-cmsg">' +
        '<span class="w-cn">' + esc(m.employee_name) + '</span>' +
        '<span class="w-ct">' + esc(m.text) + '</span>' +
        '<span class="w-cm">' + time + '</span>' +
      '</div>';
    }
    // Check for new messages
    var prevCount = parseInt(el.getAttribute('data-count') || '0');
    if (msgs.length > prevCount && prevCount > 0 && document.hidden) {
      if (!tile.querySelector('.chat-dot')) {
        var dot = document.createElement('span');
        dot.className = 'chat-dot';
        dot.title = 'Новые сообщения';
        tile.appendChild(dot);
      }
    }
    el.innerHTML = h;
    el.setAttribute('data-count', msgs.length);
    el.scrollTop = el.scrollHeight;
  }).catch(function() {});
}

function sendChatMsg() {
  var inp = document.getElementById('chatInput');
  var text = inp.value.trim();
  if (!text) return;
  inp.value = '';
  inp.disabled = true;
  document.querySelector('#chatTile .chat-dot')?.remove();
  api('/api/dashboard/chat', { method: 'POST', body: JSON.stringify({ text: text }) }).then(function(d) {
    inp.disabled = false;
    if (d.error) { toast(d.error, 'error'); return; }
    loadChat();
    inp.focus();
  }).catch(function() {
    inp.disabled = false;
  });
}

/* Snake border animation */
var snakeStart = performance.now();
var snakeRunning = true;
var _snakeTodayRows = [];
var _snakeTodayBlocks = [];
const SNAKE_DURATION = 3000;

function refreshSnakeCache() {
  _snakeTodayRows = [];
  document.querySelectorAll('tr').forEach(tr => {
    if (tr.querySelector('.today-cell')) _snakeTodayRows.push(tr);
  });
  _snakeTodayBlocks = [...document.querySelectorAll('.rev-day.today-rev,.pday.today-rev')];
}

function startSnakeLoop() {
  if (window.innerWidth < 800) return;
  refreshSnakeCache();
  function tick(now) {
    if (!snakeRunning || !document.hidden) {} // continue only if visible
    if (!snakeRunning) return;
    const elapsed = (now - snakeStart) % SNAKE_DURATION;
    const total = 400;
    const tickPos = (elapsed / SNAKE_DURATION) * total;
    const seg = Math.floor(tickPos / 100) % 4;
    const pos = tickPos % 100;
    let dir, isH;
    if (seg===0)      { dir='to right'; isH=true; }
    else if (seg===1) { dir='to bottom'; isH=false; }
    else if (seg===2) { dir='to left'; isH=true; }
    else              { dir='to top'; isH=false; }

    const g = `linear-gradient(${dir},
      transparent ${pos-25}%,
      rgba(74,222,128,0.3) ${pos-18}%,
      var(--accent) ${pos-8}%, var(--accent) ${pos+8}%,
      rgba(74,222,128,0.3) ${pos+18}%,
      transparent ${pos+25}%)`;
    const gFull = `linear-gradient(${dir},
      transparent ${pos-25}%,
      color-mix(in srgb, var(--accent) 30%, transparent) ${pos-18}%,
      var(--accent) ${pos-8}%, var(--accent) ${pos+8}%,
      color-mix(in srgb, var(--accent) 30%, transparent) ${pos+18}%,
      transparent ${pos+25}%)`;
    const grad = CSS.supports('color', 'color-mix(in srgb, red, blue)') ? gFull : g;

    _snakeTodayRows.forEach(tr => {
      tr.style.backgroundImage = grad;
      tr.style.backgroundSize = isH ? '100% 1px' : '1px 100%';
      tr.style.backgroundRepeat = 'no-repeat';
      tr.style.backgroundPosition = seg===0?'top':seg===1?'right':seg===2?'bottom':'left';
    });
    _snakeTodayBlocks.forEach(el => {
      el.style.backgroundImage = grad;
      el.style.backgroundSize = isH ? '100% 1px' : '1px 100%';
      el.style.backgroundRepeat = 'no-repeat';
      el.style.backgroundPosition = seg===0?'top':seg===1?'right':seg===2?'bottom':'left';
      el.style.border = 'none';
    });

    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

function initTooltip() {
  var tooltip = document.createElement('div');
  tooltip.className = 'schedule-tooltip';
  document.body.appendChild(tooltip);
  document.addEventListener('mouseover', function(e) {
    var cell = e.target.closest('.emp-cell');
    if (!cell) return;
    var eid = cell.getAttribute('data-eid');
    var ds = cell.getAttribute('data-ds');
    var shift = S.shifts.find(function(s) { return s.employee_id == eid && s.date === ds; });
    var emp = S.employees.find(function(e) { return e.id == eid; });
    if (!emp) return;
    var type = shift ? (shift.shift_type === 'full' ? 'Полный день' : shift.shift_type === 'half' ? '0.5 смены' : 'Выходной') : 'Выходной';
    tooltip.textContent = emp.name + ' — ' + ds + ' — ' + type;
    tooltip.classList.add('visible');
  });
  document.addEventListener('mousemove', function(e) {
    tooltip.style.left = (e.clientX + 12) + 'px';
    tooltip.style.top = (e.clientY - 30) + 'px';
  });
  document.addEventListener('mouseout', function(e) {
    if (e.target.closest('.emp-cell')) return;
    tooltip.classList.remove('visible');
  });
}

var _resizeTimer = null;
window.addEventListener('resize', function() {
  if (_resizeTimer) clearTimeout(_resizeTimer);
  _resizeTimer = setTimeout(function() {
    document.querySelectorAll('.rev-day.today-rev,.pday.today-rev').forEach(function(el) {
      el.style.backgroundImage = '';
      el.style.border = '';
    });
    updateBnSlider();
  }, 250);
});

document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    closeRevModal();
    closePurchase();
    closeArrival();
    closePwModal();
    closeFabMenu();
  }
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  if (e.key === '1') switchTab('schedule');
  else if (e.key === '2') switchTab('revenue');
  else if (e.key === '3') switchTab('purchase');
  else if (e.key === '4') switchTab('arrivals');
  else if (e.key === 't' || e.key === 'T' || e.key === '\u0435' || e.key === '\u0415') {
    if (activeTab === 'schedule') goToday();
    else if (activeTab === 'purchase') goTodayPurchase();
    else if (activeTab === 'arrivals') goTodayArrival();
  }
});

function loadHtml2Canvas() {
  if (window.html2canvas) return Promise.resolve();
  return new Promise(function(resolve, reject) {
    var s = document.createElement('script');
    s.src = 'https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js';
    s.onload = resolve;
    s.onerror = reject;
    document.head.appendChild(s);
  });
}


(function(){
  var usesZoom = 'zoom' in document.documentElement.style;
  function applyZoom(z, baseW) {
    var el = document.documentElement;
    if (z > 1) {
      if (usesZoom) {
        el.style.zoom = z;
      } else {
        el.style.transform = 'scale(' + z + ')';
        el.style.transformOrigin = 'top left';
        el.style.width = (100 / z) + 'vw';
        el.style.height = (100 / z) + 'vh';
      }
      document.body.style.maxWidth = (baseW / z) + 'px';
      document.body.style.margin = '0 auto';
      document.body.style.overflowX = 'hidden';
    } else {
      el.style.zoom = '';
      el.style.transform = '';
      el.style.transformOrigin = '';
      el.style.width = '';
      el.style.height = '';
      document.body.style.maxWidth = '';
      document.body.style.margin = '';
      document.body.style.overflowX = '';
    }
  }
  function getZoom(w) {
    if (w >= 2400) return 2.0;
    if (w >= 1800) return 1.75;
    if (w >= 1400) return 1.5;
    if (w >= 1000) return 1.25;
    return 1;
  }
  var z = getZoom(window.innerWidth);
  applyZoom(z, window.innerWidth);
  window.addEventListener('resize', function(){
    var origW = window.innerWidth;
    if (!usesZoom && z > 1) { document.documentElement.style.transform = ''; origW = window.innerWidth; }
    if (usesZoom && z > 1) { document.documentElement.style.zoom = ''; origW = window.innerWidth; }
    var nz = getZoom(origW);
    if (nz !== z) { z = nz; }
    applyZoom(z, origW);
  });
})();

