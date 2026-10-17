console.log('[OpsPilot] Client script loaded.');

// Expose sendChat globally so you can trigger it anywhere
window.sendChat = async function(message) {
  const chatBox = document.querySelector('[data-chat]') || document.querySelector('.chat-messages');
  if (!chatBox) {
    console.error('[OpsPilot] Chat message container not found.');
    return;
  }

  // 1. Render User Message
  const userMsgEl = document.createElement('div');
  userMsgEl.className = 'user-message';
  userMsgEl.textContent = message;
  chatBox.appendChild(userMsgEl);

  // 2. Render Loading Indicator
  const loadingEl = document.createElement('div');
  loadingEl.className = 'bot-message';
  loadingEl.id = 'copilot-typing';
  loadingEl.innerHTML = `
    <span class="bot-avatar">✦</span>
    <div class="bot-bubble">
      <div class="typing-indicator">
        <span></span><span></span><span></span>
      </div>
    </div>
  `;
  chatBox.appendChild(loadingEl);
  chatBox.scrollTop = chatBox.scrollHeight;

  try {
    console.log('[OpsPilot] Sending message:', message);
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: message })
    });

    console.log('[OpsPilot] Response status:', res.status);
    const data = await res.json();
    console.log('[OpsPilot] Payload:', data);

    document.getElementById('copilot-typing')?.remove();

    const botMsgEl = document.createElement('div');
    botMsgEl.className = 'bot-message';

    if (data.type === 'ERROR') {
      botMsgEl.innerHTML = `
        <span class="bot-avatar" style="background:#fee2e2; color:#ef4444;">⚠️</span>
        <div class="bot-bubble" style="border-color:#fca5a5; background:#fff5f5;">
          <b style="color:#ef4444;">${escapeHtml(data.reply)}</b>
        </div>
      `;
    } else if (data.type === 'SUCCESS_ACTION') {
      botMsgEl.innerHTML = `
        <span class="bot-avatar" style="background:#dcfce7; color:#15803d;">✓</span>
        <div class="bot-bubble" style="border-color:#bbf7d0; background:#f0fdf4;">
          <b style="color:#15803d;">${escapeHtml(data.reply)}</b>
          <p style="margin:4px 0 0; font-size:11px; color:#64748b;">Updating view...</p>
        </div>
      `;
      setTimeout(() => window.location.reload(), 1400);
    } else {
      let content = `<div class="bot-bubble"><p style="margin:0 0 6px 0; font-weight:600; color:var(--ink);">${escapeHtml(data.reply || '')}</p>`;

      if (Array.isArray(data.rows) && data.rows.length > 0) {
        const headers = Object.keys(data.rows[0]);
        content += `<div class="table-wrap"><table class="result-table"><thead><tr>`;
        headers.forEach(h => {
          content += `<th>${escapeHtml(h.replaceAll('_', ' ').toUpperCase())}</th>`;
        });
        content += `</tr></thead><tbody>`;

        data.rows.forEach(row => {
          content += `<tr>`;
          headers.forEach(h => {
            const val = String(row[h] ?? '');
            if (val === 'PRESENT' || val === 'PAID') {
              content += `<td><span class="badge badge-live">${escapeHtml(val)}</span></td>`;
            } else if (val === 'ABSENT' || val === 'OVERDUE') {
              content += `<td><span class="badge badge-warn">${escapeHtml(val)}</span></td>`;
            } else {
              content += `<td><b>${escapeHtml(val)}</b></td>`;
            }
          });
          content += `</tr>`;
        });
        content += `</tbody></table></div>`;
      }

      content += `</div>`;
      botMsgEl.innerHTML = `<span class="bot-avatar">✦</span>` + content;
    }

    chatBox.appendChild(botMsgEl);
  } catch (err) {
    console.error('[OpsPilot] Error:', err);
    document.getElementById('copilot-typing')?.remove();
    const errEl = document.createElement('div');
    errEl.className = 'bot-message';
    errEl.innerHTML = `
      <span class="bot-avatar" style="background:#fee2e2; color:#ef4444;">⚠️</span>
      <div class="bot-bubble" style="border-color:#fca5a5; background:#fff5f5;">
        <b style="color:#ef4444;">Connection failed. Check terminal logs.</b>
      </div>
    `;
    chatBox.appendChild(errEl);
  }

  chatBox.scrollTop = chatBox.scrollHeight;
};

// UI event listeners
document.addEventListener('DOMContentLoaded', () => {
  // Chat form submit
  const form = document.querySelector('[data-chat-form]') || document.querySelector('.chat-form');
  if (form) {
    form.addEventListener('submit', e => {
      e.preventDefault();
      const input = form.querySelector('input[name="message"]') || form.querySelector('input');
      const val = input?.value.trim();
      if (val) {
        window.sendChat(val);
        input.value = '';
      }
    });
  }

  // Suggestion prompt buttons
  document.querySelectorAll('[data-prompt]').forEach(btn => {
    btn.addEventListener('click', () => {
      window.sendChat(btn.dataset.prompt);
    });
  });

  // Table search
  const searchInput = document.querySelector('[data-table-search]');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      const q = searchInput.value.toLowerCase();
      document.querySelectorAll('tbody tr').forEach(r => {
        r.hidden = !r.textContent.toLowerCase().includes(q);
      });
    });
  }

  // Password toggle
  document.querySelectorAll('.password-toggle').forEach(btn => {
    btn.addEventListener('click', () => {
      const inp = btn.parentElement.querySelector('input');
      if (!inp) return;
      inp.type = inp.type === 'password' ? 'text' : 'password';
      btn.textContent = inp.type === 'password' ? 'Show' : 'Hide';
    });
  });
});

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}