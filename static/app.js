/* ── 멀티 에이전트 PM — 프론트엔드 ──────────────────────────────────────── */

// ═══════════════════════════════════════════════════════════════════════════
// 채팅 상태 관리
// ═══════════════════════════════════════════════════════════════════════════

let pmHistory      = [];   // PM 대화 이력
let agentHistory   = [];   // 에이전트 대화 이력
let agentContext   = {};   // PM이 넘긴 파라미터 + 에이전트가 수집한 파라미터
let chatMode       = 'pm'; // 'pm' | 'agent:event-planner' | 'agent:game-localizer'
let pmBusy         = false;

const AGENT_LABELS = {
  'event-planner': { short: 'EP', name: '이벤트 기획 에이전트', color: '#4f86f7' },
  'game-localizer': { short: 'GL', name: '현지화 번역 에이전트', color: '#22c55e' },
};

function currentAgentId() {
  return chatMode.startsWith('agent:') ? chatMode.split(':')[1] : null;
}

async function pmSend() {
  if (pmBusy) return;
  const input = document.getElementById('pm-input');
  const msg   = input.value.trim();
  if (!msg) return;

  input.value = '';
  addChatMsg('user', msg);

  pmBusy = true;
  document.getElementById('pm-send-btn').disabled = true;

  let endpoint, body;
  if (chatMode === 'pm') {
    pmHistory.push({ role: 'user', content: msg });
    endpoint = '/api/pm/chat';
    body     = { message: msg, history: pmHistory };
  } else {
    agentHistory.push({ role: 'user', content: msg });
    const agentId = currentAgentId();
    endpoint = '/api/agent/chat';
    body     = { agent: agentId, message: msg, history: agentHistory, context: agentContext };
  }

  let data;
  try {
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    data = await res.json();
  } catch (e) {
    addChatMsg('pm', '서버 연결 오류: ' + e.message);
    pmBusy = false;
    document.getElementById('pm-send-btn').disabled = false;
    return;
  }

  if (!data.job_id) {
    addChatMsg('pm', data.message || '오류가 발생했습니다.');
    pmBusy = false;
    document.getElementById('pm-send-btn').disabled = false;
    return;
  }

  // 현재 모드에 맞는 버블 생성
  const bubble = createResponseBubble();
  streamPmJob(data.job_id, bubble);
}

function pmSetExample(el) {
  document.getElementById('pm-input').value = el.textContent.replace(/^[^\s]+\s/, '');
  document.getElementById('pm-input').focus();
}

function addChatMsg(role, text) {
  const wrap = document.getElementById('chat-messages');
  const bubble = document.createElement('div');
  bubble.className = `chat-bubble ${role}`;

  const avatar = document.createElement('div');
  avatar.className = 'chat-avatar';
  if (role === 'user') {
    avatar.textContent = 'ME';
  } else if (role === 'pm') {
    avatar.textContent = 'PM';
  } else {
    // agent role
    const agentId = currentAgentId();
    const info = AGENT_LABELS[agentId] || {};
    avatar.textContent = info.short || 'EP';
    if (info.color) avatar.style.background = info.color;
  }

  const body = document.createElement('div');
  body.className = 'chat-body';
  body.innerHTML = mdToHtml(text);

  bubble.appendChild(avatar);
  bubble.appendChild(body);
  wrap.appendChild(bubble);
  wrap.scrollTop = wrap.scrollHeight;
  return bubble;
}

function createResponseBubble() {
  const wrap = document.getElementById('chat-messages');
  const bubble = document.createElement('div');

  const avatar = document.createElement('div');
  avatar.className = 'chat-avatar';

  if (chatMode === 'pm') {
    bubble.className = 'chat-bubble pm';
    avatar.textContent = 'PM';
  } else {
    const agentId = currentAgentId();
    const info = AGENT_LABELS[agentId] || { short: 'EP', color: '#4f86f7' };
    bubble.className = 'chat-bubble agent';
    avatar.textContent = info.short;
    avatar.style.background = info.color;
  }

  const body = document.createElement('div');
  body.className = 'chat-body';
  body.innerHTML = '<span style="color:#a0aec0;font-size:12px">처리 중...</span>';

  bubble.appendChild(avatar);
  bubble.appendChild(body);
  wrap.appendChild(bubble);
  wrap.scrollTop = wrap.scrollHeight;
  return { bubble, body };
}

function showHandoffBanner(agentId) {
  const wrap  = document.getElementById('chat-messages');
  const info  = AGENT_LABELS[agentId] || { name: agentId, color: '#4f86f7' };
  const div   = document.createElement('div');
  div.className = 'agent-handoff-banner';
  div.innerHTML = `<span style="color:${info.color}">🤝</span> <strong>${info.name}</strong>가 연결되었습니다`;
  wrap.appendChild(div);
  wrap.scrollTop = wrap.scrollHeight;

  // 입력창 플레이스홀더 업데이트
  document.getElementById('pm-input').placeholder = `${info.name}에게 답변하세요...`;

  // 채팅 헤더 배지 업데이트
  const badge = document.getElementById('chat-agent-badge');
  if (badge) {
    badge.textContent = info.name;
    badge.style.borderColor = info.color;
    badge.style.color = info.color;
    badge.classList.remove('hidden');
  }
}

async function _agentAutoStart() {
  // 에이전트 핸드오프 직후 자동으로 첫 질문을 받아옴 (사용자 입력 불필요)
  if (!chatMode.startsWith('agent:')) return;
  const agentId = currentAgentId();
  const startMsg = '__agent_start__';  // 서버에서 처리하는 내부 트리거

  let data;
  try {
    const res = await fetch('/api/agent/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agent: agentId, message: startMsg, history: agentHistory, context: agentContext }),
    });
    data = await res.json();
  } catch (e) { return; }

  if (!data.job_id) return;

  pmBusy = true;
  document.getElementById('pm-send-btn').disabled = true;
  const bub = createResponseBubble();
  streamPmJob(data.job_id, bub);
}

function resetToPmMode() {
  chatMode    = 'pm';
  agentHistory = [];
  agentContext = {};
  document.getElementById('pm-input').placeholder =
    '예: 7월 일본 마켓 이벤트 기획안 만들어줘. 소스: C:/Users/.../이벤트.xlsx, 탭: 260701, 260715';
  const badge = document.getElementById('chat-agent-badge');
  if (badge) badge.classList.add('hidden');
}

function streamPmJob(jobId, { bubble, body }) {
  const sse = new EventSource(`/api/pm/stream/${jobId}`);
  let msgText = '';
  let stepsEl = null;
  let currentStepEl = null;

  function getOrCreateSteps() {
    if (!stepsEl) {
      stepsEl = document.createElement('div');
      stepsEl.className = 'pipeline-steps';
      body.appendChild(stepsEl);
    }
    return stepsEl;
  }

  sse.onmessage = (e) => {
    const ev = JSON.parse(e.data);
    const wrap = document.getElementById('chat-messages');

    if (ev.type === 'heartbeat') return;

    if (ev.type === 'message') {
      msgText = ev.content || '';
      body.innerHTML = mdToHtml(msgText);
    }

    // 참조 탭 클릭 선택 UI
    if (ev.type === 'tab_selector') {
      _renderTabSelector(ev.new_tabs, ev.available_tabs, body);
    }

    // PM → 에이전트 위임 이벤트
    if (ev.type === 'handoff') {
      chatMode     = `agent:${ev.agent}`;
      agentContext = ev.params || {};
      // PM 대화 이력을 에이전트에게 전달 (컨텍스트 연속성)
      agentHistory = pmHistory.map(m => ({...m}));
      body.innerHTML = `<span style="color:#a0aec0;font-size:12px">에이전트에게 위임 중...</span>`;
    }

    // 에이전트가 컨텍스트 업데이트 (수집된 파라미터 반영)
    if (ev.type === 'context_update') {
      agentContext = ev.context || agentContext;
    }

    // 보상 히스토리 비교 결과 — 파이프라인 완료 후 별도 카드로 표시
    if (ev.type === 'reward_comparison') {
      _renderRewardComparison(ev.data, body);
    }

    if (ev.type === 'step') {
      getOrCreateSteps();
      currentStepEl = document.createElement('div');
      currentStepEl.className = 'pipeline-step step-running';
      currentStepEl.innerHTML = `<span class="step-icon">⏳</span> ${ev.name}`;
      stepsEl.appendChild(currentStepEl);
    }

    if (ev.type === 'step_ok' && currentStepEl) {
      currentStepEl.className = 'pipeline-step step-ok';
      currentStepEl.innerHTML = `<span class="step-icon">✅</span> ${ev.message}`;
      currentStepEl = null;
    }

    if (ev.type === 'step_fail' && currentStepEl) {
      currentStepEl.className = 'pipeline-step step-fail';
      currentStepEl.innerHTML = `<span class="step-icon">❌</span> ${ev.message}`;
      currentStepEl = null;
    }

    if (ev.type === 'error') {
      const card = document.createElement('div');
      card.className = 'chat-error-card';
      card.textContent = ev.message;
      body.appendChild(card);
    }

    if (ev.type === 'done') {
      sse.close();
      pmBusy = false;
      document.getElementById('pm-send-btn').disabled = false;

      if (ev.status === 'handoff') {
        // 에이전트 모드로 전환 — 핸드오프 배너 표시
        showHandoffBanner(currentAgentId());
        if (body.innerHTML.includes('위임 중')) {
          body.innerHTML = '';
          bubble.remove();
        }
        // 에이전트에게 자동으로 시작 메시지 전송 (사용자 입력 없이 첫 질문 시작)
        setTimeout(() => _agentAutoStart(), 300);

      } else if (ev.status === 'success') {
        const card = document.createElement('div');
        card.className = 'chat-result-card';
        let html = ev.summary ? `<p style="white-space:pre-wrap">${mdToHtml(ev.summary)}</p>` : '';
        if (ev.output_path) {
          const enc = encodeURIComponent(ev.output_path);
          html += `<p style="margin-top:8px">
            <a href="/api/event/download?path=${enc}" download>⬇️ ${ev.output_name || '파일 다운로드'}</a>
          </p>`;
        }
        if (html) { card.innerHTML = html; body.appendChild(card); }
        pmHistory.push({ role: 'assistant', content: (ev.summary || '') });
        loadHomeFiles();
        resetToPmMode();  // 파이프라인 완료 → PM 모드 복귀

      } else if (ev.status === 'chat') {
        // 대화 계속 — 이력 추가
        if (chatMode === 'pm') {
          pmHistory.push({ role: 'assistant', content: msgText });
        } else {
          agentHistory.push({ role: 'assistant', content: msgText });
        }

      } else if (ev.status === 'error') {
        // step_fail / error 이벤트로 이미 표시됨
      }

      // "처리 중..." 제거 — 메시지가 없었고 context_update만 있던 경우 버블 숨김
      if (body.innerHTML.includes('처리 중')) {
        if (ev.status === 'chat' || ev.status === 'handoff') {
          // 응답 없이 done이 온 경우 빈 버블 제거
          bubble.remove();
        } else {
          body.innerHTML = '<span style="color:#a0aec0;font-size:12px">(응답 없음)</span>';
        }
      }
    }

    wrap.scrollTop = wrap.scrollHeight;
  };

  sse.onerror = () => {
    sse.close();
    pmBusy = false;
    document.getElementById('pm-send-btn').disabled = false;
    body.innerHTML += '<br><span style="color:#dc2626;font-size:12px">연결이 끊겼습니다.</span>';
  };
}

function mdToHtml(text) {
  if (!text) return '';
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.+?)`/g, '<code style="background:#f3f4f6;padding:1px 5px;border-radius:3px">$1</code>')
    .replace(/\n/g, '<br>');
}

// PM 상태 배너 + AI 모드 배지
(async () => {
  try {
    const s = await fetch('/api/pm/status').then(r => r.json());
    const badge = document.getElementById('ai-mode-badge');
    if (!s.has_ai) {
      document.getElementById('pm-no-ai-banner')?.classList.remove('hidden');
      if (badge) { badge.textContent = 'AI: 미설정'; badge.style.color = '#f38ba8'; }
    } else if (s.ai_mode === 'ollama') {
      if (badge) badge.textContent = `Ollama: ${s.ollama_model}`;
    } else if (s.ai_mode === 'anthropic') {
      if (badge) badge.textContent = 'Claude API';
    }
  } catch {}
})();


// ── 장르 맵 ────────────────────────────────────────────────────────────────
const GENRE_MAP = {
  '액션·슈팅': ['핵앤슬래시', 'FPS', 'TPS'],
  'RPG·전략':  ['MMORPG', '턴제', '전략·RTS', 'MOBA·AOS'],
  '캐주얼':   ['시뮬레이션·어드벤처', '퍼즐', '리듬', '로그라이크·덱빌딩'],
  '스포츠':   ['야구', '축구', '농구', '기타 스포츠'],
};

// ── 상태 ────────────────────────────────────────────────────────────────────
let epOutputPath = '';
let epSourcePath = '';
let glUnregistered = [];

// ═══════════════════════════════════════════════════════════════════════════
// 네비게이션
// ═══════════════════════════════════════════════════════════════════════════
document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => goPage(btn.dataset.page));
});

function goPage(page) {
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.querySelector(`.nav-btn[data-page="${page}"]`).classList.add('active');
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById(`page-${page}`).classList.add('active');

  if (page === 'home') loadHomeFiles();
  if (page === 'event') { loadEpFiles(); checkGlossaryStatus(); }
  if (page === 'localizer') { loadGlFiles(); checkGlossaryStatus(); }
}

// ── 탭 전환 ────────────────────────────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const tabId = btn.dataset.tab;
    const parent = btn.closest('.page');
    parent.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    parent.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(tabId).classList.add('active');
  });
});

// ── 장르 세부 업데이트 ──────────────────────────────────────────────────────
function updateGenreDetail() {
  const family = document.getElementById('ep-genre-family').value;
  const detail = document.getElementById('ep-genre-detail');
  detail.innerHTML = '';
  (GENRE_MAP[family] || []).forEach(g => {
    const o = document.createElement('option');
    o.value = o.textContent = g;
    detail.appendChild(o);
  });
}
updateGenreDetail();

// ═══════════════════════════════════════════════════════════════════════════
// API 호출 유틸
// ═══════════════════════════════════════════════════════════════════════════
async function api(method, url, body = null) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(url, opts);
  return res.json();
}

function showToast(msg, type = 'ok') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = `toast toast-${type}`;
  t.style.opacity = '1';
  t.style.transform = 'translateY(0)';
  setTimeout(() => {
    t.style.opacity = '0';
    t.style.transform = 'translateY(-10px)';
    setTimeout(() => t.className = 'toast hidden', 300);
  }, 3200);
}

function setLog(elId, text, ok = true) {
  const el = document.getElementById(elId);
  el.className = 'log-box' + (ok ? ' log-ok' : ' log-fail');
  el.textContent = text || '';
  el.classList.remove('hidden');
}

function setBtnLoading(btn, loading) {
  if (loading) {
    btn._orig = btn.innerHTML;
    btn.innerHTML = `<span class="spinner"></span> 처리 중...`;
    btn.disabled = true;
  } else {
    btn.innerHTML = btn._orig || btn.innerHTML;
    btn.disabled = false;
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// 홈 — 산출물 목록
// ═══════════════════════════════════════════════════════════════════════════
async function loadHomeFiles() {
  const [ep, gl] = await Promise.all([
    api('GET', '/api/event/files'),
    api('GET', '/api/localizer/files'),
  ]);

  const epEl = document.getElementById('home-ep-files');
  epEl.innerHTML = ep.files?.length
    ? ep.files.slice(0, 4).map(f =>
        `<div>📄 <a href="/api/event/download?path=${encodeURIComponent(f.path)}" download>${f.name}</a>
         <span style="color:#a0aec0;font-size:11px"> (${f.size_kb}KB)</span></div>`
      ).join('')
    : '<span style="color:#a0aec0">아직 없음</span>';

  const glEl = document.getElementById('home-gl-files');
  glEl.innerHTML = gl.files?.length
    ? gl.files.slice(0, 4).map(f =>
        `<div>📄 <a href="/api/localizer/download?path=${encodeURIComponent(f.path)}" download>${f.name}</a>
         <span style="color:#a0aec0;font-size:11px"> (${f.size_kb}KB)</span></div>`
      ).join('')
    : '<span style="color:#a0aec0">아직 없음</span>';
}

// ═══════════════════════════════════════════════════════════════════════════
// ─── 보상 비교 리포트 렌더러 ────────────────────────────────────────────────
function _renderRewardComparison(data, container) {
  if (!data || !data.comparison) return;

  const STATUS_ICON  = { '유지': '✓', '증가': '↑', '감소': '↓', '신규': '★', '제거': '✗', '수량미상': '?' };
  const STATUS_COLOR = { '유지': '#48bb78', '증가': '#4299e1', '감소': '#ed8936', '신규': '#9f7aea', '제거': '#fc8181', '수량미상': '#a0aec0' };

  const wrap = document.createElement('div');
  wrap.style.cssText = 'margin-top:12px;border:1px solid #2d3748;border-radius:8px;overflow:hidden;';

  // 헤더
  const hdr = document.createElement('div');
  hdr.style.cssText = 'background:#2d3748;padding:10px 14px;display:flex;justify-content:space-between;align-items:center;cursor:pointer;';
  hdr.innerHTML = '<span style="font-weight:600;font-size:13px;">📊 보상 히스토리 비교 리포트</span><span style="font-size:11px;color:#a0aec0;">클릭하여 펼치기</span>';

  const body = document.createElement('div');
  body.style.cssText = 'display:none;padding:12px;max-height:420px;overflow-y:auto;';
  hdr.onclick = () => {
    const open = body.style.display !== 'none';
    body.style.display = open ? 'none' : 'block';
    hdr.querySelector('span:last-child').textContent = open ? '클릭하여 펼치기' : '클릭하여 접기';
  };

  // 탭별 요약 + 상세
  const summary = data.summary || {};
  const comparison = data.comparison || {};

  for (const [tab, sections] of Object.entries(comparison)) {
    const cnt = summary[tab] || {};
    const pills = Object.entries(cnt)
      .filter(([,v]) => v > 0)
      .map(([k, v]) => `<span style="display:inline-block;padding:1px 6px;border-radius:10px;font-size:10px;margin-right:4px;background:${STATUS_COLOR[k] || '#4a5568'}22;color:${STATUS_COLOR[k] || '#a0aec0'};">${STATUS_ICON[k] || '?'}${k} ${v}</span>`)
      .join('');

    const tabHdr = document.createElement('div');
    tabHdr.style.cssText = 'font-size:12px;font-weight:600;margin:8px 0 4px;padding:4px 8px;background:#1a202c;border-radius:4px;';
    tabHdr.innerHTML = `탭 ${tab} &nbsp; ${pills}`;
    body.appendChild(tabHdr);

    for (const sec of sections) {
      if (!sec.rewards || sec.rewards.length === 0) continue;

      const secEl = document.createElement('details');
      secEl.style.cssText = 'margin:4px 0;';
      const secTitle = document.createElement('summary');
      secTitle.style.cssText = 'font-size:11px;color:#a0aec0;cursor:pointer;padding:2px 4px;';
      secTitle.textContent = `[${sec.event_type}] ${sec.event_title}`;
      secEl.appendChild(secTitle);

      const table = document.createElement('table');
      table.style.cssText = 'width:100%;font-size:11px;border-collapse:collapse;margin:4px 0;';
      table.innerHTML = '<thead><tr style="color:#718096;"><th style="text-align:left;padding:2px 6px;">보상 아이템</th><th style="text-align:right;padding:2px 6px;">신규 수량</th><th style="text-align:right;padding:2px 6px;">히스토리 평균</th><th style="text-align:center;padding:2px 6px;">상태</th></tr></thead>';
      const tbody = document.createElement('tbody');

      for (const r of sec.rewards) {
        const icon  = STATUS_ICON[r.status]  || '?';
        const color = STATUS_COLOR[r.status] || '#a0aec0';
        const tr = document.createElement('tr');
        tr.style.borderTop = '1px solid #2d3748';
        const diffStr = r.diff_pct != null ? ` (${r.diff_pct > 0 ? '+' : ''}${r.diff_pct}%)` : '';
        tr.innerHTML = `
          <td style="padding:3px 6px;color:#e2e8f0;">${r.name}</td>
          <td style="text-align:right;padding:3px 6px;color:#e2e8f0;">${r.qty_new != null ? r.qty_new.toLocaleString() : '—'}</td>
          <td style="text-align:right;padding:3px 6px;color:#718096;">${r.qty_hist_avg != null ? r.qty_hist_avg.toLocaleString() : '—'}</td>
          <td style="text-align:center;padding:3px 6px;color:${color};">${icon} ${r.status}${diffStr}</td>`;
        tbody.appendChild(tr);
      }
      table.appendChild(tbody);
      secEl.appendChild(table);
      body.appendChild(secEl);
    }
  }

  wrap.appendChild(hdr);
  wrap.appendChild(body);
  container.appendChild(wrap);
}

// 이벤트 기획 — ① 탭 생성 (동적 탭 선택기)
// ═══════════════════════════════════════════════════════════════════════════

let _availableDateTabs = [];  // 소스 파일의 날짜형 탭 목록

async function epLoadTabs() {
  const btn    = document.getElementById('btn-load-tabs');
  const source = document.getElementById('ep-source').value.trim();
  if (!source) { showToast('소스 xlsx 경로를 먼저 입력하세요.', 'fail'); return; }

  setBtnLoading(btn, true);
  const data = await api('POST', '/api/event/tabs', { source_path: source });
  setBtnLoading(btn, false);

  if (!data.ok) { showToast('❌ ' + data.message, 'fail'); return; }

  _availableDateTabs = data.date_tabs || [];

  // 전체 탭 목록 표시
  const listEl = document.getElementById('ep-all-tabs-list');
  listEl.innerHTML = (data.all_tabs || []).map(t => {
    const isDate = _availableDateTabs.includes(t);
    return `<span style="
      padding:3px 10px;border-radius:16px;font-size:12px;font-family:monospace;cursor:default;
      background:${isDate ? '#eef2ff' : '#f3f4f6'};
      color:${isDate ? '#4f46e5' : '#9ca3af'};
      border:1px solid ${isDate ? '#c7d2fe' : '#e5e7eb'};
    " title="${isDate ? '날짜형 탭 (참조 가능)' : '기타 탭'}">${t}</span>`;
  }).join('');

  // 선택기 카드 표시
  document.getElementById('card-tab-selector').style.display = 'block';
  document.getElementById('card-tab-manual').style.display = 'none';

  showToast(`✅ 탭 ${data.all_tabs.length}개 로드 완료 (날짜형: ${_availableDateTabs.length}개)`, 'ok');
}

function _makeRefSelect(selectedVal) {
  const opts = _availableDateTabs.map(t =>
    `<option value="${t}" ${t === selectedVal ? 'selected' : ''}>${t}</option>`
  ).join('');
  return `<select style="padding:6px 10px;border:1px solid #e2e8f0;border-radius:6px;font-family:monospace;font-size:13px;background:#fff">${opts}</select>`;
}

function epAddTabRow() {
  const input   = document.getElementById('ep-new-tab-input');
  const newTab  = input.value.trim();
  if (!newTab) { showToast('탭명을 입력하세요.', 'fail'); return; }
  if (!/^\d{6}$/.test(newTab)) { showToast('YYMMDD 형식 6자리로 입력하세요. 예: 260709', 'fail'); return; }

  const container = document.getElementById('ep-tab-rows');

  // 첫 번째 안내 텍스트 제거
  const placeholder = container.querySelector('[style*="dashed"]');
  if (placeholder) placeholder.remove();

  // 자동 참조 탭 추천: new_tab 날짜 직전에 가장 가까운 날짜형 탭
  const suggestedRef = _bestRefTab(newTab, _availableDateTabs);

  const row = document.createElement('div');
  row.className = 'ep-tab-row';
  row.dataset.newTab = newTab;
  row.innerHTML = `
    <div style="display:flex;align-items:center;gap:10px;padding:10px 12px;background:#f8f9fb;border:1px solid #e2e8f0;border-radius:8px">
      <span style="font-family:monospace;font-weight:700;font-size:14px;color:#1a202c;min-width:70px">📅 ${newTab}</span>
      <span style="color:#9ca3af;font-size:13px">←</span>
      <span style="font-size:12px;color:#6b7280;white-space:nowrap">참조:</span>
      ${_makeRefSelect(suggestedRef)}
      <span style="font-size:11px;color:#a0aec0;flex:1">추천: ${suggestedRef || '없음'}</span>
      <button onclick="this.closest('.ep-tab-row').remove();_checkEmptyRows()" style="background:none;border:none;color:#dc2626;font-size:16px;cursor:pointer;padding:2px 6px" title="제거">✕</button>
    </div>
  `;
  container.appendChild(row);
  input.value = '';
  input.focus();
}

function _bestRefTab(newTab, existing) {
  if (!existing || !existing.length) return '';
  try {
    const nd = new Date(2000 + +newTab.slice(0,2), +newTab.slice(2,4)-1, +newTab.slice(4,6));
    const candidates = existing
      .map(t => ({ t, d: new Date(2000 + +t.slice(0,2), +t.slice(2,4)-1, +t.slice(4,6)) }))
      .filter(({d}) => d < nd)
      .sort((a,b) => b.d - a.d);
    return candidates.length ? candidates[0].t : existing[existing.length - 1];
  } catch { return existing[existing.length - 1] || ''; }
}

function _checkEmptyRows() {
  const container = document.getElementById('ep-tab-rows');
  if (!container.querySelector('.ep-tab-row')) {
    container.innerHTML = `<div style="color:#a0aec0;font-size:13px;padding:12px;text-align:center;border:1px dashed #e2e8f0;border-radius:8px">위에서 생성할 탭명을 입력하고 추가하세요</div>`;
  }
}

function epGetTabsFromSelector() {
  // 동적 선택기에서 new_tabs / ref_tabs 추출
  const rows = document.querySelectorAll('.ep-tab-row');
  if (!rows.length) return null;
  const newTabs = [], refTabs = [];
  rows.forEach(row => {
    newTabs.push(row.dataset.newTab);
    const sel = row.querySelector('select');
    refTabs.push(sel ? sel.value : '');
  });
  return { newTabs, refTabs };
}

async function epCreateTabs() {
  const btn    = event.currentTarget;
  const source = document.getElementById('ep-source').value.trim();
  if (!source) { showToast('소스 xlsx 경로를 입력하세요.', 'fail'); return; }

  // 동적 선택기 vs 수동 입력 분기
  let newTabs, refTabs;
  const selectorCard = document.getElementById('card-tab-selector');
  if (selectorCard && selectorCard.style.display !== 'none') {
    const sel = epGetTabsFromSelector();
    if (!sel || !sel.newTabs.length) {
      showToast('생성할 탭을 하나 이상 추가하세요.', 'fail'); return;
    }
    newTabs = sel.newTabs;
    refTabs = sel.refTabs;
  } else {
    const newTabsRaw = document.getElementById('ep-new-tabs').value.trim();
    const refTabsRaw = document.getElementById('ep-ref-tabs').value.trim();
    if (!newTabsRaw) { showToast('생성할 탭명을 입력하세요.', 'fail'); return; }
    newTabs = newTabsRaw.split('\n').map(s => s.trim()).filter(Boolean);
    refTabs = refTabsRaw ? refTabsRaw.split('\n').map(s => s.trim()).filter(Boolean) : [];
  }

  const keywords = document.getElementById('ep-keywords').value
    .split(',').map(s => s.trim()).filter(Boolean);

  setBtnLoading(btn, true);
  const data = await api('POST', '/api/event/create-tabs', {
    source_path:     source,
    new_tabs:        newTabs,
    ref_tabs:        refTabs,
    output_filename: document.getElementById('ep-output-name').value.trim(),
    genre:           document.getElementById('ep-genre-detail').value,
    market:          document.getElementById('ep-market').value,
    keywords,
  });
  setBtnLoading(btn, false);

  setLog('ep-create-log', data.log || '', data.ok);
  if (data.ok) {
    showToast('✅ ' + data.message, 'ok');
    epOutputPath = data.output_path || '';
    epSourcePath = source;
    document.getElementById('rw-source').value = source;
    document.getElementById('rw-output').value = epOutputPath;
    document.getElementById('pt-source').value = source;
    document.getElementById('pt-output').value = epOutputPath;
    document.getElementById('pt-tabs').value   = newTabs.join(',');
    document.getElementById('out-path').value  = epOutputPath;
  } else {
    showToast('❌ ' + data.message, 'fail');
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// 이벤트 기획 — ② 보상 추천
// ═══════════════════════════════════════════════════════════════════════════
async function epScanRewards(mode) {
  const targetId = mode === 'source' ? 'rw-source' : 'rw-output';
  const target = document.getElementById(targetId).value.trim();
  if (!target) { showToast('경로를 입력하세요.', 'fail'); return; }

  const btn = event.currentTarget;
  setBtnLoading(btn, true);
  const data = await api('POST', '/api/event/scan-rewards', { mode, target_path: target });
  setBtnLoading(btn, false);

  setLog('rw-log', data.log || '', data.ok);
  showToast(data.ok ? `✅ ${mode === 'source' ? '소스' : '신규'} 탭 스캔 완료` : '❌ ' + data.message,
            data.ok ? 'ok' : 'fail');
}

async function epRecommendRewards() {
  const btn = event.currentTarget;
  setBtnLoading(btn, true);
  const data = await api('POST', '/api/event/recommend-rewards', {});
  setBtnLoading(btn, false);

  setLog('rw-log', data.log || '', data.ok);
  if (data.ok) {
    showToast('✅ 보상 추천 완료', 'ok');
    const stats = data.stats || {};
    document.getElementById('rw-total').textContent   = stats.total_sections ?? '?';
    document.getElementById('rw-changes').textContent = stats.sections_with_changes ?? '?';
    document.getElementById('rw-stats').classList.remove('hidden');
  } else {
    showToast('❌ ' + data.message, 'fail');
  }
}

async function epApplyRewards() {
  const outputPath = document.getElementById('rw-output').value.trim();
  const changesRaw = document.getElementById('rw-changes-json').value.trim();
  if (!outputPath || !changesRaw) {
    showToast('output 경로와 변경 JSON을 입력하세요.', 'fail'); return;
  }
  let changes;
  try { changes = JSON.parse(changesRaw); }
  catch { showToast('JSON 파싱 오류: 형식을 확인하세요.', 'fail'); return; }

  const btn = event.currentTarget;
  setBtnLoading(btn, true);
  const data = await api('POST', '/api/event/apply-rewards', {
    output_path: outputPath, changes,
  });
  setBtnLoading(btn, false);

  setLog('rw-apply-log', data.log || '', data.ok);
  showToast(data.ok ? '✅ 변경 적용 완료' : '❌ ' + data.message, data.ok ? 'ok' : 'fail');
}

// ═══════════════════════════════════════════════════════════════════════════
// 이벤트 기획 — ③ 패턴 갭 분석
// ═══════════════════════════════════════════════════════════════════════════
async function epAnalyzePatterns() {
  const source = document.getElementById('pt-source').value.trim();
  const output = document.getElementById('pt-output').value.trim();
  const tabs   = document.getElementById('pt-tabs').value.trim();
  if (!source || !output || !tabs) {
    showToast('소스, output, 탭명을 모두 입력하세요.', 'fail'); return;
  }

  const btn = event.currentTarget;
  setBtnLoading(btn, true);
  const data = await api('POST', '/api/event/analyze-patterns', {
    source_path: source, output_path: output, tabs,
  });
  setBtnLoading(btn, false);

  setLog('pt-log', data.log || '', data.ok);
  showToast(data.ok ? '✅ 갭 분석 완료' : '⚠️ 갭 분석 경고 (블로킹 안 함)', data.ok ? 'ok' : 'info');

  // 결과 테이블 렌더
  const resultEl = document.getElementById('pt-result');
  const analysis = data.analysis || {};
  const tabs_data = analysis.tabs || {};
  if (Object.keys(tabs_data).length) {
    let html = '';
    for (const [tabName, tabData] of Object.entries(tabs_data)) {
      const patterns = tabData.patterns || [];
      if (!patterns.length) continue;
      html += `<div class="card"><h3>탭: ${tabName}</h3>
        <table style="width:100%;border-collapse:collapse;font-size:13px">
          <thead><tr style="background:#f3f4f6">
            <th style="padding:8px;text-align:left;border-bottom:1px solid #e2e8f0">이벤트 유형</th>
            <th style="padding:8px;text-align:left;border-bottom:1px solid #e2e8f0">역사 등장률</th>
            <th style="padding:8px;text-align:center;border-bottom:1px solid #e2e8f0">이번 탭</th>
            <th style="padding:8px;text-align:center;border-bottom:1px solid #e2e8f0">우선순위</th>
          </tr></thead><tbody>`;
      for (const p of patterns) {
        const rate = ((p.rate || 0) * 100).toFixed(0);
        const bar  = '█'.repeat(Math.round(rate / 20)) + '○'.repeat(5 - Math.round(rate / 20));
        const present = p.present ? '✅ 있음' : '❌ 없음';
        html += `<tr style="border-bottom:1px solid #f3f4f6">
          <td style="padding:8px">${p.event_type || ''}</td>
          <td style="padding:8px;font-family:monospace">${bar} ${rate}% (${p.count||0}/${p.total||0})</td>
          <td style="padding:8px;text-align:center">${present}</td>
          <td style="padding:8px;text-align:center">${p.priority || ''}</td>
        </tr>`;
      }
      html += '</tbody></table></div>';
    }
    resultEl.innerHTML = html;
    resultEl.classList.remove('hidden');
  } else {
    resultEl.classList.add('hidden');
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// 이벤트 기획 — ④ 날짜별 패턴 분석
// ═══════════════════════════════════════════════════════════════════════════
async function epDatePatterns() {
  const source = document.getElementById('dp-source').value.trim();
  if (!source) { showToast('소스 경로 또는 Google Sheets URL을 입력하세요.', 'fail'); return; }

  const btn = event.currentTarget;
  setBtnLoading(btn, true);
  const data = await api('POST', '/api/event/date-patterns', { source_path: source });
  setBtnLoading(btn, false);

  setLog('dp-log', data.log || '', data.ok);

  const a = data.analysis || {};
  if (!a.total_tabs) {
    showToast('분석 결과가 없습니다.', 'fail'); return;
  }

  showToast(`✅ 날짜별 패턴 분석 완료 (탭 ${a.total_tabs}개)`, 'ok');

  // ── 알림 배너 ──────────────────────────────────────────────────────────
  const alertsEl = document.getElementById('dp-alerts');
  alertsEl.classList.remove('hidden');

  const missingBanner = document.getElementById('dp-missing-banner');
  const newBanner = document.getElementById('dp-new-banner');

  if ((a.missing_alerts || []).length) {
    let html = `<div class="alert alert-warning" style="margin-bottom:10px">
      <strong>⚠️ 누락 알림 ${a.missing_alerts.length}건</strong>
      <ul style="margin:8px 0 0 18px;padding:0">`;
    for (const al of a.missing_alerts) {
      const sev = al.severity === 'high' ? '❗' : '⚠';
      html += `<li><strong>${sev} ${al.event_type}</strong> — 역사 등장률 ${al.rate_pct}, 최장 ${al.longest_absence_tabs}탭(${al.longest_absence_days}일 추정) 연속 미등장</li>`;
    }
    html += '</ul></div>';
    missingBanner.innerHTML = html;
    missingBanner.classList.remove('hidden');
  } else {
    missingBanner.innerHTML = '<div class="alert" style="background:#d1fae5;color:#065f46;margin-bottom:10px">✅ 누락 이벤트 없음</div>';
    missingBanner.classList.remove('hidden');
  }

  if ((a.new_event_alerts || []).length) {
    let html = `<div class="alert" style="background:#eff6ff;color:#1e40af;margin-bottom:10px">
      <strong>★ 신규 이벤트 ${a.new_event_alerts.length}건</strong>
      <ul style="margin:8px 0 0 18px;padding:0">`;
    for (const al of a.new_event_alerts) {
      html += `<li><strong>${al.event_type}</strong> — 첫 등장 탭: ${al.first_seen}, ${al.count}/${al.total}탭 등장 (${al.rate_pct})</li>`;
    }
    html += '</ul></div>';
    newBanner.innerHTML = html;
    newBanner.classList.remove('hidden');
  } else {
    newBanner.classList.add('hidden');
  }

  // ── 요약 통계 ──────────────────────────────────────────────────────────
  const summaryEl = document.getElementById('dp-summary');
  summaryEl.classList.remove('hidden');
  document.getElementById('dp-stats').innerHTML = `
    <div class="stat-item"><span class="stat-label">분석 탭 수</span><span class="stat-val">${a.total_tabs}개</span></div>
    <div class="stat-item"><span class="stat-label">기간</span><span class="stat-val">${a.tab_date_range?.first} ~ ${a.tab_date_range?.last}</span></div>
    <div class="stat-item"><span class="stat-label">탭 간격</span><span class="stat-val">${a.interval_days}일</span></div>
    <div class="stat-item"><span class="stat-label">탭당 평균 이벤트</span><span class="stat-val">${a.avg_events_per_tab}개</span></div>
    <div class="stat-item"><span class="stat-label">최소/최대</span><span class="stat-val">${a.min_events_per_tab} / ${a.max_events_per_tab}</span></div>
  `;

  // ── 날짜 × 이벤트 매트릭스 ────────────────────────────────────────────
  const matrixCard = document.getElementById('dp-matrix-card');
  matrixCard.classList.remove('hidden');
  const allTypes = a.all_event_types || [];
  const dateMatrix = a.date_matrix || {};
  const tabs = Object.keys(dateMatrix).sort();
  // 최근 20탭만 표시 (너무 많으면 가로 스크롤 부담)
  const displayTabs = tabs.slice(-20);

  let tableHtml = `<table style="border-collapse:collapse;font-size:12px;white-space:nowrap">
    <thead><tr>
      <th style="padding:6px 10px;background:#f3f4f6;position:sticky;left:0;z-index:2;text-align:left;border:1px solid #e2e8f0">이벤트 유형</th>`;
  for (const tab of displayTabs) {
    tableHtml += `<th style="padding:6px 8px;background:#f3f4f6;text-align:center;border:1px solid #e2e8f0;font-weight:600">${tab}</th>`;
  }
  tableHtml += '</tr></thead><tbody>';

  // 빈도 순 정렬된 이벤트 유형
  const freqData = a.frequency || {};
  const sortedTypes = [...allTypes].sort((x, y) => (freqData[y]?.rate || 0) - (freqData[x]?.rate || 0));
  const PRIORITY_COLORS = { anchor: '#fef3c7', common: '#eff6ff', optional: '#f9fafb', rare: '#fff' };
  const PRIORITY_LABEL  = { anchor: '❗', common: '⚠', optional: '〇', rare: '' };

  for (const et of sortedTypes) {
    const info = freqData[et] || {};
    const rowBg = PRIORITY_COLORS[info.priority] || '#fff';
    const icon  = PRIORITY_LABEL[info.priority]  || '';
    tableHtml += `<tr>
      <td style="padding:5px 10px;background:${rowBg};position:sticky;left:0;z-index:1;border:1px solid #e2e8f0;font-weight:${info.priority==='anchor'?'700':'400'}">
        ${icon} ${et} <small style="color:#9ca3af">${info.rate_pct||''}</small>
      </td>`;
    for (const tab of displayTabs) {
      const present = (dateMatrix[tab] || []).includes(et);
      const cell = present
        ? '<td style="text-align:center;background:#d1fae5;border:1px solid #e2e8f0">✅</td>'
        : '<td style="text-align:center;background:#fff;color:#d1d5db;border:1px solid #e2e8f0">−</td>';
      tableHtml += cell;
    }
    tableHtml += '</tr>';
  }
  tableHtml += '</tbody></table>';
  if (tabs.length > 20) {
    tableHtml = `<p style="font-size:12px;color:#6b7280;margin-bottom:6px">※ 최근 20탭만 표시 (전체 ${tabs.length}탭)</p>` + tableHtml;
  }
  document.getElementById('dp-matrix').innerHTML = tableHtml;

  // ── 이벤트 빈도 바 차트 ────────────────────────────────────────────────
  const freqCard = document.getElementById('dp-freq-card');
  freqCard.classList.remove('hidden');
  let freqHtml = `<table style="width:100%;border-collapse:collapse;font-size:13px">
    <thead><tr style="background:#f3f4f6">
      <th style="padding:8px;text-align:left;border-bottom:1px solid #e2e8f0">이벤트 유형</th>
      <th style="padding:8px;text-align:left;border-bottom:1px solid #e2e8f0;min-width:180px">등장률</th>
      <th style="padding:8px;text-align:center;border-bottom:1px solid #e2e8f0">횟수</th>
      <th style="padding:8px;text-align:center;border-bottom:1px solid #e2e8f0">우선순위</th>
      <th style="padding:8px;text-align:center;border-bottom:1px solid #e2e8f0">현재 상태</th>
    </tr></thead><tbody>`;
  for (const et of sortedTypes) {
    const info = freqData[et] || {};
    const streak = (a.streaks || {})[et] || {};
    const filled = Math.round((info.rate || 0) * 10);
    const bar = '█'.repeat(filled) + '○'.repeat(10 - filled);
    const stateBadge = streak.current_state === '등장 중'
      ? `<span style="background:#d1fae5;color:#065f46;padding:2px 7px;border-radius:12px;font-size:11px">▶ ${streak.current_streak}탭 연속 등장</span>`
      : `<span style="background:#fee2e2;color:#991b1b;padding:2px 7px;border-radius:12px;font-size:11px">■ ${streak.current_streak}탭 연속 미등장</span>`;
    const priorityBadge = {
      anchor: '<span style="background:#fef3c7;color:#92400e;padding:2px 7px;border-radius:12px;font-size:11px">❗ anchor</span>',
      common: '<span style="background:#eff6ff;color:#1e40af;padding:2px 7px;border-radius:12px;font-size:11px">⚠ common</span>',
      optional: '<span style="color:#6b7280;font-size:11px">〇 optional</span>',
      rare: '<span style="color:#d1d5db;font-size:11px">rare</span>',
    }[info.priority] || '';
    freqHtml += `<tr style="border-bottom:1px solid #f3f4f6">
      <td style="padding:8px;font-weight:${info.priority==='anchor'?'700':'400'}">${et}</td>
      <td style="padding:8px;font-family:monospace;color:#374151">${bar} ${info.rate_pct}</td>
      <td style="padding:8px;text-align:center;color:#6b7280">${info.count}/${info.total}</td>
      <td style="padding:8px;text-align:center">${priorityBadge}</td>
      <td style="padding:8px;text-align:center">${stateBadge}</td>
    </tr>`;
  }
  freqHtml += '</tbody></table>';
  document.getElementById('dp-freq').innerHTML = freqHtml;

  // ── 월별 분포 ──────────────────────────────────────────────────────────
  const monthlyCard = document.getElementById('dp-monthly-card');
  monthlyCard.classList.remove('hidden');
  const monthly = a.monthly_distribution || {};
  const months = Object.keys(monthly).sort();
  // 월별 컬럼: 최근 12개월
  const displayMonths = months.slice(-12);
  let mHtml = `<table style="border-collapse:collapse;font-size:12px;white-space:nowrap">
    <thead><tr>
      <th style="padding:6px 10px;background:#f3f4f6;position:sticky;left:0;z-index:2;text-align:left;border:1px solid #e2e8f0">이벤트 유형</th>`;
  for (const m of displayMonths) {
    const tc = monthly[m]?.tab_count || '';
    mHtml += `<th style="padding:6px 8px;background:#f3f4f6;text-align:center;border:1px solid #e2e8f0">${m}<br><small style="color:#9ca3af">${tc}탭</small></th>`;
  }
  mHtml += '</tr></thead><tbody>';
  for (const et of sortedTypes.filter(e => (freqData[e]?.priority || 'rare') !== 'rare')) {
    mHtml += '<tr>';
    mHtml += `<td style="padding:5px 10px;position:sticky;left:0;background:#fff;z-index:1;border:1px solid #e2e8f0">${et}</td>`;
    for (const m of displayMonths) {
      const cnt = (monthly[m]?.events || {})[et] || 0;
      const tc  = monthly[m]?.tab_count || 1;
      const pct = Math.round((cnt / tc) * 100);
      const bg  = cnt === 0 ? '#fff' : `rgba(59,130,246,${0.1 + pct / 120})`;
      mHtml += `<td style="text-align:center;background:${bg};border:1px solid #e2e8f0;padding:5px 8px">${cnt > 0 ? cnt : '−'}</td>`;
    }
    mHtml += '</tr>';
  }
  mHtml += '</tbody></table>';
  document.getElementById('dp-monthly').innerHTML = mHtml;
}

// ═══════════════════════════════════════════════════════════════════════════
// 이벤트 기획 — ⑤ 출력
// ═══════════════════════════════════════════════════════════════════════════
async function epUploadGsheets() {
  const outputPath = document.getElementById('out-path').value.trim();
  const targetUrl  = document.getElementById('out-gsheet-url').value.trim();
  if (!outputPath) { showToast('업로드할 xlsx 경로를 입력하세요.', 'fail'); return; }

  const btn = event.currentTarget;
  setBtnLoading(btn, true);
  const data = await api('POST', '/api/event/upload-gsheets', {
    output_path: outputPath, target_url: targetUrl,
  });
  setBtnLoading(btn, false);

  setLog('out-log', data.log || '', data.ok);
  showToast(data.ok ? '✅ 업로드 완료' : '❌ ' + data.message, data.ok ? 'ok' : 'fail');
}

async function loadEpFiles() {
  const data = await api('GET', '/api/event/files');
  const el   = document.getElementById('ep-file-list');
  if (!data.files?.length) {
    el.innerHTML = '<span style="color:#a0aec0;font-size:13px">아직 생성된 파일이 없습니다.</span>';
    return;
  }
  el.innerHTML = data.files.map(f => `
    <div class="file-item">
      <div>
        <div class="file-item-name">📄 ${f.name}</div>
        <div class="file-item-meta">${f.size_kb} KB</div>
      </div>
      <a href="/api/event/download?path=${encodeURIComponent(f.path)}" download
         class="btn btn-sm btn-secondary">⬇️ 다운로드</a>
    </div>
  `).join('');
}

// ═══════════════════════════════════════════════════════════════════════════
// 현지화 번역 — ① 용어집
// ═══════════════════════════════════════════════════════════════════════════
async function glLoadGlossary() {
  const gsheetUrl = document.getElementById('gl-gsheet-url').value.trim();
  const excelPath = document.getElementById('gl-excel-path').value.trim();
  if (!gsheetUrl && !excelPath) {
    showToast('URL 또는 Excel 경로 중 하나 이상 입력하세요.', 'fail'); return;
  }

  const btn = event.currentTarget;
  setBtnLoading(btn, true);
  const data = await api('POST', '/api/localizer/load-glossary', {
    gsheet_url: gsheetUrl, excel_path: excelPath,
  });
  setBtnLoading(btn, false);

  setLog('gl-load-log', data.log || '', data.ok);
  if (data.ok) {
    showToast('✅ 용어집 로드 완료', 'ok');
    renderGlossaryStatus(data.stats || {});
    checkGlossaryStatus();
  } else {
    showToast('❌ ' + data.message, 'fail');
  }
}

function renderGlossaryStatus(stats) {
  const el = document.getElementById('gl-glossary-status');
  el.classList.remove('hidden');
  document.getElementById('gl-stats').innerHTML = `
    <div class="stat-item">
      <span class="stat-label">등록 용어</span>
      <span class="stat-val">${stats.term_count ?? '?'}</span>
    </div>
    <div class="stat-item">
      <span class="stat-label">충돌 항목</span>
      <span class="stat-val" style="color:${stats.conflict_count > 0 ? '#d97706' : 'var(--success)'}">
        ${stats.conflict_count ?? 0}
      </span>
    </div>
    <div class="stat-item" style="min-width:160px">
      <span class="stat-label">생성 시각</span>
      <span style="font-size:13px;font-weight:600;color:var(--text)">${stats.generated_at || '—'}</span>
    </div>
  `;
}

async function glPreviewGlossary() {
  const data = await api('GET', '/api/localizer/glossary-preview');
  const el   = document.getElementById('gl-preview');
  if (!data.ok) { el.classList.add('hidden'); return; }

  const rows = Object.entries(data.terms || {}).slice(0, 30).map(([k, v]) =>
    `<tr>
      <td style="padding:6px 10px;border-bottom:1px solid #f3f4f6;font-weight:600">${k}</td>
      <td style="padding:6px 10px;border-bottom:1px solid #f3f4f6">${v.ko || '—'}</td>
      <td style="padding:6px 10px;border-bottom:1px solid #f3f4f6">${v.ja || '—'}</td>
      <td style="padding:6px 10px;border-bottom:1px solid #f3f4f6">${v.en || '—'}</td>
      <td style="padding:6px 10px;border-bottom:1px solid #f3f4f6">${v.zh || '—'}</td>
    </tr>`
  ).join('');

  el.innerHTML = `
    <p style="font-size:12px;color:#a0aec0;margin-bottom:8px">총 ${data.total}개 중 최대 30개 표시</p>
    <div style="overflow-x:auto">
    <table style="width:100%;border-collapse:collapse;font-size:12px">
      <thead><tr style="background:#f3f4f6">
        <th style="padding:6px 10px;text-align:left;border-bottom:1px solid #e2e8f0">원어</th>
        <th style="padding:6px 10px;text-align:left;border-bottom:1px solid #e2e8f0">🇰🇷 ko</th>
        <th style="padding:6px 10px;text-align:left;border-bottom:1px solid #e2e8f0">🇯🇵 ja</th>
        <th style="padding:6px 10px;text-align:left;border-bottom:1px solid #e2e8f0">🇺🇸 en</th>
        <th style="padding:6px 10px;text-align:left;border-bottom:1px solid #e2e8f0">🇨🇳 zh</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table></div>
  `;
  el.classList.toggle('hidden');
}

async function checkGlossaryStatus() {
  const data = await api('GET', '/api/localizer/glossary-preview');
  const noGlossary = document.getElementById('gl-no-glossary');
  if (data.ok && data.total > 0) {
    noGlossary?.classList.add('hidden');
    renderGlossaryStatus({ term_count: data.total, generated_at: data.generated_at, conflict_count: 0 });
  } else {
    noGlossary?.classList.remove('hidden');
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// 현지화 번역 — ② 번역
// ═══════════════════════════════════════════════════════════════════════════
async function glMatchTerms() {
  const sourceText = document.getElementById('gl-source-text').value.trim();
  if (!sourceText) { showToast('번역할 텍스트를 입력하세요.', 'fail'); return; }

  const textType = document.getElementById('gl-text-type').value || null;
  const langs    = [...document.querySelectorAll('.checkbox-label input:checked')].map(c => c.value);

  const btn = event.currentTarget;
  setBtnLoading(btn, true);
  const data = await api('POST', '/api/localizer/match-terms', {
    source_text: sourceText, text_type: textType, target_languages: langs,
  });
  setBtnLoading(btn, false);

  if (!data.ok) {
    showToast('❌ ' + data.message, 'fail'); return;
  }

  glUnregistered = data.unregistered_terms || [];

  // 매칭 결과 표시
  const matchEl = document.getElementById('gl-match-result');
  const matched = data.matched_terms || {};
  const matchCount = Object.keys(matched).length;

  document.getElementById('gl-matched-info').innerHTML = `
    <p style="font-size:13px;color:#374151">
      <strong>${matchCount}개</strong> 용어 매칭됨
      ${matchCount > 0 ? `— <code style="background:#f3f4f6;padding:2px 6px;border-radius:4px">${Object.keys(matched).join(', ')}</code>` : ''}
    </p>
  `;

  const warnEl = document.getElementById('gl-unregistered-warn');
  if (glUnregistered.length > 0) {
    warnEl.textContent = `⚠️ 미지정 용어 (${glUnregistered.length}개): ${glUnregistered.join(', ')} — 추론으로 번역됩니다.`;
    warnEl.classList.remove('hidden');
  } else {
    warnEl.classList.add('hidden');
  }

  matchEl.classList.remove('hidden');
  document.getElementById('gl-translation-form').classList.remove('hidden');
  showToast('용어 매칭 완료 — 번역 결과를 입력하세요.', 'info');
}

async function glSaveTranslation() {
  const translations = {};
  const langMap = { ko: 'tr-ko', ja: 'tr-ja', en: 'tr-en', zh: 'tr-zh' };
  for (const [lang, elId] of Object.entries(langMap)) {
    const val = document.getElementById(elId).value.trim();
    if (val) translations[lang] = val;
  }

  if (!Object.keys(translations).length) {
    showToast('번역 결과를 하나 이상 입력하세요.', 'fail'); return;
  }

  const textType = document.getElementById('gl-text-type').value || 'dialogue';
  const btn = event.currentTarget;
  setBtnLoading(btn, true);
  const data = await api('POST', '/api/localizer/save-translation', {
    translations, text_type: textType, unregistered_terms: glUnregistered,
  });
  setBtnLoading(btn, false);

  setLog('gl-save-log', data.log || '', data.ok);
  if (data.ok) {
    showToast('✅ 버퍼에 추가됨', 'ok');
    // 입력 초기화
    document.getElementById('gl-source-text').value = '';
    ['tr-ko','tr-ja','tr-en','tr-zh'].forEach(id => document.getElementById(id).value = '');
    document.getElementById('gl-match-result').classList.add('hidden');
    document.getElementById('gl-translation-form').classList.add('hidden');
    glUnregistered = [];
  } else {
    showToast('❌ ' + data.message, 'fail');
  }
}

async function glLoadBuffer() {
  const data = await api('GET', '/api/localizer/buffer');
  const el   = document.getElementById('gl-buffer-list');

  if (!data.entries?.length) {
    el.innerHTML = `<p style="color:#a0aec0;font-size:13px">버퍼가 비어 있습니다. (총 ${data.total || 0}건)</p>`;
    el.classList.remove('hidden');
    return;
  }

  el.innerHTML = `
    <p style="font-size:12px;color:#a0aec0;margin-bottom:8px">최근 ${data.entries.length}건 / 총 ${data.total}건</p>
    <div style="overflow-x:auto">
    <table style="width:100%;border-collapse:collapse;font-size:12px">
      <thead><tr style="background:#f3f4f6">
        <th style="padding:6px;border-bottom:1px solid #e2e8f0">#</th>
        <th style="padding:6px;border-bottom:1px solid #e2e8f0">유형</th>
        <th style="padding:6px;border-bottom:1px solid #e2e8f0">원문</th>
        <th style="padding:6px;border-bottom:1px solid #e2e8f0">ko</th>
        <th style="padding:6px;border-bottom:1px solid #e2e8f0">ja</th>
        <th style="padding:6px;border-bottom:1px solid #e2e8f0">en</th>
      </tr></thead>
      <tbody>
      ${data.entries.map((e, i) => `<tr>
        <td style="padding:6px;border-bottom:1px solid #f3f4f6;color:#a0aec0">${e.id ?? i+1}</td>
        <td style="padding:6px;border-bottom:1px solid #f3f4f6">
          <span style="background:#eef2ff;color:#4f46e5;padding:2px 6px;border-radius:4px;font-size:11px">
            ${e.text_type || '—'}
          </span>
        </td>
        <td style="padding:6px;border-bottom:1px solid #f3f4f6;max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
          ${e.source_text || ''}
        </td>
        <td style="padding:6px;border-bottom:1px solid #f3f4f6;max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
          ${e.translations?.ko || '—'}
        </td>
        <td style="padding:6px;border-bottom:1px solid #f3f4f6;max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
          ${e.translations?.ja || '—'}
        </td>
        <td style="padding:6px;border-bottom:1px solid #f3f4f6;max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
          ${e.translations?.en || '—'}
        </td>
      </tr>`).join('')}
      </tbody>
    </table></div>
  `;
  el.classList.remove('hidden');
}

async function glClearBuffer() {
  if (!confirm('버퍼를 초기화하면 저장되지 않은 번역이 모두 삭제됩니다. 계속할까요?')) return;
  const data = await api('POST', '/api/localizer/buffer/clear', {});
  showToast(data.ok ? '✅ 버퍼 초기화 완료' : '❌ ' + data.message, data.ok ? 'ok' : 'fail');
  document.getElementById('gl-buffer-list').classList.add('hidden');
}

// ═══════════════════════════════════════════════════════════════════════════
// 현지화 번역 — ③ Export
// ═══════════════════════════════════════════════════════════════════════════
async function glExport() {
  const fmt = document.querySelector('input[name="export-fmt"]:checked').value;
  const btn = event.currentTarget;
  setBtnLoading(btn, true);
  const data = await api('POST', '/api/localizer/export', { format: fmt });
  setBtnLoading(btn, false);

  setLog('gl-export-log', data.log || '', data.ok);
  if (data.ok) {
    showToast('✅ Export 완료', 'ok');
    loadGlFiles();
    // 자동 다운로드 링크 생성
    (data.files || []).forEach(f => {
      const a = document.createElement('a');
      a.href = `/api/localizer/download?path=${encodeURIComponent(f.path)}`;
      a.download = f.name;
      a.click();
    });
  } else {
    showToast('❌ ' + data.message, 'fail');
  }
}

async function loadGlFiles() {
  const data = await api('GET', '/api/localizer/files');
  const el   = document.getElementById('gl-file-list');
  if (!data.files?.length) {
    el.innerHTML = '<span style="color:#a0aec0;font-size:13px">아직 Export된 파일이 없습니다.</span>';
    return;
  }
  el.innerHTML = data.files.map(f => `
    <div class="file-item">
      <div>
        <div class="file-item-name">📄 ${f.name}</div>
        <div class="file-item-meta">${f.size_kb} KB</div>
      </div>
      <a href="/api/localizer/download?path=${encodeURIComponent(f.path)}" download
         class="btn btn-sm btn-secondary">⬇️ 다운로드</a>
    </div>
  `).join('');
}

// ═══════════════════════════════════════════════════════════════════════════
// 참조 탭 클릭 선택 UI
// ═══════════════════════════════════════════════════════════════════════════
function _renderTabSelector(newTabs, availableTabs, container) {
  const wrap = document.createElement('div');
  wrap.className = 'tab-selector-wrap';

  const title = document.createElement('div');
  title.className = 'tab-selector-title';
  title.textContent = '📅 생성할 탭별 참조 탭 선택';
  wrap.appendChild(title);

  // 선택 상태 { newTab → selectedRef }
  const selections = {};
  newTabs.forEach(t => selections[t] = null);

  newTabs.forEach(newTab => {
    const row = document.createElement('div');
    row.className = 'tab-selector-row';

    const label = document.createElement('span');
    label.className = 'tab-selector-label';
    label.textContent = newTab;
    row.appendChild(label);

    const arrow = document.createElement('span');
    arrow.style.cssText = 'color:#718096;margin:0 8px;font-size:16px';
    arrow.textContent = '→';
    row.appendChild(arrow);

    const optWrap = document.createElement('div');
    optWrap.className = 'tab-selector-options';

    availableTabs.forEach(refTab => {
      const btn = document.createElement('button');
      btn.className = 'tab-ref-btn';
      btn.textContent = refTab;
      btn.dataset.newTab = newTab;
      btn.dataset.refTab = refTab;
      btn.addEventListener('click', () => {
        // 같은 new_tab의 버튼들 선택 해제
        optWrap.querySelectorAll('.tab-ref-btn').forEach(b => b.classList.remove('selected'));
        btn.classList.add('selected');
        selections[newTab] = refTab;
        indicator.textContent = refTab;
        indicator.style.color = '#48bb78';
        // 모두 선택됐으면 확인 버튼 활성화
        const allDone = Object.values(selections).every(v => v !== null);
        submitBtn.disabled = !allDone;
        if (allDone) submitBtn.classList.add('ready');
      });
      optWrap.appendChild(btn);
    });

    row.appendChild(optWrap);

    const indicator = document.createElement('span');
    indicator.className = 'tab-selector-indicator';
    indicator.textContent = '미선택';
    row.appendChild(indicator);

    wrap.appendChild(row);
  });

  // 확인 버튼
  const submitBtn = document.createElement('button');
  submitBtn.className = 'btn btn-primary tab-selector-submit';
  submitBtn.textContent = '✅ 선택 완료 → 작업 시작';
  submitBtn.disabled = true;
  submitBtn.addEventListener('click', () => {
    const msg = newTabs.map(t => `${t}→${selections[t]}`).join(', ');
    wrap.innerHTML = `<div style="color:#48bb78;font-size:13px">✅ 선택 완료: ${msg}</div>`;
    // 채팅 입력창에 자동 입력 후 전송
    const input = document.getElementById('pm-input');
    input.value = msg;
    pmSend();
  });
  wrap.appendChild(submitBtn);

  container.appendChild(wrap);
  document.getElementById('chat-messages').scrollTop = 99999;
}

// ── 초기 로드 ───────────────────────────────────────────────────────────────
loadHomeFiles();
checkGlossaryStatus();
