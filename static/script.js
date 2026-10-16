document.addEventListener('DOMContentLoaded', () => {
  // Dynamic Student Enrollment Handler (Admin Console)
  const enrollForm = document.querySelector('#enrollStudentForm');
  if (enrollForm) {
    enrollForm.addEventListener('submit', async event => {
      event.preventDefault();
      const statusBox = document.querySelector('#enrollMessage');
      if (statusBox) statusBox.innerHTML = '<span style="color: #94a3b8;">Registering student in SQLite…</span>';

      const payload = {
        name: document.querySelector('#new_name')?.value.trim(),
        email: document.querySelector('#new_email')?.value.trim(),
        password: document.querySelector('#new_pass')?.value.trim(),
        phone: document.querySelector('#new_phone')?.value.trim(),
        batch_id: document.querySelector('#new_batch')?.value,
        fee_amount: document.querySelector('#new_fee')?.value || 25000
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
          showToast(data.message);
          enrollForm.reset();
          setTimeout(() => window.location.reload(), 1200);
        } else {
          if (statusBox) statusBox.innerHTML = `<span style="color: #ef4444;">❌ ${data.message}</span>`;
          showToast(data.message || 'Enrollment failed');
        }
      } catch (err) {
        if (statusBox) statusBox.innerHTML = `<span style="color: #ef4444;">❌ Network error</span>`;
        showToast('Server communication failure.');
      }
    });
  }

  // Show/hide password utility
  document.querySelectorAll('.password-toggle').forEach(button => {
    button.addEventListener('click', () => {
      const input = button.parentElement.querySelector('input');
      if (!input) return;
      input.type = input.type === 'password' ? 'text' : 'password';
      button.textContent = input.type === 'password' ? 'Show' : 'Hide';
      button.setAttribute(
        'aria-label',
        input.type === 'password' ? 'Show password' : 'Hide password'
      );
    });
  });

  // Prototype forgot-password toast
  document.querySelectorAll('[data-forgot]').forEach(link => {
    link.addEventListener('click', event => {
      event.preventDefault();
      showToast('Contact your institute administrator to reset access credentials.');
    });
  });

  // Mobile sidebar navigation toggle
  const menuButton = document.querySelector('[data-menu]');
  if (menuButton) {
    menuButton.addEventListener('click', () => {
      document.querySelector('#sidebar')?.classList.toggle('open');
    });
  }

  // Scroll to OpsPilot Copilot
  document.querySelectorAll('[data-scroll-copilot]').forEach(button => {
    button.addEventListener('click', () => {
      document.querySelector('#copilot')?.scrollIntoView({
        behavior: 'smooth',
        block: 'center'
      });
    });
  });

  // Suggested chat prompt click handlers
  document.querySelectorAll('[data-prompt]').forEach(button => {
    button.addEventListener('click', () => sendChat(button.dataset.prompt));
  });

  // Copilot chat form submission
  const chatForm = document.querySelector('[data-chat-form]');
  if (chatForm) {
    chatForm.addEventListener('submit', event => {
      event.preventDefault();
      const input = chatForm.querySelector('input[name="message"]');
      const message = input?.value.trim();

      if (message) {
        sendChat(message);
        input.value = '';
      }
    });
  }

  // Timetable conflict resolution (Deterministic Backtracker trigger)
  document.querySelectorAll('[data-reschedule]').forEach(button => {
    button.addEventListener('click', async () => {
      button.disabled = true;
      button.textContent = 'Checking room and trainer availability…';

      try {
        const response = await fetch('/api/timetable/reschedule', {
          method: 'POST'
        });
        const data = await response.json();
        showToast(data.explanation || 'Timetable updated with zero collisions.');
        setTimeout(() => window.location.reload(), 1500);
      } catch (error) {
        showToast('Schedule suggestion is unavailable right now.');
      } finally {
        button.disabled = false;
        button.textContent = '✧ Suggest a conflict-free reschedule';
      }
    });
  });

  // Filter visible table rows using global search
  const searchInput = document.querySelector('[data-table-search]');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      const query = searchInput.value.toLowerCase();
      document.querySelectorAll('tbody tr').forEach(row => {
        row.hidden = !row.textContent.toLowerCase().includes(query);
      });
    });
  }
});

// Toast notification helper
function showToast(message) {
  let region = document.querySelector('.toast-region');
  if (!region) {
    region = document.createElement('div');
    region.className = 'toast-region';
    document.body.append(region);
  }

  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.textContent = message;
  region.append(toast);

  window.setTimeout(() => toast.remove(), 4000);
}

// OpsPilot Gemini chat pipeline
async function sendChat(message) {
  const chatBox = document.querySelector('[data-chat]');
  if (!chatBox) return;

  const userMessage = document.createElement('div');
  userMessage.className = 'user-message';
  userMessage.textContent = message;
  chatBox.append(userMessage);

  const waitingMessage = document.createElement('div');
  waitingMessage.className = 'bot-message';
  waitingMessage.innerHTML = '<span class="bot-avatar">✳</span><div>Querying institute SQLite database…</div>';
  chatBox.append(waitingMessage);
  chatBox.scrollTop = chatBox.scrollHeight;

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message })
    });

    const data = await response.json();
    waitingMessage.remove();

    const result = document.createElement('div');
    result.className = 'bot-message';

    if (data.type === 'ERROR') {
      result.innerHTML = `<span class="bot-avatar">⚠️</span><div><b style="color:#ef4444;">${escapeHtml(data.reply)}</b></div>`;
    } else {
      let contentHtml = `<div><p style="margin: 0 0 8px 0;">${escapeHtml(data.reply || '')}</p>`;

      if (Array.isArray(data.rows) && data.rows.length > 0) {
        const headers = Object.keys(data.rows[0]);
        contentHtml += `<div class="table-wrap" style="margin-top: 8px;"><table class="result-table"><thead><tr>`;
        headers.forEach(h => {
          contentHtml += `<th style="text-align: left; padding: 6px;">${escapeHtml(h.replaceAll('_', ' ').toUpperCase())}</th>`;
        });
        contentHtml += `</tr></thead><tbody>`;

        data.rows.forEach(row => {
          contentHtml += `<tr style="border-top: 1px solid rgba(255,255,255,0.05);">`;
          headers.forEach(h => {
            contentHtml += `<td style="padding: 6px;">${escapeHtml(String(row[h] ?? ''))}</td>`;
          });
          contentHtml += `</tr>`;
        });
        contentHtml += `</tbody></table></div>`;
      }

      if (data.card) {
        contentHtml += `
          <div class="action-card">
            <b>Action Staged: ${escapeHtml(data.card.action)}</b>
            <p style="margin: 4px 0;">Recipient: <strong>${escapeHtml(data.card.recipient)}</strong></p>
            <p style="margin: 4px 0; font-style: italic;">"${escapeHtml(data.card.message)}"</p>
            <div style="display: flex; gap: 8px; margin-top: 8px;">
              <button class="button button-small" style="background: #10b981; color: #fff;" onclick="submitDecision('${data.card.id}', 'APPROVED', this)">Approve & Dispatch</button>
              <button class="button button-small" style="background: #ef4444; color: #fff;" onclick="submitDecision('${data.card.id}', 'REJECTED', this)">Reject</button>
            </div>
          </div>
        `;
      }

      contentHtml += `</div>`;
      result.innerHTML = `<span class="bot-avatar">✳</span>` + contentHtml;
    }

    chatBox.append(result);
  } catch (error) {
    waitingMessage.innerHTML = '<span class="bot-avatar">⚠️</span><div>Connection error. Check backend server logs.</div>';
  }

  chatBox.scrollTop = chatBox.scrollHeight;
}

async function submitDecision(actionId, decision, button) {
  button.disabled = true;

  try {
    const response = await fetch(`/api/actions/${encodeURIComponent(actionId)}/decision`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision })
    });

    if (!response.ok) throw new Error('Decision failed to save.');

    const actionCard = button.closest('.action-card');
    actionCard.innerHTML = `
      <b style="color: ${decision === 'APPROVED' ? '#10b981' : '#ef4444'};">
        Action ${decision.toLowerCase()} successfully.
      </b>
      <p style="margin: 4px 0; font-size: 0.8rem; color: #94a3b8;">Student portal notification synchronized.</p>
    `;
    showToast(`Action recorded as ${decision.toLowerCase()}`);
  } catch (error) {
    button.disabled = false;
    showToast(error.message || 'Could not record action.');
  }
}

function escapeHtml(value) {
  const element = document.createElement('span');
  element.textContent = value || '';
  return element.innerHTML;
}