document.addEventListener('DOMContentLoaded', () => {
  // Demo sign-in form handling
  document.querySelectorAll('[data-demo-form]').forEach(form => {
    form.addEventListener('submit', event => {
      event.preventDefault();

      const error = form.querySelector('.form-error');
      const button = form.querySelector('.auth-submit');

      if (!form.reportValidity()) {
        error.textContent = 'Please check the fields and try again.';
        return;
      }

      error.textContent = '';
      button.disabled = true;
      button.innerHTML = 'Opening your workspace… <span>↗</span>';

      window.setTimeout(() => {
        window.location.href = form.dataset.target;
      }, 350);
    });
  });

  // Show/hide password
  document.querySelectorAll('.password-toggle').forEach(button => {
    button.addEventListener('click', () => {
      const input = button.parentElement.querySelector('input');
      input.type = input.type === 'password' ? 'text' : 'password';
      button.textContent = input.type === 'password' ? 'Show' : 'Hide';
      button.setAttribute(
        'aria-label',
        input.type === 'password' ? 'Show password' : 'Hide password'
      );
    });
  });

  // Prototype forgot-password message
  document.querySelectorAll('[data-forgot]').forEach(link => {
    link.addEventListener('click', event => {
      event.preventDefault();
      showToast('For this prototype, contact your institute administrator to reset access.');
    });
  });

  // Mobile sidebar
  const menuButton = document.querySelector('[data-menu]');
  if (menuButton) {
    menuButton.addEventListener('click', () => {
      document.querySelector('#sidebar')?.classList.toggle('open');
    });
  }

  // Scroll to the OpsPilot chat
  document.querySelectorAll('[data-scroll-copilot]').forEach(button => {
    button.addEventListener('click', () => {
      document.querySelector('#copilot')?.scrollIntoView({
        behavior: 'smooth',
        block: 'center'
      });
    });
  });

  // Suggested chat prompts
  document.querySelectorAll('[data-prompt]').forEach(button => {
    button.addEventListener('click', () => sendChat(button.dataset.prompt));
  });

  // Chat form
  const chatForm = document.querySelector('[data-chat-form]');
  if (chatForm) {
    chatForm.addEventListener('submit', event => {
      event.preventDefault();

      const input = chatForm.querySelector('input[name="message"]');
      const message = input.value.trim();

      if (message) {
        sendChat(message);
        input.value = '';
      }
    });
  }

  // Ask the Flask route to suggest a schedule change
  document.querySelectorAll('[data-reschedule]').forEach(button => {
    button.addEventListener('click', async () => {
      button.disabled = true;
      button.textContent = 'Checking room and trainer availability…';

      try {
        const response = await fetch('/api/timetable/reschedule', {
          method: 'POST'
        });
        const data = await response.json();
        showToast(data.explanation || 'Schedule updated.');
      } catch (error) {
        showToast('Schedule suggestion is unavailable right now.');
      } finally {
        button.disabled = false;
        button.textContent = '✧ Suggest a conflict-free reschedule';
      }
    });
  });

  // Student watchlist actions
  document.querySelectorAll('[data-row]').forEach(button => {
    button.addEventListener('click', () => {
      const studentName = button.dataset.row;

      showConfirmDialog(
        `Review ${studentName}`,
        `Open the student record for ${studentName}?`,
        () => showToast(`Showing ${studentName}’s student record.`),
        'View record'
      );
    });
  });

  // Filter visible table rows using the dashboard search field
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

function showToast(message) {
  const region = document.querySelector('.toast-region');
  if (!region) return;

  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.textContent = message;
  region.append(toast);

  window.setTimeout(() => toast.remove(), 4300);
}

async function sendChat(message) {
  const chatBox = document.querySelector('[data-chat]');
  if (!chatBox) return;

  const userMessage = document.createElement('div');
  userMessage.className = 'user-message';
  userMessage.textContent = message;
  chatBox.append(userMessage);

  const waitingMessage = document.createElement('div');
  waitingMessage.className = 'bot-message';
  waitingMessage.innerHTML =
    '<span class="bot-avatar">✳</span><div>Checking institute records…</div>';
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
    result.className = 'result-message';
    result.textContent = data.reply || 'I could not complete that request.';

    // Add query results as a table when the API returns rows
    if (Array.isArray(data.rows) && data.rows.length > 0) {
      const table = document.createElement('table');
      const headers = Object.keys(data.rows[0]);
      const headerRow = document.createElement('tr');

      headers.forEach(header => {
        const cell = document.createElement('th');
        cell.textContent = header.replaceAll('_', ' ');
        headerRow.append(cell);
      });

      table.append(headerRow);

      data.rows.forEach(row => {
        const tableRow = document.createElement('tr');

        headers.forEach(header => {
          const cell = document.createElement('td');
          cell.textContent = row[header] ?? '';
          tableRow.append(cell);
        });

        table.append(tableRow);
      });

      result.append(table);
    }

    // Add approve/reject controls for staged actions
    if (data.card) {
      const actionCard = document.createElement('div');
      actionCard.className = 'action-card';

      actionCard.innerHTML = `
        <b>${escapeHtml(data.card.action)}</b>
        <p>${escapeHtml(data.card.recipient)}</p>
        <p>${escapeHtml(data.card.message)}</p>
      `;

      ['APPROVED', 'REJECTED'].forEach(decision => {
        const button = document.createElement('button');
        button.textContent = decision === 'APPROVED' ? 'Approve' : 'Reject';

        button.addEventListener('click', () => {
          submitDecision(data.card.id, decision, button);
        });

        actionCard.append(button);
      });

      result.append(actionCard);
    }

    chatBox.append(result);
  } catch (error) {
    waitingMessage.querySelector('div').textContent =
      'Could not reach OpsPilot. Please try again.';
  }

  chatBox.scrollTop = chatBox.scrollHeight;
}

async function submitDecision(actionId, decision, button) {
  button.disabled = true;

  try {
    const response = await fetch(
      `/api/actions/${encodeURIComponent(actionId)}/decision`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision })
      }
    );

    if (!response.ok) {
      throw new Error('The decision could not be saved.');
    }

    const actionCard = button.closest('.action-card');
    actionCard.querySelectorAll('button').forEach(item => item.remove());
    actionCard.append(document.createTextNode(`Decision recorded: ${decision.toLowerCase()}.`));
  } catch (error) {
    button.disabled = false;
    showToast(error.message || 'Could not save the decision.');
  }
}

function escapeHtml(value) {
  const element = document.createElement('span');
  element.textContent = value || '';
  return element.innerHTML;
}

function showConfirmDialog(title, message, onConfirm, actionLabel = 'Confirm') {
  const backdrop = document.createElement('div');
  backdrop.className = 'modal-backdrop';

  const dialog = document.createElement('section');
  dialog.className = 'confirm-modal';
  dialog.setAttribute('role', 'dialog');
  dialog.setAttribute('aria-modal', 'true');

  const heading = document.createElement('h3');
  heading.textContent = title;

  const body = document.createElement('p');
  body.textContent = message;

  const actions = document.createElement('div');
  actions.className = 'modal-actions';

  const cancelButton = document.createElement('button');
  cancelButton.textContent = 'Cancel';
  cancelButton.addEventListener('click', () => backdrop.remove());

  const confirmButton = document.createElement('button');
  confirmButton.className = 'confirm';
  confirmButton.textContent = actionLabel;
  confirmButton.addEventListener('click', () => {
    backdrop.remove();
    onConfirm();
  });

  actions.append(cancelButton, confirmButton);
  dialog.append(heading, body, actions);
  backdrop.append(dialog);

  backdrop.addEventListener('click', event => {
    if (event.target === backdrop) backdrop.remove();
  });

  document.body.append(backdrop);
}