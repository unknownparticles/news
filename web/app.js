(() => {
  const input = document.querySelector('#report-search');
  if (!input) return;
  const cards = [...document.querySelectorAll('.report-card')];
  const buttons = [...document.querySelectorAll('[data-filter]')];
  let kind = 'all';
  const update = () => {
    const query = input.value.trim().toLocaleLowerCase();
    let count = 0;
    for (const card of cards) {
      card.hidden = !((kind === 'all' || card.dataset.kind === kind) && card.dataset.search.toLocaleLowerCase().includes(query));
      if (!card.hidden) count++;
    }
    document.querySelector('#result-count').textContent = `${count} 份报告`;
    document.querySelector('#no-results').hidden = count > 0 || cards.length === 0;
  };
  input.addEventListener('input', update);
  for (const button of buttons) button.addEventListener('click', () => {
    kind = button.dataset.filter;
    for (const current of buttons) {
      const active = current === button;
      current.classList.toggle('active', active);
      current.setAttribute('aria-pressed', String(active));
    }
    update();
  });
  update();
})();
