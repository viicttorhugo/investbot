(function(){
  const apiKeyInput = document.getElementById('apiKey');
  const saveKeyBtn = document.getElementById('saveKey');
  const emailAdd = document.getElementById('emailAdd');
  const ativoAdd = document.getElementById('ativoAdd');
  const btnAdd = document.getElementById('btnAdd');
  const btnRefresh = document.getElementById('btnRefresh');
  const filter = document.getElementById('filter');
  const tbody = document.querySelector('#tbl tbody');

  const API_BASE = ''; // same host
  const KEY_STORAGE = 'investbot_admin_key';

  function getKey(){ return localStorage.getItem(KEY_STORAGE) || ''; }
  function setKey(v){ localStorage.setItem(KEY_STORAGE, v || ''); }

  function headers(){
    const h = { 'Content-Type': 'application/json' };
    const k = getKey();
    if (k) h['x-api-key'] = k;
    return h;
  }

  function badge(v){
    return `<span class="badge ${v ? 'ok':'no'}">${v ? 'Ativo':'Inativo'}</span>`;
  }

  function rowHtml(item){
    const created = item.created_at ? new Date(item.created_at).toLocaleString() : '';
    const ativo = !!Number(item.ativo);
    const email = item.email;
    return `<tr>
      <td>${item.id}</td>
      <td>${email}</td>
      <td>${badge(ativo)}</td>
      <td>${created}</td>
      <td class="actions">
        <button data-action="activate" data-email="${email}">Ativar</button>
        <button data-action="deactivate" data-email="${email}">Desativar</button>
        <button data-action="delete" data-email="${email}">Excluir</button>
      </td>
    </tr>`;
  }

  async function refresh(){
    tbody.innerHTML = '<tr><td colspan="5">Carregando...</td></tr>';
    try{
      const r = await fetch(`${API_BASE}/api/admin/licenses`, { headers: headers() });
      if(!r.ok) throw new Error('HTTP '+r.status);
      const j = await r.json();
      const text = (filter.value || '').toLowerCase();
      const items = (j.items || []).filter(x => !text || (x.email||'').toLowerCase().includes(text));
      tbody.innerHTML = items.map(rowHtml).join('') || '<tr><td colspan="5">Vazio</td></tr>';
    }catch(e){
      tbody.innerHTML = `<tr><td colspan="5">Erro: ${e}</td></tr>`;
    }
  }

  async function add(){
    const email = (emailAdd.value||'').trim().toLowerCase();
    const ativo = Number(ativoAdd.value||1);
    if(!email){ alert('Informe um email.'); return; }
      try{
    const r = await fetch(`/api/admin/licenses`, {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify({ email, ativo })
    });
    const ctype = (r.headers.get('content-type') || '').toLowerCase();
    const j = ctype.includes('application/json') ? await r.json() : { error: 'http', detail: await r.text() };
    if (r.ok && j.status === 'ok') {
      emailAdd.value=''; await refresh();
    } else {
      alert('Erro: ' + (j.error || 'desconhecido') + (j.detail ? `\nDetalhe: ${j.detail}` : ''));
    }
  } catch(e) {
    alert('Erro: ' + (e.message||e));
  }

  async function action(type, email){
    try{
      if(type==='activate'){
        await fetch(`${API_BASE}/api/admin/licenses`, {
          method: 'POST', headers: headers(), body: JSON.stringify({ email, ativo:1 })
        });
      }else if(type==='deactivate'){
        await fetch(`${API_BASE}/api/admin/licenses/deactivate`, {
          method: 'PATCH', headers: headers(), body: JSON.stringify({ email })
        });
      }else if(type==='delete'){
        await fetch(`${API_BASE}/api/admin/licenses?email=${encodeURIComponent(email)}`, {
          method: 'DELETE', headers: headers()
        });
      }
      await refresh();
    }catch(e){ alert('Erro: '+e); }
  }

  tbody.addEventListener('click', (ev)=>{
    const b = ev.target.closest('button'); if(!b) return;
    const email = b.getAttribute('data-email');
    const action = b.getAttribute('data-action');
    if(action==='delete' && !confirm(`Excluir ${email}?`)) return;
    if(action && email){ action && email && action.length; }
    // dispara
    if(action && email){ action(type, email); }
  });

  btnAdd.addEventListener('click', add);
  btnRefresh.addEventListener('click', refresh);
  saveKeyBtn.addEventListener('click', ()=>{ setKey(apiKeyInput.value||''); refresh(); });

  // init
  apiKeyInput.value = getKey();
  refresh();
})();
