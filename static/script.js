console.log('[OpsPilot] Client script loaded.');

window.sendChat = async function(message) {
  const chatBox = document.querySelector('[data-chat]') || document.querySelector('.chat-messages');
  if (!chatBox) {
    console.error('[OpsPilot] Chat message container not found.');
    return;
  }

  const userMsgEl = document.createElement('div');
  userMsgEl.className = 'user-message';
  userMsgEl.textContent = message;
  chatBox.appendChild(userMsgEl);

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
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: message })
    });

    const data = await res.json();
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

document.addEventListener('DOMContentLoaded', () => {
  // Chat form submission
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

  // Quick Action Buttons
  document.querySelectorAll('[data-prompt]').forEach(btn => {
    btn.addEventListener('click', () => {
      window.sendChat(btn.dataset.prompt);
    });
  });

  // Clear Chat Button
  const clearBtn = document.querySelector('.copilot-clear-btn');
  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      const chatBox = document.querySelector('[data-chat]') || document.querySelector('.chat-messages');
      if (chatBox) {
        chatBox.innerHTML = `
          <div class="bot-message">
            <span class="bot-avatar">✦</span>
            <div class="bot-bubble">
              <p>Chat cleared. How can I assist you next?</p>
            </div>
          </div>
        `;
      }
    });
  }

  // Provisioning Form Submission
  const enrollForm = document.querySelector('#enrollStudentForm');
  if (enrollForm) {
    enrollForm.addEventListener('submit', async event => {
      event.preventDefault();
      const statusBox = document.querySelector('#enrollMessage');
      if (statusBox) statusBox.innerHTML = '<span style="color: #64748b;">Provisioning account in database…</span>';

      const payload = {
        name: document.querySelector('#new_name')?.value.trim(),
        email: document.querySelector('#new_email')?.value.trim(),
        password: document.querySelector('#new_pass')?.value.trim(),
        phone: document.querySelector('#new_phone')?.value.trim(),
        batch_id: document.querySelector('#new_batch')?.value || 'b_py',
        fee_amount: parseInt(document.querySelector('#new_fee')?.value, 10) || 25000
      };

      try {
        const response = await fetch('/api/students/add', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await response.json();

        if (data.status === 'SUCCESS') {
          if (statusBox) statusBox.innerHTML = `<span style="color: #10b981;">✅ ${data.message}</span>`;
          enrollForm.reset();
          setTimeout(() => window.location.reload(), 1200);
        } else {
          if (statusBox) statusBox.innerHTML = `<span style="color: #ef4444;">❌ ${data.message}</span>`;
        }
      } catch (err) {
        if (statusBox) statusBox.innerHTML = `<span style="color: #ef4444;">❌ Server communication error</span>`;
      }
    });
  }

  // Edit Student Modal Event Handlers
  const editModal = document.querySelector('#editModal');
  const closeEditBtn = document.querySelector('#closeEditModal');
  const cancelEditBtn = document.querySelector('#cancelEditModal');
  const updateForm = document.querySelector('#updateStudentForm');

  function hideEditModal() {
    if (editModal) editModal.style.display = 'none';
  }

  if (closeEditBtn) closeEditBtn.addEventListener('click', hideEditModal);
  if (cancelEditBtn) cancelEditBtn.addEventListener('click', hideEditModal);

  document.querySelectorAll('.edit-student-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelector('#edit_student_id').value = btn.dataset.id;
      document.querySelector('#edit_name').value = btn.dataset.name;
      document.querySelector('#edit_email').value = btn.dataset.email;
      document.querySelector('#edit_phone').value = btn.dataset.phone;
      document.querySelector('#edit_batch').value = btn.dataset.batch;
      document.querySelector('#edit_fee').value = btn.dataset.fee;
      
      const statusSelect = document.querySelector('#edit_fee_status');
      if (statusSelect) {
        statusSelect.value = btn.dataset.status || 'PENDING';
      }

      document.querySelector('#edit_password').value = '';
      document.querySelector('#updateMessage').innerHTML = '';

      if (editModal) editModal.style.display = 'grid';
    });
  });

  if (updateForm) {
    updateForm.addEventListener('submit', async event => {
      event.preventDefault();
      const studentId = document.querySelector('#edit_student_id').value;
      const statusBox = document.querySelector('#updateMessage');
      if (statusBox) statusBox.innerHTML = '<span style="color: #64748b;">Saving updates…</span>';

      const payload = {
        name: document.querySelector('#edit_name').value.trim(),
        email: document.querySelector('#edit_email').value.trim(),
        password: document.querySelector('#edit_password').value.trim(),
        phone: document.querySelector('#edit_phone').value.trim(),
        batch_id: document.querySelector('#edit_batch').value,
        fee_amount: parseInt(document.querySelector('#edit_fee').value, 10) || 25000,
        fee_status: document.querySelector('#edit_fee_status')?.value || 'PENDING'
      };

      try {
        const response = await fetch(`/api/students/${studentId}/update`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await response.json();

        if (data.status === 'SUCCESS') {
          if (statusBox) statusBox.innerHTML = `<span style="color: #10b981;">✅ ${data.message}</span>`;
          setTimeout(() => window.location.reload(), 1000);
        } else {
          if (statusBox) statusBox.innerHTML = `<span style="color: #ef4444;">❌ ${data.message}</span>`;
        }
      } catch (err) {
        if (statusBox) statusBox.innerHTML = `<span style="color: #ef4444;">❌ Server communication error</span>`;
      }
    });
  }

  // Live Table Search Filter
  const searchInput = document.querySelector('[data-table-search]');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      const q = searchInput.value.toLowerCase();
      document.querySelectorAll('tbody tr').forEach(r => {
        r.hidden = !r.textContent.toLowerCase().includes(q);
      });
    });
  }

  // CSP Timetable Reschedule Trigger
  const rescheduleBtn = document.querySelector('#triggerRescheduleBtn');
  if (rescheduleBtn) {
    rescheduleBtn.addEventListener('click', async () => {
      rescheduleBtn.disabled = true;
      rescheduleBtn.textContent = 'Calculating CSP Slot...';
      try {
        const res = await fetch('/api/timetable/reschedule', { method: 'POST' });
        const data = await res.json();
        alert(data.explanation);
        window.location.reload();
      } catch (e) {
        alert('Rescheduling failed');
        rescheduleBtn.disabled = false;
        rescheduleBtn.textContent = 'Solve Schedule Collisions';
      }
    });
  }
});

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}