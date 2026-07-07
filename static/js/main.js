document.addEventListener('click', async (e) => {
  const btn = e.target.closest('.like-btn');
  if (!btn) return;
  e.preventDefault();

  const id = btn.dataset.id;
  try {
    const res = await fetch(`/memory/${id}/like`, { method: 'POST' });
    if (!res.ok) return;
    const data = await res.json();
    btn.classList.toggle('liked', data.liked);
    btn.querySelector('.count').textContent = data.count;
  } catch (err) {
    console.error('Like failed', err);
  }
});

// Click-to-label for file drop zone
const dropLabel = document.getElementById('file-drop-label');
if (dropLabel) {
  const dropZone = document.getElementById('file-drop');
  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.style.borderColor = 'var(--gold)';
  });
  dropZone.addEventListener('dragleave', () => {
    dropZone.style.borderColor = '';
  });
  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.style.borderColor = '';
    const input = document.getElementById('media-input');
    if (e.dataTransfer.files.length) {
      input.files = e.dataTransfer.files;
      input.dispatchEvent(new Event('change'));
    }
  });
}
