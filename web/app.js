(() => {
  const archiveMenu = document.querySelector('.nav-archive');
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && archiveMenu?.open) {
      archiveMenu.open = false;
      archiveMenu.querySelector('summary').focus();
    }
  });
  document.addEventListener('click', event => {
    if (archiveMenu?.open && !archiveMenu.contains(event.target)) archiveMenu.open = false;
  });
  const navLinks = [...document.querySelectorAll('.site-header nav > a')];
  const markLocation = () => {
    for (const link of navLinks) {
      const url = new URL(link.href);
      const current = url.pathname === location.pathname && url.hash === location.hash && (url.hash || location.pathname.endsWith('competitions.html'));
      if (current) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    }
  };
  markLocation();
  window.addEventListener('hashchange', markLocation);
  const domains = [...document.querySelectorAll('[data-domain]')];
  const domainFilters = [...document.querySelectorAll('[data-domain-filter]')];
  const updateDomainCount = () => {
    const count = document.querySelector('#news-result-count');
    if (!count) return;
    const visible = domains.filter(domain => !domain.hidden);
    const total = visible.reduce((sum, domain) => sum + domain.querySelectorAll('[data-news-category]').length, 0);
    const selected = domainFilters.find(button => button.getAttribute('aria-pressed') === 'true');
    count.textContent = `${selected?.textContent || '全部领域'} · ${total} 条新闻`;
  };
  updateDomainCount();
  for (const selected of domainFilters) selected.addEventListener('click', () => {
    for (const domain of domains) {
      domain.hidden = selected.dataset.domainFilter !== 'all' && domain.dataset.domain !== selected.dataset.domainFilter;
    }
    for (const button of domainFilters) {
      const active = button === selected;
      button.classList.toggle('active', active);
      button.setAttribute('aria-pressed', String(active));
    }
    updateDomainCount();
  });
  const contests = [...document.querySelectorAll('.competition-table [data-competition-state]')];
  const contestFilters = [...document.querySelectorAll('[data-competition-filter]')];
  const contestSearch = document.querySelector('#competition-search');
  let contestState = 'eligible';
  for (const contest of contests) {
    const expired = contest.dataset.deadline && Date.parse(contest.dataset.deadline) < Date.now();
    const stale = Date.now() - Date.parse(contest.dataset.checked) > 7 * 24 * 60 * 60 * 1000;
    if (expired) {
      contest.dataset.competitionState = 'closed';
      contest.querySelector('.competition-status').textContent = '已截止';
      contest.querySelector('.competition-status').dataset.state = 'closed';
    } else if (stale && contest.dataset.competitionState === 'eligible') {
      contest.dataset.competitionState = 'conditional';
      contest.querySelector('.competition-status').textContent = '需确认';
      contest.querySelector('.competition-status').dataset.state = 'conditional';
    }
  }
  const updateContests = () => {
    let count = 0;
    const search = contestSearch?.value.trim().toLocaleLowerCase() || '';
    for (const contest of contests) {
      contest.hidden = contestState !== 'all' && contest.dataset.competitionState !== contestState || !contest.dataset.search.toLocaleLowerCase().includes(search);
      if (!contest.hidden) count++;
    }
    const empty = document.querySelector('#no-competitions');
    if (empty) empty.hidden = count > 0;
    const resultCount = document.querySelector('#competition-result-count');
    if (resultCount) resultCount.textContent = `显示 ${count} 项赛事 · 共 ${contests.length} 项记录`;
  };
  for (const selected of contestFilters) selected.addEventListener('click', () => {
    contestState = selected.dataset.competitionFilter;
    for (const button of contestFilters) {
      button.classList.toggle('active', button === selected);
      button.setAttribute('aria-pressed', String(button === selected));
    }
    updateContests();
  });
  contestSearch?.addEventListener('input', updateContests);
  document.querySelector('[data-reset-competitions]')?.addEventListener('click', () => {
    if (contestSearch) contestSearch.value = '';
    contestFilters.find(button => button.dataset.competitionFilter === 'all')?.click();
    contestSearch?.focus();
  });
  if (contestFilters.length) updateContests();
  else for (const contest of contests) contest.hidden = contest.dataset.competitionState !== 'eligible';
  const headlines = [...document.querySelectorAll('[data-news-category]')];
  const newsFilters = [...document.querySelectorAll('[data-news-filter]')];
  for (const selected of newsFilters) selected.addEventListener('click', () => {
    let visible = 0;
    for (const headline of headlines) {
      headline.hidden = selected.dataset.newsFilter !== 'all' && headline.dataset.newsCategory !== selected.dataset.newsFilter;
      if (!headline.hidden) visible++;
    }
    for (const button of newsFilters) {
      button.classList.toggle('active', button === selected);
      button.setAttribute('aria-pressed', String(button === selected));
    }
    const empty = document.querySelector('#no-news');
    if (empty) empty.hidden = visible > 0;
  });
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
  document.querySelector('[data-reset-reports]')?.addEventListener('click', () => {
    input.value = '';
    buttons.find(button => button.dataset.filter === 'all')?.click();
    input.focus();
  });
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
